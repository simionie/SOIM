from pathlib import Path
from rich.console import Console
from sys import exit

console= Console()
def action():
    project_list = Path('project_list.yml')
    if not project_list.exists():
        console.print("Error. Projects list not found")
        exit(1)

if __name__ == "__main__":
    action()