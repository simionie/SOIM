
import csv
import math

import numpy as np
import spiceypy as spice
from rich.table import Table

from SOIM.lib.console import console
from SOIM.lib.utility import eprint, lprint, print_dic, wprint


#%% Classes
class instr:
    nameFk = ""
    naifID = 0

    def __init__(self, nameFk_, naifID_):
        self.nameFk = nameFk_
        self.naifID = naifID_


class Aquisition:
    instr = ""
    time=0
    # 3D points
    pbore=[]
    pcorners=[]
    psubnad=[]
    
    # 3D points coordinates
    boresight_latlong = []
    corners_lat = []
    corners_long = []
    subnad = []



    pog_h = 0
    pog_w = 0
    vel = 0
    ill = []
    norbit=0
    def __init__(self, instr_,time_):
        self.instr=instr_
        self.time=time_
        self.norbit=epoch2orbs(time_)
        a=1
    def add_borep(self,pbore_):
        self.pbore=pbore_
    def add_bore(self,lat,long):
        self.boresight_latlong.append(lat)
        self.boresight_latlong.append(long)
    def add_subnp(self,ps):
        self.psubnad=ps
    def add_subn(self,lat,long):
        self.subnad.append(lat)
        self.subnad.append(long)
    def add_cornersp(self,a_ps):
        self.pcorners=a_ps
    def add_corners(self,lat,long):
        self.corners_lat=lat
        self.corners_long=long
    def add_pog(self,pog):
        self.pog_h=pog
        self.pog_w=pog
    def add_pog(self,pog_h,pog_w):
        self.pog_h=pog_h
        self.pog_w=pog_w
    def add_swaths(self,swvect):
        self.swath_vect=swvect
    def add_vel(self,vel):
        self.vel=vel
    def add_ill(self,inc,sol,emi):
        self.ill=[inc,sol,emi]
    def add_subsolar(self,lat,long):
        self.ss_lat=lat
        self.ss_long=long
    def add_subsolarp(self,ss_p):
        self.subsolarp=ss_p
    def get_foot(self):
        return [(self.corners_lat[0], self.corners_long[0]), (self.corners_lat[1], self.corners_long[1]), (self.corners_lat[2], self.corners_long[2]), (self.corners_lat[3], self.corners_long[3])] 
    def get_foot_longlat(self):
        return [(self.corners_long[0], self.corners_lat[0]), (self.corners_long[1], self.corners_lat[1]), (self.corners_long[2], self.corners_lat[2]), (self.corners_long[3], self.corners_lat[3])] 
    def has_foot(self):
        return len(self.corners_lat)>0
        

        



class Product:
    instr = ""
    name = ""
    mode = ""
    format = ""
    boresight = False
    corners = False
    subnadiral = False
    subsolar = False
    pog = False
    vel = False
    swath = False
    printCSV = False
    #formats
    f_latlong = False
    f_ray = False
    f_ill = False
    f_x = False
    f_inc = False
    f_emi = False
    f_pha = False



    met = ''
    tar = ''
    tfr = ''
    lc = ''
    obs = ''

    def __init__(self, instr_, name_, mode_, format_,printCSV_=True):
        self.instr = instr_
        self.name = name_
        self.mode = mode_
        self.format = format_
        if len(mode_) != len(format_):
            eprint("Error in definition of product:")
            eprint("  "+instr_+":"+name_)
            eprint("Check Product file")
            eprint("Formats not coherent with Mode (they should have the same length)")
            exit()
        fixed=False
        if ((self.name == 'boresight') | (self.name == 'Boresight') | (self.name == 'BORESIGHT')):
            self.name='Bore'
            self.boresight = True
            fixed=True

        if ((self.name == 'subnadiral') | (self.name == 'Subnadiral') | (self.name == 'SUBNADIRAL')):
            self.name='SubNd'
            self.subnadiral = True
            fixed=True

        if ((self.name == 'corners') | (self.name == 'Corners') | (self.name == 'CORNERS')):
            self.name='Corners'
            self.corners = True
            fixed=True

        if ((self.name == 'pog') | (self.name == 'Pog') | (self.name == 'POG')| (self.name == 'PoG')):
            self.name='PoG'
            self.pog = True      
            fixed=True
      
        if ((self.name == 'VelBor') | (self.name == 'velbor') | (self.name == 'VELBOR')):
            self.name='Vel_on_bore'
            self.vel = True         
            fixed=True
   
        if ((self.name == 'Swath') | (self.name == 'swath') | (self.name == 'SWATH')):
            self.name='Swath'
            self.swath = True 
            fixed=True
        if ((self.name == 'Subsolar') | (self.name == 'subsolar') | (self.name == 'SubSolar')):
            self.name='Subsolar'
            self.subsolar = True 
            fixed=True            
        #if (not fixed):
        #    eprint('Error in productfile')
        #    eprint(self.name+' not recognized as a product')
        #    exit(-1)


        if 'L' in mode_:
            f_latlong = True
        if 'R' in mode_:
            f_ray = True
        if 'I' in mode_:
            f_ill = True
        if 'X' in mode_:
            f_x = True
        if 'I' in mode_:
            f_inc = True
        if 'E' in mode_:
            f_emi = True
        if 'P' in mode_:
            f_pha = True
        self.printCSV=printCSV_

    def addScenario(self, s):
        self.metSic  = s["ShapeSinc"]
        self.metSbnd = s["ShapeSbnd"]
        self.tar = s["Target"]
        self.tfr = s["Target Frame"]
        self.lc = s["Light"]
        self.obs = s["Orbiter"]

