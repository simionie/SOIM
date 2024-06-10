import csv
import math
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import spiceypy as spice
from rich.panel import Panel
from shapely.geometry import Point, Polygon

from SOIM.lib.classes import Aquisition, Product, listproducts
from SOIM.lib.console import console
from SOIM.lib.IO_functions import writeShapeFile
from SOIM.lib.simulator import (convert_Acqusitions2CSVfile, evalTimeline,
                                timelog)
from SOIM.lib.utility import (appendHOR, eprint, lprint, print_dic, soimExit,
                              wprint)


# Python program to convert a list to string
def list2str(l,tab):
 
    str1 = ""
    i=0
    for ele in l:
        if (i==0):
            str1 += ele
        else:
            str1 += tab+ele
        i=i+1
    return str1





#def listproducts(lookforins,Products):
#    lp=[]
#    for p_ in Products:
#        if ((p_.instr== lookforins)|(p_.instr=='ALL')):
#            lp.append(p_)
#    return lp




def SOIM_simulation(Timelines:list,Scenario,Products,PATH_RESULTS,MERGE_TIMELINES,SHAPE_FILE,log_file:Path):

    t0=time.time()
    metsinc_=Scenario["ShapeSinc"]
    metsbnd_=Scenario["ShapeSbnd"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("\n\n\n\nRun all timelines", log_file)
    it=0

    risTOT=[]
    AcquisitionsTOT=[]

    ntimeline=0
    firstimeline=True
    for tl in Timelines:                                                                        # Run all the simulations
        title_cols1=[] #output document first  row (instrument)
        title_cols2=[] #                second row (products)
        title_cols3=[] #                third  row (measurement unit)
        risTIME=[]     #output document ris
        with open(log_file,'a') as fl:
            fl.write(f"------- Running sub-timeline <{ntimeline+1}> ---------\n")
        

        tl.print(log_file)
        
        first_ins=True
        for ins in tl.instr:  
            risINS=[]                                                                      # For all the instrument required
            listprod=listproducts(ins,Products)
            idinstr=Scenario['Instruments'][ins]
            lprint('# Starting  Instrument:'+ins+"->"+str(idinstr), log_file)
            samples=spice.gdpool('INS'+str(idinstr)+'_PIXEL_SAMPLES', 0, 1 )
            lines=spice.gdpool('INS'+str(idinstr)+'_PIXEL_LINES', 0, 1 )

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
                vh_pix=(FOVBoundaryVectors[0]-FOVBoundaryVectors[1])/lines[0]
                vw_pix=(FOVBoundaryVectors[0]-FOVBoundaryVectors[3])/samples[0]

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
                # soimExit(error=True)


            n_p=1
            lprint('   |Required products:', log_file)
            for p in listprod:                                                                  
                lprint('   |'+str(n_p)+'.', log_file)
                p.print(compact=True, log_file=log_file)
                n_p=n_p+1
            lprint('   |End Required products for the instrument', log_file)
            lprint('   Analizing...', log_file)

            Aquisitions,   BORENOTFOUND,BOREINSUFFIC,SBNANOTFOUND,SBNAINSUFFIC,CORNNOTFOUND,CORNINSUFFIC=evalTimeline(tl,ins,FOVBoundaryVectors,listprod,Scenario, fr, Bor,vh_pix,vw_pix)
            
            risINS,title_cols1,title_cols2,title_cols3=convert_Acqusitions2CSVfile(Aquisitions,title_cols1,title_cols2,title_cols3,listprod,ins,first_ins,risINS)
            
            

            risTIME=appendHOR(risTIME,risINS)

            if (BORENOTFOUND>0):
                wprint(':Spice NOT FOUND point in sincpt BORE ['+str(BORENOTFOUND)+']')
            if (BOREINSUFFIC>0):
                wprint(':Spice INSUFFICIENT EFF in sincpt BORE ['+str(BOREINSUFFIC)+']')
            if (SBNANOTFOUND>0):
                wprint(':Spice NOT FOUND point in SUBNAD ['+str(SBNANOTFOUND)+']')
            if (SBNAINSUFFIC>0):
                wprint(':Spice INSUFFICIENT EFF in SUBNAD ['+str(SBNAINSUFFIC)+']')
            if (CORNNOTFOUND>0):
                wprint(':Spice NOT FOUND point in sincpt CORNER ['+str(CORNNOTFOUND)+']')
            if (CORNINSUFFIC>0):
                wprint(':Spice NOT FOUND point in sincpt CORNER ['+str(CORNINSUFFIC)+']')
            lprint('# Ended  Instrument:'+ins+"->" +
                   str(idinstr)+"\n\n\n", log_file)
            first_et=True
            first_ins=False
            #End instrument---------------------------------- 
        
        
        if (not MERGE_TIMELINES):
        #Save CSV file 
            namefile=Path(PATH_RESULTS).joinpath(f"timeline_{str(ntimeline)}_{tl.tostring()}.csv")
            tl.write2file(namefile,title_cols1,title_cols2,title_cols3,risTIME,log_file=log_file)
            

            if (SHAPE_FILE):        
                # Create an empty geopandas GeoDataFrame
                namefile = Path(PATH_RESULTS).joinpath(
                    f"timeline_{str(ntimeline)}_{tl.tostring()}.shp")
                writeShapeFile(Aquisitions, namefile, log_file)
        else:
            if (firstimeline):
                risTOT=risTIME
                AcquisitionsTOT=Aquisitions
                firstimeline=False
            else:
                risTOT.extend(risTIME)
                for acq in Aquisitions:
                    AcquisitionsTOT.append(acq)
        ntimeline=ntimeline+1
    AcquisitionsTOT_AM=antimeridian_claening(AcquisitionsTOT)  
       
    if (MERGE_TIMELINES):
        #Save CSV file 

        lprint("Simulation ended", log_file)
        t_end=time.time()-t0
        lprint('Time required '+str(t_end/60)+'[m]', log_file)

        namefile=Path(PATH_RESULTS).joinpath(f"tot_timeline.csv") 
        tl.write2file(namefile, title_cols1, title_cols2,
                      title_cols3, risTOT, log_file=log_file)
        # Create an empty geopandas GeoDataFrame
        if (SHAPE_FILE):   
            namefile = str(PATH_RESULTS).joinpath(f"tot_timeline.shp")
            writeShapeFile(AcquisitionsTOT_AM, namefile, log_file)



        it=it+1
    lprint("Simulation and save ended", log_file)
    t_end=time.time()-t0
    lprint("Time required "+str(t_end/60)+" m ", log_file)
    




def SOIM_simulationFOOTPRINT(Timelines:list,Scenario,Products,PATH_RESULTS,log_file):




    t0=time.time()
    metsinc_=Scenario["ShapeSinc"]
    metsbnd_=Scenario["ShapeSbnd"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("\n\n\n\nRun all timelines",log_file)
    it=0

    

    ntimeline=0
    for tl in Timelines:                                                                        # Run all the simulations
        title_cols1=[] #output document first  row (instrument)
        title_cols2=[] #                second row (products)
        title_cols3=[] #                third  row (measurement unit)
        risTIME=[]     #output document ris
        
        with open(log_file,'a') as fl:
            fl.write(f"Running timeline <{it+1}>")

        # console.rule(" Running timeline <"+str(it+1)+">", style='green')

        tl.print(log_file)
        
        first_ins=True
        for ins in tl.instr:  
            risINS=[]                                                                      # For all the instrument required
            listprod=listproducts(ins,Products)
            idinstr=Scenario['Instruments'][ins]
            lprint('# Starting  Instrument:'+ins+"->"+str(idinstr),log_file)
            samples=spice.gdpool('INS'+str(idinstr)+'_PIXEL_SAMPLES', 0, 1 )
            lines=spice.gdpool('INS'+str(idinstr)+'_PIXEL_LINES', 0, 1 )

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
                    vh_pix=(FOVBoundaryVectors[0]-FOVBoundaryVectors[1])/lines[0]
                    vw_pix=(FOVBoundaryVectors[0]-FOVBoundaryVectors[3])/samples[0]

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
                # soimExit(error=True)


            n_p=1
            n_p=1
            lprint('   |Required products:',log_file)
            for p in listprod:                                                                  
                lprint('   |'+str(n_p)+'.', log_file)
                p.print(True)
                n_p=n_p+1
            lprint('   |End Required products for the instrument', log_file)
            lprint('   Analizing...', log_file)



# START ACQUSIRION
# input ins et  *123#
 #output risET acq

            net=1

            BORENOTFOUND=0
            BOREINSUFFIC=0
            SBNANOTFOUND=0
            SBNAINSUFFIC=0
            CORNNOTFOUND=0
            CORNINSUFFIC=0
            

            first_et=True
            
            # Start simulation

            Acquisitions=[]


            for et in tl.t:                                                                     # For each time

                
                acq=Aquisition(ins,et)

                if (net==1):
                    t = time.time()

                risET=[]
                if (first_ins):
                    if (first_et):
                        title_cols1.extend(['Time'])
                        title_cols2.extend(['ISOC'])
                        title_cols3.extend(['[txt]'])                
                        title_cols1.extend(['Time'])
                        title_cols2.extend(['J2000'])
                        title_cols3.extend(['[s]'])
                    risET.extend([spice.et2utc(et, 'ISOC', 6)])                
                    risET.extend([str(et)]) 
                    risET.extend(str(acq.norbit))                  

                for p in listprod:                                                              # For each products

                    if p.corners:                                                               # CASE CORNERS
                        index=0
                        lat=[]
                        long=[]
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
                            risET.extend(converted)
                            lat.append(converted[0])
                            long.append(converted[1])

                            if (first_et):
                                title_cols1.extend(p.getInstr(ins))
                                title_cols2.extend(p.getNamesPost(str(index)))
                                title_cols3.extend(p.getLabels())
                            index=index+1
                        acq.add_corners(lat,long)
                        
                if (net==1):
                    elapsed = time.time() - t
                    wprint('Wait '+timelog(elapsed*len(tl.t)))
                net=net+1


# END ACQUSIRION
#
                risINS.append(risET)
                Acquisitions.append(acq)
                first_et=False

            risTIME=appendHOR(risTIME,risINS)

            if (BORENOTFOUND>0):
                wprint(':Spice NOT FOUND point in sincpt BORE ['+str(BORENOTFOUND)+']')
            if (BOREINSUFFIC>0):
                wprint(':Spice INSUFFICIENT EFF in sincpt BORE ['+str(BOREINSUFFIC)+']')
            if (SBNANOTFOUND>0):
                wprint(':Spice NOT FOUND point in SUBNAD ['+str(SBNANOTFOUND)+']')
            if (SBNAINSUFFIC>0):
                wprint(':Spice INSUFFICIENT EFF in SUBNAD ['+str(SBNAINSUFFIC)+']')
            if (CORNNOTFOUND>0):
                wprint(':Spice NOT FOUND point in sincpt CORNER ['+str(CORNNOTFOUND)+']')
            if (CORNINSUFFIC>0):
                wprint(':Spice NOT FOUND point in sincpt CORNER ['+str(CORNINSUFFIC)+']')
            lprint('# Ended  Instrument:'+ins+"->" +
                   str(idinstr)+"\n\n\n", log_file)
            first_et=True
            first_ins=False
            #End instrument---------------------------------- 
        
        
        
        #Save CSV file 
        namefile=str(PATH_RESULTS)+'\\timeline_'+str(ntimeline)+"_"+tl.tostring()+'.csv' 
        tl.write2file(namefile, title_cols1, title_cols2,
                      title_cols3, risTIME, log_file=log_file)
        ntimeline=ntimeline+1
                
        # Create an empty geopandas GeoDataFrame
        namefile=str(PATH_RESULTS)+'\\timeline_'+str(ntimeline)+"_"+tl.tostring()+'.shp' 
        Acquisitions_AM=antimeridian_claening(Acquisitions)  
        writeShapeFile(Acquisitions_AM,namefile,log_file)



        it=it+1
    lprint("Done", log_file)
    t_end=time.time()-t0
    lprint('Time required '+str(t_end)+'[s]', log_file)
    




def antimeridian_claening(AquisitionsTOT):
    a=1
    return AquisitionsTOT



