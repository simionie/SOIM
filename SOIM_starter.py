#! /usr/bin/env python3
import os
import pathlib
import sys
import time
from datetime import datetime
from os import path
from pathlib import Path

import numpy as np
import pandas as pd
import rich_click as click
import spiceypy as spice
import yaml

import csv
from SOIM_simulation import SOIM_simulation
from lib.classes import Product, timeline
from lib.utility import wprint, lprint, print_dic, eprint, MSG
from lib.console import console

#######################
click.rich_click.USE_RICH_MARKUP = True
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])






class Loader(yaml.SafeLoader):
    """Add to the YAML standar class the command !include to include slave yaml file"""

    def __init__(self, stream):

        self._root = path.split(stream.name)[0]
        super(Loader, self).__init__(stream)

    def include(self, node):
        filename = path.join(self._root, self.construct_scalar(node))
        with open(filename, 'r') as f:
            return yaml.load(f, Loader)


Loader.add_constructor('!include', Loader.include)


def read_yaml(filepath):
    ''' Read a yaml file'''
    with open(filepath, 'r') as f:
        # return yaml.safe_load(f)
        return yaml.load(f, Loader)
################################

def timelog(num_sec):
    if (num_sec<100):
        ris=    "{:.2f}".format(num_sec)+' s'
        return ris
    if (num_sec< 36000):
        ris=    "{:.2f}".format(num_sec/(60))+' m'
        return ris
    ris=    "{:.2f}".format(num_sec/(60*60))+' h'
    return ris        
    
        
#%% Functions Cheking coerence Project 

# Detect if in a project folder is present 1 unique txt item with the
# defined prefix if not send an allert and stop the program 

def checkPrjTxtItem(name_project,prefix,extention):
    p=Path(name_project)
    #p.joinpath(prefix+'*.txt')
    items2=list(p.glob(prefix+'*.'+extention))
    if len(items2)==0:
        console.print(f"{MSG.ERROR} no {prefix} file found. ({prefix}*."+extention+")")
        sys.exit()
    elif len(items2) == 1:
        console.print(f"{MSG.INFO} File {prefix} detected. [magenta]{items2[0]}[/magenta]")
    else:
        console.print(f"{MSG.ERROR} Multiple {prefix} file found. Please Check")
        sys.exit()
    return items2[0]

# def checkPrjFolderNoLog(name_project,namefolder):
def checkPrjFolder(name_project, namefolder):
    folder=Path(name_project).joinpath(namefolder)
    if not folder.exists():
        console.print(f"{MSG.WARNING} The folder {namefolder} not exists")
        console.print(f"{MSG.INFO} Creating The foleder {namefolder}")
        folder.mkdir()
    else:
        console.print(f"{MSG.INFO} detected the folder {namefolder}")
    return folder   

#%% Functions Cheking all project items 

# PathFILE: containing MICE folder and reading spice kernels

def checkPathFile(PATHFILE):
    lprint('################################################')
    lprint('############ Checking path file')
    lprint('################################################')

    dic=read_yaml(PATHFILE)

    if 'MICE' not in dic.keys():
        console.print(f"{MSG.ERROR} MICE not defined in Pathfile")
        return False
    else:
        if not Path(dic['MICE']).exists():
            console.print(f"{MSG.ERROR} MICE folder not found")
            return False
        else:
             lprint("MICE folder found")
             lprint("  "+dic['MICE'])
             
    if not 'SPICE' in dic.keys():
        console.print(f"{MSG.ERROR} SPICE MT not defined in Pathfile")
        return False
        
    else:
        if not Path(dic['SPICE']).exists():
            console.print(f"{MSG.ERROR} MICE folder not found")
            return False
        else:
            console.print(f"{MSG.INFO} SPICE TM found")
            lprint("  "+dic['SPICE'])
            console.print(f"{MSG.INFO} Furnshing MetaKernel")
            spice.kclear()
            spice.furnsh(dic['SPICE'])
            lprint(' done.');
    return True

# InsFILE: reading NAIF frame kernels used 

def LoadInstrumentFile(INSTFILE):
    lprint('################################################')
    lprint('############ Checking Instrument file')
    lprint('################################################')

    dic=read_yaml(INSTFILE)

    if (len(dic)==0):
        eprint('Instruements not defined in InstrumentFile('+INSTFILE+')')
    else:
        lprint('Instruements read')
        print_dic(dic)
    return dic


