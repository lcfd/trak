"""
Including a __main__.py module in a Python package enables 
you to run the package as an executable program using the command python -m trak.
"""

from trak import cli, __app_name__


def main():
    cli.app(prog_name=__app_name__)


if __name__ == "__main__":
    main()
