import os
from typing import Optional

from rich.console import JustifyMethod
from rich.highlighter import Highlighter
from rich.progress import TextColumn, Task, DownloadColumn
from rich.style import StyleType
from rich.table import Column
from rich.text import Text

from exegol.utils.ExeLog import logger


class LayerTextColumn(TextColumn, DownloadColumn):
    """Merging two Rich class to obtain a double behavior in the same RichTable"""

    def __init__(self,
                 text_format: str,
                 layer_key: str,
                 style: StyleType = "none",
                 justify: JustifyMethod = "left",
                 markup: bool = True,
                 highlighter: Optional[Highlighter] = None,
                 table_column: Optional[Column] = None,
                 binary_units: bool = False
                 ) -> None:
        # Custom field
        self.__data_key = layer_key
        # Inheritance configuration
        try:
            TextColumn.__init__(self, text_format, style, justify, markup, highlighter, table_column)
        except TypeError:
            logger.critical(f"Your version of Rich does not correspond to the project requirements. Please update your dependencies with pip:{os.linesep}"
                            f"[bright_magenta]python3 -m pip install --user --requirement requirements.txt[/bright_magenta]")
        DownloadColumn.__init__(self, binary_units, table_column)

    def render(self, task: "Task") -> Text:
        """Custom render depending on the existence of data with data_key"""
        if task.fields.get(self.__data_key) is None:
            # Default render with classic Text render
            return TextColumn.render(self, task)
        else:
            # If the task download a file, render the Download progress view
            return DownloadColumn.render(self, task)
