import os

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolImage import ExegolImage


class ExegolContainerTemplate:

    def __init__(self, name: str, config: ContainerConfig, image: ExegolImage):
        self.name = name.replace('exegol-', '')
        if not name.startswith("exegol-"):
            self.hostname = 'exegol-' + name
        else:
            self.hostname = name
        self.image = image
        self.config = config

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self):
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)
