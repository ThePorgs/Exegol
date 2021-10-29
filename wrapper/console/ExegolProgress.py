from rich.progress import Progress, Task, TaskID


class ExegolProgress(Progress):

    def getTask(self, task_id: TaskID) -> Task:
        """Return a specific task from task_id without error"""
        return self._tasks.get(task_id)
