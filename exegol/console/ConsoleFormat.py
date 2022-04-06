from typing import Tuple, Union


# Generic text generation functions

def boolFormatter(val: bool) -> str:
    """Generic text formatter for bool value"""
    return '[green]On :heavy_check_mark:[/green]  ' if val else '[red]Off :cross_mark:[/red]'


def getColor(val: Union[bool, int, str]) -> Tuple[str, str]:
    """Generic text color getter for bool value"""
    if type(val) is str:
        try:
            val = int(val)
        except ValueError:
            val = False
    return ('[green]', '[/green]') if val else ('[red]', '[/red]')