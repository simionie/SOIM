import csv
import pathlib
import sys
import time
from datetime import datetime
from os import environ, path
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rich_click as click
import spiceypy as spice
import yaml
from rich.panel import Panel
from shapely.geometry import Point, Polygon

from SOIM.lib.classes import Product, Timeline, listproducts
from SOIM.lib.console import console
from SOIM.lib.utility import (MSG, appendHOR, eprint, lprint, print_dic,
                              soimExit, wprint)


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
        return yaml.load(f, Loader)


# Detect if in a project folder is present 1 unique txt item with the
# defined prefix if not send an allert and stop the program 

def checkPrjTxtItem(name,name_project,prefix,extention,suppress):
    p=Path(name_project)
    #p.joinpath(prefix+'*.txt')
    items2=list(p.glob(prefix+'*.'+extention))
    if len(items2)==0:
        console.print(
            f"{MSG.ERROR} -{name}- no {prefix} file found. ({prefix}*."+extention+")")
        sys.exit()
    elif len(items2) == 1:
        if not suppress:
            console.print(
                f"{MSG.INFO} -{name}- File {prefix} detected. [magenta]{items2[0]}[/magenta]")
    else:
        console.print(
            f"{MSG.ERROR} -{name}- Please check <{name_project}> project")
        console.print(f"{MSG.ERROR}              Multiple {prefix} file found. Please Check")
        sys.exit()
    return items2[0]

# def checkPrjFolderNoLog(name_project,namefolder):
def checkPrjFolder(name,output_folder, namefolder,suppress):
    folder=Path(output_folder).joinpath(name).joinpath(namefolder)
    folder.mkdir(parents=True,exist_ok=True)
    if not folder.exists():
        console.print(f"{MSG.WARNING} -{name}- The folder {namefolder} not exists")
        console.print(f"{MSG.INFO} -{name}- Creating The folder {namefolder}")
        folder.mkdir()
    else:
        if not suppress:
            console.print(f"{MSG.INFO} -{name}- Detected the folder {namefolder}")
    return folder   


# PathFILE: containing MICE folder and reading spice kernels

def checkPathFile(name,PATHFILE):
     console.rule(f"Checking path file ", style='yellow')
     console.print(f"       {PATHFILE}")
     console.rule("", style='yellow')

     dic=read_yaml(PATHFILE)
     #if 'MICE' not in dic.keys():
     #    console.print(f"{MSG.ERROR} MICE not defined in Pathfile")
     #    return False
     #else:
     #    if not Path(dic['MICE']).exists():
     #        console.print(f"{MSG.ERROR} MICE folder not found {dic['MICE']}")
     #        return False
     #    else:
     #         lprint("MICE folder found")
     #         lprint("  "+dic['MICE'])
            
     if not 'SPICE' in dic.keys():
         console.print(f"{MSG.ERROR} SPICE MT not defined in Pathfile")
         return False
       
     else:
         if not Path(dic['SPICE']).exists():
             console.print(f"{MSG.ERROR} SPICE folder not found!")
             console.print(f"{MSG.ERROR}       {dic['SPICE']}")
             console.print(f"{MSG.ERROR}       Verify the PathFile: {PATHFILE}")            
             return False
         else:
             console.print(f"{MSG.INFO} SPICE TM found")
             console.print(f"{MSG.INFO} "+dic['SPICE'])
             console.print(f"{MSG.INFO} Furnshing MetaKernel")
             spice.kclear()
             try:
                 spice.furnsh(dic['SPICE'])
             except Exception as e:
                 console.print("Kernel Error")
                 console.print(e)
                 soimExit(error=True)
             console.print(' done.')
     return True

# InsFILE: reading NAIF frame kernels used 

