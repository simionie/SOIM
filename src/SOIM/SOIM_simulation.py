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
from SOIM.lib.simulator import (convert_Acqs2TabData, evalTimeline,
                                timelog)
from SOIM.lib.utility import MSG, eprint, lprint, print_dic, wprint, soimExit, appendHOR
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




def SOIM_simulation(Timelines:list,Scenario,Products,PATH_RESULTS,MERGE_TIMELINES,SHAPE_FILE,ANTI_MERIDAN,log_file:Path):

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
        for ins in tl.instr:  # For all the instrument required
            risINS=[]              
            console.print("Evaluating instrument: "+ins)
                                                                    
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
            
            risINS,title_cols1,title_cols2,title_cols3,START_CORNERS,STEP_CORNERS=convert_Acqs2TabData(Aquisitions,title_cols1,title_cols2,title_cols3,listprod,ins,first_ins,risINS)
            
            

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
            console.print(f"{MSG.INFO} Writing CSV file")
            tl.write2file(namefile,title_cols1,title_cols2,title_cols3,risTIME,log_file=log_file)
            

            if (SHAPE_FILE):        
                # Create an empty geopandas GeoDataFrame
                console.print(f"{MSG.INFO} Writing SHP file")
                namefile = Path(PATH_RESULTS).joinpath(
                    f"timeline_{str(ntimeline)}_{tl.tostring()}.shp")
                writeShapeFile(namefile,title_cols1,title_cols2,title_cols3,risTIME,START_CORNERS,STEP_CORNERS,log_file=log_file)
              #  writeShapeFile(Aquisitions, namefile,listprod,log_file)
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



    if (ANTI_MERIDAN):
        AcquisitionsTOT_FIN=antimeridian_claening(AcquisitionsTOT)  
    else:
        AcquisitionsTOT_FIN=AcquisitionsTOT
       
    if (MERGE_TIMELINES):
        #Save CSV file 

        lprint("Simulation ended", log_file)
        console.print(f"{MSG.INFO} Simlation ENDED")
        t_end=time.time()-t0
        lprint('Time required '+str(t_end/60)+'[m]', log_file)
        console.print(f"{MSG.INFO} Writing tot_timeline.csv")
        
        namefile=Path(PATH_RESULTS).joinpath(f"tot_timeline.csv") 
        tl.write2file(namefile, title_cols1, title_cols2,
                      title_cols3, risTOT, log_file=log_file)
        # Create an empty geopandas GeoDataFrame
        if (SHAPE_FILE):   
            console.print(f"{MSG.INFO} Writing tot_timeline.shp")
            namefile = Path(PATH_RESULTS).joinpath(f"tot_timeline.shp")
            writeShapeFile(namefile, title_cols1, title_cols2,title_cols3, risTOT,START_CORNERS,STEP_CORNERS, log_file=log_file)



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
                #Correct antimeridian *123#
                for acq_ in acqs:
                    acqs=correct_antimer(acq)

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





#Correct antimeridian *123#
def correct_antimer(acq): 
    # Input
    th=40 
    thLAT=80
    l=acq.corners_long
    L=acq.corners_lat
    acq1=acq.clone()
    ris, changed=duplicate_in_case_of_meridian(l,L)
    if (changed):
        lprint('Duplicated')
        ris1_,changed1=extends_in_case_of_poles(ris(0).l,ris(0).L,thLAT,ris(0).l0,ris(0).L0,ris(0).l1,ris(0).L1)
        ris2_,changed2=extends_in_case_of_poles(ris(1).l,ris(1).L,thLAT,ris(1).l0,ris(1).L0,ris(1).l1,ris(1).L1)
        acq1.add_corners(ris1_.L,ris1_.l)
        acq2=acq.clone()
        acq2.add_corners(ris2_.L,ris2_.l)
        ris[0]=acq1
        ris[1]=acq2
        






        if (changed1):                   lprint('   1: Extended')
        if (changed2):                   lprint('   2: Extended')

    else:
        ris_Ll, changed  =extends_in_case_of_poles(ris(0).l,ris(0).L,thLAT,ris.l0,ris.L0,ris.l1,ris.L1)
        acq1.add_corners(ris_Ll.L,ris_Ll.l)
        ris[0]=acq1
        if (changed):                    lprint('Extended')
    return ris


