from lib.console import console
from os import environ
from sys import exit


class MSG:
    WARNING = "[yellow][WARNINIG][/yellow]"
    INFO = "[green][INFO][/green]"
    ERROR = "[red][ERROR][/red]"


def wprint(wstr):
    console.print(f"{MSG.WARNING} "+wstr)


def lprint(lstr):
    console.print(f"{MSG.INFO} "+lstr)


def eprint(lstr):
    console.print(f"{MSG.ERROR} "+lstr)


def print_dic(dct):
    for item, amount in dct.items():  # dct.iteritems() in Python 2
        console.print(f"{MSG.INFO} "+"   {} ({})".format(item, amount))
        
def soimExit(error=False):
    console.save_text(environ['SOIM_LOG'], styles=False)
    if error:
        exit(0)
    else:
        exit(1)