#   in case return lat long
    def convert(self, p, et=0, found=True):
        ris = []
        for c in self.mode:
            if ((c == 'L') | (c == 'R')):   #Lat Long and Ray
                if (found):
                    [ray,  long ,lat] = spice.reclat(p)
                    long=math.degrees(long)
                    lat=math.degrees(lat)
            if (c == 'L'):                  #Lat Long 
                if (found):
                    ris.append(lat)
                    ris.append(long)
                else:
                    ris.append(np.nan)
                    ris.append(np.nan)

            if (c == 'R'):                  #Ray
                if (found):
                    ris.append(ray)
                else:
                    ris.append(np.nan)
            if (c == 'D'):                  #Distance vs Observer 
                if (found):
                    #define position of obs respect target
                    p_obs = spice.spkpos(self.obs, et, self.tfr,self.lc,self.tar) 
                    dist = np.linalg.norm(p-p_obs[0])
                    ris.append(dist)
                else:
                    ris.append(np.nan)
            if (c == 'S'):                  #Distance vs Observer 
                if (found):
                    #define position of sun respect target
                    p_obs = spice.spkpos('SUN', et, self.tfr,self.lc,self.tar) 
                    dist = np.linalg.norm(p-p_obs[0])
                    ris.append(dist)
                else:
                    ris.append(np.nan)




            if (c == 'X'):                  #3D coordinates xyz 

                if (found):
                    ris.append(p[0])
                    ris.append(p[1])
                    ris.append(p[2])
                else:
                    ris.append(np.nan)
                    ris.append(np.nan)
                    ris.append(np.nan)

            if ((c == 'I') | (c == 'E') | (c == 'P')): #Emission hase angle 
                if (found):
                    [pha, inc, emi] = spice.illum(self.tar, et, self.lc, self.obs, p)
                    pha=math.degrees(pha)
                    inc=math.degrees(inc)
                    emi=math.degrees(emi)
                    


            if (c == 'I'):
                if (found):
                    ris.append(inc)
                else:
                    ris.append(np.nan)
            if c == 'E':
                if (found):
                    ris.append(emi)
                else:
                    ris.append(np.nan)
            if c == 'P':
                if (found):
                    ris.append(pha)
                else:
                    ris.append(np.nan)
            
            # Caso pog or vel
            if (c == 'k'):                      #km for pog or km/s for velocity
                if (not self.pog)&(not self.vel):
                    eprint("Mode [k='km' or 'km/s'] can be used only for pog or vel product")
                    exit()                    
                if (found):
                    if (self.pog):
                        ris.append(np.linalg.norm(p)/1000)
                    if (self.vel):
                        ris.append(p[0])
                    if (self.swath):
                        ris.append(p[0]*p[2])                         
                        ris.append(p[1]*p[2])                         

                else:
                    ris.append(np.nan)
            if (c == 'm'):                      #m for pog or m/s for velocity
                if (not self.pog)&(not self.vel)&(not self.swath):
                    eprint("Mode [m='m' or 'mm/s'] can be used only for pog or vel swath product")
                    exit()                    
                if (found):
                    if (self.pog):
                        ris.append(np.linalg.norm(p))
                    if (self.vel):
                        ris.append(p[0])
                    if (self.swath):
                        #radh radw r
                        ris.append(p[0]*p[2]*1000)                         
                        ris.append(p[1]*p[2]*1000)                        
                else:
                    ris.append(np.nan) 
            if (c == 'd'):                      #m for pog or m/s for velocity
                if (not self.swath)&(not self.vel):
                    eprint("Mode m='d' can be used only for swath and vel product")
                    exit()                    
                if (found):
                    if (self.swath):
                        #radh radw r
                        ris.append(p[0]*(180/math.pi) )                         
                        ris.append(p[1]*(180/math.pi))
                    if (self.vel):
                        # p[0] is the velocity in m/s 
                        # p[3] is the Ray of the planet
                        ris.append((p[0]/p[3])*(180/math.pi) )                                                 
                else:
                    if (self.swath):
                        ris.append(np.nan)                     
                        ris.append(np.nan)                     
                    if (self.vel):
                        ris.append(np.nan)                     
            if (c == 'p'):                      #s for px
                if (not self.vel):
                    eprint("Mode [p='ms/pix'] can be used only for vel product")
                    exit()                    
                if (found):
                    ris.append(1000*p[1]/p[0])
                else:
                    ris.append(np.nan)                     
   
        if (len(ris)==1):  
            return ris[0]
        else:          
            return ris

    def print(self, compact=False):
        if (compact):
            lprint("       "+self.name+"("+self.instr +
                   ") ["+self.mode+"("+self.format+")]")
        else:
            lprint("      Instruments:"+self.instr)
            lprint("      Name       :"+self.name)
            lprint("      Mode       :"+self.mode)
            lprint("      Format     :"+self.format)
        if self.printCSV:
            lprint("      to be printed in CSV")
        else:
            lprint("      NOT to be printed in CSV")

    def getLabels(self):
        ris = []
        for c in self.mode:
            if (c == 'L'):
                ris.append('Lat[°]')
                ris.append('Long[°]')
            if (c == 'R'):
                ris.append('Ray[km]')
            if (c == 'D'):
                ris.append('Dist[km]')
            if (c == 'S'):
                ris.append('SunDist[km]')
            if (c == 'X'):
                ris.append('X[km]')
                ris.append('Y[km]')
                ris.append('Z[km]')
            if (c == 'I'):
                ris.append('Inc[°]')
            if (c == 'E'):
                ris.append('Emi[°]')
            if (c == 'P'):
                ris.append('Pha[°]')
            # pixel on ground
            if (c == 'k'):
                if ((self.pog)|(self.swath)):
                    ris.append('h[km]')
                    ris.append('w[km]')
                if (self.vel):
                    ris.append('[km/s]')
                if (self.swath):
                    ris.append('h[km/s]')
                    ris.append('w[km/s]')
                    
            if (c == 'm'):
                if ((self.pog)|(self.swath)):
                    ris.append('h[m]')
                    ris.append('w[m]')  
                if (self.vel):
                    ris.append('[m/s]')  
            if (c == 'd'):
                if (self.vel):
                    ris.append('AT[°/s]')
                if (self.swath):
                    ris.append('h[°]')
                    ris.append('w[°]')
            if (c == 'p'):
                ris.append('AT[ms/px]')
 
        return ris
    # Fast call without postfix
    def getNames(self):
        ris = []
        for c in self.mode:
            if (c == 'L'):
                ris.append(self.name)
                ris.append(self.name)
            if (c == 'R'):
                ris.append(self.name)
            if (c == 'D'):
                ris.append(self.name)
            if (c == 'X'):
                ris.append(self.name)
                ris.append(self.name)
                ris.append(self.name)
            if (c == 'I'):
                ris.append(self.name)
            if (c == 'E'):
                ris.append(self.name)
            if (c == 'P'):
                ris.append(self.name)
            # pixel on groundor vel
            if ((c == 'k')|(c == 'm')):
                if (self.pog):
                    ris.append(self.name)
                    ris.append(self.name)
                if (self.vel):
                    ris.append(self.name)
                if (self.swath):
                    ris.append(self.name)
                    ris.append(self.name)
            if (c == 'p'):
                if (self.vel):
                    ris.append(self.name) 
                if (self.swath):
                    ris.append(self.name) 
                    ris.append(self.name) 
            if (c == 'd'):
                if (self.vel):
                    ris.append(self.name) 
                if (self.swath):
                    ris.append(self.name) 
                    ris.append(self.name) 
            if (c == 'S'):
                ris.append(self.name)                  
        return ris
    # Fast call with postfix
    def getNamesPost(self,postfix):
        ris = []
        str=self.name+postfix
        for c in self.mode:
            if (c == 'L'):
                ris.append(str)
                ris.append(str)
            if (c == 'R'):
                ris.append(str)
            if (c == 'D'):
                ris.append(str)
            if (c == 'X'):
                ris.append(str)
                ris.append(str)
                ris.append(str)

            if (c == 'I'):
                ris.append(str)
            if (c == 'E'):
                ris.append(str)
            if (c == 'P'):
                ris.append(str)
        return ris    
    def getInstr(self,ins):
        ris = []
        for c in self.mode:
            if (c == 'L'):
                ris.append(ins)
                ris.append(ins)
            if (c == 'R'):
                ris.append(ins)
            if (c == 'D'):
                ris.append(ins)
            if (c == 'X'):
                ris.append(ins)
                ris.append(ins)
                ris.append(ins)

            if (c == 'I'):
                ris.append(ins)
            if (c == 'E'):
                ris.append(ins)
            if (c == 'P'):
                ris.append(ins)
            # pixel on groundor vel
            if ((c == 'k')|(c == 'm')):
                if (self.pog):
                    ris.append(ins)
                    ris.append(ins)
                if (self.vel):
                    ris.append(ins)
            if (c == 'p'):
                    ris.append(ins)
                    ris.append(ins)
            if (c == 'S'):
                    ris.append(ins)                    


        return ris


