import os
from typing import Optional

from rich.prompt import Prompt

from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolImage import ExegolImage


class ExegolContainerTemplate:
    """Exegol template class used to create a new container"""

    def __init__(self, name: Optional[str], config: ContainerConfig, image: ExegolImage, hostname: Optional[str] = None):
        if name is None:
            name = Prompt.ask("[bold blue][?][/bold blue] Enter the name of your new exegol container", default="default")
        assert name is not None
        self.container_name: str = name if name.startswith("exegol-") else f'exegol-{name}'
        self.name: str = name.replace('exegol-', '')
        if hostname:
            self.hostname: str = hostname
        else:
            self.hostname = self.container_name
        self.image: ExegolImage = image
        self.config: ContainerConfig = config

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self):
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)

    def getDisplayName(self) -> str:
        """Getter of the container's name for TUI purpose"""
        if self.container_name != self.hostname:
            return f"{self.name} [bright_black]({self.hostname})[/bright_black]"
        return self.name
