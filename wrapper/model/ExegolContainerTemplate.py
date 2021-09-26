from model.ContainerConfig import ContainerConfig
from model.ExegolImage import ExegolImage


class ExegolContainerTemplate:

    def __init__(self, name: str, config: ContainerConfig, image: ExegolImage = None):
        self.name = name.replace('exegol-', '')
        self.image = image
        self.config = config

    def __str__(self):
        return f"{self.name} - {self.image.getName()} ({self.config})"
