from typing import cast

from rich.progress import Progress, Task, TaskID


class ExegolProgress(Progress):
    """Addition of a practical function to Rich Progress"""

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
