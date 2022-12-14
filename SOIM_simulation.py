from SOIM_starter import * 
import spiceypy as spice


def SOIM_simulation(Timelines,Scenario,Products):

    met_=Scenario["Shape"]
    tar_=Scenario["Target"]
    tfr_=Scenario["Target Frame"]
    lc_=Scenario["Light"]
    obs_=Scenario["Orbiter"]
    
    lprint("Run all timelines")
    it=0
    for tl in Timelines:
        lprint("############ Running timeline ["+str(it)+"]")
        tl.print()
        for et in tl.t:
            for p in Products:

                ins=p.instr                         #definition instrument list
                ins_list=[]
                if ins=="ALL":
                    for q in Scenario['Instruments']:
                        ins_list.append(q)
                else:
                    ins_list.append(ins)
                for ins in ins_list:
                    idinstr=Scenario['Instruments'][ins]
                    lprint(ins+"->"+str(idinstr))
                    try:
                        [fovshape_, fr, Bor, NumBoundaryV, FOVBoundaryVectors]=spice.getfov(idinstr,5)
                    except spice.SpiceIDCODENOTFOUND as message:
                        eprint("spice.getfov")
                        eprint(str(message))
                        exit()
                    try:
                        [point, iep, v_ob2p]=spice.sincpt(met_, tar_, et, tfr_ , lc_, obs_, fr, Bor)
                    except spice.NotFoundError as message:
                        lprint(str(message))
                    
            
        it=it+1
    lprint("end")
    