def LoadScenarioFile(SCENFILE):
    lprint('################################################')
    lprint('############ Checking SCENARIO file')
    lprint('################################################')

    dic=read_yaml(SCENFILE)

    if (len(dic)==0):
        eprint('Instruements not defined in InstrumentFile('+SCENFILE+')')
    else:
        lprint('Scenario read')

    if "Shape" not in dic:
        wprint("Shape not defined. Default as Ellipsoid")
        dic["Shape"]="Ellipsoid"
    if "Light" not in dic:
        wprint("Light correction not define defined.Defaolut as LT+S")
        dic["Light"]="LT+S"

    print_dic(dic)
    
    return dic    

# Reference frame IDs are not used as input and/or output arguments 
# in any high level user APIs

def checkInstrumentFile(INSFILE):
    lprint('################################################')
    lprint('############ Checking Instrument file')
    lprint('################################################')
    f = open(INSFILE,'r')
    ind=0
    InstFK=[]
    ID=[]
    
    while True:
        line = f.readline()
        if not line:
            break
        x=line.split("|");
        name=x[0].rstrip();
        nid=int(x[1].rstrip());
        InstFK.append(name)
        ID.append(nid)
        lprint(name+':'+str(nid))
        ind=ind+1;
    f.close()
    lprint('Found '+str(ind)+' instruments')
    lprint('INSTRUMENTS NOT VERFIED IN SPICE KERNEL POOL')
    lprint('REMOVE ID BY INSTRUMENT TXT FILE')
    return InstFK


def LoadProductsFile(PROFILE,Scenario):
    lprint('################################################')
    lprint('############ Loading Product file')
    lprint('################################################')    
    prod=[]
    file = open(PROFILE, "r")
    data = list(csv.reader(file, delimiter=","))
    file.close()
    ind=0
    for x in data:
        if ind>0:
            if len(x)==3:
                n=len(x[2])
                d=""
                for i in range(n):
                    d=d+"6"
                wprint(" Format not spepecified for ")
                wprint(" "+x[0]+":"+x[1])
                wprint("  All output set to 6 format")
               
                p=product(x[0],x[1],x[2],d)
                p.addScenario(Scenario)
                prod.append(p)
            else:
                p = product(x[0],x[1],x[2],x[3])
                p.addScenario(Scenario)
                prod.append(p)
            lprint(str(ind)+".")
            prod[ind-1].print()
        ind=ind+1
    return prod
    



# TimFILE: reading timeline and associated instruments  

def LoadTimingFile(TIMFILE):
    lprint('################################################')
    lprint('############ Reading timing file')
    lprint('################################################')
    f = open(TIMFILE,'r')
    ind=0
    Timelines=[]
    
    while True:
        line = f.readline()
        if not line:
            break
        x=line.split("|");
        starting_time=x[0].rstrip();
        step_time=x[1].rstrip();
        stopping_time=x[2].rstrip();
        list_fk=x[3].rstrip();
        x=list_fk.split();
        t_item=timeline(starting_time,stopping_time,step_time,x)
        Timelines.append(t_item)
        lprint(str(ind+1)+".")
        t_item.print()
        ind=ind+1;
    f.close()
    lprint('Found '+str(ind)+' timelines')
    
    return Timelines

  

# def wprint(wstr):
#       console.print(f"{MSG.WARNING} "+wstr)
# def lprint(lstr):
#         console.print(f"{MSG.INFO} "+lstr)
# def eprint(lstr):
#         console.print(f"{MSG.ERROR} "+lstr)
# def print_dic(dct):
#     for item, amount in dct.items():  # dct.iteritems() in Python 2
#         console.print(f"{MSG.INFO} "+"   {} ({})".format(item, amount))


#%% STARTER

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--project', metavar='PROJ', help="Project name", default='my_project')
def main(project):
    starttime = time.time()

    # name_project='my_project'   #name of the project


    #% CHECK FILE PATHS
    path_log=checkPrjFolder(project,'logs')
    nowstr = time.strftime("%Y%m%d-%H%M%S")

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
        
        SOIM_simulation(Timelines,Scenario,Products)
    
       
    console.save_text(path_log.joinpath(f"log_{nowstr}.txt"),styles=False)
    
    
if __name__=="__main__":
    main()
