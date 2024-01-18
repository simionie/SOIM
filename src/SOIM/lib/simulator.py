import csv
import math
import time

import geopandas as gpd
import numpy as np
import spiceypy as spice
from numpy import linalg as LA
from rich.panel import Panel
from shapely.geometry import Point, Polygon

from SOIM.lib.classes import Aquisition, Product, listproducts
from SOIM.lib.console import console
from SOIM.lib.IO_functions import writeShapeFile
from SOIM.lib.utility import (appendHOR, eprint, lprint, print_dic, soimExit,
                              wprint)


def timelog(num_sec):
    if (num_sec < 100):
        ris = "{:.2f}".format(num_sec)+' s'
        return ris
    if (num_sec < 36000):
        ris = "{:.2f}".format(num_sec/(60))+' m'
        return ris
    ris = "{:.2f}".format(num_sec/(60*60))+' h'
    return ris 

def evalTimeline(tl,ins,FOVBoundaryVectors,listprod,Scenario, fr, Bor,vh_pix,vw_pix):
    

    metsinc_=Scenario["ShapeSinc"]
    metsbnd_=Scenario["ShapeSbnd"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]

    BORENOTFOUND=0
    BOREINSUFFIC=0
    SBNANOTFOUND=0
    SBNAINSUFFIC=0
    CORNNOTFOUND=0
    CORNINSUFFIC=0
    
    
    # Start simulation
    Aquisitions=[]
    net=1

    for et in tl.t:                                                                     # For each time

        
        acq=Aquisition(ins,et)

        if (net==1):
            t = time.time()

        for p in listprod:                                                              # For each products

            if p.boresight:  
                
                                                                                    # CASE BORESIGHT
                found=False
                try:
                    [point_bor, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et, tfr_ , lc_, obs_, fr, Bor)
                    found=True
                except spice.NotFoundError as message:
                    BORENOTFOUND=BORENOTFOUND+1
                    point_bor= [0,0,0]
                    found=False
                except spice.SpiceSPKINSUFFDATA as message: 
                    BOREINSUFFIC=BOREINSUFFIC+1
                    point_bor=[0,0,0] 
                    found=False
                acq.add_borep(point_bor)
                pconv=p.convert(point_bor,et,found)
                if (p.f_latlong):
                    acq.add_borep(pconv[0],pconv[1])
                    if (len(pconv)==6):
                        acq.add_ill(pconv[3],pconv[4],pconv[5])
            if p.subnadiral:                                                            # CASE SUBNADIRAL
                found=False
                try:
                    [point, iep, v_ob2p]=spice.subpnt(metsbnd_, tar_, et, tfr_ , lc_, obs_)
                    found=True
                except spice.NotFoundError as message:
                    SBNANOTFOUND=SBNANOTFOUND+1
                    point= [0,0,0]  
                    found=False
                except spice.SpiceSPKINSUFFDATA as message: 
                    SBNAINSUFFIC=SBNAINSUFFIC+1
                    point=[0,0,0] 
                    found=False   
                #add results
                acq.add_subnp(point)
                pconv=p.convert(point,et,found)
                if (p.subnadiral):
                    acq.add_subn(pconv[0],pconv[1])

            if p.corners:                                                               # CASE CORNERS
                index=0
                lat=[]
                long=[]
                cpoints=[]
                for v in FOVBoundaryVectors:
                    found=False
                    try:
                        [point, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et, tfr_ , lc_, obs_, fr, v)
                        found=True
                    except spice.NotFoundError as message: 
                        CORNNOTFOUND=CORNNOTFOUND+1
                        point=[0,0,0] 
                        found=False
                    except spice.SpiceSPKINSUFFDATA as message:
                        CORNINSUFFIC=CORNINSUFFIC+1; 
                        point=[0,0,0] 
                        found=False
                    #add results                                
                    converted=p.convert(point,et,found)
                    lat.append(converted[0])
                    long.append(converted[1])
                    cpoints.append(point)
                    index=index+1
                acq.add_corners(lat,long)
                acq.add_cornersp(cpoints)
            if p.swath:
                # we assume
                #   3      -------> vw   0
                #                        ^
                #                        |vh
                #
                #   2                    1     

                #    1                                 2
                #    ^
                #    |vh
                #
                #    0                                 3




                #c0= cpoints[0]/R
                c0= cpoints[0]/np.linalg.norm(cpoints[0])
                c1= cpoints[1]/np.linalg.norm(cpoints[1])
                c2= cpoints[2]/np.linalg.norm(cpoints[2])
                c3= cpoints[3]/np.linalg.norm(cpoints[3])
                ang_h01=math.acos(np.inner(c0,c1))
                ang_w12=math.acos(np.inner(c1,c2))
                ang_h23=math.acos(np.inner(c2,c3))
                ang_w03=math.acos(np.inner(c0,c3))
                # convert radh radw r
                ris=p.convert([0.5*(ang_h01+ang_h23),0.5*(ang_w12+ang_w03),R],et,found)
                acq.add_swaths(ris)

            if p.pog:                                                             # CASE DWELL TIME
                    try:
                        [point_h, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et, tfr_ , lc_, obs_, fr, Bor+vh_pix)
                        [point_w, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et, tfr_ , lc_, obs_, fr, Bor+vw_pix)
                        found=True
                        dpoint_h=point_bor-point_h
                        dpoint_w=point_bor-point_w
                    except spice.NotFoundError as message: 
                        CORNNOTFOUND=CORNNOTFOUND+1
                        dpoint_h=[0,0,0] 
                        dpoint_w=[0,0,0] 
                        found=False
                    except spice.SpiceSPKINSUFFDATA as message:
                        CORNINSUFFIC=CORNINSUFFIC+1; 
                        dpoint_h=[0,0,0] 
                        dpoint_w=[0,0,0] 
                        found=False
                    h=p.convert(dpoint_h,et,found)
                    w=p.convert(dpoint_w,et,found)

                    acq.add_pog(h,w)

            if p.vel:  
                    
                tvel=0.001
                found=False
                try:
                    [point_bor_old, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et-tvel, tfr_ , lc_, obs_, fr, Bor)
                    found=True
                except spice.NotFoundError as message:
                    BORENOTFOUND=BORENOTFOUND+1
                    point_bor_old= [0,0,0]
                    found=False
                except spice.SpiceSPKINSUFFDATA as message: 
                    BOREINSUFFIC=BOREINSUFFIC+1
                    point_bor_old=[0,0,0] 
                    found=False
                    # vel 3d vector of [velocity , pogh , podw]
                R=LA.norm(point_bor_old)
                console.log(f"{point_bor=}")
                console.log(f"{point_bor_old=}")
                # console.log
                vel = [np.linalg.norm([val - point_bor_old[idx] for idx, val in enumerate(
                    point_bor)])/tvel, np.linalg.norm(dpoint_h), np.linalg.norm(dpoint_h), R]
                # vel=[((point_bor[0]-point_bor_old[0])^2 +(point_bor[1]-point_bor_old[1])^2 + (point_bor[2]-point_bor_old[2])^2)^0.5/tvel, np.linalg.norm(dpoint_h), np.linalg.norm(dpoint_h), R]
                
                if (np.isfinite(vel[0])):
                    found=True
                else:
                    CORNNOTFOUND=CORNNOTFOUND+1
                    found=False
                    # CASE DWELL TIME
                v_=p.convert(vel,et,found)
                acq.add_vel(v_)
                a=1

            if p.subsolar:  
                found=False
                try:
                    [x,y,z]=spice.subsol('Intercept', tar_, et, lc_, obs_)
                    point_ss=[x,y,z]
                    found=True
                except spice.NotFoundError as message:
                    SUBSOLARNOTFOUND=SUBSOLARNOTFOUND+1
                    point_ss= [0,0,0]
                    found=False
                except spice.SpiceSPKINSUFFDATA as message: 
                    SUBSOLARNOTFOUND=SUBSOLARNOTFOUND+1
                    point_ss=[0,0,0] 
                    found=False
                acq.add_subsolarp(point_ss)
                pconv=p.convert(point_ss,et,found)
                if (p.f_latlong):
                    acq.add_subsolar(pconv[0],pconv[1])


        Aquisitions.append(acq)
        if (net==1):
            elapsed = time.time() - t
            wprint('Wait '+timelog(elapsed*len(tl.t)))
        net=net+1
    
    return  Aquisitions,   BORENOTFOUND,    BOREINSUFFIC,    SBNANOTFOUND,    SBNAINSUFFIC,    CORNNOTFOUND,    CORNINSUFFIC