#%% ---------------------------------------------------------------------------------------duplicate_in_case_of_meridian
#Consider 4 elements lat long in l(long)e L (lat)
# define if meridian issue
# return a list of data which could be:
#
# ris(1)
#        ris(1).l (same as previous) [deg]
#        ris(1).L (same as previous) [deg]
#        ris(1).l0 (1th point  as previous) [deg]
#        ris(1).L0 (1th point  as previous) [deg]
#
# in case of no changes or:
#
# ris(1)
#        ris(1).l [deg]
#        ris(1).L [deg]
#        ris(1).l0 (1th point  as previous) [deg]
#        ris(1).L0 (1th point  as previous) [deg]
# ris(2)
#        ris(2).l [deg]
#        ris(2).L [deg]
#        ris(2).l0 (1th point  as previous) [deg]
#        ris(2).L0 (1th point  as previous) [deg]


def duplicate_in_case_of_meridian(l,L):

    s=1; #id second verted 

    ris(0).l=l;        ris(0).L=L
    ris(0).l0=l(0);    ris(0).L0=L(0)
    ris(0).l1=l(s);    ris(0).L1=L(s)
    changed=false

    torad=pi/180
    isexternal, x, y, SIGN =consider_poles(L*torad,l*torad,80*torad)

    if (isexternal):
        x=cos(L*torad)*sin(l*torad)
        y=cos(L*torad)*cos(l*torad)
        z=sin(L*torad)
        X=[x,y,z]; X=X.reshape(3,1)
        inters=false
        cutted=[]
        Xsol=[]
        for k in range(0, 3):
            j=k+1
            if (j==4):
                j=0
            end
            # From equation Y=X(:,k)+lambda*[X(:,j)-X(:,k)]
            l0=-X(1,k)/(X(1,j)-X(1,k));  # intersezione su x=0;
            y0=X(2,k)+l0*(X(2,j)-X(2,k))
            if ((l0>0) and (l0<1) and (y0<0)):
                inters=true;  # generate intersection
                cutted=np.vstack((cutted,[k,j])) # indici degli intersecati
                Xsol=np.vstack((Xsol,X[:,k]+l0*(X[:,j]-X[:,k]))) # cordinate di intersezione
 
        
        if (inters):
            # CASE A: 2 intersect consecutivi (1 spigolo rimane tagliato fuori)
            if (cutted(0,1)==cutted(1,0))|(cutted(0,0)==cutted(1,1)):  
                if (cutted(0,1)==cutted(1,0)):
                    Xnew1=[Xsol[:,1],Xsol[:,0],X[:,cutted(0,1)],Xsol[:,1]]; # triangolo tagliato fuori
                    next=cutted(1,1)+1
                    if (next>3):
                        next=0
                    end
                    Xnew2=[Xsol[:,1],X[:,cutted(1,1)],X[:,next],X[:,cutted(0,0)],Xsol[:,0]]; #resto del poligono
                else:
                    Xnew1=[Xsol[:,1],Xsol[:,0],X[:,cutted(0,0)],Xsol[:,1]]; #triangolo tagliato fuori
                    prev=cutted(1,0)-1
                    if (prev==-1):
                        prev=0
                    Xnew2=[Xsol[:,1],X[:,cutted(1,0)],X[:,prev],X[:,cutted(0,1)],Xsol[:,0]]; #resto del poligono

                    
                l1New=np.arctan2(Xnew1[0, :], Xnew1[1, :])/torad
                l2New=np.arctan2(Xnew2[0, :], Xnew2[1, :])/torad
                if (l1New(2)<0):
                    l1New[1,3,0]=-180
                    l2New[:len(l2New)]=180
                else:
                    l1New[1,3,0]=180
                    l2New[:len(l2New)]=-180
                
                L1New=SIGN*acos(Xnew1[1, :]/cos(l1New*torad))/torad
                L2New=SIGN*acos(Xnew2[1, :]/cos(l2New*torad0))/torad
                tf1 = ispolycw(l1New,L1New)
                if (not tf1):
                    l1New[:len(l1New)]=l1New[::-1] 
                    L1New[:len(L1New)]=L1New[::-1] 

                tf2 = ispolycw(l2New,L2New)
                if (not tf2):
                    l2New[:len(l2New)]=l2New[::-1] 
                    L2New[:len(l2New)]=L2New[::-1] 

                # Saving
                ris(0).l=l1New;                ris(0).L=L1New
                ris(0).l0=l(0);                ris(0).L0=L(0)
                ris(0).l1=l(s);                ris(0).L1=L(s)
                ris(1).l=l2New;                ris(1).L=L2New
                ris(1).l0=l(0);                ris(1).L0=L(0)
                ris(1).l1=l(s);                ris(1).L1=L(s)
                changed=true
            # CASE B: 2 intersect non consecutivi (1 lato rimane tagliato fuori)
            else:
                Xnew1=[Xsol[:,0],X[:,cutted(0,0)],X[:,cutted(1,1)],Xsol[:,1],Xsol[:,0]]
                Xnew2=[Xsol[:,0],X[:,cutted(1,0)],X[:,cutted(0,1)],Xsol[:,0],Xsol[:,1]]
                l1New=np.arctan2(Xnew1[0,:],Xnew1[1,:])/torad
                l2New=np.arctan2(Xnew2[0,:],Xnew2[1,:])/torad
                if (l1New(1)<0):
                    l1New[0,3,4]=-180
                    l2New[0,3,4]=180
                else:
                    l1New[0,3,3]=180
                    l2New[0,3,3]=-180

                L1New=SIGN*acos(Xnew1[1,:]/cos(l1New*torad))/torad;
                L2New=SIGN*acos(Xnew2[1,:]/cos(l2New*torad))/torad;
                tf1 = ispolycw(l1New,L1New)
                if (not tf1):
                    l1New[:len(l1New)]=l1New[::-1]
                    L1New[:len(L1New)]=L1New[::-1]


                tf2 = ispolycw(l2New,L2New);
                if (not tf2):
                    l2New[:len(l2New)]=l2New[::-1]
                    L2New[:len(L2New)]=L2New[::-1]
                #Saving
                ris(0).l=l1New;                ris(0).L=L1New;
                ris(0).l0=l(0);                ris(0).L0=L(0);
                ris(0).l1=l(s);                ris(0).L1=L(s);
                ris(1).l=l2New;                ris(1).L=L2New;
                ris(1).l0=l(0);                ris(1).L0=L(0);
                ris(1).l1=l(s);                ris(1).L1=L(s);
                changed=true
    return ris,changed



