# import csv
import math
import time

# import geopandas as gpd
import numpy as np
import spiceypy as spice
from numpy import linalg as LA

# from rich.panel import Panel
# from shapely.geometry import Point, Polygon
from spiceypy.utils.exceptions import SpiceNOFRAMECONNECT, SpiceSPKINSUFFDATA

from SOIM.lib.classes import Aquisition, Product  #, listproducts
from SOIM.lib.console import console

# from SOIM.lib.IO_functions import writeShapeFile
from SOIM.lib.utility import (
    missing_attitude_error,
    wprint,
)


def timelog(num_sec):
    if (num_sec < 100):
        ris = f"{num_sec:.2f} s"
        return ris
    if (num_sec < 36000):
        ris = f"{num_sec/(60):.2f} m"
        return ris
    ris = f"{num_sec/(60*60):.2f} h"
    return ris 

def evalTimeline(tl,ins,FOVBoundaryVectors,listprod,Scenario, fr, Bor,vh_pix,vw_pix, *, sun_gm=None):
    

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
    SUBSOLARNOTFOUND=0
    
    
    # Start simulation
    Aquisitions=[]
    net=1

    pixel_height_ray = Bor + vh_pix
    pixel_width_ray = Bor + vw_pix
    products = sorted(listprod, key=lambda product: not (product.boresight or product.corners))
    if sun_gm is None and any(product.mta for product in products):
        sun_gm = solar_gravitational_parameter()
    
    it = 0
    while it < len(tl.t):

        et = tl.t[it]  
        TOBEADD=True                                                                 # For each time

        
        acq=Aquisition(ins,et)
        pixel_offsets = None
        velocity_inputs = None

        if (net==1):
            t = time.time()

        # Evaluate the geometry that derived products need before processing them.
        for p in products:

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
                except SpiceNOFRAMECONNECT as error:
                    raise missing_attitude_error(ins, fr, et) from error
                except SpiceSPKINSUFFDATA as message:
                    BOREINSUFFIC=BOREINSUFFIC+1
                    point_bor=[0,0,0] 
                    found=False
                if np.isnan(point_bor[0]):
                    TOBEADD=False
                    break

                acq.add_borep(point_bor)
                pconv=acq.surface_values(p, point_bor, found)
                acq.results[p] = pconv

                if (p.f_latlong):
                    acq.add_bore(pconv["latitude"], pconv["longitude"])
                if all(key in pconv for key in ("incidence", "phase", "emission")):
                    acq.add_ill_ise(
                        pconv["incidence"], pconv["phase"], pconv["emission"]
                    )
                if p.f_latlong and "incidence" in pconv and pconv["incidence"] > 90:
                    nextday_index = find_first_dayside_index_from_false(
                        tl.t, func_dayside, et, p, fr, Bor
                    )
                    it = nextday_index
                    TOBEADD=False
                    continue

                if p.f_naz:
                    acq.add_naz(pconv["north_azimuth"])

            if p.subnadiral:                                                            # CASE SUBNADIRAL
                found=False
                try:
                    [point, iep, v_ob2p]=spice.subpnt(metsbnd_, tar_, et, tfr_ , lc_, obs_)
                    found=True
                except spice.NotFoundError as message:
                    SBNANOTFOUND=SBNANOTFOUND+1
                    point= [0,0,0]  
                    found=False
                except SpiceSPKINSUFFDATA as message:
                    SBNAINSUFFIC=SBNAINSUFFIC+1
                    point=[0,0,0] 
                    found=False   
                #add results
                acq.add_subnp(point)
                pconv=acq.surface_values(p, point, found)
                acq.results[p] = pconv
                if p.f_latlong:
                    acq.add_subn(pconv["latitude"], pconv["longitude"])

            if (p.corners):                                                               # CASE CORNERS
                index=0
                lat=[]
                long=[]
                cpoints=[]
                acq.results[p] = {}
                for v in FOVBoundaryVectors:
                    found=False
                    try:
                        [point, iep, v_ob2p]=spice.sincpt(metsinc_, tar_, et, tfr_ , lc_, obs_, fr, v)
                        found=True
                    except spice.NotFoundError as message: 
                        CORNNOTFOUND=CORNNOTFOUND+1
                        point=[0,0,0] 
                        found=False
                    except SpiceNOFRAMECONNECT as error:
                        raise missing_attitude_error(ins, fr, et) from error
                    except SpiceSPKINSUFFDATA as message:
                        CORNINSUFFIC=CORNINSUFFIC+1; 
                        point=[0,0,0] 
                        found=False
                    #add results                                
                    converted=acq.surface_values(p, point, found)
                    acq.results[p][index] = converted
                    if p.f_latlong:
                        lat.append(converted["latitude"])
                        long.append(converted["longitude"])
                    cpoints.append(point)
                    index=index+1
                acq.add_corners(lat,long)
                acq.add_cornersp(cpoints)
            if p.f_swath:
                if not all(np.linalg.norm(point) for point in acq.pcorners) or not acq.pcorners:
                    acq.add_swaths(p.convert([], et, False))
                    continue
                # we assume
                #   3      -------> vw   0
                #                        ^
                #                        |vh
                #
                #   2                    1     

                #    1                   2
                #    ^
                #    |vh
                #
                #    0                     3

                #c0= cpoints[0]/R
                c0= cpoints[0]/np.linalg.norm(cpoints[0])
                c1= cpoints[1]/np.linalg.norm(cpoints[1])
                c2= cpoints[2]/np.linalg.norm(cpoints[2])
                c3= cpoints[3]/np.linalg.norm(cpoints[3])
                ang_h01=math.acos(np.inner(c0,c1))
                ang_w12=math.acos(np.inner(c1,c2))
                ang_h23=math.acos(np.inner(c2,c3))
                ang_w03=math.acos(np.inner(c0,c3))


                radius = np.mean(np.linalg.norm(cpoints, axis=1))
                ris=p.convert([0.5*(ang_h01+ang_h23),0.5*(ang_w12+ang_w03),radius],et,True)
                acq.add_swaths(ris)
            if (p.f_coverage):
                coverage_lat=np.max(acq.corners_lat)-np.min(acq.corners_lat)
                coverage_long=np.max(acq.corners_long)-np.min(acq.corners_long)
                acq.add_coverage(coverage_lat,coverage_long)




            if p.pog or p.vel or p.smearing:
                if pixel_offsets is None:
                    try:
                        point_h, _, _ = spice.sincpt(
                            metsinc_, tar_, et, tfr_, lc_, obs_, fr, pixel_height_ray
                        )
                        point_w, _, _ = spice.sincpt(
                            metsinc_, tar_, et, tfr_, lc_, obs_, fr, pixel_width_ray
                        )
                        pixel_offsets = (point_bor - point_h, point_bor - point_w, True)
                    except spice.NotFoundError:
                        CORNNOTFOUND += 1
                        pixel_offsets = ([0, 0, 0], [0, 0, 0], False)
                    except SpiceSPKINSUFFDATA:
                        CORNINSUFFIC += 1
                        pixel_offsets = ([0, 0, 0], [0, 0, 0], False)
                    except SpiceNOFRAMECONNECT as error:
                        raise missing_attitude_error(ins, fr, et) from error

                dpoint_h, dpoint_w, pixel_found = pixel_offsets
                if p.pog:
                    acq.add_pog(p.convert(dpoint_h, et, pixel_found),
                                p.convert(dpoint_w, et, pixel_found))

            if p.vel or p.smearing:
                if velocity_inputs is None:
                    tvel = 0.001
                    try:
                        point_bor_old, _, _ = spice.sincpt(
                            metsinc_, tar_, et - tvel, tfr_, lc_, obs_, fr, Bor
                        )
                    except spice.NotFoundError:
                        BORENOTFOUND += 1
                        point_bor_old = [0, 0, 0]
                    except SpiceSPKINSUFFDATA:
                        BOREINSUFFIC += 1
                        point_bor_old = [0, 0, 0]
                    except SpiceNOFRAMECONNECT as error:
                        raise missing_attitude_error(ins, fr, et - tvel) from error

                    velocity_inputs = [
                        np.linalg.norm([point - point_bor_old[i] for i, point in enumerate(point_bor)]) / tvel,
                        np.linalg.norm(dpoint_h),
                        LA.norm(point_bor_old),
                    ]
                    if not np.isfinite(velocity_inputs[0]):
                        CORNNOTFOUND += 1

                values = p.convert(velocity_inputs, et, np.isfinite(velocity_inputs[0]))
                if p.smearing:
                    acq.add_smearing(values)
                else:
                    acq.add_vel(values)

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
                except SpiceSPKINSUFFDATA as message:
                    SUBSOLARNOTFOUND=SUBSOLARNOTFOUND+1
                    point_ss=[0,0,0] 
                    found=False
                acq.add_subsolarp(point_ss)
                pconv=acq.surface_values(p, point_ss, found)
                acq.results[p] = pconv
                if p.f_latlong:
                    acq.add_subsolar(pconv["latitude"], pconv["longitude"])


            if (p.mta):
                acq.add_mta(mercury_true_anomaly(et, sun_gm=sun_gm))                 
        it=it+1



        if (TOBEADD):
            Aquisitions.append(acq)
        if (net==1):
            elapsed = time.time() - t
            wprint('Wait '+timelog(elapsed*len(tl.t)))
        net=net+1
    
    return  Aquisitions,   BORENOTFOUND,    BOREINSUFFIC,    SBNANOTFOUND,    SBNAINSUFFIC,    CORNNOTFOUND,    CORNINSUFFIC