def convert_Acqusitions2CSVfile(Aquisitions,title_cols1,title_cols2,title_cols3,listprod,ins,first_ins,risINS):
    
    first_et=True
    
    # Start simulation
    for acq in Aquisitions:                                                                     # For each time
        
        risET=[]
        et=acq.time
        if (first_ins):
            if (first_et):
                title_cols1.extend(['Time'])
                title_cols2.extend(['ISOC'])
                title_cols3.extend(['[txt]'])                
                title_cols1.extend(['Time'])
                title_cols2.extend(['J2000'])
                title_cols3.extend(['[s]'])
                title_cols1.extend(['Time'])
                title_cols2.extend(['Norbit'])
                title_cols3.extend(['[#]'])
            risET.extend([spice.et2utc(et, 'ISOC', 6)])                
            risET.extend([str(et)])
            risET.extend([str(acq.norbit)])                

        for p in listprod:                                                              # For each products
           
            if p.boresight:  

                pconv=p.convert(acq.pbore,et,True)
                risET.extend(pconv)
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())

            if p.subnadiral:                                                            # CASE SUBNADIRAL
                #add results
                pconv=p.convert(acq.psubnad,et,True)
                risET.extend(pconv)  
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())

            if p.corners:                                                               # CASE CORNERS
                cp=acq.pcorners
                index=0
                for v in cp:
                    
                    converted=p.convert(v,et,True)
                    risET.extend(converted)
                    if (first_et):
                        title_cols1.extend(p.getInstr(ins))
                        title_cols2.extend(p.getNamesPost(str(index)))
                        title_cols3.extend(p.getLabels())
                        index=index+1
            if p.pog:                                                               # CASE DWELL TIME
                risET.append(acq.pog_h)
                risET.append(acq.pog_w)
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
            if p.swath:   
                risET.extend(acq.swath_vect)                                                          # CASE DWELL TIME
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                q=1

                    
            if p.vel:  
                risET.extend(acq.vel)
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())

            if p.subsolar:  
                pconv=p.convert(acq.subsolarp,et,True)
                risET.extend(pconv)
                if (first_et):
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
  
        first_et=False
        risINS.append(risET)
        a=1
    return risINS,title_cols1,title_cols2,title_cols3
