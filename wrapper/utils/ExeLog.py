import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class ExeLog(logging.getLoggerClass()):
    """Project's Logger custom class"""
    # New logging level
    VERBOSE = 15
    SUCCESS = 25

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default debug text format with rich color support"""
        super(ExeLog, self).debug("{}[D]{} {}".format("[yellow3]", "[/yellow3]", msg), *args, **kwargs)

    def verbose(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Add verbose logging method with text format / rich color support"""
        if self.isEnabledFor(ExeLog.VERBOSE):
            self._log(ExeLog.VERBOSE,
                      "{}[V]{} {}".format("[blue]", "[/blue]", msg), args, **kwargs)

    def raw(self, msg: Any, level=VERBOSE) -> None:
        """Add raw text logging, used for stream printing."""
        if self.isEnabledFor(level):
            if type(msg) is bytes:
                msg = msg.decode('utf-8', errors="ignore")
            # Raw message are print directly to the console bypassing logging system and auto formatting
            console.print(msg, end='', markup=False, highlight=False, emoji=False)

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
        super(ExeLog, self).exception("{}[x]{} {}".format("[red3]", "[/red3]", msg), *args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Change default critical text format with rich color support
        Add auto exit."""
        super(ExeLog, self).critical("{}[X]{} {}".format("[bold dark_red]", "[/bold dark_red]", msg), *args, **kwargs)
        exit(1)

    def success(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Add success logging method with text format / rich color support"""
        if self.isEnabledFor(ExeLog.SUCCESS):
            self._log(ExeLog.SUCCESS,
                      "{}[+]{} {}".format("[bold green]", "[/bold green]", msg), args, **kwargs)


# Main logging default config
# Set default Logger class as ExeLog
logging.setLoggerClass(ExeLog)

# Add new level to the logging config
logging.addLevelName(ExeLog.VERBOSE, "VERBOSE")
logging.addLevelName(ExeLog.SUCCESS, "SUCCESS")
# Logging setup using RichHandler and minimalist text format
logging.basicConfig(
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False, markup=True, show_level=False, show_path=False)]
)

# Global logger object
logger: ExeLog = logging.getLogger("main")
# Default log level
logger.setLevel(logging.INFO)

# Global rich console object
console = Console()
