import csv
import math
from pathlib import Path

import numpy as np
import spiceypy as spice
from prettytable import PrettyTable
from rich.table import Table

from SOIM.lib.console import console
from SOIM.lib.product_types import PRODUCT_BY_ALIAS
from SOIM.lib.utility import eprint, lprint, pprint, print_dic, wprint


class instr:
    nameFk = ""
    naifID = 0

    def __init__(self, nameFk_, naifID_):
        self.nameFk = nameFk_
        self.naifID = naifID_


class Aquisition:
    # Class of the single acqusition including all the output requered
    instr = ""
    time = 0
    norbit = 0
    time_str = []
    # 3D points
    pbore = []
    pcorners = []
    psubnad = []
    psubsol = []

    # 3D points coordinates
    boresight_latlong = []
    corners_lat = []
    corners_long = []
    subnad = []
    swath_vect = []

    covLat = 0
    covLong = 0

    pog_h = 0
    pog_w = 0
    vel = 0
    smearing = 0
    ill = []
    nord_az = []

    mta = 0

    def __init__(self, instr_, time_):
        self.instr = instr_
        self.time = time_
        self.norbit = epoch2orbs(time_)
        self._surface_values = {}
        self._body_positions = {}

    def surface_values(self, product, point, found=True):
        if not found:
            return product.convert(point, self.time, found=False)

        key = (product, tuple(point))
        if key not in self._surface_values:
            self._surface_values[key] = product.convert(
                point, self.time, positions=self._body_positions
            )
        return self._surface_values[key]

    def add_borep(self, pbore_):
        self.pbore = pbore_

    def add_bore(self, lat, long):
        self.boresight_latlong.append(lat)
        self.boresight_latlong.append(long)

    def add_naz(self, naz):
        self.nord_az.append(naz)

    def add_subnp(self, ps):
        self.psubnad = ps

    def add_subn(self, lat, long):
        self.subnad.append(lat)
        self.subnad.append(long)

    def add_cornersp(self, a_ps):
        self.pcorners = a_ps

    def add_corners(self, lat, long):
        self.corners_lat = lat
        self.corners_long = long

    def add_coverage(self, c1, c2):
        self.covLat = c1
        self.covLong = c2

    def add_pog(self, pog):
        self.pog_h = pog
        self.pog_w = pog

    def add_pog(self, pog_h, pog_w):
        self.pog_h = pog_h
        self.pog_w = pog_w

    def add_swaths(self, swvect):
        self.swath_vect = swvect

    def add_vel(self, vel):
        self.vel = vel

    def add_smearing(self, smearing):
        self.smearing = smearing

    def add_ill(self, inc, sol, emi):
        self.ill = [inc, sol, emi]

    def add_subsolar(self, lat, long):
        self.ss_lat = lat
        self.ss_long = long

    def add_subsolarp(self, ss_p):
        self.subsolarp = ss_p

    def add_mta(self, mta):
        self.mta = mta

    def get_foot(self):
        return [
            (self.corners_lat[0], self.corners_long[0]),
            (self.corners_lat[1], self.corners_long[1]),
            (self.corners_lat[2], self.corners_long[2]),
            (self.corners_lat[3], self.corners_long[3]),
        ]

    def get_foot_longlat(self):
        return [
            (self.corners_long[0], self.corners_lat[0]),
            (self.corners_long[1], self.corners_lat[1]),
            (self.corners_long[2], self.corners_lat[2]),
            (self.corners_long[3], self.corners_lat[3]),
        ]

    def has_foot(self):
        return len(self.corners_lat) > 0

    def get_orbit(self):
        return self.norbit

    def get_time(self):
        return self.time

    def get_strtime(self):
        return self.time_str

    def clone(self):
        acq = Aquisition(self.instr_, self.time_)
        acq.add_borep(self.pbore_)
        acq.add_naz(self.nord_az)
        acq.add_bore(self.lat, self.long)
        acq.add_subnp(self.ps)
        acq.add_subn(self.lat, self.long)
        acq.add_cornersp(self.a_ps)
        acq.add_corners(self.lat, self.long)
        acq.add_pog(self.pog)
        acq.add_pog(self.pog_h, self.pog_w)
        acq.add_coverage(self.covLat, self.covLong)
        acq.add_swaths(self.swvect)
        acq.add_vel(self.vel)
        acq.add_smearing(self.smearing)
        acq.add_ill(self.inc, self.sol, self.emi)
        acq.add_subsolar(self.lat, self.long)
        acq.add_subsolarp(self.ss_p)
        acq.add_mta(self.mta)
        return acq


