from email.message import Message
from importlib.metadata import distribution
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest
from click.testing import CliRunner

from SOIM.tools import download_spice_kernels as archive
from SOIM.tools import download_spice_metakernels as selected

BASE = "https://example.test/kernels/"


class Response(BytesIO):
    def __init__(self, url, data, *, length=None):
        super().__init__(data)
        self.url = url
        self.status = 200
        self.length = len(data) if length is None else length
        self.headers = Message()
        self.headers["ETag"] = '"unchanged"'

    def geturl(self):
        return self.url


def install_http_archive(monkeypatch, files):
    requests = []

    def urlopen(request, *, timeout):
        url = request.full_url
        requests.append((url, request.get_header("If-none-match")))
        if request.get_header("If-none-match"):
            raise HTTPError(url, 304, "Not Modified", Message(), BytesIO())
        return Response(url, files[url])

    monkeypatch.setattr(archive, "urlopen", urlopen)
    return requests


def test_archive_mirror_filters_links_and_reuses_unchanged_files(tmp_path, monkeypatch):
    files = {
        BASE: b'<a href="../">Parent</a><a href="ck/">CK</a><a href="notes.txt">Notes</a>'
        b'<a href="former_versions/">Old</a><a href="https://external.test/">Other</a>'
        b'<a href="?C=N">Order</a><a href="%2Fabsolute">Escape</a><a href="ck/">CK again</a>',
        BASE + "ck/": b'<a href="attitude.bc">Attitude</a>',
        BASE + "ck/attitude.bc": b"example",
    }
    requests = install_http_archive(monkeypatch, files)
    dest = tmp_path / "kernels"
    assert archive.download(dest, BASE) == (1, 0)
    assert (dest / "ck/attitude.bc").read_bytes() == b"example"
    assert not (dest / "former_versions").exists()
    assert archive.download(dest, BASE) == (0, 1)
    assert requests[-1] == (BASE + "ck/attitude.bc", '"unchanged"')
    assert (dest / "ck/attitude.bc").read_bytes() == b"example"

    (dest / "ck/attitude.bc").write_bytes(b"changed locally")
    assert archive.download(dest, BASE) == (1, 0)
    assert requests[-1] == (BASE + "ck/attitude.bc", None)
    assert (dest / "ck/attitude.bc").read_bytes() == b"example"


def test_metakernel_selection_downloads_only_referenced_kernels(tmp_path, monkeypatch):
    files = {
        BASE + "mk/": b"".join(
            f'<a href="{name}">{name}</a>'.encode()
            for name in selected.METAKERNELS.values()
        ),
        **{
            BASE + "mk/" + name: (
                "KPL/MK\n\n\\begindata\n\nPATH_SYMBOLS = ( 'KERNELS' )\n"
                f"PATH_VALUES = ( '..' )\nKERNELS_TO_LOAD = ( '$KERNELS/ck/{family}.bc' )\n"
            ).encode()
            for family, name in selected.METAKERNELS.items()
        },
    }
    install_http_archive(monkeypatch, files)
    downloaded = []

    def wget(url, path):
        downloaded.append(url)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test kernel")

    monkeypatch.setattr(selected, "wget", wget)
    destination = tmp_path / "kernels"
    selected.download(destination, ["plan"], BASE)
    assert downloaded == [BASE + "ck/plan.bc"]
    assert (destination / "ck/plan.bc").read_bytes() == b"test kernel"
    assert sorted(p.name for p in (destination / "mk").glob("*.tm")) == sorted(
        selected.METAKERNELS.values()
    )
    assert "'..'" in (destination / "mk/bc_plan.tm").read_text()


def test_failed_selected_download_preserves_previous_tree(tmp_path, monkeypatch):
    install_http_archive(
        monkeypatch,
        {BASE + "mk/": b'<a href="bc_ops.tm">ops</a>', BASE + "mk/bc_ops.tm": b"ops"},
    )
    destination = tmp_path / "kernels"
    destination.mkdir()
    existing = destination / "old-file"
    existing.write_text("keep")
    with pytest.raises(FileNotFoundError, match="bc_plan.tm"):
        selected.download(destination, ["plan"], BASE)
    assert existing.read_text() == "keep"
    assert not list(tmp_path.glob(".spice-metakernels-*"))
    selected.download(destination, [], BASE)
    assert (destination / "mk/bc_ops.tm").is_file()
    assert not existing.exists()


