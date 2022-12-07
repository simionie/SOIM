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
from rich.console import Console

#######################
click.rich_click.USE_RICH_MARKUP = True
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
console=Console(record=True)

class MSG:
    WARNING="[yellow][WARNINIG][/yellow]"
    INFO="[green][INFO][/green]"
    ERROR = "[red][ERROR][/red]"


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
#%% Classes

class scenario:
    Orbiter=""
    Target=""
    TFrame=""
    Shape='Ellipsoid'
    LCorr='LT+S'
    
    def __init__(self, Orbiter_, Target_, TFrame_,Shape_,LCorr_): 
        self.Orbiter=Orbiter_;
        self.Target=Target_;
        self.TFrame=TFrame_;
        self.Shape=Shape_;
        self.LCorr=LCorr_;
        
    def print(self, LOGFILE):
          lprint("Orbiter      :"+self.Orbiter, LOGFILE)        
          lprint("Target       :"+self.Target, LOGFILE)       
          lprint("Frame Target :"+self.TFrame, LOGFILE)        
          lprint("Shape        :"+self.Shape, LOGFILE)        
          lprint("LCorrection  :"+self.LCorr, LOGFILE)        
    
    

class timel:
 
    # A simple class attribute
    t0_str=""
    te_str=""
    t0=0
    te=0
    dt=0
    instr=[];
    t=[];
    def __init__(self, starting_time, stop_time,tstep, instr_):  
        self.t0_str = starting_time  
        self.t0 = spice.str2et(starting_time)
        self.te_str = stop_time
        self.te = spice.str2et(stop_time)
        self.dt = float(tstep)
        self.instr = instr_
        self.t = np.arange( self.t0, self.te, self.dt)
        
    def print(self, LOGFILE):
        st1=self.t0_str+"("+str(self.t0)+")"
        st2=self.te_str+"("+str(self.te)+")"
        st3="["+str(self.dt)+"s]"
        st4="";
        for x in self.instr:
            st4=st4+"  "+x 
        st5="N-Acq: "+str(len(self.t))
        lprint("      "+st1,LOGFILE);
        lprint("      "+st2,LOGFILE);
        lprint("      "+st3,LOGFILE);
        lprint("      "+st4,LOGFILE);
        dur=self.te-self.t0
        dur_min=(dur)/60
        dur="{:.2f}".format(dur)
        dur_min="{:.2f}".format(dur_min)
        lprint("      Duration "+str(dur)+"[s]="+str(dur_min)+"[min]",LOGFILE);
        lprint("      "+st5,LOGFILE);
    
    

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

    # print('§°§°§§§§§§§§§§§§§§§§§§§§§§§§§§')
    # p = Path('.')
    # list(p.glob('**/*.py'))
    # for child in p.iterdir(): child
    # items=glob.glob(name_project+'\\'+prefix+'*.txt')
    # if (len(items)==1):
    #     lprint('Detected '+prefix+' file:\t'+items[0],LOGFILE)
    # else:
    #     if (len(items)==0):
    #         wprint('ERROR: no '+prefix+' file found (format '+prefix+'*.txt)',LOGFILE);
    #         sys.exit()
    #     else:
    #         wprint('ERROR: too many instrument files found (format '+prefix+'*.txt)',LOGFILE);
    #         sys.exit()
    # return items[0]

# Detect if in a project folder is present 1 folder if not send generate the 
# folder and senda Warning 

# def checkPrjFolder(name_project,namefolder,LOGFILE):
#     item=glob.glob(name_project+'\\'+namefolder)
#     if (len(item)!=1):
#         wprint('WARNING: no '+namefolder+' folder found (I generate it)',LOGFILE);
#         os.mkdir(name_project+'\\'+namefolder)
#     item=glob.glob(name_project+'\\'+namefolder)
#     lprint('Detected\t\t'+item[0],LOGFILE)
#     return item[0]
# Detect if in a project folder is present 1 folder if not send generate the 
# folder and senda Warning 

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
    # item=glob.glob(name_project+'\\'+namefolder)
    # if (len(item)!=1):
    #     print('WARNING: no '+namefolder+' folder found (I generate it)');
    #     os.mkdir(name_project+'\\'+namefolder)
    # item=glob.glob(name_project+'\\'+namefolder)
    # print('Detected\t\t'+item[0])
    # return item[0]    

#%% Functions Cheking all project items 

# PathFILE: containing MICE folder and reading spice kernels

