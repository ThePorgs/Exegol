from typing import Union, Optional, Dict

from git import RemoteProgress
from git.objects.submodule.base import UpdateProgress
from rich.console import Console
from rich.progress import Progress, ProgressColumn, GetTimeCallable, Task

from exegol.utils.ExeLog import console as exelog_console
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class SubmoduleUpdateProgress(UpdateProgress):

    def update(self, op_code: int, cur_count: Union[str, float], max_count: Union[str, float, None] = None, message: str = "") -> None:
        # Full debug log
        logger.debug(f"[{op_code}] {cur_count}/{max_count} : '{message}'")
        if message:
            logger.verbose(f"{message}")
        if max_count is None:
            max_count = 0
        max_count = int(max_count)
        cur_count = int(cur_count)
        main_task = MetaGitProgress().tasks[0]
        step = 0

        # CLONING
        if MetaGitProgress.handle_task(op_code, self.CLONE, "Cloning", max_count, cur_count):
            step = 1

        # UPDWKTREE
        if MetaGitProgress.handle_task(op_code, self.UPDWKTREE, "Updating local git registry", max_count, cur_count):
            step = 2

        main_task.total = 2
        main_task.completed = step


def clone_update_progress(op_code: int, cur_count: Union[str, float], max_count: Union[str, float, None] = None, message: str = '') -> None:
    # Full debug log
    # logger.debug(f"[{op_code}] {cur_count}/{max_count} : '{message}'")
    if max_count is None:
        max_count = 0
    max_count = int(max_count)
    cur_count = int(cur_count)
    main_task = MetaGitProgress().tasks[0]
    step = 0

    # COUNTING
    if MetaGitProgress.handle_task(op_code, RemoteProgress.COUNTING, "Counting git objects", max_count, cur_count, message):
        step = 1

    # COMPRESSING
    elif MetaGitProgress.handle_task(op_code, RemoteProgress.COMPRESSING, "Compressing", max_count, cur_count, message):
        step = 2

    # RECEIVING
    elif MetaGitProgress.handle_task(op_code, RemoteProgress.RECEIVING, "Downloading", max_count, cur_count, message):
        step = 3

    # RESOLVING
    elif MetaGitProgress.handle_task(op_code, RemoteProgress.RESOLVING, "Resolving", max_count, cur_count, message):
        step = 4
    else:
        logger.debug(f"Git OPCODE {op_code} is not handled by Exegol TUI.")

    main_task.total = 4
    main_task.completed = step


class MetaGitProgress(Progress, metaclass=MetaSingleton):
    """Singleton instance of the current Progress. Used with git operation to support callback updates."""

    def __init__(self, *columns: Union[str, ProgressColumn], console: Optional[Console] = None, auto_refresh: bool = True, refresh_per_second: float = 10, speed_estimate_period: float = 30.0,
                 transient: bool = False, redirect_stdout: bool = True, redirect_stderr: bool = True, get_time: Optional[GetTimeCallable] = None, disable: bool = False, expand: bool = False) -> None:
        if console is None:
            console = exelog_console
        self.task_dict: Dict[int, Task] = {}

        super().__init__(*columns, console=console, auto_refresh=auto_refresh, refresh_per_second=refresh_per_second, speed_estimate_period=speed_estimate_period, transient=transient,
                         redirect_stdout=redirect_stdout, redirect_stderr=redirect_stderr, get_time=get_time, disable=disable, expand=expand)

    @staticmethod
    def handle_task(op_code: int, ref_op_code: int, description: str, total: int, completed: int, message: str = '') -> bool:
        description = "[bold gold1]" + description
        # filter op code
        if op_code & ref_op_code != 0:
            # new task to create
            if op_code & RemoteProgress.BEGIN != 0:
                MetaGitProgress().add_task(description, start=True, total=total, completed=completed)
                MetaGitProgress().task_dict[ref_op_code] = MetaGitProgress().tasks[-1]
            else:
                counting_task = MetaGitProgress().task_dict.get(ref_op_code)
                if counting_task is not None:
                    counting_task.completed = completed
                    if message:
                        description += f" • [green4]{message}"
                    counting_task.description = description
            if op_code & RemoteProgress.END != 0:
                MetaGitProgress().remove_task(MetaGitProgress().task_dict[ref_op_code].id)
            return True
        return False