class Product:
    # Class of the Product required
    instr = ""
    name = ""
    mode = ""
    print_mode = ""

    boresight = False
    corners = False
    subnadiral = False
    subsolar = False
    pog = False
    vel = False
    smearing = False
    f_swath = False
    f_coverage = False
    printCSV = False
    mta = False
    # formats
    f_latlong = False
    f_ray = False
    f_ill = False
    f_x = False
    f_inc = False
    f_emi = False
    f_pha = False
    f_naz = False
    f_sun2bore = False

    met = ""
    tar = ""
    tfr = ""
    lc = ""
    obs = ""

    def __init__(self, instr_, name_, mode_, print_mode_, print_outputs=True):

        # Class of the Product required.
        # Example of the CSV file describing:
        # instr, name,mode, format

        #     INSTRUMENT	       Product	Mode	Sign
        # MPO_SIMBIO-SYS_STC-L_P700	Corners	    LR	  33
        # MPO_SIMBIO-SYS_STC-L_P700	Subnadiral	LRD	  333
        # MPO_SIMBIO-SYS_STC-L_P700	Boresight	LIEPS 33883
        # MPO_SIMBIO-SYS_STC-L_P700	Pog	        m	  3
        # MPO_SIMBIO-SYS_STC-L_P700	VelBor	    mpd	  333
        # MPO_SIMBIO-SYS_STC-L_P700	Swath	    dm	  33

        self.instr = instr_
        self.name = name_
        self.mode = mode_
        # Numeric legacy formats exported all columns.
        self.print_mode = (
            "b" * len(print_mode_) if print_mode_.isdigit() else print_mode_
        )
        self.print_outputs = print_outputs
        if len(mode_) != len(print_mode_):
            eprint(
                f"Error in definition of product:\n   {instr_}:{name_}\n Check Product file\n Print Modes not coherent with Mode (they should have the same length)"
            )
            eprint(f"                              :\n   mode      :{mode_}\n ")
            eprint(f"                              :\n   print_mode: {print_mode_}\n ")
            exit()
        definition = PRODUCT_BY_ALIAS.get(self.name)
        if definition is not None:
            self.name, flag = definition
            setattr(self, flag, True)

        # Possible modes

        if "L" in mode_:  # lat logn
            self.f_latlong = True
        if "R" in mode_:  # ray
            self.f_ray = True
        if "I" in mode_:  # illumination angles
            self.f_ill = True
        if "X" in mode_:  # 3D point coordinates
            self.f_x = True
        if "I" in mode_:  # incidence angle
            self.f_inc = True
        if "E" in mode_:  # Emission Angles
            self.f_emi = True
        if "P" in mode_:  # Phase angle
            self.f_pha = True
        if "N" in mode_:  # Nord Azimuth
            self.f_naz = True
        if "S" in mode_:  # Nord Azimuth
            self.f_sun2bore = True

    def addScenario(self, s):
        # Example of scenario:
        #    Orbiter: 'BEPICOLOMBO MPO'
        #    Target: 'Mercury'
        #    Target Frame: 'IAU_Mercury'

        self.metSic = s["ShapeSinc"]  # mode of interpolation with Sinc
        self.metSbnd = s["ShapeSbnd"]  # mode of interpolation with subnadiral
        self.tar = s["Target"]  # target name
        self.tfr = s["Target Frame"]  # target frame
        self.lc = s["Light"]  # Light correction
        self.obs = s["Orbiter"]  # Orbiter

    def _body_position(self, body, et, positions):
        if positions is None:
            return spice.spkpos(body, et, self.tfr, self.lc, self.tar)[0]
        key = (body, et, self.tfr, self.lc, self.tar)
        if key not in positions:
            positions[key] = spice.spkpos(*key)[0]
        return positions[key]

    #   convert a product considering the mode
    def convert(self, point3D, et=0, found=True, *, positions=None):
        ris = []
        if found and ("L" in self.mode or "R" in self.mode):
            ray, longitude, latitude = spice.reclat(point3D)
            long = math.degrees(longitude)
            lat = math.degrees(latitude)
        if found and any(field in self.mode for field in "IEPN"):
            _, _, phase, incidence, emission = spice.ilumin(
                self.metSic, self.tar, et, self.tfr, self.lc, self.obs, point3D
            )
            pha = math.degrees(phase)
            inc = math.degrees(incidence)
            emi = math.degrees(emission)
        for c in self.mode:
            if c == "L":  # Lat Long
                if found:
                    ris.append(lat)
                    ris.append(long)
                else:
                    ris.append(np.nan)
                    ris.append(np.nan)

            if c == "R":  # Ray
                if found:
                    ris.append(ray)
                else:
                    ris.append(np.nan)
            if c == "D":  # Distance vs Observer
                if found:
                    # define position of obs respect target
                    position = self._body_position(self.obs, et, positions)
                    dist = np.linalg.norm(point3D - position)
                    ris.append(dist)
                else:
                    ris.append(np.nan)
            if c == "S":  # Distance sun vs Observer
                if found:
                    # define position of sun respect target
                    position = self._body_position("SUN", et, positions)
                    dist = np.linalg.norm(point3D - position)
                    ris.append(dist)
                else:
                    ris.append(np.nan)

            if c == "X":  # 3D coordinates xyz
                if found:
                    ris.append(point3D[0])
                    ris.append(point3D[1])
                    ris.append(point3D[2])
                else:
                    ris.append(np.nan)
                    ris.append(np.nan)
                    ris.append(np.nan)

            if c == "N":  # Distance sun vs Observer
                if found:
                    posSun = self._body_position("SUN", et, positions)
                    naz = get_NordAz(point3D, posSun, inc)
                    ris.append(naz)
                else:
                    ris.append(np.nan)

            if c == "I":  # Incience angle
                if found:
                    ris.append(inc)
                else:
                    ris.append(np.nan)
            if c == "E":  # Emission angle
                if found:
                    ris.append(emi)
                else:
                    ris.append(np.nan)
            if c == "P":  # Phase angle
                if found:
                    ris.append(pha)
                else:
                    ris.append(np.nan)

            # Caso pog or vel
            if c == "k":  # km for pog or km/s for velocity
                if (not self.pog) & (not self.vel) & (not self.f_swath):
                    eprint(
                        "Mode [k='km' or 'km/s'] can be used only for pog or vel product"
                    )
                    exit()
                if found:
                    if self.pog:
                        ris.append(np.linalg.norm(point3D))
                    if self.vel:
                        ris.append(point3D[0])
                    if self.f_swath:
                        ris.append(point3D[0] * point3D[2])
                        ris.append(point3D[1] * point3D[2])

                else:
                    ris.extend([np.nan] * (2 if self.f_swath else 1))
            if c == "m":  # m for pog or m/s for velocity
                if (
                    (not self.pog)
                    & (not self.vel)
                    & (not self.f_swath)
                    & (not self.smearing)
                ):
                    eprint(
                        "Mode m can be used only for pog or vel swath , Smearing, product"
                    )
                    exit()
                if found:
                    if self.pog:
                        ris.append(np.linalg.norm(point3D) * 1000)
                    if self.vel:
                        ris.append(point3D[0] * 1000)
                    if self.smearing:
                        ris.append(1000 * 0.25 * point3D[1] / point3D[0])
                    if self.f_swath:
                        # radh radw r
                        ris.append(point3D[0] * point3D[2] * 1000)
                        ris.append(point3D[1] * point3D[2] * 1000)
                else:
                    ris.extend([np.nan] * (2 if self.f_swath else 1))
            if c == "s":  # s for semaring 1/4 : point3D[2]=pogh point3D[1]=vel
                if self.smearing:
                    ris.append(0.25 * point3D[1] / point3D[0])
            if c == "d":  # m for pog or m/s for velocity
                if (not self.f_swath) & (not self.vel) & (not self.mta):
                    eprint("Mode m='d' can be used only for swath, mta and vel product")
                    exit()
                if found:
                    if self.f_swath:
                        # radh radw r
                        ris.append(point3D[0] * (180 / math.pi))
                        ris.append(point3D[1] * (180 / math.pi))
                    if self.vel:
                        # p[0] is the velocity in m/s
                        # p[2] is the Ray of the planet
                        ris.append((point3D[0] / point3D[2]) * (180.0 / math.pi))
                    if self.f_coverage:
                        ris.append(0)
                        ris.append(0)

                else:
                    if self.f_swath:
                        ris.append(np.nan)
                        ris.append(np.nan)
                    if self.vel:
                        ris.append(np.nan)
                    if self.f_coverage:
                        ris.append(np.nan)
                        ris.append(np.nan)
            if c == "p":  # s for px
                if not self.vel:
                    pprint("Mode [p='ms/pix'] can be used only for vel product")
                    exit()
                if found:
                    if point3D[0] == 0:
                        ris.append(np.nan)
                    else:
                        ris.append(1000 * point3D[1] / point3D[0])
                else:
                    ris.append(np.nan)

        # if (len(ris)==1):
        #     return ris[0]
        # else:
        return ris

    def print(self, log_file: Path, compact=False):
        if compact:
            lprint(
                "       "
                + self.name
                + "("
                + self.instr
                + ") ["
                + self.mode
                + "("
                + self.print_mode
                + ")]",
                log_file,
            )
        else:
            lprint("      Instruments:" + self.instr, log_file)
            lprint("      Name       :" + self.name, log_file)
            lprint("      Mode       :" + self.mode, log_file)
            lprint("      PrintMode     :" + self.print_mode, log_file)
        if self.printCSV:
            lprint("      to be printed in CSV", log_file)
        else:
            lprint("      NOT to be printed in CSV", log_file)

    def getLabels(self):
        ris = []
        for c in self.mode:
            if c in {"L", "2"}:
                ris.append("La[°]")
                ris.append("Lo[°]")
            if c == "R":
                ris.append("R[km]")
            if c == "D":
                ris.append("Di[km]")
            if c == "S":
                ris.append("2S[km]")
            if c == "X":
                ris.append("X[km]")
                ris.append("Y[km]")
                ris.append("Z[km]")
            if c == "I":
                ris.append("Inc[°]")
            if c == "E":
                ris.append("Emi[°]")
            if c == "P":
                ris.append("Pha[°]")
            if c == "N":
                ris.append("NaZ[°]")
            # pixel on ground
            if c == "k":
                if (self.pog) | (self.f_swath):
                    ris.append("h[km]")
                    ris.append("w[km]")
                if self.vel:
                    ris.append("[km/s]")

            if c == "m":
                if (self.pog) | (self.f_swath):
                    ris.append("h[m]")
                    ris.append("w[m]")
                if self.smearing:
                    ris.append("[ms]")
                if self.vel:
                    ris.append("[m/s]")
            if c == "s":
                if self.smearing:
                    ris.append("[s]")
            if c == "d":
                if self.vel:
                    ris.append("AT[°/s]")
                if self.f_swath:
                    ris.append("h[°]")
                    ris.append("w[°]")
                if self.f_coverage:
                    ris.append("Lat[°]")
                    ris.append("Long[°]")
                if self.mta:
                    ris.append("[°]")

            if c == "p":
                ris.append("AT[ms/px]")

        return ris

    # Fast call without postfix
    def getNames(self):
        ris = []
        for c in self.mode:
            if c == "L":
                ris.append(self.name)
                ris.append(self.name)
            if c == "S":
                ris.append(self.name)
            if c == "R":
                ris.append(self.name)
            if c == "D":
                ris.append(self.name)
            if c == "X":
                ris.append(self.name)
                ris.append(self.name)
                ris.append(self.name)
            if c == "I":
                ris.append(self.name)
            if c == "E":
                ris.append(self.name)
            if c == "P":
                ris.append(self.name)
            if c == "N":
                ris.append(self.name)
            if c == "2":
                ris.extend([self.name, self.name])
            # pixel on groundor vel
            if (c == "k") | (c == "m"):
                if self.pog:
                    ris.append(self.name)
                    ris.append(self.name)
                if self.vel:
                    ris.append(self.name)
                if self.f_swath:
                    ris.append(self.name)
                    ris.append(self.name)
                if self.smearing:
                    ris.append(self.name)

            if c == "d":
                if (self.vel) | (self.mta):
                    ris.append(self.name)
                if self.f_swath:
                    ris.append(self.name)
                    ris.append(self.name)
                if self.f_coverage:
                    ris.append(self.name)
                    ris.append(self.name)
            if c == "s":
                if self.smearing:
                    ris.append(self.name)
            if c == "p":
                ris.append(self.name)
        return ris

    def getPrintMode(self):
        risc = []
        riss = []
        for c, p in zip(self.mode, self.print_mode):
            if c in {"L", "2"}:
                risc.append((p == "c") | (p == "b"))
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "S":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "R":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "D":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "X":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "I":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "E":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "P":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            if c == "N":
                risc.append((p == "c") | (p == "b"))
                riss.append((p == "s") | (p == "b"))
            # pixel on groundor vel
            if (c == "k") | (c == "m"):
                if self.pog:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                if self.vel:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                if self.f_swath:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                if self.smearing:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))

            if c == "d":
                if (self.vel) | (self.mta):
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                if self.f_swath:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                if self.f_coverage:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
            if c == "s":
                if self.smearing:
                    risc.append((p == "c") | (p == "b"))
                    riss.append((p == "s") | (p == "b"))
            if c == "p":
                risc.append(p in "cb")
                riss.append(p in "sb")
        return (
            (risc, riss)
            if self.print_outputs
            else ([False] * len(risc), [False] * len(riss))
        )

    # Fast call with postfix
    def getNamesPost(self, postfix):
        ris = []
        str = self.name + postfix
        for c in self.mode:
            if c in {"L", "2"}:
                ris.append(str)
                ris.append(str)
            if c == "R":
                ris.append(str)
            if c == "S":
                ris.append(str)
            if c == "D":
                ris.append(str)
            if c == "X":
                ris.append(str)
                ris.append(str)
                ris.append(str)

            if c == "I":
                ris.append(str)
            if c == "E":
                ris.append(str)
            if c == "P":
                ris.append(str)
            if c == "N":
                ris.append(str)
        return ris

    def getInstr(self, ins):
        ris = []
        for c in self.mode:
            if c in {"L", "2"}:
                ris.append(ins)
                ris.append(ins)
            if c == "R":
                ris.append(ins)
            if c == "D":
                ris.append(ins)
            if c == "X":
                ris.append(ins)
                ris.append(ins)
                ris.append(ins)

            if c == "I":
                ris.append(ins)
            if c == "E":
                ris.append(ins)
            if c == "P":
                ris.append(ins)
            if c == "N":
                ris.append(ins)
            if c == "S":
                ris.append(ins)
            # pixel on groundor vel
            if (c == "k") | (c == "m"):
                if self.pog:
                    ris.append(ins)
                    ris.append(ins)
                if self.f_swath:
                    ris.append(ins)
                    ris.append(ins)
                if self.smearing:
                    ris.append(ins)
                if self.vel:
                    ris.append(ins)
            if c == "d":
                if self.f_swath:
                    ris.append(ins)
                    ris.append(ins)
                if self.f_coverage:
                    ris.append(ins)
                    ris.append(ins)
                if self.mta:
                    ris.append(ins)
                if self.vel:
                    ris.append(ins)
            if c == "p":
                ris.append(ins)
            if c == "s":
                if self.smearing:
                    ris.append(ins)

        return ris


