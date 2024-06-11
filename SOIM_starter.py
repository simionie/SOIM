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

from SOIM.lib.IO_functions import *
from SOIM.lib.classes import Product, Timeline
from SOIM.lib.Verify_DarkSide import Verify_DarkSide
from SOIM.lib.console import console
from SOIM.lib.utility import MSG, eprint, lprint, print_dic, wprint, soimExit, appendHOR
from SOIM.SOIM_simulation import SOIM_simulation,SOIM_simulationFOOTPRINT, listproducts
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

    suppress=False
    name='nameTBD'

    #% CHECK FILE PATHS
    path_log=checkPrjFolder(name, project, 'logs',suppress) 
    log_file=path_log.joinpath(f"{name}_output.log")
    
    nowstr = time.strftime("%Y%m%d-%H%M%S")
    environ['SOIM_LOG']=path_log.joinpath(f"log_{nowstr}.txt").as_posix()
    
    PATH_RESULTS=checkPrjFolder(name,project,'results',suppress)
    PATFILE=checkPrjTxtItem(name,project,'paths','yml',suppress)
    INSFILE=checkPrjTxtItem(name,project,'instruments','yml',suppress)    
    TIMFILE=checkPrjTxtItem(name,project,'timeline','txt',suppress)
    SCEFILE=checkPrjTxtItem(name,project,'scenario','yml',suppress)
    PROFILE=checkPrjTxtItem(name,project,'products','csv',suppress)

    # #% Check interln value
   
    SpiceReaded=checkPathFile(name, PATFILE )
    if SpiceReaded:
        InstFK=LoadInstrumentFile(INSFILE,log_file)
        Scenario=LoadScenarioFile(SCEFILE,log_file)
        Scenario['Instruments']=InstFK
        Timelines=LoadTimingFile(TIMFILE,log_file)
        Products=LoadProductsFile(PROFILE,Scenario,log_file)
        Products, InstrUsed=VelidateProducts(Products) #controllare gerarchia
        FOOTPRINT=False


#%% VERIFY DARK REGION AND SIMULATE       

        SEC_OF_OVERSAMPLING=60
        console.print("Verifing Timelines INPUT: "+str(len(Timelines)))

        Timelines_DaySide=Verify_DarkSide(Timelines,Scenario,Products,SEC_OF_OVERSAMPLING,log_file)
        console.print("Verifing Timelines OUTPUT: "+str(len(Timelines_DaySide)))


        if (FOOTPRINT):
            console.print(f"{MSG.INFO} FOOTPRINT  : ON")
            console.print(f"{MSG.INFO} SIMULATION : OFF")
            #old version to simulate only fooprints
            SOIM_simulationFOOTPRINT(Timelines_DaySide,Scenario,Products,PATH_RESULTS,log_file)  #simulazione
        else:
            console.print(f"{MSG.INFO} FOOTPRINT  : OFF")
            console.print(f"{MSG.INFO} SIMULATION : ON")
            #Version complete to simulate a list of timelines and save the,
            MERGE_TIMELINES=True
            SHAPE_FILE=True
            ANTI_MERIDAN=False
            SOIM_simulation(Timelines_DaySide,Scenario,Products,PATH_RESULTS,MERGE_TIMELINES,SHAPE_FILE,ANTI_MERIDAN,log_file)  #simulazione


    time_end = time.time()-starttime
    wprint(':Time required '+str(time_end)+' s')
    soimExit(error=False)
       
    
    
    
if __name__=="__main__":
    main()

# %%
