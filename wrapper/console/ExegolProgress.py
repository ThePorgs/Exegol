from rich.progress import Progress


class ExegolProgress(Progress):

    def getTask(self, task_id):
        """Return a specific task from task_id without error"""
        return self._tasks.get(task_id)
