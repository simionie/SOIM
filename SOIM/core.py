from SOIM_simulation import SOIM_simulation, SOIM_simulationFOOTPRINT, listproducts
from rich.panel import Panel
from lib.utility import MSG, eprint, lprint, print_dic, wprint, soimExit, appendHOR
from lib.console import console
from lib.Verify_DarkSide import Verify_DarkSide
from lib.classes import Product, Timeline
from lib.IO_functions import *
import yaml
import spiceypy as spice
import rich_click as click
import pandas as pd
from pathlib import Path
from os import path
from datetime import datetime
import time
import sys
import pathlib
from os import environ
import csv
import os
from SOIM.lib.console import console


def info(title):
    print(title)
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())




def main(name,project):
    starttime = time.time()

    path_log = checkPrjFolder(project, 'logs')

    nowstr = time.strftime("%Y%m%d-%H%M%S")
    environ['SOIM_LOG'] = path_log.joinpath(f"log_{nowstr}.txt").as_posix()

    PATH_RESULTS = checkPrjFolder(project, 'results')
    PATFILE = checkPrjTxtItem(project, 'paths', 'yml')
    INSFILE = checkPrjTxtItem(project, 'instruments', 'yml')
    TIMFILE = checkPrjTxtItem(project, 'timeline', 'txt')
    SCEFILE = checkPrjTxtItem(project, 'scenario', 'yml')
    PROFILE = checkPrjTxtItem(project, 'products', 'csv')

    # #% Check interln value

    SpiceReaded = checkPathFile(PATFILE)
    if SpiceReaded:
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

        Timelines_DaySide = Verify_DarkSide(Timelines,Scenario,Products,SEC_OF_OVERSAMPLING)
        lprint("Verifing Timelines OUTPUT: "+str(len(Timelines_DaySide)))

        if (FOOTPRINT):
            # old version to simulate only fooprints
            SOIM_simulationFOOTPRINT(Timelines_DaySide, Scenario,Products,PATH_RESULTS)  #simulazione
        else:
            # Version complete to simlate a list of timelines and save the,
            MERGE_TIMELINES = True
            SHAPE_FILE = False
            SOIM_simulation(Timelines_DaySide, Scenario,Products,PATH_RESULTS,MERGE_TIMELINES,SHAPE_FILE)  #simulazione

    time_end = time.time()-starttime
    wprint(':Time required '+str(time_end)+' s')
    soimExit(error=False)


def pippo(elem):
    info('funtion pippo')
    console.print(elem[0])
    main(*elem)
