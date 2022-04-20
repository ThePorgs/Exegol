import logging
import os
from typing import Any, cast

from rich.console import Console
from rich.logging import RichHandler


# Customized logging class
class ExeLog(logging.Logger):
    """Project's Logger custom class"""
    # New logging level
    SUCCESS: int = 25
    VERBOSE: int = 15
    ADVANCED: int = 13

    @staticmethod
    def setVerbosity(verbose: int, quiet: bool = False):
        """Set logging level accordingly to the verbose count or with quiet enable."""
        if quiet:
            logger.setLevel(logging.CRITICAL)
        elif verbose == 1:
            logger.setLevel(ExeLog.VERBOSE)
        elif verbose == 2:
            logger.setLevel(ExeLog.ADVANCED)
        elif verbose >= 3:
            logger.setLevel(logging.DEBUG)
        else:
            # Default INFO
            logger.setLevel(logging.INFO)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default debug text format with rich color support"""
        super(ExeLog, self).debug("{}[D]{} {}".format("[bold yellow3]", "[/bold yellow3]", msg), *args, **kwargs)

    def advanced(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Add advanced logging method with text format / rich color support"""
        if self.isEnabledFor(ExeLog.ADVANCED):
            self._log(ExeLog.ADVANCED,
                      "{}[A]{} {}".format("[bold yellow3]", "[/bold yellow3]", msg), args, **kwargs)

    def verbose(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Add verbose logging method with text format / rich color support"""
        if self.isEnabledFor(ExeLog.VERBOSE):
            self._log(ExeLog.VERBOSE,
                      "{}[V]{} {}".format("[bold blue]", "[/bold blue]", msg), args, **kwargs)

    def raw(self, msg: Any, level=VERBOSE, markup=False, highlight=False, emoji=False, rich_parsing=False) -> None:
        """Add raw text logging, used for stream printing."""
        if rich_parsing:
            markup = True
            highlight = True
            emoji = True
        if self.isEnabledFor(level):
            if type(msg) is bytes:
                msg = msg.decode('utf-8', errors="ignore")
            # Raw message are print directly to the console bypassing logging system and auto formatting
            console.print(msg, end='', markup=markup, highlight=highlight, emoji=emoji)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default info text format with rich color support"""
        super(ExeLog, self).info("{}[*]{} {}".format("[bold blue]", "[/bold blue]", msg), *args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default warning text format with rich color support"""
        super(ExeLog, self).warning("{}[!]{} {}".format("[bold orange3]", "[/bold orange3]", msg), *args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default error text format with rich color support"""
        super(ExeLog, self).error("{}[-]{} {}".format("[bold red]", "[/bold red]", msg), *args, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default exception text format with rich color support"""
        super(ExeLog, self).exception("{}[x]{} {}".format("[bold red]", "[/bold red]", msg), *args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default critical text format with rich color support
        Add auto exit."""
        super(ExeLog, self).critical("{}[!]{} {}".format("[bold red]", "[/bold red]", msg), *args, **kwargs)
        exit(1)

    def success(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Add success logging method with text format / rich color support"""
        if self.isEnabledFor(ExeLog.SUCCESS):
            self._log(ExeLog.SUCCESS,
                      "{}[+]{} {}".format("[bold green]", "[/bold green]", msg), args, **kwargs)

    def empty_line(self) -> None:
        """Print an empty line."""
        self.raw(os.linesep, level=logging.INFO)


# Global rich console object
console: Console = Console()

# Main logging default config
# Set default Logger class as ExeLog
logging.setLoggerClass(ExeLog)

# Add new level to the logging config
logging.addLevelName(ExeLog.VERBOSE, "VERBOSE")
logging.addLevelName(ExeLog.SUCCESS, "SUCCESS")
logging.addLevelName(ExeLog.ADVANCED, "ADVANCED")
# Logging setup using RichHandler and minimalist text format
logging.basicConfig(
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True,
                          show_time=False,
                          markup=True,
                          show_level=False,
                          show_path=False,
                          console=console)]
)

# Global logger object
logger: ExeLog = cast(ExeLog, logging.getLogger("main"))
# Default log level
logger.setLevel(logging.INFO)
