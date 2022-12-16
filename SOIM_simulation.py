from SOIM_starter import * 
import spiceypy as spice


def listproducts(lookforins,Products):
    lp=[]
    for p_ in Products:
        if ((p_.instr== lookforins)|(p_.instr=='ALL')):
            lp.append(p_)
    return lp




def SOIM_simulation(Timelines,Scenario,Products):

    met_=Scenario["Shape"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("Run all timelines")
    it=0
    for tl in Timelines:
        lprint("############ Running timeline ["+str(it+1)+"]")
        tl.print()
        
        for ins in tl.instr:

            try:
                [fovshape_, fr, Bor, NumBoundaryV, FOVBoundaryVectors]=spice.getfov(idinstr,5)
            except spice.SpiceIDCODENOTFOUND as message:
                eprint("Spice ID INSTRUMENT CODE NOT FOUND in spice.getfov")
                eprint("Correct Products or Timeline")
                eprint(str(message))
                exit()

            
            listprod=listproducts(ins,Products)
            idinstr=Scenario['Instruments'][ins]
            lprint('Instrument:'+ins+"->"+str(idinstr))
            for p in listprod:
                lprint('   Required products:')
                p.print()
                for et in tl.t:
                    
                    try:
                        [point, iep, v_ob2p]=spice.sincpt(met_, tar_, et, tfr_ , lc_, obs_, fr, Bor)
                    except spice.NotFoundError as message:
                        wprint(str(et)+':Spice NOT FOUND point in sincpt')
                        point=0
                    
            
        it=it+1
    lprint("end")
    


