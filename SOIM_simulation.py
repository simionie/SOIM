from SOIM_starter import * 


def SOIM_simulation(Timelines,Scenario,Products):
    lprint("Run all timelines")
    it=0
    for tl in Timelines:
        lprint("############ Running timeline ["+str(it)+"]")
        tl.print()
        for t in tl.t:
            for p in Products:

                ins=p.instr                         #definition instrument list
                ins_list=[]
                if ins=="ALL":
                    for q in Scenario['Instruments']:
                        ins_list.append(q)
                else:
                    ins_list.append(ins)
                for ins in ins_list:
#                    print(ins)
            
        it=it+1
    lprint("end")
    