# ---------------------------------------------------------------------------------------extends_in_case_of_poles
#
#Consider 4 elements lat long in l(long)e L (lat)              MATLAB CONVENTION IN ALL THE COMMENTS
# define if pole issue
# return a list of data which could be:

# ris(1)
# %       ris(1).l (same as previous) [deg]
# %       ris(1).L (same as previous) [deg]
# %       ris(1).l0 (1th point  as previous) [deg]
# %       ris(1).L0 (1th point  as previous) [deg]

# in case of no changes or:

# ris(1)
# %       ris(1).l [deg] (longer vector)
# %       ris(1).L [deg] (longer vector)
# %       ris(1).l0 (1th point  as previous) [deg]
# %       ris(1).L0 (1th point  as previous) [deg]
# ris(1).l0 and ris(1).L0 can be imposed using all the input 


def extends_in_case_of_poles(l,L,thLAT,l0,L0,l1,L1):

    s=1

    ris(0).l=l
    ris(0).L=L
    if (nargin<8):
        ris(0).l0=l(0)
        ris(0).L0=L(0)
        ris(0).l1=l(s)
        ris(0).L1=L(s)
    else:
        ris(0).l0=l0
        ris(0).L0=L0
        ris(0).l1=l1
        ris(0).L1=L1

    changed=false
    torad=pi/180

    Lr=L*torad
    lr=l*torad

    npoints=len(Lr)
    
    if (npoints==4) :
        isexternal,x,y,SIGN=consider_poles4(Lr,lr,thLAT*torad)
        tbc = np.array([[0,1], [1,2], [2,3], [3,0]], np.int32)
    else:
        isexternal,x,y,SIGN=consider_poles5(Lr,lr,thLAT*torad)
        tbc = np.array([[0,1], [1,2], [2,3], [3,4],[4,0]], np.int32)

        if (not isexternal): # entrambi esterni
            changed=true

            # dei punti volgio trovare quello che ha un intersezione con
            # x=0 e y<0
            # xy=[x(1);y(1)]+lambda*([x(2);y(2)]-[x(1);y(1)])  EQ 1
            # x=0 -> lambda=-x(1)/(x(2)-x(1))
            # lambda tra 0 e 1

            int_p=NaN; # indici 1234 dei due punti che si intersecano col meridiano
            int_l=NaN; # lambda di EQ1 
            int_y=NaN; # coordinate y dell'intersezione
            int_k=NaN; # k di tbc
            for k in range(0,npoints-1):
                p=tbc[k,:]
                lambda_=-x(p(0))/(x(p(1))-x(p(0)))
                yn=y(p(0))-x(p(0))*(y(p(1))-y(p(0)))/(x(p(1))-x(p(0)))
                if ((lambda_<1) and (lambda_>0) and yn<0):
                    int_p=p;
                    int_l=lambda_;
                    int_y=yn;
                    int_k=k;

            # caso in cui un lato sia sul meridiano , risulta lmbda inf
            if (1-isfinite(lambda_)):
                change=false
                return
            if ((len(int_p)==1) and (isnan(int_p))):
                change=false;
                return


            int_x=x(int_p(0))+int_l*(x(int_p(1))-x(int_p(0))); # coordinate x dell'intersezione

            deltar=0.0001
            N_ang=10
            ang=(2*pi*range(0,N_ang)/N_ang)-pi
            if (SIGN<0):
               ang=ang[::-1]

            xc=deltar*sin(ang)
            yc=deltar*cos(ang)

            #  1-int            2:5-rect                      6-int   7:end limits   
            x1=[int_x,x(tbc(range(int_k,len(tbc)),1)),x(tbc(range(1,(int_k-1)),1)),int_x,xc]
            y1=[int_y,y(tbc(range(int_k,len(tbc)),1)),y(tbc(range(1,(int_k-1)),1)),int_y,yc]


            l2=np.atan2(x1,y1)/torad
            l2[0]=abs(l2(0))*sign(l2(1))
            l2[5]=abs(l2(5))*sign(l2(4))
            L2=SIGN*acos(y1/cos(l2*torad))/torad
            L2[range(6,len(L))]=SIGN*90

            tf2 = ispolycw(l2,L2)
            if (not tf2):
                l2[:len(l2)]=l2[::-1]
                L2[:len(L2)]=L2[::-1]

            ris(0).l=l2
            ris(0).L=L2
            ris(0).l0=ris(0).l0
            ris(0).L0=ris(0).L0
            ris(0).l1=ris(0).l1
            ris(0).L1=ris(0).L1
    return ris,changed



