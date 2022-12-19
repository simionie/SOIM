from lib.classes import Product
from lib.utility import wprint, lprint, print_dic, eprint, soimExit
from lib.console import console
import spiceypy as spice
import time


def timelog(num_sec):
    if (num_sec < 100):
        ris = "{:.2f}".format(num_sec)+' s'
        return ris
    if (num_sec < 36000):
        ris = "{:.2f}".format(num_sec/(60))+' m'
        return ris
    ris = "{:.2f}".format(num_sec/(60*60))+' h'
    return ris 


def listproducts(lookforins,Products):
    lp=[]
    for p_ in Products:
        if ((p_.instr== lookforins)|(p_.instr=='ALL')):
            lp.append(p_)
    return lp




def SOIM_simulation(Timelines:list,Scenario,Products):

    met_=Scenario["Shape"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("Run all timelines")
    it=0

    
    for tl in Timelines:                                                                        # Run all the simulations
        lprint("#############################################################")
        lprint("################### Running timeline ["+str(it+1)+"]")
        lprint("#############################################################")
        tl.print()
        
        

        for ins in tl.instr:                                                                    # For all the instrument required
            listprod=listproducts(ins,Products)
            idinstr=Scenario['Instruments'][ins]
            try:
                [fovshape_, fr, Bor, NumBoundaryV, FOVBoundaryVectors]=spice.getfov(idinstr,5) # Read FoV
            except spice.SpiceIDCODENOTFOUND as message:
                eprint("Spice ID INSTRUMENT CODE NOT FOUND in spice.getfov")
                eprint("Correct Products or Timeline")
                eprint(str(message))
                soimExit(False)

            lprint('# Instrument:'+ins+"->"+str(idinstr))

            np=1
            lprint('   |Required products:')
            for p in listprod:                                                                  
                lprint('   |'+str(np)+'.')
                p.print(True)
                np=np+1
            lprint('   |End Required products for the instrument')
            lprint('Starting simulation')


            net=1
            for et in tl.t:                                                                     # For each time
                
                if (net==1):
                    t = time.time()

                ris=[]
                for p in listprod:                                                              # For each products

                    if p.boresight:                                                             # CASE BORESIGHT
                        found=False
                        try:
                            [point, iep, v_ob2p]=spice.sincpt(met_, tar_, et, tfr_ , lc_, obs_, fr, Bor)
                            found=True
                        except spice.NotFoundError as message:
                            wprint(str(et)+':Spice NOT FOUND point in sincpt BORE')
                            point= [0,0,0]
                            found=False
                        except spice.SpiceSPKINSUFFDATA as message: 
                            wprint(str(et)+':Spice INSUFFICIENT EFF in sincpt BORE')
                            point=[0,0,0] 
                            found=False
                        ris.append(p.convert(point,et,found))

                    if p.subnadiral:                                                            # CASE SUBNADIRAL
                        found=False
                        try:
                            [point, iep, v_ob2p]=spice.subpnt(met_, tar_, et, tfr_ , lc_, obs_)
                            found=True
                        except spice.NotFoundError as message:
                            wprint(str(et)+':Spice NOT FOUND point in sincpt SUBNAD')
                            point= [0,0,0]  
                            found=False
                        except spice.SpiceSPKINSUFFDATA as message: 
                            wprint(str(et)+':Spice INSUFFICIENT EFF in sincpt SUBNAD')
                            point=[0,0,0] 
                            found=False                            
                        ris.append(p.convert(point,et,found))  

                    if p.corners:                                                               # CASE CORNERS
                        
                        for v in FOVBoundaryVectors:
                            found=False
                            try:
                                [point, iep, v_ob2p]=spice.sincpt(met_, tar_, et, tfr_ , lc_, obs_, fr, v)
                                found=True
                            except spice.NotFoundError as message: 
                                wprint(str(et)+':Spice NOT FOUND point in sincpt CORNER')
                                point=[0,0,0] 
                                found=False
                            except spice.SpiceSPKINSUFFDATA as message: 
                                wprint(str(et)+':Spice INSUFFICIENT EFF in sincpt CORNER')
                                point=[0,0,0] 
                                found=False
                            ris.append(p.convert(point,et,found))
                          
                if (net==1):
                    elapsed = time.time() - t
                    wprint('Wait '+timelog(elapsed*len(tl.t)))
                net=net+1
                
                
            
        it=it+1
    lprint("end")
    


