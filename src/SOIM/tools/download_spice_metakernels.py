"""Download the BepiColombo kernels referenced by selected ESA metakernels."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack, contextmanager
from logging import StreamHandler, getLogger
from os import process_cpu_count
from pathlib import Path
from tempfile import TemporaryDirectory

import rich_click as click
from planetary_coverage import MetaKernel
from planetary_coverage.misc import wget
from rich.console import Console
from rich.file_proxy import FileProxy
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
)

from SOIM.tools.download_spice_kernels import KERNEL_URL, install, mirror

METAKERNELS = {
    "ops": "bc_ops.tm",
    "plan": "bc_plan.tm",
    "nadir": "bc_nadir.tm",
}


@contextmanager
def planetary_output(console):
    """Send Planetary Coverage's existing log handlers through Rich Live."""
    with ExitStack() as restore:
        for logger in getLogger("planetary_coverage.misc").getChildren():
            for handler in logger.handlers:
                if type(handler) is StreamHandler:
                    stream = handler.stream
                    handler.setStream(FileProxy(console, stream))
                    restore.callback(handler.setStream, stream)
        yield


class ProgressMetaKernel(MetaKernel):
    def __init__(self, metakernel, *, progress, task, **kwargs):
        self.progress = progress
        self.task = task
        super().__init__(metakernel, **kwargs)
        total = len(set(self.kernels))
        progress.update(task, total=total, completed=total)

    def _wget(self, missing):
        """Report completed transfers using Planetary Coverage's downloader."""
        total = len(set(self.kernels))
        self.progress.update(self.task, total=total, completed=total - len(missing))
        pool = ThreadPoolExecutor(max_workers=self.n_threads)
        try:
            futures = [pool.submit(wget, url, path) for url, path in missing]
            for future in as_completed(futures):
                future.result()
                self.progress.advance(self.task)
        finally:
            pool.shutdown(cancel_futures=True)


def download(destination, families, url=KERNEL_URL):
    destination = destination.expanduser()
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError(f"Destination must be a directory: {destination}")
    destination = destination.resolve()
    if Path.cwd().is_relative_to(destination) or Path(
        __file__
    ).resolve().is_relative_to(destination):
        raise ValueError(
            f"Cannot replace a directory containing the working directory or script: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Planetary Coverage buffers each kernel in memory before writing it.
    workers = min(4, max(1, (process_cpu_count() or 1) - 1))
    with TemporaryDirectory(
        prefix=".spice-metakernels-", dir=destination.parent
    ) as staging:
        staged = Path(staging) / destination.name
        mk_dir = staged / "mk"
        mk_dir.mkdir(parents=True)
        mirror(url.rstrip("/") + "/mk/", mk_dir, destination / "mk")

        selected = []
        for family in families:
            metakernel = mk_dir / METAKERNELS[family]
            if not metakernel.is_file():
                raise FileNotFoundError(f"Missing metakernel: {metakernel.name}")
            selected.append(metakernel)

        if selected:
            console = Console(stderr=True)
            progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                console=console,
            )
            with progress, planetary_output(console):
                tasks = [
                    progress.add_task(
                        path.stem.removeprefix("bc_"), total=None, start=False
                    )
                    for path in selected
                ]
                for metakernel, task in zip(selected, tasks, strict=True):
                    progress.start_task(task)
                    ProgressMetaKernel(
                        metakernel,
                        progress=progress,
                        task=task,
                        kernels=staged,
                        remote=url.rstrip("/"),
                        download=True,
                        load_kernels=False,
                        n_threads=workers,
                    )

        install(staged, destination)


@click.command()
@click.argument("destination", type=click.Path(path_type=Path, file_okay=False))
@click.option(
    "--exclude-ops", is_flag=True, help="Skip kernels for the operational metakernel."
)
@click.option(
    "--exclude-plan", is_flag=True, help="Skip kernels for the planning metakernel."
)
@click.option(
    "--exclude-nadir", is_flag=True, help="Skip kernels for the nadir metakernel."
)
def main(destination, exclude_ops, exclude_plan, exclude_nadir):
    """Download mk/ and the kernels for ops, plan, and nadir into DESTINATION.

    The destination is replaced after all selected kernels have downloaded.
    Excluding all three families downloads only mk/.
    """
    excluded = {
        "ops": exclude_ops,
        "plan": exclude_plan,
        "nadir": exclude_nadir,
    }
    try:
        download(
            destination, [family for family in METAKERNELS if not excluded[family]]
        )
    except KeyboardInterrupt:
        click.echo("Download interrupted.", err=True)
        raise click.exceptions.Exit(130) from None
    except Exception as error:
        raise click.ClickException(str(error)) from error
    click.echo(
        f"Installed metakernels and selected kernels in {destination.expanduser().resolve()}"
    )


if __name__ == "__main__":
    main()
