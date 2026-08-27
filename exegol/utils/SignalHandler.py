import asyncio
import signal
from contextlib import contextmanager
from types import FrameType
from typing import Any, Generator, Optional

from exegol.utils.ExeLog import logger


class SignalHandler:
    """Centralized SIGINT (Ctrl+C) handling for the exegol wrapper.

    Since Python 3.11, asyncio.run() installs its own SIGINT handler: the first Ctrl+C only
    requests the cancellation of the main task, and that cancellation is delivered at the next
    await point. Every blocking call running on the main thread (rich prompts, docker SDK calls,
    sleeps, thread joins) therefore swallows the first Ctrl+C, forcing the user to press it twice.
    asyncio.Runner only installs its handler when SIGINT is still bound to the default handler,
    so registering our own opts out of that behavior."""

    # Main asyncio task, the interruption must be delivered inside it to allow a graceful shutdown
    __main_task: Optional["asyncio.Task[Any]"] = None
    # True once the cancellation of the main task has been requested
    __interrupt_requested: bool = False
    # Depth of the critical sections currently running (see protect())
    __protection_depth: int = 0
    # Number of SIGINT received while the outermost critical section was running
    __deferred_signals: int = 0

    @classmethod
    def install(cls) -> None:
        """Register the exegol SIGINT handler. Must be called from the main thread, before asyncio.run()."""
        try:
            signal.signal(signal.SIGINT, cls.__on_sigint)
        except ValueError:
            # signal.signal() is only available from the main thread of the main interpreter
            logger.debug("Unable to register the SIGINT handler from the current thread.")

    @classmethod
    def attach_main_task(cls, task: Optional["asyncio.Task[Any]"]) -> None:
        """Register the main asyncio task the interruption must be delivered to."""
        cls.__main_task = task
        cls.__interrupt_requested = False

    @classmethod
    def __on_sigint(cls, signum: int, frame: Optional[FrameType]) -> None:
        """Deliver a user interruption inside the main coroutine, whatever it is currently doing."""
        if cls.__protection_depth > 0:
            cls.__deferred_signals += 1
            if cls.__deferred_signals == 1:
                # Let the critical section finish, protect() will re-raise the interruption once done
                cls.__warn_forced_exit("Waiting for critical background tasks to complete.")
                return
            cls.__warn_forced_exit()
            raise KeyboardInterrupt

        main_task = cls.__main_task
        if main_task is not None and not main_task.done():
            try:
                running_task = asyncio.current_task()
            except RuntimeError:
                running_task = None
            if running_task is not main_task:
                # Either the event loop is idle, or a background task is currently running: raising
                # here would escape the main coroutine and skip its graceful shutdown. Request a
                # cancellation instead, the loop will deliver a CancelledError inside the coroutine.
                if not cls.__interrupt_requested:
                    cls.__interrupt_requested = True
                    main_task.cancel()
                    # Wake up the loop if it is blocked in a long select()
                    main_task.get_loop().call_soon_threadsafe(lambda: None)
                    return
                # The main coroutine is still stuck despite the previous interruption, force the exit
                cls.__warn_forced_exit()
        # A main coroutine step is running (i.e. blocked in synchronous code): raising here aborts
        # the blocking call and lands the KeyboardInterrupt inside the main coroutine.
        raise KeyboardInterrupt

    @staticmethod
    def __warn_forced_exit(message: Optional[str] = None) -> None:
        """Tell the user what is happening and how to force the exit."""
        logger.empty_line()
        if message is None:
            logger.warning("Forced exit requested, some background tasks might not have completed.")
        else:
            logger.warning(f"{message} Press [red]Ctrl+C[/red] again to force the exit.")

    @classmethod
    @contextmanager
    def protect(cls) -> Generator[None, None, None]:
        """Defer any user interruption until the end of the critical section.

        A single Ctrl+C received while protected is held back and re-raised once the section is
        over, so that critical background tasks (e.g. license session refresh holding a
        cross-process lock) always complete. A second Ctrl+C forces the interruption."""
        cls.__protection_depth += 1
        if cls.__protection_depth == 1:
            cls.__deferred_signals = 0
        try:
            yield
        except BaseException:
            cls.__protection_depth -= 1
            raise
        cls.__protection_depth -= 1
        if cls.__protection_depth == 0 and cls.__deferred_signals > 0:
            cls.__deferred_signals = 0
            raise KeyboardInterrupt
