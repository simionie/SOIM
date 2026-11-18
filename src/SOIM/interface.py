"""Local web interface for SOIM project files and starter runs."""

import csv
import hashlib
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from threading import Lock

import click
import yaml
from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from SOIM.interface_forms import (
    FIELDS,
    IntervalEndError,
    form_content,
    form_rows,
    yaml_mapping,
)
from SOIM.lib.product_types import PRODUCT_MODES, PRODUCT_TYPES

DEFAULT_CHANNELS = Path(__file__).with_name("defaults") / "instruments_Dic.yml"

SECTIONS = {
    "Timeline": ("timeline", "txt", ""),
    "Products": ("products", "csv", "INSTRUMENT,Product,Mode,Sign\n"),
    "Instruments": ("instruments", "yml", "{}\n"),
    "Scenario": (
        "scenario",
        "yml",
        "Orbiter: BEPICOLOMBO MPO\nTarget: Mercury\nTarget Frame: IAU_Mercury\n",
    ),
}
FOLDER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}")
MAX_FILE_BYTES = 1024 * 1024
RUN_PREFERENCES_COOKIE = "soim_run_preferences"


def project_files(project):
    """Discover configuration files using the same patterns as the starter."""
    for label, (prefix, extension, _) in SECTIONS.items():
        matches = list(project.glob(f"{prefix}*.{extension}"))
        if len(matches) == 1 and matches[0].is_file() and not matches[0].is_symlink():
            yield label, matches[0], None
        elif matches:
            yield label, None, f"Expected one regular {prefix}*.{extension} file."
        else:
            yield label, None, f"Missing {prefix}*.{extension}."


def read_config_file(path):
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            abort(413, f"{path.name} exceeds the 1 MiB editor limit.")
        content = raw.decode("utf-8-sig")
    except UnicodeError:
        abort(422, f"{path.name} must be UTF-8.")
    return content, hashlib.sha256(raw).hexdigest()


