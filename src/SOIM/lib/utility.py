import csv
import math
from os import environ
from sys import exit

from rich.table import Table

from SOIM.lib.console import console


class MSG:
    WARNING = "[yellow][WARNINIG][/yellow]"
    INFO = "[green][INFO][/green]"
    ERROR = "[red][ERROR][/red]"


def wprint(wstr):
    console.print(f"{MSG.WARNING} "+wstr)


def lprint(lstr,log_file):
     with open(log_file,'a') as fl:
         fl.write(f"{lstr}\n")
    # console.print(f"{MSG.INFO} "+lstr)


def eprint(lstr):
    console.print(f"{MSG.ERROR} "+lstr)


def print_dic(dct):
    tb=Table.grid()
    tb.add_column("Instrument")
    tb.add_column()
    tb.add_column("Amount")
    for item in dct.keys():  # dct.iteritems() in Python 2
        tb.add_row(item,'    ',f"[cyan]{dct[item]}[/cyan]")
        # console.print(f"{MSG.INFO} "+"   {} ({})".format(item, amount))
    console.print(tb)
        
def soimExit(error=False):
    # console.save_text(environ['SOIM_LOG'], styles=False)
    if error:
        exit(1)
    else:
        exit(0)

#risTIME is a list of items 
#   [a 2 3]
#   [b 2 3]
#   [c 2 3]
#   [d 2 3]
#risINS  is a list (same length) of items 
#   [a e 8]
#   [b f 8]
#   [c g 8]
#   [d f 8]
#result is a horizontal merging
#   [a 2 3  a e 8]
#   [b 2 3  b f 8]
#   [c 2 3  c g 8]
#   [d 2 3  d f 8]
def appendHOR(risTIME,risINS):
    if len(risTIME)==0:
        return risINS
    else:
        merged=[]
        for x in range(len(risTIME)):
            l1=risTIME[x]
            l2=risINS[x]
            merged.append(l1+l2)
        return merged

# Area of a triangle defined by 3d points
def getAof3D(p0,p1,p2): 
    x1=p0[0]
    y1=p0[1]
    z1=p0[2]
    x2=p1[0]
    y2=p1[1]
    z2=p1[2]
    x3=p2[0]
    y3=p2[1]
    z3=p2[2]
           
    return 0.5*math.sqrt( (x2*y1 - x3*y1 - x1*y2 + x3*y2 + x1*y3 - x2*y3)^2 + (x2*z1 - x3*z1 - x1*z2 + x3*z2 + x1*z3 - x2*z3)^2 + (y2*z1 - y3*z1 - y1*z2 + y3*z2 + y1*z3 - y2*z3)^2 ) 

# Area of quadrangle defined by 3d points (clockwise)
def getAof3D(p0,p1,p2,p3): 
    return getAof3D(p0,p1,p2)+getAof3D(p0,p2,p3)
# Area of quadrangle defined by 3d points (clockwise)
# we assume followoing position
#
#  c0            c1
#  p0  --------  p1
#  |             |
#  |             |
#  |             |
#  |             |
#  |             |
#  c3            c2
#  p3  --------  p2

def getOverATof3D(p0,p1,p2,p3,c0,c1,c2,c3): 
    return getAof3D(p0,p1,c2,c3)/getAof3D(p0,p1,p2,p3)
