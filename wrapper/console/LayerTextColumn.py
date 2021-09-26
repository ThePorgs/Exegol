from typing import Optional

from rich.console import JustifyMethod
from rich.highlighter import Highlighter
from rich.progress import TextColumn, Task, DownloadColumn
from rich.style import StyleType
from rich.table import Column
from rich.text import Text


class LayerTextColumn(TextColumn, DownloadColumn):

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
        self.__layer_key = layer_key
        TextColumn.__init__(self, text_format, style, justify, markup, highlighter, table_column)
        DownloadColumn.__init__(self, binary_units, table_column)

    def render(self, task: "Task") -> Text:
        if task.fields.get(self.__layer_key) is None:
            return TextColumn.render(self, task)
        else:
            return DownloadColumn.render(self, task)
