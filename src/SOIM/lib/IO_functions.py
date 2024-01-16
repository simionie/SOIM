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

def checkPrjTxtItem(name,name_project,prefix,extention):
    p=Path(name_project)
    #p.joinpath(prefix+'*.txt')
    items2=list(p.glob(prefix+'*.'+extention))
    if len(items2)==0:
        console.print(
            f"{MSG.ERROR} -{name}- no {prefix} file found. ({prefix}*."+extention+")")
        sys.exit()
    elif len(items2) == 1:
        console.print(
            f"{MSG.INFO} -{name}- File {prefix} detected. [magenta]{items2[0]}[/magenta]")
    else:
        console.print(
            f"{MSG.ERROR} -{name}- Please check <{name_project}> project")
        console.print(f"{MSG.ERROR}              Multiple {prefix} file found. Please Check")
        sys.exit()
    return items2[0]

# def checkPrjFolderNoLog(name_project,namefolder):
def checkPrjFolder(name,output_folder, namefolder):
    folder=Path(output_folder).joinpath(name).joinpath(namefolder)
    folder.mkdir(parents=True,exist_ok=True)
    if not folder.exists():
        console.print(f"{MSG.WARNING} -{name}- The folder {namefolder} not exists")
        console.print(f"{MSG.INFO} -{name}- Creating The folder {namefolder}")
        folder.mkdir()
    else:
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
            lprint("  "+dic['SPICE'])
            console.print(f"{MSG.INFO} Furnshing MetaKernel")
            spice.kclear()
            try:
                spice.furnsh(dic['SPICE'])
            except Exception as e:
                eprint("Kernel Error")
                console.print(e)
                soimExit(error=True)
            lprint(' done.')
    return True

# InsFILE: reading NAIF frame kernels used 

def LoadInstrumentFile(INSTFILE):

    console.rule("Checking Instrument file ", style='yellow')
    console.print(f"       {INSTFILE}")
    console.rule("", style='yellow')

    
    dic=read_yaml(INSTFILE)

    if (len(dic)==0):
        eprint('Instruements not defined in InstrumentFile('+INSTFILE+')')
    else:
        lprint('Instruements read')
        print_dic(dic)
    return dic


def LoadScenarioFile(SCENFILE):

    console.rule("Checking SCENARIO  file ", style='yellow')
    console.print(f"       {SCENFILE}")
    console.rule("", style='yellow')

    dic=read_yaml(SCENFILE)

    if (len(dic)==0):
        eprint('Instruements not defined in InstrumentFile('+SCENFILE+')')
    else:
        lprint('Scenario read')

    if "Shape" not in dic.keys():
        wprint("Shape not defined. Default as Ellipsoid           for sinc")
        wprint("                              INTERCEPT/ELLIPSOID for sbnd")
        dic["ShapeSinc"]="Ellipsoid"
        dic["ShapeSbnd"]="INTERCEPT/ELLIPSOID"
        
    if "Light" not in dic.keys():
        wprint("Light correction not define defined. Default as LT+S")
        dic["Light"]="LT+S"

    print_dic(dic)
    
    return dic    

# Reference frame IDs are not used as input and/or output arguments 
# in any high level user APIs

def checkInstrumentFile(INSFILE):

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

    console.rule("Loading Product file ", style='yellow')
    console.print(f"       {PROFILE}")
    console.rule("", style='yellow')

 
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
            lprint(str(ind)+".")
            prod[ind-1].print()
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

def LoadTimingFile(TIMFILE):

    console.rule("Reading timing file ", style='yellow')
    console.print(f"       {TIMFILE}")
    console.rule("", style='yellow')
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
            lprint(f"Timeline #{ind}")
            t_item.print()
            ind +=1 
    lprint(f'Found {len(timeLines)} timelines')

    
    return timeLines

def writeShapeFile(Aquisitions,namefile):
    lprint('WRITING SHAPEFILE ')
    lprint('             NAME '+namefile)
    nfoot=0

    crs_string = 'GEOGCRS["Mercury_2015",DATUM["Mercury_2015",ELLIPSOID["Mercury_2015",2439400,0,LENGTHUNIT["metre",1]]],PRIMEM["Reference_Meridian",0,ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],AXIS["geodetic latitude (Lat)",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],AXIS["geodetic longitude (Lon)",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],ID["ESRI",104974]]'
    poly=[]
    data=[]
    for i in range(len(Aquisitions)):
        acq=Aquisitions[i]
        if (acq.has_foot()):
            coordinates = acq.get_foot_longlat()   # *123#
            poly.append(Polygon(coordinates))
            data.append( [ acq.instr, acq.time,acq.norbit, acq.pog_h, acq.pog_w, acq.vel])
            nfoot=nfoot+1
    newdata = gpd.GeoDataFrame(data=data,columns=['instrument','time','orbit','pog_h','pog_w','vel'],geometry=poly,crs=crs_string)
    newdata.to_file(namefile)

    lprint('Fooprints saved: '+str(nfoot))