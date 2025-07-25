from rich.status import Status

from exegol.utils.ExeLog import console, ConsoleLock


class ExegolStatus(Status):

    def __init__(self, status: str, **kwargs) -> None:
        super().__init__(status, console=console, **kwargs)

    async def __aenter__(self) -> "ExegolStatus":
        await ConsoleLock.acquire()
        try:
            self.__enter__()
            return self
        except Exception as e:
            ConsoleLock.release()
            raise e

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.__exit__(exc_type, exc_val, exc_tb)
        finally:
            ConsoleLock.release()