def write_config_file(path, content):
    """Replace one file atomically and keep its permissions."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            staged.write(content.encode("utf-8"))
            staged.close()
            temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def create_app(root, config=None):
    app = Flask(__name__)
    app.config.update(
        TRUSTED_HOSTS=["localhost", "127.0.0.1"],
        MAX_CONTENT_LENGTH=2 * MAX_FILE_BYTES,
    )
    root = Path(root).resolve()
    config = Path(config).resolve() if config else None
    jobs = {}
    lock = Lock()

    def relative_name(path):
        return path.relative_to(root).as_posix()

    def projects():
        candidates = list(root.iterdir())
        container = root / "projects"
        if container.is_dir() and not container.is_symlink():
            candidates.extend(container.iterdir())
        return sorted(
            (
                path
                for path in candidates
                if path.is_dir()
                and not path.is_symlink()
                and not path.name.startswith(".")
                and any(path.glob("scenario*.yml"))
            ),
            key=lambda path: (
                relative_name(path) != "my_project",
                relative_name(path).casefold(),
            ),
        )

    def get_project(name):
        for path in projects():
            if relative_name(path) == name:
                return path
        abort(404, "Project not found.")

    def describe(path):
        sections = []
        for label, file, error in project_files(path):
            item = {"label": label, "error": error}
            if file:
                content, revision = read_config_file(file)
                item.update(filename=file.name, revision=revision)
                try:
                    item["rows"] = form_rows(label, content)
                except (ValueError, TypeError, csv.Error, yaml.YAMLError) as exc:
                    item["error"] = f"Could not read {file.name} as a form: {exc}"
            sections.append(item)
        return {"id": relative_name(path), "name": path.name, "sections": sections}

    def payload():
        values = request.get_json()
        if not isinstance(values, dict):
            abort(400, "Expected a JSON object.")
        return values

    def check_idle(path):
        job = jobs.get(path)
        if job and job["process"].poll() is None:
            abort(409, "Wait for the current run to finish.")

    def run_status(job):
        if not job:
            return None
        exit_code = job["process"].poll()
        with job["log"].open("rb") as source:
            source.seek(0, os.SEEK_END)
            log_start = max(0, source.tell() - 32_768)
            source.seek(log_start)
            log = source.read().decode("utf-8", errors="replace")
        completed = any((job["output"] / "results").glob("*.csv"))
        state = (
            "Running"
            if exit_code is None
            else "Completed"
            if exit_code == 0 and completed
            else "Failed"
        )
        return {
            "state": state,
            "exit_code": exit_code,
            "output": relative_name(job["output"]),
            "log": log,
            "log_truncated": log_start > 0,
        }

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.after_request
    def prevent_stale_project_data(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/")
    def index():
        saved = request.cookies.get(RUN_PREFERENCES_COOKIE, "{}")
        try:
            preferences = app.json.loads(saved)
        except ValueError:
            preferences = {}
        if not isinstance(preferences, dict):
            preferences = {}

        kernel_dirs = (root, root / "kernels", root / "kernels/mk", root / "kernels/tm")
        metakernels = sorted(
            {
                relative_name(file)
                for directory in kernel_dirs
                for file in directory.glob("*.tm")
                if file.is_file()
            }
        )
        return render_template(
            "interface.html",
            form_fields=FIELDS,
            product_names=["Time", *(aliases[0] for _, _, aliases in PRODUCT_TYPES)],
            product_modes=PRODUCT_MODES,
            soim_version=version("SOIM"),
            python_version=platform.python_version(),
            run_preferences=preferences,
            metakernels=metakernels,
        )

    @app.get("/api/projects")
    def list_projects():
        return jsonify(
            [{"id": relative_name(path), "name": path.name} for path in projects()]
        )

    @app.get("/api/project")
    def open_project():
        with lock:
            return jsonify(describe(get_project(request.args.get("id"))))

    @app.post("/api/projects")
    def new_project():
        values = payload()
        name = values.get("name")
        if not isinstance(name, str) or not FOLDER_NAME.fullmatch(name):
            abort(
                400,
                "Use 1–80 letters, digits, hyphens or underscores, starting with a letter or digit.",
            )
        with lock:
            catalog = DEFAULT_CHANNELS.read_text(encoding="utf-8")
            template = values.get("template")
            if template:
                files = {}
                for label, file, error in project_files(get_project(template)):
                    if error:
                        abort(422, f"{label}: {error}")
                    content = read_config_file(file)[0]
                    if label == "Instruments":
                        try:
                            channels = yaml_mapping(catalog) | yaml_mapping(content)
                        except (TypeError, yaml.YAMLError) as exc:
                            abort(422, f"Could not copy the channel catalog: {exc}")
                        content = yaml.safe_dump(
                            channels, sort_keys=False, allow_unicode=True
                        )
                    files[file.name] = content
            else:
                files = {
                    f"{prefix}.{extension}": content
                    for label, (prefix, extension, content) in SECTIONS.items()
                    if label != "Instruments"
                }
                files[DEFAULT_CHANNELS.name] = catalog
                default_project = root / "my_project"
                if default_project in projects():
                    for label, file, _ in project_files(default_project):
                        if label == "Scenario" and file:
                            files["scenario.yml"] = read_config_file(file)[0]
            destination = root / name
            if destination.exists() or destination.is_symlink():
                abort(409, "A file or project with that name already exists.")
            try:
                with tempfile.TemporaryDirectory(
                    prefix=".soim-", dir=root
                ) as directory:
                    staged = Path(directory) / name
                    staged.mkdir()
                    for filename, content in files.items():
                        (staged / filename).write_text(content, encoding="utf-8")
                    staged.rename(destination)
            except OSError:
                abort(409, "Could not create the project folder.")
            return jsonify(describe(destination)), 201

    @app.put("/api/project")
    def save_section():
        values = payload()
        with lock:
            path = get_project(values.get("id"))
            check_idle(path)
            for label, file, error in project_files(path):
                if label == values.get("section"):
                    if error:
                        abort(422, error)
                    original, revision = read_config_file(file)
                    if revision != values.get("revision"):
                        abort(
                            409,
                            "The file changed on disk. Reopen the project before editing it.",
                        )
                    try:
                        content = form_content(label, values.get("rows"), original)
                        content_size = len(content.encode("utf-8"))
                    except IntervalEndError as exc:
                        return jsonify(error=str(exc), field="stop", row=exc.row), 422
                    except (ValueError, TypeError, csv.Error, yaml.YAMLError) as exc:
                        abort(422, str(exc))
                    if content_size > MAX_FILE_BYTES:
                        abort(
                            413, "Configuration content exceeds the 1 MiB editor limit."
                        )
                    try:
                        if content != original:
                            write_config_file(file, content)
                    except OSError:
                        abort(409, "Could not save the configuration file.")
                    return jsonify(describe(path))
            abort(404, "Configuration section not found.")

    @app.get("/api/run")
    def current_run():
        with lock:
            path = get_project(request.args.get("id"))
            return jsonify(run_status(jobs.get(path)))

    @app.get("/api/metakernels")
    def browse_metakernels():
        location = request.args.get("directory", "")
        if "\x00" in location:
            abort(400, "Enter a valid folder path.")
        try:
            directory = Path(os.path.abspath(root / Path(location).expanduser()))
            if request.args.get("from_file"):
                directory = directory.parent
                if not directory.is_dir():
                    directory = root
            files = []
            folders = []
            for entry in directory.iterdir():
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    folders.append(entry.name)
                elif entry.suffix.lower() == ".tm" and entry.is_file():
                    files.append(entry.name)
        except (OSError, RuntimeError, ValueError):
            abort(422, "Could not open this folder.")
        return jsonify(
            directory=str(directory),
            parent=str(directory.parent) if directory != directory.parent else None,
            ancestors=[
                {"name": ancestor.name or ancestor.anchor, "path": str(ancestor)}
                for ancestor in reversed(directory.parents)
            ],
            folders=[
                {"name": name, "path": str(directory / name)}
                for name in sorted(folders, key=str.casefold)
            ],
            files=[
                {"name": name, "path": str(directory / name)}
                for name in sorted(files, key=str.casefold)
            ],
        )

    @app.post("/api/metakernels/match")
    def match_metakernel():
        values = payload()
        name, size, digest = (values.get(key) for key in ("name", "size", "sha256"))
        location = values.get("directory", "")
        if (
            not isinstance(name, str)
            or not name.lower().endswith(".tm")
            or any(char in name for char in "/\\:\x00")
            or type(size) is not int
            or not 0 <= size <= MAX_FILE_BYTES
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not isinstance(location, str)
            or "\x00" in location
        ):
            abort(400, "Drop a .tm file of up to 1 MiB.")

        home = Path.home()
        candidates = {
            folder / name
            for folder in (home / "Desktop", home / "Downloads", home / "Documents")
        }
        if location:
            candidates.add(root / Path(location) / name)
        for index, (directory, folders, files) in enumerate(os.walk(root)):
            if index >= 2000:
                break
            folders[:] = [folder for folder in folders if not folder.startswith(".")]
            if name in files:
                candidates.add(Path(directory) / name)

        matches = []
        for path in sorted(candidates):
            try:
                if path.is_file() and path.stat().st_size == size:
                    with path.open("rb") as source:
                        content = source.read(MAX_FILE_BYTES + 1)
                    if hashlib.sha256(content).hexdigest() == digest:
                        matches.append(str(path))
            except OSError:
                continue
        return jsonify(matches=matches)

    @app.post("/api/run")
    def start_run():
        values = payload()
        workers = values.get("workers", 1)
        if type(workers) is not int or workers < 1:
            abort(400, "Parallel workers must be a positive integer.")
        metakernel = values.get("metakernel", "")
        if not isinstance(metakernel, str) or "\x00" in metakernel:
            abort(400, "Enter a valid metakernel path.")
        metakernel = metakernel.strip()
        environment = None
        if metakernel:
            try:
                selected = (root / Path(metakernel).expanduser()).resolve()
                is_file = selected.is_file()
            except (OSError, RuntimeError, ValueError):
                is_file = False
            if not is_file:
                abort(422, "Metakernel file not found. Enter a path on this computer.")
            environment = os.environ.copy()
            environment["SOIM_METAKERNEL"] = str(selected)
        name = values.get("name") or datetime.now().strftime("run-%Y%m%d-%H%M%S")
        if not isinstance(name, str) or not FOLDER_NAME.fullmatch(name):
            abort(
                400, "Use a folder name with letters, digits, hyphens or underscores."
            )
        with lock:
            path = get_project(values.get("id"))
            check_idle(path)
            for label, file, error in project_files(path):
                if error:
                    abort(422, f"{label}: {error}")
                content, _ = read_config_file(file)
                if label in {"Timeline", "Products"} and not content.strip():
                    abort(422, f"Add {label.lower()} before starting SOIM.")
            output = path / name
            try:
                output.mkdir()
            except OSError:
                abort(409, f"Could not create {name}. Choose a new output folder name.")

            command = [
                sys.executable,
                "-u",
                "-m",
                "SOIM.starter",
                "--project",
                str(path),
                "--name",
                name,
                "--workers",
                str(workers),
            ]
            if config:
                command.extend(["--config", str(config)])
            log = output / "starter.log"
            try:
                with log.open("xb") as stream:
                    process = subprocess.Popen(
                        command,
                        cwd=root,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        env=environment,
                    )
            except OSError:
                log.unlink(missing_ok=True)
                output.rmdir()
                abort(500, "Could not start soim-starter.")
            jobs[path] = {"process": process, "output": output, "log": log}
            response = jsonify(run_status(jobs[path]))
            response.set_cookie(
                RUN_PREFERENCES_COOKIE,
                app.json.dumps({"metakernel": metakernel, "workers": workers}),
                max_age=180 * 24 * 60 * 60,
                httponly=True,
                samesite="Strict",
            )
            return response, 202

    return app


@click.command()
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Workspace containing project folders.",
    show_default=True,
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="SOIM TOML configuration file. Defaults to soim.toml in the workspace.",
)
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535),
    default=5050,
    show_default=True,
    help="Local HTTP port.",
)
def main(root, config, port):
    """Open the local SOIM project interface."""
    create_app(root, config).run(
        host="127.0.0.1", port=port, debug=False, use_reloader=False
    )
