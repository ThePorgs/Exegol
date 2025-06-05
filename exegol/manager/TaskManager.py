import asyncio
import threading
from asyncio import Task
from enum import Enum
from threading import Thread
from typing import Coroutine, Dict, Optional, Any, Tuple, List, Set, cast

from exegol.utils.ExeLog import logger


class TaskManager:
    class TaskId(Enum):
        RemoteImageList = "remote_image_list"
        LocalImageList = "local_image_list"
        ImageList = "image_list"
        ContainerList = "container_list"
        LoadLicense = "load_license"
        # Threaded tasks
        RefreshSession = "session_refresh"  # Sub-task of LoadLicense

    __named_tasks: Dict[TaskId, Task] = {}
    __named_threads: Dict[TaskId, threading.Thread] = {}
    __tasks: Set[Task] = set()

    __waitable_tasks: Set[str] = {TaskId.LoadLicense.value}
    __threaded_tasks: Set[TaskId] = {TaskId.RefreshSession}

    @classmethod
    def add_task(cls, task_function: Coroutine, task_id: Optional[TaskId] = None) -> None:
        if task_id is not None:
            # Adding named tasks to the task manager
            if cls.__named_tasks.get(task_id) is None:
                logger.debug(f"Creating new {task_id} background task.")
                if task_id in cls.__threaded_tasks:
                    cls.__named_threads[task_id] = cls.__coro_to_thread(task_function, name=task_id.value)
                else:
                    cls.__named_tasks[task_id] = asyncio.create_task(task_function, name=task_id.value)
            else:
                logger.error(f"Task {task_id} already exists.")
        else:
            # Adding unnamed background tasks to the task manager
            new_task = asyncio.create_task(task_function)
            cls.__tasks.add(new_task)
            new_task.add_done_callback(cls.__tasks.discard)

    @classmethod
    async def wait_for(cls, task_id: TaskId, clean_task: bool = True) -> Any:
        if task_id in cls.__threaded_tasks:
            # Wait for the thread
            thread = cls.__named_threads.get(task_id)
            if thread is not None:
                await asyncio.to_thread(thread.join)
                if clean_task:
                    cls.__named_threads.pop(task_id)
        else:
            # Wait for the task
            task: Optional[Task] = cls.__named_tasks.get(task_id)
            if task is not None:
                await task
                if clean_task:
                    cls.__named_tasks.pop(task_id)
                return task.result()
        return None

    @classmethod
    async def gather(cls, *tasks: TaskId, clean_task: bool = True) -> Tuple[Any, ...]:
        all_tasks = []
        for t in tasks:
            current_task = cls.__named_tasks.get(t)
            if current_task is not None:
                all_tasks.append(current_task)
        results = await asyncio.gather(*all_tasks)
        if clean_task:
            for t in tasks:
                if t in cls.__named_tasks:
                    cls.__named_tasks.pop(t)
        return tuple(results)

    @staticmethod
    def __coro_to_thread(task: Coroutine, name: str) -> Thread:
        try:
            import asyncio
            import sys

            def run_in_thread(tasks: Coroutine) -> None:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(tasks)
                except (EOFError, KeyboardInterrupt, SystemExit) as err:
                    # Ignore exit from thread
                    logger.debug(f"Received exit signal from thread. Exiting thread: {type(err)} {err}")
                finally:
                    new_loop.close()
                    logger.debug("Thread closing")

            import threading
            license_thread = threading.Thread(target=run_in_thread, args=(task,), name=name, daemon=False)
            license_thread.start()

            return license_thread
        except Exception as e:
            logger.critical(f"Error during license tasks execution: {e}")
            raise

    @classmethod
    async def wait_for_all(cls, exit_mode: bool = False) -> None:
        tasks: List[Task] = []
        threads: List[Thread] = []
        for t in cls.__tasks.copy():
            if not t.done() and not t.cancelled():
                tasks.append(t)
        for t in cls.__named_tasks.values():
            if (t.get_name() in cls.__waitable_tasks and
                    not t.done() and not t.cancelled()):
                tasks.append(t)
            else:
                t.cancel()
        for th in cls.__named_threads.values():
            if th.is_alive():
                threads.append(th)

        if (len(tasks) + len(threads)) > 0:
            warning_sent = False
            logger.debug(f"Waiting for {len(tasks) + len(threads)} tasks")
            if len(threads) > 0:
                for th in threads:
                    if not th.is_alive():
                        continue
                    logger.debug(f"Waiting for {th.name} background task")
                    th.join(timeout=2 if exit_mode else 5)  # Max 10 seconds
                    if th.is_alive():
                        if not warning_sent:
                            logger.warning("Please wait for background tasks to complete.")
                            warning_sent = True
                        th.join(timeout=10)
            if len(tasks) > 0:
                logger.debug(f"Waiting for {', '.join([t.get_name() for t in tasks if not t.done()])} background task")
                # Task will not be awaited if the current context is canceled by user exit
                await asyncio.gather(*tasks)
            logger.debug(f"All background tasks done")

    @classmethod
    def sync_wait(cls, coroutine: Coroutine) -> Any:
        asyncio.run(coroutine)
