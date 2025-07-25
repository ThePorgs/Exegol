from typing import cast, Union

from rich.progress import Progress, Task, TaskID, ProgressColumn

from exegol.utils.ExeLog import console, ConsoleLock


class ExegolProgress(Progress):
    """Addition of a practical function to Rich Progress"""

    def __init__(self, *columns: Union[str, ProgressColumn], **kwargs) -> None:
        super().__init__(*columns, console=console, **kwargs)

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
