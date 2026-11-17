import tomllib
from os import environ
from pathlib import Path
from sys import exit
from time import perf_counter

import humanize
import rich_click as click
from rich.console import Console

__lazy_modules__ = {"SOIM.core", "SOIM.lib.console", "SOIM.lib.IO_functions"}

from importlib.metadata import metadata
from importlib.metadata import version as get_version

from SOIM.core import core_soim

# from SOIM.lib.console import console
from SOIM.lib.IO_functions import read_yaml

click.rich_click.TEXT_MARKUP = "rich"
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
__version__ = get_version("SOIM")


def load_config(config_file):
    if config_file is None:
        config_file = Path("soim.toml")
        if not config_file.exists():
            return config_file, {}

    try:
        with config_file.open("rb") as source:
            return config_file, tomllib.load(source)
    except (OSError, ValueError) as error:
        raise click.ClickException(f"Cannot read {config_file}: {error}") from error


def configured_path(config_file, config, key, cli_value):
    value = environ.get(f"SOIM_{key.upper()}") or cli_value
    if value is not None:
        return Path(value).expanduser()
    if key not in config:
        return None

    value = config[key]
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(f"{config_file}: {key} must be a non-empty path.")
    return config_file.parent / Path(value).expanduser()


# Funzione di chiamata da linea di comando


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    "-k",
    "--kernel",
    "kernel_folder",
    metavar="FOLDER",
    help="Kernel Folder",
    default="kernels",
)
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    help="TOML configuration file. Defaults to soim.toml when present.",
)
@click.option(
    "--metakernel",
    type=click.Path(path_type=Path),
    help="Use a local SPICE metakernel and its configured kernel paths.",
)
@click.option(
    "-p",
    "--project-list",
    "project_list_file",
    metavar="FILE",
    help="file with the list of the active project",
)
@click.option(
    "-o",
    "--output-folder",
    metavar="FOLDER",
    help="Set the output folder",
    default="output_soim",
)
@click.option(
    "-s",
    "--suppress-output",
    is_flag=True,
    help="suppress the output on the standard output device",
    default=False,
)
@click.version_option(__version__, "-V", "--version", prog_name="SOIM")
@click.pass_context
def action(
    ctx,
    kernel_folder,
    config,
    metakernel,
    project_list_file,
    output_folder,
    suppress_output: bool,
):
    ctx.obj = {
        "kernel": kernel_folder,
        "config": config,
        "metakernel": metakernel,
        "project": project_list_file,
        "output": output_folder,
        "suppress": suppress_output,
    }
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@action.command()
def about():
    """Show software information."""
    info = metadata("SOIM")
    click.secho(f"{info['Name']} {info['Version']}", fg="cyan", bold=True)
    click.echo(info["Summary"])
    fields = [
        ("Authors", info["Author"] or info["Author-email"]),
        ("License", info.get("License-Expression") or info["License"]),
        ("Python", info["Requires-Python"]),
    ]
    for project_url in info.get_all("Project-URL", []):
        label, _, url = project_url.partition(",")
        fields.append((label, url.strip()))

    for label, value in fields:
        click.echo(f"{click.style(f'{label}:', fg='blue', bold=True)} {value}")


@action.command()
@click.pass_context
def run(ctx):
    """Run all The projects"""
    start = perf_counter()
    config_file, config = load_config(ctx.obj["config"])
    project_list = read_project_list(ctx, config_file, config)
    metakernel, kernel_folder = prepare_metakernel(
        config_file, config, ctx.obj["metakernel"], ctx.obj["kernel"]
    )
    core_soim(
        project_list,
        metakernel,
        kernel_folder,
        ctx.obj["output"],
        ctx.obj["suppress"],
    )
    if not ctx.obj["suppress"]:
        elapsed = humanize.precisedelta(perf_counter() - start)
        click.echo(f"Total elapsed time: {elapsed}")


def prepare_metakernel(config_file, config, cli_metakernel, kernel_folder):
    metakernel = configured_path(config_file, config, "metakernel", cli_metakernel)
    if metakernel is not None:
        if not metakernel.is_file():
            raise click.ClickException(f"Metakernel not found: {metakernel}")
        return metakernel, None

    from planetary_coverage import ESA_MK, MetaKernel

    metakernel = ESA_MK["MPO"]["latest"]
    click.echo(metakernel)
    kernel_folder = Path(kernel_folder)
    kernel_folder.mkdir(parents=True, exist_ok=True)
    MetaKernel(metakernel, kernels=kernel_folder, download=True)
    return metakernel, kernel_folder


def read_project_list(ctx, config_file, config):
    path = configured_path(config_file, config, "project_list", ctx.obj["project"])
    if path is None:
        path = Path("projects/project_list.yml")
    if not path.is_file():
        raise click.ClickException(f"Project list not found: {path}")
    return read_yaml(path)


@action.command("list")
@click.pass_context
def list_project(ctx):
    """Display the list of avalaible projects"""
    from rich.table import Table

    console = Console()

    config_file, config = load_config(ctx.obj["config"])
    project_list = read_project_list(ctx, config_file, config)
    tb = Table()
    tb.add_column("Project", style="yellow")
    tb.add_column("Path")
    for k, v in project_list.items():
        tb.add_row(k, str(Path(v).absolute()))
    console.print(tb)