def convert_Acqs2TabData(Aquisitions,title_cols1,title_cols2,title_cols3,listprod,ins,first_ins,risINS,REPORTPRODUCTS):

    n_instr=0
    n_names=0
    n_labels=0
    first_et=True
    START_CORNERS=-1 # column of the corner 0
    STEP_CORNERS=0
    column=0 # Column used
    # Start simulation
    print_c=[]
    print_s=[]
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
                print_c.extend([True])
                print_c.extend([True])
                print_c.extend([True])
                print_s.extend([True])
                print_s.extend([True])
                print_s.extend([True])

                column=column+3
            risET.extend([spice.et2utc(et, 'ISOC', 6)])                
            risET.extend([str(et)])
            risET.extend([str(acq.norbit)])

        if ((first_et)&(REPORTPRODUCTS)):
            console.print ("Products in convert_Acqs2TabData")
        
        for p in listprod:

            if ((first_et)&(REPORTPRODUCTS)):
                console.print(f">{p.name} {len(p.getInstr(ins))} {len(p.getNames())} {len(p.getLabels())}")
                n_instr+=len(p.getInstr(ins))
                n_names+=len(p.getNames())
                n_labels+=len(p.getLabels())                                                      # For each products
           
            if p.boresight:  

                pconv = (
                    acq.results[p] if p in acq.results
                    else acq.surface_values(p, acq.pbore)
                )
                risET.extend(p.surface_row(pconv))
                if (first_et):
                    column=column+len(p.surface_fields())
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)

            if p.subnadiral:                                                            # CASE SUBNADIRAL
                #add results
                pconv = (
                    acq.results[p] if p in acq.results
                    else acq.surface_values(p, acq.psubnad)
                )
                risET.extend(p.surface_row(pconv))
                if (first_et):
                    column=column+len(p.surface_fields())
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)


            if p.corners:                                                               # CASE CORNERS
                cp=acq.pcorners
                
                index=0
                for i, v in enumerate(cp):
                
                    converted = (
                        acq.results[p][i] if p in acq.results
                        else acq.surface_values(p, v)
                    )
                    risET.extend(p.surface_row(converted))
                                                                    
                    if (first_et):
                        if (START_CORNERS==-1):
                            START_CORNERS=column
                            STEP_CORNERS = len(p.surface_fields())

                        column=column+len(p.surface_fields())
                        title_cols1.extend(p.getInstr(ins))
                        title_cols2.extend(p.getNamesPost(str(index)))
                        title_cols3.extend(p.getLabels())
                        c,s=p.getPrintMode()
                        print_c.extend(c)
                        print_s.extend(s)
                        
                        index=index+1
                end4=0
                if '2' in p.mode:
                    for index, v in enumerate(cp):
                        converted = (
                            acq.results[p][index] if p in acq.results
                            else acq.surface_values(p, v)
                        )
                        risET.extend([converted["latitude"], converted["longitude"]])

                        if (first_et):
                            title_cols1.extend(p.getInstr(ins,True))
                            title_cols2.extend(p.getNamesPost("S"+str(index), True))
                            title_cols3.extend(p.getLabels(True))
                            c,s=p.getPrintMode(True)
                            print_c.extend(c)
                            print_s.extend(s)
                        if (index==1):
                            break
                    end2=0
                        

            if p.pog:                                                               # CASE DWELL TIME
                risET.extend(acq.pog_h)
                risET.extend(acq.pog_w)
                if (first_et):
                    column=column+2

                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)

            if p.f_swath:
                risET.extend(acq.swath_vect)                                                          # CASE DWELL TIME
                if (first_et):
                    column=column+len(acq.swath_vect)
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)

                    
            if p.vel:
                risET.extend(acq.vel)
                if (first_et):
                    column=column+len(acq.vel)
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)

            if p.smearing:
                risET.extend(acq.smearing)
                if (first_et):
                    column=column+len(acq.smearing)
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)


            if p.subsolar:  
                pconv = (
                    acq.results[p] if p in acq.results
                    else acq.surface_values(p, acq.subsolarp)
                )
                risET.extend(p.surface_row(pconv))
                if (first_et):
                    column=column+len(p.surface_fields())
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)
            if p.mta:

                risET.append(acq.mta)
                if (first_et):
                    column += len(p.getLabels())
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)
            if p.f_coverage:
                risET.append(acq.covLat)
                risET.append(acq.covLong)
                if (first_et):
                    column += len(p.getLabels())
                    title_cols1.extend(p.getInstr(ins))
                    title_cols2.extend(p.getNames())
                    title_cols3.extend(p.getLabels())
                    c,s=p.getPrintMode()
                    print_c.extend(c)
                    print_s.extend(s)
            q=1

        first_et=False
        risINS.append(risET)
    if (REPORTPRODUCTS):
        console.print(f"Total> { n_instr} {n_names} {n_labels}")
    return risINS,title_cols1,title_cols2,title_cols3,print_c,print_s,START_CORNERS,STEP_CORNERS