def listproducts(lookforins,Products):
    lp=[]
    for p_ in Products:
        if ((p_.instr== lookforins)|(p_.instr=='ALL')):
            lp.append(p_)
    return lp



class Timeline:

    # # A simple class attribute
    # t0_str = ""
    # te_str = ""
    # t0 = 0
    # te = 0
    # dt = 0
    # instr = []
    # t = []
    #               starting_time   string et
    #               stop_time       string et
    #               tstep           float seconds
    def __init__(self, starting_time, stop_time, tstep, instr_):
        self.t0_str = starting_time
        try:
            self.t0 = spice.str2et(starting_time)
        except:
            eprint("Starting Date in timeline is not correct:"+starting_time)
            exit()

        self.te_str = stop_time
        try:
            self.te = spice.str2et(stop_time)
        except:
            eprint("Stope Date in timeline is not correct:"+stop_time)
            exit()
        self.dt = float(tstep)
        self.instr = instr_
        self.t = np.arange(self.t0, self.te, self.dt)

    def add_incidence(self,inc):
        self.incidence=inc

# Convert timeline to string
    def tostring(self):
        s=self.t0_str+' '+self.te_str+'d'+str(self.dt)
        s = s.replace(' ', '_')
        s = s.replace(':', '.')
        return s
            


