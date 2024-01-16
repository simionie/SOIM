from pathlib import Path
from sys import exit

import rich_click as click

from SOIM.core import core_soim
from SOIM.lib.console import console
from SOIM.lib.IO_functions import read_yaml

click.rich_click.USE_RICH_MARKUP = True
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
__version__='7.0.0'



# Funzione di chiamata da linea di comando


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option('-k', '--kernel', 'kernel_folder', metavar="FOLDER", help="Kernel Folder", default="kernels")
@click.option('-p', '--project-list', 'project_list_file', metavar='FILE', help='file with the list of the active project', default='projects/project_list.yml')
@click.option('-o','--output-folder',metavar="FOLDER",help="Set the output folder",default='output_soim')
@click.pass_context
def action(ctx, kernel_folder, project_list_file,output_folder):
    ctx.obj={'kernel':kernel_folder,'project':project_list_file,'output':output_folder}
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


@action.command()
@click.pass_context
def run(ctx):
    """Run all The projects"""
    kernel_folder = Path(ctx.obj['kernel'])
    project_list_file = Path(ctx.obj['project'])
    if not project_list_file.exists():
        console.print("Error. Projects list not found")
        exit(1)
    project_list = read_yaml(project_list_file)
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
    core_soim(project_list, info['latest'], kernel_folder,ctx.obj['output'])


@action.command('list')
@click.pass_context
def list_project(ctx):
    """Display the list of avalaible projects"""
    from rich.table import Table
    project_list_file = Path(ctx.obj['project'])
    project_list = read_yaml(project_list_file)
    tb = Table()
    tb.add_column('Project', style='yellow')
    tb.add_column('Path')
    for k, v in project_list.items():
        tb.add_row(k, Path(v).absolute().__str__())
    console.print(tb)


if __name__ == "__main__":
    action()
