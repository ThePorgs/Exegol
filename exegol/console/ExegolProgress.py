from typing import cast, Union

from rich.progress import Progress, Task, TaskID, ProgressColumn

from exegol.utils.ExeLog import ConsoleLock, ExeLog


class ExegolProgress(Progress):
    """Addition of a practical function to Rich Progress"""

    def __init__(self, *columns: Union[str, ProgressColumn], **kwargs) -> None:
        super().__init__(*columns, console=ExeLog.console, **kwargs)

    def getTask(self, task_id: TaskID) -> Task:
        """Return a specific task from task_id without error"""
        task = self._tasks.get(task_id)
        if task is None:
            # If task doesn't exist, raise IndexError exception
            raise IndexError
        return cast(Task, task)

    def __clear_tasks(self) -> None:
        """Remove every remaining task so no progress bar lingers after the context exits."""
        for task_id in list(self.task_ids):
            self.remove_task(task_id)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Generic cleanup: drop any leftover tasks BEFORE stopping so the final render is
        # empty and nothing stays on screen, regardless of how the operation ended.
        self.__clear_tasks()
        super(ExegolProgress, self).__exit__(exc_type, exc_val, exc_tb)

    def __enter__(self) -> "ExegolProgress":
        super(ExegolProgress, self).__enter__()
        return self

    async def __aenter__(self) -> "ExegolProgress":
        await ConsoleLock.acquire()
        try:
            super(ExegolProgress, self).__enter__()
            return self
        except Exception as e:
            ConsoleLock.release()
            raise e

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.__exit__(exc_type, exc_val, exc_tb)
        finally:
            ConsoleLock.release()