def listproducts(lookforins, Products):
    lp = []
    for p_ in Products:
        if (p_.instr == lookforins) | (p_.instr == "ALL"):
            lp.append(p_)
    return lp


class Timeline:
    #               starting_time   string et
    #               stop_time       string et
    #               tstep           float seconds
    #               instr_          instrument
    def __init__(self, starting_time, stop_time, tstep, instr_):
        self.t0_str = starting_time
        try:
            self.t0 = spice.str2et(starting_time)
        except:
            eprint("Starting Date in timeline is not correct:" + starting_time)
            exit()

        self.te_str = stop_time
        try:
            self.te = spice.str2et(stop_time)
        except:
            eprint("Stope Date in timeline is not correct:" + stop_time)
            exit()
        self.dt = float(tstep)
        self.instr = instr_
        self.t = np.arange(self.t0, self.te, self.dt)

    def add_incidence(self, inc):
        self.incidence = inc

    # Convert timeline to string
    def tostring(self):
        s = self.t0_str + " " + self.te_str + "d" + str(self.dt)
        s = s.replace(" ", "_")
        s = s.replace(":", ".")
        return s

    # Print details on the output window
    def print(self, log_file):
        tb = PrettyTable(header=False)
        # tb=Table(show_header=False)
        # tb.add_column()
        # tb.add_column()
        tb.add_row(["Start Time", f"{self.t0_str} ({self.t0})"])
        tb.add_row(["End Time", f"{self.te_str} ({self.te})"])
        tb.add_row(["t_step", f"{self.dt} s"], divider=True)
        st4 = ""
        for x in self.instr:
            st4 = st4 + "  " + x

        dur = self.te - self.t0
        dur_min = (dur) / 60
        dur = f"{dur:.2f}"
        dur_min = f"{dur_min:.2f}"
        tb.add_row(["Duration", f"{dur} s= {dur_min} m"])
        # lprint("      Duration "+str(dur)+"s ="+str(dur_min)+"m")
        tb.add_row(["N-Acq", str(len(self.t))])
        # lprint("      "+st5)
        with open(log_file, "a") as fl:
            fl.write(str(tb) + "\n")

    # write to file
    # Write a csv file with first row  title_cols1
    # second row title_cols2
    # third row title_cols2
    # followed by the row of risINS

    def write2file(
        self,
        namefile,
        title_cols1,
        title_cols2,
        title_cols3,
        risINS,
        log_file: Path,
        tab=";",
        *,
        print_csv=None,
        append=False,
    ):
        if print_csv is None:
            print_csv = [True] * len(title_cols1)
        with open(
            namefile, "a" if append else "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.writer(file)
            if not append:
                for header in (title_cols1, title_cols2, title_cols3):
                    writer.writerow(
                        [value for value, keep in zip(header, print_csv) if keep]
                    )
            for row in risINS:
                writer.writerow([value for value, keep in zip(row, print_csv) if keep])
        lprint("Done writing", log_file)


def epoch2orbs(et):
    origin = 827529239.6856
    duration = 8503.3919
    return math.floor((et - origin) / duration)


def get_NordAz(x, posSun, solar):

    if solar >= 90:
        return np.nan
    else:
        radius, lon, lat = spice.reclat(x)

        dlat = 0.001
        dlon = 0.001

        if lat + dlat > np.pi / 2:
            xn = spice.latrec(radius, lon, lat - dlat)
            n = x - xn
        else:
            xn = spice.latrec(radius, lon, lat + dlat)
            n = xn - x

        n = n / np.linalg.norm(n)

        if lon + dlon > np.pi:
            xe = spice.latrec(radius, lon - dlon, lat)
            e = x - xe
        else:
            xe = spice.latrec(radius, lon + dlon, lat)
            e = xe - x

        e = e / np.linalg.norm(e)

        s = posSun - x

        r2 = e - np.dot(n, e) * n
        r2 = r2 / np.linalg.norm(r2)

        R = np.vstack((n, r2, np.cross(n, r2)))
        s = R @ s

        azimuth = (180.0 / np.pi) * np.arctan2(s[1], s[0])
        if azimuth < 0:
            azimuth += 360.0
        return azimuth
