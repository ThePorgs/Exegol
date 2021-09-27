import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class ExeLog(logging.getLoggerClass()):
    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).debug("{}[D]{} {}".format("[yellow3]", "[/yellow3]", msg), *args, **kwargs)

    def verbose(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.getLevelName("VERBOSE")):
            self._log(logging.getLevelName("VERBOSE"),
                      "{}[V]{} {}".format("[blue]", "[/blue]", msg), args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).info("{}[*]{} {}".format("[bold blue]", "[/bold blue]", msg), *args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).warning("{}[!]{} {}".format("[bold orange3]", "[/bold orange3]", msg), *args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).error("{}[-]{} {}".format("[bold red]", "[/bold red]", msg), *args, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).exception("{}[x]{} {}".format("[red3]", "[/red3]", msg), *args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        super(ExeLog, self).critical("{}[X]{} {}".format("[bold dark_red]", "[/bold dark_red]", msg), *args, **kwargs)

    def success(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(logging.getLevelName("SUCCESS")):
            self._log(logging.getLevelName("SUCCESS"),
                      "{}[+]{} {}".format("[bold green]", "[/bold green]", msg), args, **kwargs)


logging.setLoggerClass(ExeLog)

logging.addLevelName(15, "VERBOSE")
logging.addLevelName(25, "SUCCESS")
logging.basicConfig(
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False, markup=True, show_level=False, show_path=False)]
)

logger: ExeLog = logging.getLogger("main")
logger.setLevel(logging.DEBUG)

console = Console()