def solar_gravitational_parameter():
    try:
        return float(spice.bodvrd("SUN", "GM", 1)[1][0])
    except Exception:
        return 132712440041.9394


def mercury_true_anomaly(et: float, *, sun_gm=None) -> float:
    """Return Mercury's heliocentric true anomaly in degrees at ``et``."""
    state, _lt = spice.spkezr("MERCURY", et, "ECLIPJ2000", "NONE", "SUN")
    if sun_gm is None:
        sun_gm = solar_gravitational_parameter()
    elts = spice.oscltx(state, et, sun_gm)
    return math.degrees(elts[8]) % 360.0



def find_first_dayside_index_from_false(timeline, func_dayside, t0, P,frBor, Bor):
    t1=t0+138*60*3/4
    return  find_first_dayside_index(timeline, func_dayside, t0, t1,P,frBor, Bor)


def find_first_dayside_index(timeline, func_dayside, t0, t1,P,frBor, Bor):

    # Indici dei tempi che racchiudono la transizione
    i0 = np.searchsorted(timeline, t0)
    i1 = np.searchsorted(timeline, t1)

    # Ricerca binaria
    while i1 - i0 > 1:

        im = (i0 + i1) // 2

        if func_dayside(timeline[im],P,frBor, Bor):
            i1 = im
        else:
            i0 = im

    return i1

def func_dayside(et, P: Product,frBor, Bor):
     [point_bor, iep, v_ob2p]=spice.sincpt(P.metSic, P.tar, et, P.tfr , P.lc, P.obs, frBor, Bor)

     _, _, _, incidence, _= spice.ilumin(P.metSic, P.tar, et, P.tfr , P.lc, P.obs, point_bor )
     #console.print(f'DAY-NIGHT SIDE: Jumping to next orbit: current incidence {incidence*180/3.1415}'  )
     return (incidence<1.57079633)  #90° 