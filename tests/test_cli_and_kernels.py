from pathlib import Path

import planetary_coverage as pc
import pytest
import spiceypy as spice
from click.testing import CliRunner
from planetary_coverage.spice import SpicePool

from SOIM import cli, core


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.delenv("SOIM_PROJECT_LIST", raising=False)
    monkeypatch.delenv("SOIM_METAKERNEL", raising=False)
    return CliRunner()


def test_cli_commands_and_project_sources(tmp_path, runner, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("toml.yml").write_text("toml_case: input\n")
    Path("cli.yml").write_text("cli_case: input\n")
    Path("env.yml").write_text("env_case: input\n")
    Path("soim.toml").write_text('project_list = "toml.yml"\n')
    assert "toml_case" in runner.invoke(cli.action, ["list"]).output
    assert "cli_case" in runner.invoke(cli.action, ["-p", "cli.yml", "list"]).output
    res = runner.invoke(
        cli.action, ["-p", "missing.yml", "list"], env={"SOIM_PROJECT_LIST": "env.yml"}
    )
    assert res.exit_code == 0 and "env_case" in res.output
    res = runner.invoke(cli.action, ["about"])
    assert res.exit_code == 0 and "Repository:" in res.output
    assert cli.__version__ in runner.invoke(cli.action, ["--version"]).output


def test_run_relative_config_env_cli_and_default_dispatch(
    tmp_path, runner, monkeypatch
):
    config = tmp_path / "config"
    config.mkdir()
    for name in ["config.tm", "cli.tm", "env.tm"]:
        (config / name).touch()
    (config / "list.yml").write_text("sample: input\n")
    config_file = config / "run.toml"
    config_file.write_text('project_list = "list.yml"\nmetakernel = "config.tm"\n')
    calls = []
    monkeypatch.setattr(cli, "core_soim", lambda *args: calls.append(args))
    command = ["--config", str(config_file)]
    env_path = config / "env.tm"
    cli_path = config / "cli.tm"
    for args, env, path in [
        ([], {}, config / "config.tm"),
        (["--metakernel", str(cli_path), "run"], {}, cli_path),
        (
            ["--metakernel", "missing.tm", "run"],
            {"SOIM_METAKERNEL": str(env_path)},
            env_path,
        ),
    ]:
        result = runner.invoke(cli.action, [*command, *args], env=env)
        assert result.exit_code == 0, result.output
        assert calls[-1][:3] == ({"sample": "input"}, path, None)
        assert "Total elapsed time:" in result.output
    result = runner.invoke(cli.action, [*command, "-s", "run"])
    assert result.exit_code == 0 and "Total elapsed time:" not in result.output
    assert calls[-1][-1] == 1
    result = runner.invoke(cli.action, [*command, "run", "--workers", "4"])
    assert result.exit_code == 0 and calls[-1][-1] == 4
    (config / "list.yml").write_text("sample: input\nsecond: input2\n")
    result = runner.invoke(cli.action, [*command, "run", "--workers", "4"])
    assert result.exit_code == 2
    assert "requires a single project" in result.output


@pytest.mark.parametrize(
    "config, args, message",
    [
        (None, ["--config", "missing.toml", "list"], "Cannot read"),
        ("x = [", ["list"], "Cannot read"),
        ("project_list = 4", ["list"], "must be a non-empty path"),
        ('project_list = "absent.yml"', ["list"], "Project list not found"),
        (None, ["list"], "projects/project_list.yml"),
        (
            'project_list = "ok.yml"\nmetakernel = "missing.tm"',
            ["run"],
            "Metakernel not found",
        ),
    ],
)
def test_invalid_configuration(tmp_path, runner, monkeypatch, config, args, message):
    monkeypatch.chdir(tmp_path)
    Path("ok.yml").write_text("demo: path\n")
    if config is not None:
        Path("soim.toml").write_text(config)
    res = runner.invoke(cli.action, args)
    assert res.exit_code == 1
    assert message in res.output


def test_esa_fallback_looks_up_and_downloads(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(pc, "ESA_MK", {"MPO": {"latest": "bc_test.tm"}})
    monkeypatch.setattr(pc, "MetaKernel", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.delenv("SOIM_METAKERNEL", raising=False)
    cache = tmp_path / "kernels"
    assert cli.prepare_metakernel(Path("unused.toml"), {}, None, cache) == (
        "bc_test.tm",
        cache,
    )
    assert calls == [(("bc_test.tm",), {"kernels": cache, "download": True})]
    assert cache.is_dir()


def test_relative_metakernel_from_unrelated_cwd(tmp_path, monkeypatch):
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    for name, value in (("a.tpc", 11), ("b.tpc", 22)):
        (kernels / name).write_text(
            f"KPL/PCK\n\n\\begindata\n\nSOIM_TEST_{value} = ( {value} )\n"
        )
    mk = kernels / "mk"
    mk.mkdir()
    single = mk / "single.tm"
    single.write_text(
        "KPL/MK\n\n\\begindata\n\nPATH_SYMBOLS = ( 'KERNELS' )\n"
        "PATH_VALUES = ( '..' )\nKERNELS_TO_LOAD = ( '$KERNELS/a.tpc' )\n"
    )
    multi = mk / "multi.tm"
    multi.write_text(
        "KPL/MK\n\n\\begindata\n\nPATH_SYMBOLS = ( 'A' 'B' )\n"
        "PATH_VALUES = ( '..' '..' )\nKERNELS_TO_LOAD = ( '$A/a.tpc' '$B/b.tpc' )\n"
    )
    monkeypatch.chdir(tmp_path)
    try:
        core.load_metakernel(single, None)
        assert spice.gdpool("SOIM_TEST_11", 0, 1)[0] == 11
        core.load_metakernel(multi, None)
        assert spice.gdpool("SOIM_TEST_22", 0, 1)[0] == 22
        assert "'..'" in multi.read_text()
        core.load_metakernel(single, kernels)
        assert spice.gdpool("SOIM_TEST_11", 0, 1)[0] == 11
    finally:
        SpicePool.purge()


@pytest.mark.parametrize("workers", [1, 4])
def test_single_project_dispatches_kernel_and_project(monkeypatch, tmp_path, workers):
    from contextlib import nullcontext

    seen = []
    executor = object() if workers > 1 else None
    monkeypatch.setattr(core, "load_metakernel", lambda *args: seen.append(args))

    def worker_pool(*args):
        seen.append(args)
        return nullcontext(executor)

    monkeypatch.setattr(core, "timeline_worker_pool", worker_pool)
    monkeypatch.setattr(
        core, "main", lambda *args, **kwargs: seen.append((args, kwargs))
    )
    core.core_soim(
        {"sample": tmp_path}, "a.tm", None, tmp_path / "out", workers=workers
    )
    assert seen == [
        ("a.tm", None),
        (workers, "a.tm", None),
        (
            ("sample", tmp_path, tmp_path / "out", False),
            {"executor": executor, "workers": workers},
        ),
    ]


def test_core_schedules_multiple_projects(monkeypatch, tmp_path):
    seen = []

    class Process:
        def __init__(self, target, args):
            self.target, self.args = target, args
            self.running = True

        def start(self):
            self.target(*self.args)

        def is_alive(self):
            was_running, self.running = self.running, False
            return was_running

        def terminate(self):
            assert not self.running

    monkeypatch.setattr(core, "cpu_count", lambda: 4)
    monkeypatch.setattr(core, "Process", Process)
    monkeypatch.setattr(core, "readSK_run", seen.append)
    core.core_soim({"a": tmp_path, "b": tmp_path}, "m.tm", None, tmp_path)
    assert [item[0] for item in seen] == ["a", "b"]


def test_module_entry_point(monkeypatch):
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["SOIM", "--version"])
    with pytest.raises(SystemExit) as error:
        runpy.run_module("SOIM", run_name="__main__")
    assert error.value.code == 0


def test_spawned_worker_loads_local_metakernel(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    (tmp_path / "a.tpc").write_text(
        "KPL/PCK\n\n\\begindata\n\nSOIM_WORKER_VALUE = ( 23 )\n"
    )
    mk = tmp_path / "worker.tm"
    mk.write_text(
        "KPL/MK\n\n\\begindata\n\nPATH_SYMBOLS = ( 'KERNELS' )\n"
        "PATH_VALUES = ( '.' )\nKERNELS_TO_LOAD = ( '$KERNELS/a.tpc' )\n"
    )
    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=get_context("spawn"),
        initializer=core.load_metakernel,
        initargs=(mk, None),
    ) as executor:
        assert (
            executor.submit(spice.gdpool, "SOIM_WORKER_VALUE", 0, 1).result(timeout=20)[
                0
            ]
            == 23
        )


def test_installed_starter_metadata_and_help():
    from importlib.metadata import distribution

    starter_entry = next(
        entry
        for entry in distribution("SOIM").entry_points
        if entry.group == "console_scripts" and entry.name == "soim-starter"
    )
    assert starter_entry.value == "SOIM.starter:main"
    result = CliRunner().invoke(starter_entry.load(), ["--help"])
    assert result.exit_code == 0
    for option in ("--project", "--name", "--metakernel", "--dayside", "--workers"):
        assert option in result.output


def test_readme_version_badge_matches_installed_package():
    from importlib.metadata import version

    readme = Path(__file__).resolve().parents[1] / "README.md"
    assert f"img.shields.io/badge/version-{version('SOIM')}-" in readme.read_text(
        encoding="utf-8"
    )


def test_root_starter_wrapper_calls_packaged_entry_point(monkeypatch):
    import runpy

    from SOIM import starter

    called = []
    monkeypatch.setattr(starter, "main", lambda: called.append(True))
    namespace = runpy.run_module("SOIM_starter", run_name="__main__")
    assert called == [True]
    assert namespace["main"] is starter.main
