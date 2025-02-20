import os
from typing import Optional

from rich.prompt import Prompt

from exegol.config.EnvInfo import EnvInfo
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolImage import ExegolImage


class ExegolContainerTemplate:
    """Exegol template class used to create a new container"""

    def __init__(self, name: Optional[str], config: ContainerConfig, image: ExegolImage, hostname: Optional[str] = None, new_container: bool = True):
        if name is None:
            name = Prompt.ask("[bold blue][?][/bold blue] Enter the name of your new exegol container", default="default")
        assert name is not None
        if (EnvInfo.isWindowsHost() or EnvInfo.isMacHost()) and not name.startswith("exegol-"):
            # Force container as lowercase because the filesystem of windows / mac are case-insensitive => https://github.com/ThePorgs/Exegol/issues/167
            name = name.lower()
        self.container_name: str = name if name.startswith("exegol-") else f'exegol-{name}'
        self.name: str = name.replace('exegol-', '')
        self.image: ExegolImage = image
        self.config: ContainerConfig = config
        if hostname:
            self.config.hostname = hostname
            if new_container:
                self.config.addEnv(ContainerConfig.ExegolEnv.exegol_name.value, self.container_name)
        else:
            self.config.hostname = self.container_name

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self) -> None:
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)

    def rollback(self) -> None:
        """Rollback change in case of container creation fail."""
        self.config.rollback_preparation(self.name)

    def getDisplayName(self) -> str:
        """Getter of the container's name for TUI purpose"""
        if self.container_name != self.config.hostname:
            return f"{self.name} [bright_black]({self.config.hostname})[/bright_black]"
        return self.name

    def getTextStatus(self) -> str:
        return ""
