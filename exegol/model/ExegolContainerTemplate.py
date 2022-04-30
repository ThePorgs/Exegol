import os
from typing import Optional

from rich.prompt import Prompt

from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolImage import ExegolImage


class ExegolContainerTemplate:
    """Exegol template class used to create a new container"""

    def __init__(self, name: Optional[str], config: ContainerConfig, image: ExegolImage):
        if name is None:
            name = Prompt.ask("[bold blue][?][/bold blue] Enter the name of your new exegol container", default="default")
        assert name is not None
        self.name: str = name.replace('exegol-', '')
        self.hostname: str = name if name.startswith("exegol-") else f'exegol-{name}'
        self.image: ExegolImage = image
        self.config: ContainerConfig = config

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self):
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)
