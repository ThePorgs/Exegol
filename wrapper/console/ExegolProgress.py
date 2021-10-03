from rich.progress import Progress


class ExegolProgress(Progress):

    def getTask(self, task_id):  # Safe search of progress task
        return self._tasks.get(task_id)