def test_archive_install_rolls_back_if_publication_fails(tmp_path, monkeypatch):
    staged, destination = (tmp_path / name for name in ("staged", "destination"))
    staged.mkdir()
    destination.mkdir()
    (destination / "old").touch()
    rename = Path.rename

    def fail_staged(self, path):
        if self == staged:
            raise OSError("test failure")
        return rename(self, path)

    monkeypatch.setattr(Path, "rename", fail_staged)
    with pytest.raises(OSError, match="test failure"):
        archive.install(staged, destination)
    assert (destination / "old").exists()
    assert staged.is_dir() and not list(tmp_path.glob(".spice-backup-*"))


@pytest.mark.parametrize(
    "download,args", [(archive.download, ()), (selected.download, ([],))]
)
def test_rejects_file_symlink_and_working_directory(
    download, args, tmp_path, monkeypatch
):
    target = tmp_path / "file"
    target.touch()
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    for destination in (target, link, tmp_path):
        with pytest.raises((OSError, ValueError), match="directory"):
            download(destination, *args)


def test_https_failure_falls_back_to_ftp(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("HTTPS unavailable")

    class FTP:
        def __init__(self, host, *, timeout):
            assert host == "example.test"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def login(self):
            pass

        def cwd(self, folder):
            assert folder == "/kernels/"

        def retrlines(self, command, callback):
            assert command == "LIST"
            callback("total 1")
            callback("-rw-r--r-- 1 owner group 5 Jan 1 12:00 test.bc")

        def voidcmd(self, command):
            assert command == "TYPE I"

        def size(self, path):
            return 5

        def sendcmd(self, command):
            assert command == "MDTM /kernels/test.bc"
            return "213 20270101000000"

        def retrbinary(self, command, callback, *, blocksize):
            assert command == "RETR /kernels/test.bc"
            callback(b"hello")

    monkeypatch.setattr(archive, "urlopen", unavailable)
    monkeypatch.setattr(archive, "FTP", FTP)
    destination = tmp_path / "kernels"
    assert archive.download(destination, BASE) == (1, 0)
    assert archive.download(destination, BASE) == (0, 1)
    assert (destination / "test.bc").read_bytes() == b"hello"


def test_http_rejects_incomplete_download(tmp_path, monkeypatch):
    url = BASE + "kernel.bc"
    monkeypatch.setattr(
        archive, "urlopen", lambda *_args, **_kw: Response(url, b"short", length=10)
    )
    with (
        (tmp_path / "staged").open("wb") as file,
        pytest.raises(OSError, match="Incomplete"),
    ):
        archive.fetch_http(url, file)


def test_installed_download_command_and_family_flags(tmp_path, monkeypatch):
    entry = next(
        e
        for e in distribution("SOIM").entry_points
        if e.group == "console_scripts" and e.name == "soim-download-metakernels"
    )
    assert entry.load() is selected.main
    calls = []
    monkeypatch.setattr(
        selected, "download", lambda path, families: calls.append((path, families))
    )
    destination = tmp_path / "kernels"
    runner = CliRunner()
    result = runner.invoke(
        entry.load(), [str(destination), "--exclude-ops", "--exclude-nadir"]
    )
    assert result.exit_code == 0 and "Installed metakernels" in result.output
    assert calls == [(destination, ["plan"])]
    monkeypatch.setattr(archive, "download", lambda *_: (2, 3))
    result = runner.invoke(archive.main, [str(destination)])
    assert result.exit_code == 0 and "Downloaded 2 files, reused 3" in result.output


@pytest.mark.parametrize("module", [archive, selected])
@pytest.mark.parametrize(
    "error,status,message",
    [
        (KeyboardInterrupt(), 130, "Download interrupted"),
        (OSError("download failed"), 1, "download failed"),
    ],
)
def test_download_commands_report_failures(
    module, error, status, message, tmp_path, monkeypatch
):
    def fail(*_):
        raise error

    monkeypatch.setattr(module, "download", fail)
    result = CliRunner().invoke(module.main, [str(tmp_path / "kernels")])
    assert result.exit_code == status
    assert message in result.output
