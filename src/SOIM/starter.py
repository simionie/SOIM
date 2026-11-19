"""Command-line entry point for running a single SOIM project."""

import time
from os import process_cpu_count
from pathlib import Path

import humanize
import rich_click as click

from SOIM.cli import CONTEXT_SETTINGS, load_config, prepare_metakernel
from SOIM.core import load_metakernel, timeline_worker_pool
from SOIM.lib.console import console
from SOIM.lib.IO_functions import (
    LoadInstrumentFile,
    LoadProductsFile,
    LoadScenarioFile,
    LoadTimingFile,
    VelidateProducts,
    checkPrjFolder,
    checkPrjTxtItem,
)
from SOIM.lib.utility import MSG
from SOIM.lib.Verify_DarkSide import Verify_DarkSide
from SOIM.SOIM_simulation import SOIM_simulation


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-p", "--project", metavar="PROJ", help="Project directory.", default="my_project"
)
@click.option(
    "-n",
    "--name",
    default="my_project_results",
    show_default=True,
    help="Name of the output directory inside the project.",
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
    "-k",
    "--kernel",
    "kernel_folder",
    default="kernels",
    help="Kernel folder for the ESA metakernel.",
)
@click.option(
    "--dayside/--no-dayside",
    default=False,
    show_default=True,
    help="Restrict the simulation to sunlit acquisitions.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=max(1, (process_cpu_count() or 1) - 1),
    show_default=True,
    help="Worker processes for long timelines.",
)
def main(project, name, config, metakernel, kernel_folder, dayside, workers):
    """Run a single project and export its CSV and footprint shapefile."""
    started = time.perf_counter()
    log_folder = checkPrjFolder(name, project, "logs", False)
    folder_name = Path(project).name
    log_file = log_folder / f"SOIM_log_{folder_name}{time.strftime('%Y%m%d-%H%M%S')}.txt"

    results = checkPrjFolder(name, project, "results", False)
    instrument_file = checkPrjTxtItem(name, project, "instruments", "yml", False)
    timeline_file = checkPrjTxtItem(name, project, "timeline", "txt", False)
    scenario_file = checkPrjTxtItem(name, project, "scenario", "yml", False)
    product_file = checkPrjTxtItem(name, project, "products", "csv", False)

    config_file, settings = load_config(config)
    metakernel, kernel_folder = prepare_metakernel(
        config_file, settings, metakernel, kernel_folder
    )
    load_metakernel(metakernel, kernel_folder)

    scenario = LoadScenarioFile(scenario_file, log_file)
    scenario["Instruments"] = LoadInstrumentFile(instrument_file, log_file)
    timelines = LoadTimingFile(timeline_file, log_file)
    products, _ = VelidateProducts(LoadProductsFile(product_file, scenario, log_file))
    #if dayside:
    #    timelines = Verify_DarkSide(timelines, scenario, products, 60, log_file)

    console.print(f"{MSG.INFO} Simulation outputs: CSV and footprint shapefile")
    with timeline_worker_pool(workers, metakernel, kernel_folder) as executor:
        SOIM_simulation(
            timelines,
            scenario,
            products,
            results,
            True,
            True,
            False,
            log_file,
            executor=executor,
            workers=workers,
        )

    elapsed = humanize.precisedelta(time.perf_counter() - started)
    click.echo(f"Total elapsed time: {elapsed}")


if __name__ == "__main__":
    main()
