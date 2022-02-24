from typing import Tuple, Union


# Generic text generation functions

def boolFormatter(val: bool) -> str:
    """Generic text formatter for bool value"""
    return '[green]On :heavy_check_mark:[/green]  ' if val else '[red]Off :cross_mark:[/red]'


def getColor(val: Union[bool, int]) -> Tuple[str, str]:
    """Generic text color getter for bool value"""
    return ('[green]', '[/green]') if val else ('[red]', '[/red]')
