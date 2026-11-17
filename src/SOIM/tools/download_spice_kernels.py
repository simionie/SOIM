"""Mirror the ESA BepiColombo SPICE kernel archive into a local directory."""

import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack, contextmanager
from ftplib import FTP, error_perm
from ftplib import all_errors as ftp_errors
from html.parser import HTMLParser
from http.client import HTTPException
from os import process_cpu_count
from pathlib import Path
from stat import S_ISREG
from tempfile import TemporaryDirectory, mkdtemp
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

import rich_click as click
from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

KERNEL_URL = "https://spiftp.esac.esa.int/data/SPICE/BEPICOLOMBO/kernels/"
TIMEOUT = 60
STATE_FILE = ".spice-sync.json"


class DirectoryIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and (href := dict(attrs).get("href")):
            self.links.append(href)


@contextmanager
def transfer_writer(progress, stream, total):
    if progress is None:
        yield stream.write
        return

    task = progress.add_task(Path(stream.name).name, total=total)
    try:

        def write(chunk):
            written = stream.write(chunk)
            progress.advance(task, written)

        yield write
    finally:
        progress.remove_task(task)


def fetch_http(url, stream=None, previous=None, *, progress=None):
    headers = {}
    if previous:
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        elif previous.get("modified"):
            headers["If-Modified-Since"] = previous["modified"]
    try:
        response = urlopen(Request(url, headers=headers), timeout=TIMEOUT)
    except HTTPError as error:
        with error:
            if error.code == 304 and headers and error.geturl() == url:
                return previous, True
            raise
    with response:
        if response.geturl() != url or response.status != 200:
            raise OSError(
                f"Unexpected response for {url}: {response.status} {response.geturl()}"
            )
        expected = response.length
        if stream is None:
            return response.read().decode(
                response.headers.get_content_charset() or "utf-8"
            )

        with transfer_writer(progress, stream, expected) as write:
            while chunk := response.read1(1024 * 1024):
                write(chunk)
        if expected is not None and stream.tell() != expected:
            raise OSError(f"Incomplete download: {url}")
        return {
            "etag": response.headers.get("ETag"),
            "modified": response.headers.get("Last-Modified"),
        }, False


def http_links(url):
    index = DirectoryIndex()
    index.feed(fetch_http(url))
    index.close()
    if not index.links:
        raise OSError(f"No directory index found at {url}")
    return index.links


def ftp_url(url):
    return urlsplit(url)._replace(scheme="ftp").geturl()


def fetch_ftp(url, stream=None, previous=None, *, progress=None):
    address = urlsplit(url)
    path = unquote(address.path)
    try:
        with FTP(address.hostname, timeout=TIMEOUT) as ftp:
            ftp.login()
            if stream is not None:
                ftp.voidcmd("TYPE I")
                try:
                    size = ftp.size(path)
                except error_perm:
                    size = None
                try:
                    modified = ftp.sendcmd(f"MDTM {path}").removeprefix("213 ")
                except error_perm:
                    modified = None
                current = {"size": size, "modified": modified}
                if modified and size is not None and current == previous:
                    return current, True
                with transfer_writer(progress, stream, size) as write:
                    ftp.retrbinary(f"RETR {path}", write, blocksize=1024 * 1024)
                if size is not None and stream.tell() != size:
                    raise OSError(f"Incomplete download: {url}")
                # A file changed during RETR must be checked again next time.
                if modified and ftp.sendcmd(f"MDTM {path}") != f"213 {modified}":
                    raise OSError(f"File changed during download: {url}")
                return current, False

            lines = []
            ftp.cwd(path)
            # ESA's FTP server exposes Unix-style LIST output.
            ftp.retrlines("LIST", lines.append)
    except ftp_errors as error:
        raise OSError(f"FTP failed for {url}: {error}") from error

    links = []
    for line in lines:
        if not line or line.startswith("total "):
            continue
        fields = line.split(maxsplit=8)
        if len(fields) != 9 or fields[0][0] not in "-dl":
            raise OSError(f"Unexpected FTP directory entry at {url}: {line}")
        kind, name = fields[0][0], fields[-1]
        if kind == "l":
            name = name.split(" -> ", 1)[0]
        links.append(quote(name, safe="") + ("/" if kind == "d" else ""))
    return links


def fetch(url, output, local, entry, progress):
    previous = {}
    if entry and local.resolve() == local:
        try:
            status = local.stat()
        except FileNotFoundError:
            pass
        else:
            if S_ISREG(status.st_mode) and entry.get("local") == [
                status.st_size,
                status.st_mtime_ns,
            ]:
                previous = entry.get("remote", {})

    with output.open("xb") as stream:
        if urlsplit(url).scheme != "ftp":
            try:
                validators, reused = fetch_http(
                    url, stream, previous.get(url), progress=progress
                )
            except (OSError, HTTPException) as error:
                click.echo(f"HTTPS failed for {url}, trying FTP: {error}", err=True)
                url = ftp_url(url)
                stream.seek(0)
                stream.truncate()
        if urlsplit(url).scheme == "ftp":
            validators, reused = fetch_ftp(
                url, stream, previous.get(url), progress=progress
            )

    if reused:
        output.unlink()
        try:
            output.hardlink_to(local)
        except OSError:
            shutil.copy2(local, output)
    status = output.stat()
    return {
        "remote": {url: validators},
        "local": [status.st_size, status.st_mtime_ns],
    }, reused


