import re
from typing import Tuple, Union


# Generic text generation functions

def boolFormatter(val: bool) -> str:
    """Generic text formatter for bool value"""
    return '[green]On :heavy_check_mark:[/green] ' if val else '[orange3]Off :axe:[/orange3]'


def getColor(val: Union[bool, int, str]) -> Tuple[str, str]:
    """Generic text color getter for bool value"""
    if type(val) is str:
        try:
            val = int(val)
        except ValueError:
            val = False
    return ('[green]', '[/green]') if val else ('[orange3]', '[/orange3]')


def richLen(text: str) -> int:
    """Get real length of a text without Rich colors"""
    # remove rich color tags
    color_removed = re.sub(r"\[/?[^]]+]", '', text, 0, re.MULTILINE)
    # replace emoji by two random char (because emoji are wide)
    emoji_removed = re.sub(r":[a-z-_+()\d'’.&]+:", 'XX', color_removed, 0, re.MULTILINE)
    return len(emoji_removed)