## CONSIDER POLES DIFFERRENT VERSIONS



##-------------------------------------------------CONSIDER_POLES
# Conside the frame defined by the four point 
# L,l (Lats e longs) 1x4 in rad
# return if the poles are external to the frame
# It ignores all Latitudes >thLAT <-thLAT

def consider_poles(L,l,thLAT):
  isexternal=false
  x=[]
  y=[]
  SIGN=sign(mean(L*180/pi))
  if any((L<-thLAT) or (L>thLAT)):
    x=cos(L)*sin(l);
    y=cos(L)*cos(l);
    # Area definition
    At1_=area_tri(x([0,1,2]),y([0,1,2]));
    At1p_=area_triangle_and_point(x([0,1,2]),y([0,1,2]),0,0);
    At2_=area_tri(x([2,3,0]),y([2,3,0]));
    At2p_=area_triangle_and_point(x([2,3,0]),y([2,3,0]),0,0);
    isexternal=(((At1p_-At1_)>1e-10) and ((At2p_-At2_)>1e-10)); # entrambi esterni nuemric error
  else:
    isexternal=true
    return isexternal,x,y,SIGN



##-------------------------------------------------CONSIDER_POLES4
# Conside the frame defined by the four point 
# L,l (Lats e longs) 1x4 in rad
# return if the poles are external to the frame
# It ignores all Latitudes >thLAT <-thLAT
def consider_poles4(L,l,thLAT):
    isexternal=false;
    x=[];
    y=[];
    SIGN=sign(mean(L*180/pi))
    if any((L<-thLAT) or (L>thLAT)):
        
        x=cos(L)*sin(l);
        y=cos(L)*cos(l);
        # Area definition
        At1_=area_tri(x([0,1,2]),y([0,1,2]))
        At1p_=area_triangle_and_point(x([0,1,2]),y([0,1,2]),0,0)
        At2_=area_tri(x([2,3,0]),y([2,3,0]))
        At2p_=area_triangle_and_point(x([2,3,0]),y([2,3,0]),0,0)

        isexternal=(((At1p_-At1_)>1e-10) and ((At2p_-At2_)>1e-10)) # entrambi esterni nuemric error
    else:
        isexternal=true;
    
    return isexternal,x,y,SIGN