def LoadInstrumentFile(INSTFILE,log_file:Path):
    with open(log_file,'a') as fl:
        fl.write("--------- Checking Instrument file -------\n")
        fl.write(f"       {INSTFILE}\n")
        fl.write("------------------------------------------\n")

    
    dic=read_yaml(INSTFILE)

    if (len(dic)==0):
        eprint('Instruments not defined in InstrumentFile('+INSTFILE+')')
    else:
        lprint('Instruements read',log_file)
        print_dic(dic,log_file)
    return dic


def LoadScenarioFile(SCENFILE,log_file:Path):
    with open(log_file,'a') as fl:
        fl.write("--------- Checking SCENARIO  file -------\n")
        fl.write(f"       {SCENFILE}\n")
        fl.write("------------------------------------------\n")

    dic=read_yaml(SCENFILE)

    if (len(dic)==0):
        eprint('Instruements not defined in InstrumentFile('+SCENFILE+')')
    else:
        lprint('Scenario read',log_file)

    if "Shape" not in dic.keys():
        wprint("Shape not defined. Default as Ellipsoid           for sinc")
        wprint("                              INTERCEPT/ELLIPSOID for sbnd")
        dic["ShapeSinc"]="Ellipsoid"
        dic["ShapeSbnd"]="INTERCEPT/ELLIPSOID"
        
    if "Light" not in dic.keys():
        wprint("Light correction not define defined. Default as LT+S")
        dic["Light"]="LT+S"

    print_dic(dic, log_file)
    
    return dic    

# Reference frame IDs are not used as input and/or output arguments 
# in any high level user APIs

def checkInstrumentFile(INSFILE,log_file:Path):

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
        lprint(name+':'+str(nid), log_file)
        ind=ind+1;
    f.close()
    lprint('Found '+str(ind)+' instruments',log_file)
    lprint('INSTRUMENTS NOT VERFIED IN SPICE KERNEL POOL', log_file)
    lprint('REMOVE ID BY INSTRUMENT TXT FILE', log_file)
    return InstFK


def LoadProductsFile(PROFILE,Scenario,log_file:Path):

    #Return the list of products in the CSVFILE 
    #    INSTRUMENT	INSTRUMENT	INSTRUMENT	INSTRUMENT
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Corners	LR	33
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Subnadiral	LRD	333
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Boresight	LRIEPS	338883
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Pog	m	3
    #    MPO_SIMBIO-SYS_HRIC_FPAN	VelBor	mpd	333
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Swath	dm	33
    #    MPO_SIMBIO-SYS_HRIC_FPAN	Subsolar	LR	33


    with open(log_file,'a') as fl:
        fl.write("--------- Loading Product file -------\n")
        fl.write(f"       {PROFILE}\n")
        fl.write("------------------------------------------\n")

 
    prod=[]
    with open(PROFILE, "r") as f:
    # file = open(PROFILE, "r")
        data = list(csv.reader(f, delimiter=","))
    # file.close()
    ind=0
    for x in data:
        if ind>0:
            if len(x)==3:
                n=len(x[2])
                d=""
                for i in range(n):
                    d=d+"6"
                txt=f"Format not spepecified for  <{x[0].strip()}:\t{x[1].strip()}> \nAll output set to 6 format"
                console.print(Panel(txt,title='WARNING',border_style='yellow',title_align='left',expand=False))
                p=Product(x[0],x[1],x[2],d,True)
                p.addScenario(Scenario)
                prod.append(p)
            else:
                p = Product(x[0],x[1],x[2],x[3],True)
                p.addScenario(Scenario)
                prod.append(p)
            lprint(str(ind)+".",log_file)
            prod[ind-1].print(log_file)
        ind=ind+1
    return prod
    

