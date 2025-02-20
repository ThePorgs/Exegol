import time
from datetime import datetime, timedelta
from typing import Optional

from docker.models.containers import Container

from exegol.utils.ExeLog import logger


class ContainerLogStream:

    def __init__(self, container: Container, start_date: Optional[datetime] = None, timeout: int = 5):
        # Container to extract logs from
        self.__container = container
        # Fetch more logs from this datetime
        self.__start_date: datetime = datetime.now() if start_date is None else start_date
        self.__since_date = self.__start_date
        self.__until_date: Optional[datetime] = None
        # The data stream is returned from the docker SDK. It can contain multiple line at the same.
        self.__data_stream = None
        self.__line_buffer = b''

        # Enable timeout if > 0. Passed timeout_date, the iterator will stop.
        self.__enable_timeout = timeout > 0
        self.__timeout_date: datetime = self.__since_date + timedelta(seconds=timeout)

        # Hint message flag
        self.__tips_sent = False
        self.__tips_timedelta = self.__start_date + timedelta(seconds=30)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        """Get the next line of the stream"""
        if self.__until_date is None:
            self.__until_date = datetime.now()
        while True:
            # The data stream is fetch from the docker SDK once empty.
            if self.__data_stream is None:
                # The 'follow' mode cannot be used because there is no timeout mechanism and will stuck the process forever
                self.__data_stream = self.__container.logs(stream=True, follow=False, since=self.__since_date, until=self.__until_date)
            assert self.__data_stream is not None
            # Parsed the data stream to extract characters and merge them into a line.
            for streamed_char in self.__data_stream:
                self.__enable_timeout = False  # disable timeout if the container is up-to-date and support console logging
                # Add new char to the buffer + Unify \r\n to \n
                self.__line_buffer += streamed_char.replace(b'\r\n', b'\n')
                # When detecting an end of line, the buffer is returned as a single line.
                if b'\n' in self.__line_buffer:
                    lines = self.__line_buffer.split(b'\n')
                    self.__line_buffer = b'\n'.join(lines[1:]) if len(lines) > 1 else b''
                    if len(lines[0]) > 0:
                        return lines[0].decode('utf-8').strip()
            # When the data stream is empty, check if a timeout condition apply
            if self.__enable_timeout and self.__until_date >= self.__timeout_date:
                logger.debug("Container log stream timed-out")
                raise StopIteration
            elif not self.__tips_sent and self.__until_date >= self.__tips_timedelta:
                self.__tips_sent = True
                logger.info("Your start-up sequence takes time, your my-resource setup configuration may be significant.")
                logger.info("[orange3][Tips][/orange3] If you want to skip startup update, "
                            "you can use [green]CTRL+C[/green] and spawn a shell immediately. "
                            "[blue](Startup sequence will continue in background)[/blue]")
            # Prepare the next iteration to fetch next logs
            self.__data_stream = None
            self.__since_date = self.__until_date
            time.sleep(1)  # Wait for more logs
            self.__until_date = datetime.now()