# Print details on the output window
    def print(self):
        tb=Table(show_header=False)
        tb.add_column()
        tb.add_column()
        tb.add_row('Start Time', f"{self.t0_str} ({self.t0})")
        tb.add_row("End Time", f"{self.te_str} ({self.te})")
        tb.add_row("t_step", f"{self.dt} s")
        st4 = ""
        for x in self.instr:
            st4 = st4+"  "+x
        tb.add_section()
        # st5 = "N-Acq: "+str(len(self.t))
        # lprint("      "+st1)
        # lprint("      "+st2)
        # lprint("      "+st3)
        # lprint("      "+st4)
        # console.print(tb)
        dur = self.te-self.t0
        dur_min = (dur)/60
        dur = "{:.2f}".format(dur)
        dur_min = "{:.2f}".format(dur_min)
        tb.add_row("Duration",  f"{dur} s= {dur_min} m")
        # lprint("      Duration "+str(dur)+"s ="+str(dur_min)+"m")
        tb.add_row('N-Acq',  str(len(self.t)))
        # lprint("      "+st5)
        console.print(tb)

# write to file
# Write a csv file with first row  title_cols1
# second row title_cols2
# third row title_cols2
# followed by the row of risINS

    def write2file(self,namefile,title_cols1,title_cols2,title_cols3,risINS,tab=';'):
    #   'E:/SOIM/my_project/results/csv_file.csv'    
        f = open(namefile, 'w',newline='',encoding='utf-8-sig')
        writer = csv.writer(f)
        writer.writerow(title_cols1)
        writer.writerow(title_cols2)
        writer.writerow(title_cols3)
        for ele in risINS:
            writer.writerow(ele)
        # close the file
        f.close()
        lprint("Done writing")


def epoch2orbs(et):
    origin=827529239.6856
    duration=8503.3919
    return math.floor((et-origin)/duration)
