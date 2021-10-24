def boolFormatter(val: bool):
    return '[green]:heavy_check_mark:[/green]' if val else '[red]:cross_mark:[/red]'


def getColor(val: bool):
    return ('[green]', '[/green]') if val else ('[red]', '[/red]')