def checkPathFile(PATHFILE,LOGFILE):
    lprint('################################################',LOGFILE)
    lprint('############ Checking path file',LOGFILE)
    lprint('################################################',LOGFILE)

    dic=read_yaml(PATHFILE)


    if (len(dic['MICE'])== 0):
        console.print(f"{MSG.ERROR} MICE not defined in Pathfile")
        return False
    else:
        if (os.path.exists(dic['MICE'])):
            console.print(f"{MSG.ERROR} MICE folde not found")
    if (len(dic['SPICE'])== 0):
        console.print(f"{MSG.ERROR} SPICE MT not defined in Pathfile")
        return False
        
    else:
        if (os.path.isfile(dic['SPICE'])):
            console.print(f"{MSG.INFO} SPICE TM found")
            console.print(f"{MSG.INFO} Furnshing MetaKernel")
            spice.kclear()
            spice.furnsh(dic['SPICE'])
            lprint(' done.',LOGFILE);
            
    return True

# InsFILE: reading NAIF frame kernels used 

# Reference frame IDs are not used as input and/or output arguments 
# in any high level user APIs

def checkInstrumentFile(INSFILE,LOGFILE):
    lprint('################################################',LOGFILE)
    lprint('############ Checking Instrument file',LOGFILE)
    lprint('################################################',LOGFILE)
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
        lprint(name+':'+str(nid),LOGFILE)
        ind=ind+1;
    f.close()
    lprint('Found '+str(ind)+' instruments',LOGFILE)
    lprint('INSTRUMENTS NOT VERFIED IN SPICE KERNEL POOL',LOGFILE)
    lprint('REMOVE ID BY INSTRUMENT TXT FILE',LOGFILE)
    return InstFK

# TimFILE: reading timeline and associated instruments  

def checkTimingFile(TIMFILE,LOGFILE):
    lprint('################################################',LOGFILE)
    lprint('############ Checking timing file',LOGFILE)
    lprint('################################################',LOGFILE)
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
        x=list_fk.split(" ");
        t_item=timel(starting_time,stopping_time,step_time,x)
        Timelines.append(t_item)
        lprint(str(ind+1)+".",LOGFILE)
        t_item.print(LOGFILE)
        ind=ind+1;
    f.close()
    lprint('Found '+str(ind)+' timelines',LOGFILE)
    return Timelines

    
# ScenarioFILE: containing scenario definitions

def checkScenarioFile(SCENFILE,LOGFILE):
    lprint('################################################',LOGFILE)
    lprint('############ Checking Scenario file',LOGFILE)
    lprint('################################################',LOGFILE)
    Lbool=False
    Sbool=False
    


    
    f = open(SCENFILE,'r')
    while True:
        line = f.readline()
        if not line:
            break
        x=line.split("|");
        if x[0]=="Orbiter":
            orb=x[1].rstrip()
        if x[0]=="Target":
            tar=x[1].rstrip()
        if x[0]=="Target Frame":
            tarf=x[1].rstrip()
        if x[0]=="Shape":
            shp=x[1].rstrip()
            Sbool=True
        if x[0]=="Light":
            lgth=x[1].rstrip()
            Lbool=True
    f.close()
    if (Lbool!= True):
        wprint('Default setting for Light Correction',LOGFILE);
        lgth='LT+S'
    if (Sbool!= True):
        wprint('Default setting for Shape model',LOGFILE);
        lgth='Ellipsoid'
        
    scen_=scenario(orb,tar,tarf,shp,lgth)    
    scen_.print(LOGFILE)
            
    return scen_


def wprint(wstr,LOGFILE):
    print('\t\t'+wstr);
    LOGFILE.write('     '+wstr+'\n')
def lprint(lstr,LOGFILE):
    print(lstr);
    LOGFILE.write('     '+lstr+'\n')


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
    PROFILE=checkPrjTxtItem(project,'products','yml')

    # #% Check interln value
   
    SpiceReaded=checkPathFile(PATFILE)
    # InstFK=checkInstrumentFile(INSFILE,LOGFILE)
    # Timelines=checkTimingFile(TIMFILE,LOGFILE)
    # Scenario=checkScenarioFile(SCEFILE,LOGFILE)

    # #% CLOSE
    # stoptime = time.time()
    # dur=stoptime-starttime
    # dur_min=(dur)/60
    # dur="{:.2f}".format(dur)
    # dur_min="{:.2f}".format(dur_min)
    # lprint('\n\nDURATION '+str(dur)+'[s]='+str(dur_min)+'[m]',LOGFILE)
    

    # p = pathlib.PurePath('C:\\Pippo')    
    # print(p)    

    # p = pathlib.PurePath('C://Pippo')    
    # print(p)    
    console.save_text(path_log.joinpath(f"log_{nowstr}.txt"),styles=False)
    
    
if __name__=="__main__":
    main()
