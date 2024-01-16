import time
from multiprocessing import Pool
from os import environ
from pathlib import Path

from rich.panel import Panel

from SOIM.lib.classes import Product, Timeline
from SOIM.lib.console import console
from SOIM.lib.IO_functions import *
from SOIM.lib.utility import (MSG, appendHOR, eprint, lprint, print_dic,
                              soimExit, wprint)
from SOIM.lib.Verify_DarkSide import Verify_DarkSide
from SOIM.SOIM_simulation import (SOIM_simulation, SOIM_simulationFOOTPRINT,
                                  listproducts)


def main(name: str, project: Path,output_folder):
    starttime = time.time()
    project = Path(project).absolute()
    path_log = checkPrjFolder(name, project, 'logs')

    nowstr = time.strftime("%Y%m%d-%H%M%S")
    # TODO: guardare per il log
    environ[f'SOIM_LOG'] = path_log.joinpath(f"log_{nowstr}.txt").as_posix()

    PATH_RESULTS = checkPrjFolder(name, output_folder, 'results')
    # PATFILE = checkPrjTxtItem(name, project, 'paths', 'yml')
    INSFILE = checkPrjTxtItem(name, project, 'instruments', 'yml')
    TIMFILE = checkPrjTxtItem(name, project, 'timeline', 'txt')
    SCEFILE = checkPrjTxtItem(name, project, 'scenario', 'yml')
    PROFILE = checkPrjTxtItem(name, project, 'products', 'csv')

    # SpiceReaded = checkPathFile(PATFILE)
    # if SpiceReaded:
    InstFK = LoadInstrumentFile(INSFILE)
    Scenario = LoadScenarioFile(SCEFILE)
    Scenario['Instruments'] = InstFK
    Timelines = LoadTimingFile(TIMFILE)
    Products = LoadProductsFile(PROFILE, Scenario)
    Products, InstrUsed = VelidateProducts(
        Products)  # controllare gerarchia
    FOOTPRINT = False

    SEC_OF_OVERSAMPLING = 60
    lprint("Verifing Timelines INPUT: "+str(len(Timelines)))

    Timelines_DaySide = Verify_DarkSide(
        Timelines, Scenario, Products, SEC_OF_OVERSAMPLING)
    lprint("Verifing Timelines OUTPUT: "+str(len(Timelines_DaySide)))

    if (FOOTPRINT):
        # old version to simulate only fooprints
        SOIM_simulationFOOTPRINT(
            Timelines_DaySide, Scenario, Products, PATH_RESULTS)  # simulazione
    else:
        # Version complete to simlate a list of timelines and save the,
        MERGE_TIMELINES = True
        SHAPE_FILE = False
        SOIM_simulation(Timelines_DaySide, Scenario, Products,
                        PATH_RESULTS, MERGE_TIMELINES, SHAPE_FILE)  # simulazione

    time_end = time.time()-starttime
    wprint(':Time required '+str(time_end)+' s')
    soimExit(error=False)


def core_soim(project_list: dict, latest, kernel_folder,output_folder):
    console.print(tuple(project_list.values()))
    if len(project_list) == 1:
        k = list(project_list.keys())
        readSK_run([k[0], project_list[k[0]], latest, kernel_folder])
    else:
        with Pool(len(project_list)) as p:
            p.map(readSK_run, [(k, v, latest, kernel_folder,output_folder)
                  for k, v in project_list.items()])

    # console.print(p.map(queque,project_list))
    pass

def readSK_run(elem):
    from planetary_coverage import ESA_MK, MetaKernel
    console.print(elem[0])
    a = MetaKernel(
        # 'meta.tm',
        elem[2],
        kernels=elem[3],
        download=False,
        load_kernels=True
    )
    main(*elem[0:2],elem[4])
