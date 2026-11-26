import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from multiprocessing import Pool, Process, cpu_count, get_context
from os import environ
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# from SOIM.lib.classes import Product, Timeline
# from SOIM.lib.console import console
from SOIM.lib.IO_functions import *
from SOIM.lib.utility import MSG, appendHOR, eprint, lprint, print_dic, soimExit, wprint
from SOIM.lib.Verify_DarkSide import Verify_DarkSide
from SOIM.SOIM_simulation import SOIM_simulation, SOIM_simulationFOOTPRINT, listproducts


def main(
    name: str, project: Path, output_folder: Path, suppress: bool, *, executor=None, workers=1
):
    starttime = time.time()
    project = Path(project).absolute()
    path_log = checkPrjFolder(name, output_folder, 'logs',suppress)

    nowstr = time.strftime("%Y%m%d-%H%M%S")
    # TODO: guardare per il log
    environ[f'SOIM_LOG'] = path_log.joinpath(f"log_{nowstr}.txt").as_posix()

    PATH_RESULTS = checkPrjFolder(name, output_folder, 'results',suppress)
    # PATFILE = checkPrjTxtItem(name, project, 'paths', 'yml')
    INSFILE = checkPrjTxtItem(name, project, 'instruments', 'yml', suppress)
    TIMFILE = checkPrjTxtItem(name, project, 'timeline', 'txt', suppress)
    SCEFILE = checkPrjTxtItem(name, project, 'scenario', 'yml', suppress)
    PROFILE = checkPrjTxtItem(name, project, 'products', 'csv', suppress)
    log_file=path_log.joinpath(f"{name}_output.log")
    # SpiceReaded = checkPathFile(PATFILE)
    # if SpiceReaded:
    InstFK = LoadInstrumentFile(INSFILE,log_file)
    Scenario = LoadScenarioFile(SCEFILE, log_file)
    Scenario['Instruments'] = InstFK
    Timelines = LoadTimingFile(TIMFILE,log_file)
    Products = LoadProductsFile(PROFILE, Scenario,log_file)
    Products, InstrUsed = VelidateProducts(
        Products)  # controllare gerarchia
    if 'shapefile' in [x.name.lower() for x in Products]:
        FOOTPRINT = True
        Products.pop(-1)
    else:
        FOOTPRINT = False
    
        

    SEC_OF_OVERSAMPLING = 60
    lprint("Verifing Timelines INPUT: "+str(len(Timelines)),log_file)
    lprint(f"Verifing DarkSide",log_file)
    Timelines_DaySide = Verify_DarkSide(Timelines, Scenario, Products, SEC_OF_OVERSAMPLING,log_file)
    lprint(f"Verifing Timelines OUTPUT: {len(Timelines_DaySide)}",log_file)

    if (FOOTPRINT):
        # old version to simulate only fooprints
        SOIM_simulationFOOTPRINT(
            Timelines_DaySide, Scenario, Products, PATH_RESULTS,log_file)  # simulazione
    else:
        # Version complete to simlate a list of timelines and save the,
        MERGE_TIMELINES = True
        SHAPE_FILE = False
        SOIM_simulation(
            Timelines_DaySide,
            Scenario,
            Products,
            PATH_RESULTS,
            MERGE_TIMELINES,
            SHAPE_FILE,
            ANTI_MERIDAN=False,
            DAYSIDE=False,
            log_file=log_file,
            executor=executor,
            workers=workers,
        )

    time_end = time.time()-starttime
    wprint(':Time required '+str(time_end)+' s')
    # soimExit(error=False)

def results_callback(results):
    for item in results:
        console.print(f"{MSG.INFO}{item} completed.")

def core_soim(project_list: dict, latest, kernel_folder, output_folder, suppress=False, workers=1):
    console=Console(record=True,width=80)
    console.print(tuple(project_list.values()))
    if len(project_list) == 1:
        (name, project), = project_list.items()
        readSK_run((name, project, latest, kernel_folder, output_folder, suppress), workers)
    else:
        num_core = cpu_count() -2
        if num_core > len(project_list):
            num_processes = len(project_list)
        else:
            num_processes=num_core
        console.print(f"{MSG.INFO }Using {num_processes} of core(s)")
        current_proc=0
        proc_array=[]
        args=[(k, v, latest, kernel_folder, output_folder, suppress)
         for k, v in project_list.items()]
        while True:
            # console.log(f"{len(proc_array)=}, {current_proc=}, {len(project_list)=},")
            # console.log(current_proc)
            if len(proc_array)==0 or (len(proc_array)<num_processes and current_proc != len(project_list)):
                # console.print(args[current_proc])
                proc_array.append(Process(target=readSK_run,args=[args[current_proc]]))
                current_proc +=1
                proc_array[-1].start()
                # proc_array[-1].join()
            ended=[]
            for idx,item in enumerate(proc_array):
                if not item.is_alive():
                    item.terminate()
                    ended.append(idx)
            if len(ended) !=0:
                for elem in ended:
                    proc_array.pop(elem)
            if len(proc_array)==0:
                break
            


def load_metakernel(metakernel, kernel_folder):
    from planetary_coverage import MetaKernel
    from planetary_coverage.spice import SpicePool, kernel_parser

    if kernel_folder is not None:
        MetaKernel(metakernel, kernels=kernel_folder, load_kernels=True)
        return

    path = Path(metakernel).expanduser().absolute()
    _, data = kernel_parser(path)
    path_values = data.get("PATH_VALUES", [])
    overrides = {}
    for symbol, value in zip(data.get("PATH_SYMBOLS", []), path_values, strict=True):
        kernel_path = Path(value).expanduser()
        if not kernel_path.is_absolute():
            kernel_path = (path.parent / kernel_path).resolve()
        if str(kernel_path) != value:
            overrides[symbol] = kernel_path

    mk = MetaKernel(path, **overrides)
    if overrides and len(path_values) > 1:
        # MetaKernel's text writer only substitutes single-value PATH_VALUES.
        SpicePool.add(mk.kernels, purge=True)
    else:
        mk.load_kernels()


def timeline_worker_pool(workers, metakernel, kernel_folder):
    """Make each worker load the same SPICE kernels as the parent."""
    if workers == 1:
        return nullcontext()
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("spawn"),
        initializer=load_metakernel,
        initargs=(metakernel, kernel_folder),
    )


def readSK_run(elem, workers=1):
    name, project, metakernel, kernel_folder, output_folder, suppress = elem
    console.print(name)
    load_metakernel(metakernel, kernel_folder)
    with timeline_worker_pool(workers, metakernel, kernel_folder) as executor:
        main(name, project, output_folder, suppress, executor=executor, workers=workers)
    console.print(f"{MSG.INFO} Task {name} ended")
