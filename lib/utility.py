from lib.console import console
from os import environ
from sys import exit
from rich.table import Table


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
    tb=Table.grid()
    tb.add_column("Instrument")
    tb.add_column()
    tb.add_column("Amount")
    for item in dct.keys():  # dct.iteritems() in Python 2
        tb.add_row(item,'    ',f"[cyan]{dct[item]}[/cyan]")
        # console.print(f"{MSG.INFO} "+"   {} ({})".format(item, amount))
    console.print(tb)
        
def soimExit(error=False):
    console.save_text(environ['SOIM_LOG'], styles=False)
    if error:
        exit(1)
    else:
        exit(0)
