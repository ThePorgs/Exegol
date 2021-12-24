# Generic text generation functions

def boolFormatter(val: bool):
    """Generic text formatter for bool value"""
    return '[green]:heavy_check_mark:[/green]' if val else '[red]:cross_mark:[/red]'


def getColor(val: bool):
    """Generic text color getter for bool value"""
    return ('[green]', '[/green]') if val else ('[red]', '[/red]')
