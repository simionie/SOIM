
from lib.utility import wprint, lprint, print_dic, eprint
import spiceypy as spice
import numpy as np


#%% Classes
class instr:
    nameFk = ""
    naifID = 0

    def __init__(self, nameFk_, naifID_):
        self.nameFk = nameFk_
        self.naifID = naifID_


class Product:
    instr = ""
    name = ""
    mode = ""
    format = ""
    boresight = False
    corners = False
    subnadiral = False
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

    def __init__(self, instr_, name_, mode_, format_):
        self.instr = instr_
        self.name = name_
        self.mode = mode_
        self.format = format_
        if len(mode_) != len(format_):
            eprint("Error in definition of product " +
                   instr_+":"+name_+" check Product file")
            eprint("Formats not coherent with Mode")
            exit()
        if ((self.name == 'boresight') | (self.name == 'Boresight') | (self.name == 'BORESIGHT')):
            self.boresight = True
        if ((self.name == 'subnadiral') | (self.name == 'Subnadiral') | (self.name == 'SUBNADIRAL')):
            self.subnadiral = True
        if ((self.name == 'corners') | (self.name == 'Corners') | (self.name == 'CORNERS')):
            self.corners = True
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

    def addScenario(self, s):
        self.met = s["Shape"]
        self.tar = s["Target"]
        self.tfr = s["Target Frame"]
        self.lc = s["Light"]
        self.obs = s["Orbiter"]

    def convert(self, p, et=0, found=True):
        ris = []
        for c in self.mode:
            if ((c == 'L') | (c == 'R')):
                if (found):
                    [lat, long, ray] = spice.reclat(p)
            if (c == 'L'):
                if (found):
                    ris.append(lat)
                    ris.append(long)
                else:
                    ris.append(142857)
                    ris.append(142857)

            if (c == 'R'):
                if (found):
                    ris.append(ray)
                else:
                    ris.append(142857)
            if (c == 'D'):
                if (found):

                    p_obs = spice.spkpos(self.obs, et, self.tfr)
                    dist = np.linalg.norm(p-p_obs)
                    ris.append(dist)
                else:
                    ris.append(142857)
            if (c == 'X'):

                if (found):
                    ris.append(p[0])
                    ris.append(p[1])
                    ris.append(p[2])
                else:
                    ris.append(142857)
                    ris.append(142857)
                    ris.append(142857)

            if ((c == 'I') | (c == 'E') | (c == 'P')):
                if (found):
                    [inc, emi, pha] = spice.illum(
                        self.tar, et, self.lc, self.obs, p)

            if (c == 'I'):
                if (found):
                    ris.append(inc)
                else:
                    ris.append(142857)
            if c == 'E':
                if (found):
                    ris.append(emi)
                else:
                    ris.append(142857)
            if c == 'P':
                if (found):
                    ris.append(pha)
                else:
                    ris.append(142857)
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


class timeline:

    # A simple class attribute
    t0_str = ""
    te_str = ""
    t0 = 0
    te = 0
    dt = 0
    instr = []
    t = []

    def __init__(self, starting_time, stop_time, tstep, instr_):
        self.t0_str = starting_time
        self.t0 = spice.str2et(starting_time)
        self.te_str = stop_time
        self.te = spice.str2et(stop_time)
        self.dt = float(tstep)
        self.instr = instr_
        self.t = np.arange(self.t0, self.te, self.dt)

    def print(self):
        st1 = self.t0_str+"("+str(self.t0)+")"
        st2 = self.te_str+"("+str(self.te)+")"
        st3 = "["+str(self.dt)+"s]"
        st4 = ""
        for x in self.instr:
            st4 = st4+"  "+x
        st5 = "N-Acq: "+str(len(self.t))
        lprint("      "+st1)
        lprint("      "+st2)
        lprint("      "+st3)
        lprint("      "+st4)
        dur = self.te-self.t0
        dur_min = (dur)/60
        dur = "{:.2f}".format(dur)
        dur_min = "{:.2f}".format(dur_min)
        lprint("      Duration "+str(dur)+"s ="+str(dur_min)+"m")
        lprint("      "+st5)
