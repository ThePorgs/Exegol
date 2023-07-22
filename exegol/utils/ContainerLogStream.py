import asyncio
import concurrent.futures
import threading
import time
from datetime import datetime, timedelta
from typing import Union, List, Any, Optional

from docker.models.containers import Container
from docker.types import CancellableStream

from exegol.utils.ExeLog import logger


class ContainerLogStream:

    def __init__(self, container: Container, start_date: Optional[datetime] = None, timeout: int = 5):
        self.__container = container
        self.__start_date: datetime = datetime.utcnow() if start_date is None else start_date
        self.__until_date: Optional[datetime] = None
        self.__data_stream = None
        self.__line_buffer = b''

        self.__enable_timeout = timeout > 0
        self.__timeout_date: datetime = self.__start_date + timedelta(seconds=timeout)

    def __iter__(self):
        return self

    def __next__(self):
        data = self.next_line()
        if data is None:
            raise StopIteration
        return data

    def next_line(self) -> Optional[str]:
        """Get the next line of the stream"""
        if self.__until_date is None:
            self.__until_date = datetime.utcnow()
        while True:
            if self.__data_stream is None:
                # The 'follow' mode cannot be used because there is no timeout mechanism and will stuck the process forever
                self.__data_stream = self.__container.logs(stream=True, follow=False, since=self.__start_date, until=self.__until_date)
            for streamed_char in self.__data_stream:
                if (streamed_char == b'\r' or streamed_char == b'\n') and len(self.__line_buffer) > 0:
                    line = self.__line_buffer.decode('utf-8').strip()
                    self.__line_buffer = b""
                    return line
                else:
                    self.__enable_timeout = False  # disable timeout if the container is up-to-date and support console logging
                    self.__line_buffer += streamed_char
            if self.__enable_timeout and self.__until_date >= self.__timeout_date:
                logger.debug("Container log stream timed-out")
                return None
            self.__data_stream = None
            self.__start_date = self.__until_date
            time.sleep(0.5)
            self.__until_date = datetime.utcnow()