def  VelidateProducts(Products):

    Prod2beAdd=[]
    for p in Products:
        if (p.pog|p.vel):
            listprod=listproducts(p.instr,Products)
            boresightdefined=False
            for p2 in listprod:
                boresightdefined=boresightdefined|p2.boresight 
            if not(boresightdefined): #Boresight fastr is X TBC *123#
                if (p.pog):
                    wprint(p.instr+' pog required need Boresight definition')
                if (p.vel):
                    wprint(p.instr+' vel required need Boresight definition')
                Prod2beAdd.append(Product(p.instr,'Boresight', 'X', '3',False))
    for p in Prod2beAdd:  
        Products.append(p)

    InstrUsed=[]
    for p in Products:
        ins=p.instr
        new=True
        for ins_ in InstrUsed:
            if (ins_==ins):
                new=False
        if (new):
            InstrUsed.append(ins)



    return Products, InstrUsed

# TimFILE: reading timeline and associated instruments  

def LoadTimingFile(TIMFILE,log_file:Path):
    with open(log_file, 'a') as fl:
        fl.write("--------- Reading timing file  file -------\n")
        fl.write(f"       {TIMFILE}\n")
        fl.write("------------------------------------------\n")
   
    # f = open(TIMFILE,'r')
    ind=1
    timeLines=[]
    with open(TIMFILE, 'r') as f:
    # while True:
        lines = f.readlines()
        
    
    for line in lines:
        if line.isspace():
            wprint(f"Timeline #X")
            wprint(f"Removed last timeline becouse empty")
        else:
            x=line.split("|")
            starting_time=x[0].strip()
            step_time=x[1].strip()
            stopping_time=x[2].strip()
            list_fk=x[3].strip()
            x=list_fk.split()
            t_item=Timeline(starting_time,stopping_time,step_time,x)
            timeLines.append(t_item)
            lprint(f"Timeline #{ind}",log_file)
            t_item.print(log_file)
            ind +=1 
    lprint(f'Found {len(timeLines)} timelines',log_file)

    
    return timeLines


def getname_vars(title_cols1,title_cols2,title_cols3):
    ris=[]
    for i in range(0,len(title_cols1)):
        str=title_cols2[i]+title_cols3[i]
        str=str.replace('°]','deg')
        str=str.replace('[°/s]','_DpS')
        str=str.replace('[','_')
        str=str.replace(']','')
        ris.append(str)
    return ris


# Save all the output defined in convert_Acqs2TabData

def writeShapeFile(namefile,title_cols1,title_cols2,title_cols3,risTIME,START_CORNERS,STEP_CORNERS,log_file):
    lprint('WRITING SHAPEFILE ', log_file)
    lprint('             NAME '+str(namefile), log_file)

    #START_CORNERS=3
    #STEP_CORNERS=3

    nfoot=0

    crs_string = 'GEOGCRS["Mercury_2015",DATUM["Mercury_2015",ELLIPSOID["Mercury_2015",2439400,0,LENGTHUNIT["metre",1]]],PRIMEM["Reference_Meridian",0,ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],AXIS["geodetic latitude (Lat)",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],AXIS["geodetic longitude (Lon)",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],ID["ESRI",104974]]'
    poly=[]
    data={}
    NVAR=len(risTIME[0])
    LEN=len(risTIME)

    dati=pd.DataFrame(risTIME).T
    var_names=getname_vars(title_cols1,title_cols2,title_cols3)
    for i in range(0,NVAR):
        console.print(var_names[i])
        x=[]
        for j in range(0,LEN):
            x.append(risTIME[j][i])
        data[var_names[i]]=x


    for i in range(0,LEN):
        y=risTIME[i][START_CORNERS:(STEP_CORNERS*4+START_CORNERS):STEP_CORNERS]    # dipende dalla struttura
        x=risTIME[i][(START_CORNERS+1):(STEP_CORNERS*4+START_CORNERS):STEP_CORNERS]
        poly.append(Polygon(zip(x, y)))
    poly = gpd.GeoSeries(poly)  

    newdata = gpd.GeoDataFrame(data=data,geometry=poly,crs=crs_string)
    newdata.to_file(str(namefile))
    lprint('Fooprints saved: '+str(nfoot), log_file)




