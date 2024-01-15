#! /usr/bin/env python3
import csv
from os import environ
import pathlib
import sys
import time
from datetime import datetime
from os import path
from pathlib import Path

import pandas as pd
import rich_click as click
import spiceypy as spice
import yaml

from lib.IO_functions import *
from lib.classes import Product, Timeline
from lib.Verify_DarkSide import Verify_DarkSide
from lib.console import console
from lib.utility import MSG, eprint, lprint, print_dic, wprint, soimExit, appendHOR
from SOIM_simulation import SOIM_simulation,SOIM_simulationFOOTPRINT, listproducts
from rich.panel import Panel


#######################
click.rich_click.USE_RICH_MARKUP = True
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

#%% STARTER

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--project', metavar='PROJ', help="Project name", default='my_project')
def main(project):
    starttime = time.time()
    

    # name_project='my_project'   #name of the project

#%% READ PROJECT

    #% CHECK FILE PATHS
    path_log=checkPrjFolder(project,'logs')
    
    nowstr = time.strftime("%Y%m%d-%H%M%S")
    environ['SOIM_LOG']=path_log.joinpath(f"log_{nowstr}.txt").as_posix()
    
    PATH_RESULTS=checkPrjFolder(project,'results')
    PATFILE=checkPrjTxtItem(project,'paths','yml')
    INSFILE=checkPrjTxtItem(project,'instruments','yml')    
    TIMFILE=checkPrjTxtItem(project,'timeline','txt')
    SCEFILE=checkPrjTxtItem(project,'scenario','yml')
    PROFILE=checkPrjTxtItem(project,'products','csv')

    # #% Check interln value
   
    SpiceReaded=checkPathFile(PATFILE)
    if SpiceReaded:
        InstFK=LoadInstrumentFile(INSFILE)
        Scenario=LoadScenarioFile(SCEFILE)
        Scenario['Instruments']=InstFK
        Timelines=LoadTimingFile(TIMFILE)
        Products=LoadProductsFile(PROFILE,Scenario)
        Products, InstrUsed=VelidateProducts(Products) #controllare gerarchia
        FOOTPRINT=False


#%% VERIFY DARK REGION AND SIMULATE       

        SEC_OF_OVERSAMPLING=60
        lprint("Verifing Timelines INPUT: "+str(len(Timelines)))

        Timelines_DaySide=Verify_DarkSide(Timelines,Scenario,Products,SEC_OF_OVERSAMPLING)
        lprint("Verifing Timelines OUTPUT: "+str(len(Timelines_DaySide)))


        if (FOOTPRINT):
            #old version to simulate only fooprints
            SOIM_simulationFOOTPRINT(Timelines_DaySide,Scenario,Products,PATH_RESULTS)  #simulazione
        else:
            #Version complete to simlate a list of timelines and save the,
            MERGE_TIMELINES=True
            SHAPE_FILE=False
            SOIM_simulation(Timelines_DaySide,Scenario,Products,PATH_RESULTS,MERGE_TIMELINES,SHAPE_FILE)  #simulazione


    time_end = time.time()-starttime
    wprint(':Time required '+str(time_end)+' s')
    soimExit(error=False)
       
    
    
    
if __name__=="__main__":
    main()

# %%
