import os

from rich.prompt import Prompt

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolImage import ExegolImage


# Class template used to create a new container
class ExegolContainerTemplate:

    def __init__(self, name: str, config: ContainerConfig, image: ExegolImage):
        if name is None:
            name = Prompt.ask("[blue][?][/blue] Enter the name of your new exegol container", default="default")
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
