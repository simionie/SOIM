import csv
import time

import geopandas as gpd
import numpy as np
import spiceypy as spice
from rich.panel import Panel
from shapely.geometry import Point, Polygon

from SOIM.lib.classes import Aquisition, Product, Timeline, listproducts
from SOIM.lib.console import console
from SOIM.lib.utility import (appendHOR, eprint, lprint, print_dic, soimExit,
                              wprint)


def Verify_DarkSide(Timelines,Scenario,Products,SEC_OF_OVERSAMPLING):


    t0=time.time()
    metsinc_=Scenario["ShapeSinc"]
    metsbnd_=Scenario["ShapeSbnd"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("\n\n\n\n VERIFING DARKSIDE")
    it=0

    Timelines_DaySide=[]

    ntimeline=0
    for tl in Timelines:                                                                        # Run all the simulations
        console.rule(" Running timeline <"+str(it+1)+"> with Oversampling "+str(SEC_OF_OVERSAMPLING)+"[s]", style='green')

        first_ins=True
        for ins in tl.instr:  
            idinstr=Scenario['Instruments'][ins]
            lprint('# Starting  Instrument:'+ins+"->"+str(idinstr))
            samples=spice.gdpool('INS'+str(idinstr)+'_PIXEL_SAMPLES', 0, 1 )
            lines=spice.gdpool('INS'+str(idinstr)+'_PIXEL_LINES', 0, 1 )
            #Fake product to define incindence angle
            p=Product(idinstr, 'Boresight', 'LRIEP', '33888',False) 
            p.addScenario(Scenario)
            try:
                [fovshape_, fr, Bor, NumBoundaryV, FOVBoundaryVectors]=spice.getfov(idinstr,5) # Read FoV
                # we assume
                #   3      -------> vw   0
                #                        ^
                #                        |vh
                #
                #   2                    1 
                #
                #  where vh represent the line of the detector
                #        vw represent the line of the detector
            except spice.SpiceIDCODENOTFOUND as message:
                txt=f"""
                Spice ID INSTRUMENT CODE NOT FOUND in spice.getfov
                Correct Products or Timeline
                {message}
                """
                console.print(Panel(txt, title="ERROR",border_style="red",title_align="left"))
                # eprint("Spice ID INSTRUMENT CODE NOT FOUND in spice.getfov")
                # eprint("Correct Products or Timeline")
                # eprint(str(message))
                soimExit(error=True)
            BORENOTFOUND=0
            BOREINSUFFIC=0

            time_sampled=np.arange(tl.t[0],tl.t[-1],SEC_OF_OVERSAMPLING)
            lprint("# Number of acqusitiopns "+str(len(time_sampled)))
            ind=0
            # Start simulation
            starting_time=tl.t0_str
            stop_time=0 
            tstep=tl.dt
            INDAY=True
            first_et=True
            for et in time_sampled: # *123#                                                                     # For each time

                t = time.time()
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
                pconv=p.convert(point_bor,et,found)
                inc=pconv[3]
                #lprint("#  "+str(pconv[0])+" "+str(pconv[1])+" "+str(pconv[2])+" * "+str(pconv[3])+" "+str(pconv[4])+" "+str(pconv[5])+" ")
                if (first_et):
                    if (inc>=90):
                        INDAY=False
                    else:
                        INDAY=True
                        starting_time=spice.et2utc(et, 'ISOC', 6)

                if (inc>=90)&(INDAY):
                    INDAY=False
                    stop_time=spice.et2utc(et, 'ISOC', 6)
                    tln=Timeline(starting_time, stop_time, tstep, tl.instr)
                    Timelines_DaySide.append(tln)
                if (inc<90)&(1-INDAY):
                    starting_time=spice.et2utc(et, 'ISOC', 6)
                    stop_time=0
                    INDAY=True
                first_et=False
            if (INDAY):
                stop_time=spice.et2utc(time_sampled[-1], 'ISOC', 6)
                tln=Timeline(starting_time, stop_time, tstep, tl.instr)
                Timelines_DaySide.append(tln)

            if (BORENOTFOUND>0):
                wprint(':Spice NOT FOUND point in sincpt BORE ['+str(BORENOTFOUND)+']')
            if (BOREINSUFFIC>0):
                wprint(':Spice INSUFFICIENT EFF in sincpt BORE ['+str(BOREINSUFFIC)+']')
    
            lprint('# Ended  Instrument:'+ins+"->"+str(idinstr)+"\n\n\n")

            #End instrument---------------------------------- 
    lprint("Done")
    t_end=time.time()-t0
    lprint('Time required '+str(t_end)+'[s]')
    return Timelines_DaySide
    