##-------------------------------------------------CONSIDER_POLES5
# Conside the frame defined by the five point 
# L,l (Lats e longs) 1x5 in rad
# return if the poles are external to the frame
# It ignores all Latitudes >thLAT <-thLAT
def consider_poles5(L,l,thLAT):


    isexternal1,x1,y1,SIGN1=consider_poles4(L([0,1,2,3]),l([0,1,2,3]),thLAT);
    isexternal2,x2,y2,SIGN2=consider_poles4(L([0,1,3,4]),l([0,1,3,4]),thLAT);
    
    isexternal=(isexternal1 and isexternal2);
    x=cos(L)*sin(l);
    y=cos(L)*cos(l);
    SIGN=sign(mean(L*180/pi));
    return isexternal,x,y,SIGN


## OTHER FUNCTIONS
# -----------------------------------------------------------AREA



def area_tri(x,y):
    A=abs(det(np.hstack(x,y,np.vstack(1,1,1))))/2;
    return A

def area_triangle_and_point(x,y,x0,y0):
    A=0;
    tbc=np.hstack([0,1], 
         [1,2],
         [2,0])
    for i in range(1,3):
        p=tbc[i,:];
        A1=area_tri([x(p(1)),x(p(2)),x0],[y(p(1)),y(p(2)),y0]);
        A=A+A1;
    return A


# -----------------------------------------------------------CLOCKWISE

def ispolycw(x, y):
    #ISPOLYCW True if polygon vertices are in clockwise order
    #
    #   TF = ISPOLYCW(X, Y) returns true if the polygonal contour vertices 
    #   represented by X and Y are ordered in the clockwise direction.  X and Y
    #   are numeric vectors with the same number of elements.
    #
    #   Alternatively, X and Y can contain multiple contours, either in
    #   NaN-separated vector form or in cell array form.  In that case,
    #   ISPOLYCW returns a logical array containing one true or false value
    #   per contour.
    #
    #   ISPOLYCW always returns true for polygonal contours containing two or
    #   fewer vertices.
    #
    #   Vertex ordering is not well defined for self-intersecting polygonal
    #   contours (e.g., "bowties"), but ISPOLYCW uses a signed area test which
    #   is robust with respect to self-intersection defects localized to a few
    #   vertices near the edge of a relatively large polygon.
    #
    #   Class Support
    #   -------------
    #   X and Y may be any numeric class.
    #
    #   Example
    #   -------
    #   Orientation of a square:
    #
    #       x = [0 1 1 0 0];
    #       y = [0 0 1 1 0];
    #       ispolycw(x, y)                     % Returns 0
    #       ispolycw(fliplr(x), fliplr(y))     % Returns 1
    #
    #   See also POLY2CW, POLY2CCW, POLYSHAPE
    
    if isempty(x):
       tf = true
    else:

        sum = 0.0

        x0=x(len(x)-1)
        y0=x(len(y)-1)
        for i in range (0,len(x)):
            x1=x(i)
            y1=y(i)
            sum += (v2.X - v1.X) * (v2.Y + v1.Y);
            x0=x1
            y0=y1
        tf=(sum>0)
    return tf

