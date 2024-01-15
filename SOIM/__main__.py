from pathlib import Path
from SOIM.lib.console import console
from SOIM.core import readSK_run
from sys import exit
from SOIM.lib.IO_functions import read_yaml
from multiprocessing import Pool
import rich_click as click


click.rich_click.USE_RICH_MARKUP = True
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])



def core_soim(project_list:dict,latest,kernel_folder):
    console.print(tuple(project_list.values()))
    if len(project_list) == 1:
        k=list(project_list.keys())
        readSK_run([k[0], project_list[k[0]], latest, kernel_folder])
    else:
        with Pool(len(project_list)) as p:
            p.map(readSK_run, [(k, v, latest, kernel_folder)
                  for k, v in project_list.items()])

    # console.print(p.map(queque,project_list))
    pass

# Funzione di chiamata da linea di comando
@click.command()
def action():
    # kernel_folder=Path("../../../../Simbio-Sys/Software/soimAuto/kernels")
    kernel_folder=Path("kernels")
    project_list_file = Path('project_list.yml')
    if not project_list_file.exists():
        console.print("Error. Projects list not found")
        exit(1)
    project_list= read_yaml(project_list_file)
    from planetary_coverage import ESA_MK, MetaKernel
    info = ESA_MK['MPO']
    # console.print(info)
    console.print(info['latest'])
    kernel_folder = Path(kernel_folder)
    if not kernel_folder.exists():
        kernel_folder.mkdir(parents=True)
    a = MetaKernel(
        # 'meta.tm',
        info['latest'],
        kernels=kernel_folder,
        download=True,
        load_kernels=False
    )
    core_soim(project_list,info['latest'],kernel_folder)

if __name__ == "__main__":
    action()