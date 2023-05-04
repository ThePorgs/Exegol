from typing import cast, Union, Optional

from rich.console import Console
from rich.progress import Progress, Task, TaskID, ProgressColumn, GetTimeCallable

from exegol.utils.ExeLog import console as exelog_console


class ExegolProgress(Progress):
    """Addition of a practical function to Rich Progress"""

    def __init__(self, *columns: Union[str, ProgressColumn], console: Optional[Console] = None, auto_refresh: bool = True, refresh_per_second: float = 10, speed_estimate_period: float = 30.0,
                 transient: bool = False, redirect_stdout: bool = True, redirect_stderr: bool = True, get_time: Optional[GetTimeCallable] = None, disable: bool = False, expand: bool = False) -> None:
        if console is None:
            console = exelog_console
        super().__init__(*columns, console=console, auto_refresh=auto_refresh, refresh_per_second=refresh_per_second, speed_estimate_period=speed_estimate_period, transient=transient,
                         redirect_stdout=redirect_stdout, redirect_stderr=redirect_stderr, get_time=get_time, disable=disable, expand=expand)

    def getTask(self, task_id: TaskID) -> Task:
        """Return a specific task from task_id without error"""
        task = self._tasks.get(task_id)
        if task is None:
            # If task doesn't exist, raise IndexError exception
            raise IndexError
        return cast(Task, task)

    def __enter__(self) -> "ExegolProgress":
        super(ExegolProgress, self).__enter__()
        return self
