import re
from datetime import datetime
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


def getArchColor(arch: str) -> str:
    if arch.startswith("arm"):
        color = "slate_blue3"
    elif "amd64" == arch:
        color = "medium_orchid3"
    else:
        color = "yellow3"
    return color


def get_display_date(date: Union[str, datetime]) -> str:
    if type(date) is str:
        if date == '':
            return ''
        date = parse_date(date)
    assert type(date) is datetime
    return date.astimezone().strftime("%d %B %Y %H:%M")


def parse_date(date: str) -> datetime:
    """Parse an ISO date string to a datetime object"""
    try:
        return datetime.fromisoformat(date)
    except ValueError:
        # Handle date parsing for python before 3.11
        from dateutil.parser import isoparse
        return isoparse(date)