def iter_files(url, directory):
    if urlsplit(url).scheme == "ftp":
        links = fetch_ftp(url)
    else:
        try:
            links = http_links(url)
        except (OSError, HTTPException, UnicodeError) as error:
            click.echo(f"HTTPS failed for {url}, trying FTP: {error}", err=True)
            url = ftp_url(url)
            links = fetch_ftp(url)

    for href in dict.fromkeys(links):
        # Apache indexes use relative links for children; skip navigation links.
        link = urlsplit(href)
        if link.scheme or link.netloc or link.query or link.fragment:
            continue
        is_directory = link.path.endswith("/")
        name = unquote(link.path.removesuffix("/"))
        if name in {"", ".", ".."} or any(char in name for char in "/\\\x00\r\n"):
            continue
        child = directory / name
        child_url = urljoin(url, href)
        if is_directory:
            if name == "former_versions":
                continue
            child.mkdir()
            yield from iter_files(child_url, child)
        elif not name.lower().endswith(".txt"):
            yield child_url, child


def mirror(url, directory, destination):
    click.echo("Scanning archive for files...")
    jobs = list(iter_files(url, directory))
    total = len(jobs)
    if not total:
        raise OSError(f"No files found at {url}")

    try:
        state = json.loads((destination / STATE_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        state = {}
    previous = {}
    if isinstance(state, dict) and state.get("source") == url:
        files = state.get("files")
        if isinstance(files, dict):
            previous = files

    workers = min(total, max(1, (process_cpu_count() or 1) - 1))
    click.echo(f"Synchronizing {total} files with {workers} workers")
    entries = {}
    reused = 0
    overall = Progress(
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
    )
    transfers = Progress(
        TextColumn("{task.description}", markup=False),
        BarColumn(),
        TaskProgressColumn(text_format_no_percentage="—"),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )
    task = overall.add_task("Synchronizing files", total=total)
    console = Console(stderr=True)
    with ExitStack() as display:
        if not console.is_terminal and not console.is_jupyter:
            display.callback(console.line)
        display.enter_context(Live(Group(overall, transfers), console=console))
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {}
            for file_url, path in jobs:
                relative = path.relative_to(directory)
                key = relative.as_posix()
                future = pool.submit(
                    fetch,
                    file_url,
                    path,
                    destination / relative,
                    previous.get(key),
                    transfers,
                )
                futures[future] = key
            for future in as_completed(futures):
                entry, was_reused = future.result()
                entries[futures[future]] = entry
                reused += was_reused
                overall.advance(task)
        finally:
            pool.shutdown(cancel_futures=True)
    with (directory / STATE_FILE).open("x", encoding="utf-8") as stream:
        json.dump({"source": url, "files": entries}, stream)
    return total - reused, reused


def install(staged, destination):
    if destination.is_symlink():
        raise OSError(f"Destination is a symbolic link: {destination}")
    if not destination.exists():
        staged.rename(destination)
        return
    if not destination.is_dir():
        raise OSError(f"Destination is not a directory: {destination}")

    # Keep the old tree until the new tree is in place. Both renames stay
    # on the same filesystem.
    backup_dir = Path(mkdtemp(prefix=".spice-backup-", dir=destination.parent))
    backup = backup_dir / destination.name
    try:
        destination.rename(backup)
        try:
            staged.rename(destination)
        except BaseException:
            backup.rename(destination)
            raise
    finally:
        if not backup.exists():
            backup_dir.rmdir()
    shutil.rmtree(backup_dir)


def download(destination, url=KERNEL_URL):
    destination = destination.expanduser()
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise OSError(
            f"Destination must be a directory, not a file or symbolic link: {destination}"
        )
    destination = destination.resolve()
    if Path.cwd().is_relative_to(destination) or Path(
        __file__
    ).resolve().is_relative_to(destination):
        raise OSError(
            f"Cannot replace a directory containing the working directory or script: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".spice-download-", dir=destination.parent
    ) as staging:
        staged = Path(staging) / destination.name
        staged.mkdir()
        counts = mirror(url, staged, destination)
        install(staged, destination)
    return counts


@click.command()
@click.argument("destination", type=click.Path(path_type=Path, file_okay=False))
def main(destination):
    """Mirror the ESA BepiColombo SPICE kernel archive into DESTINATION.

    Download new and updated kernels and remove files absent from the archive.
    Replace the destination only after synchronization succeeds.
    The first run without synchronization metadata downloads the full archive.
    Use anonymous FTP if HTTPS fails.
    """
    try:
        downloaded, reused = download(destination)
    except KeyboardInterrupt:
        click.echo("Download interrupted.", err=True)
        raise click.exceptions.Exit(130) from None
    except (OSError, HTTPException, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Downloaded {downloaded} files, reused {reused} unchanged files.")
    click.echo(f"Synchronized {destination.expanduser().resolve()}")


if __name__ == "__main__":
    main()
