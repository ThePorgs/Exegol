import os
from typing import Optional

from exegol.config.EnvInfo import EnvInfo
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolImage import ExegolImage


class ExegolContainerTemplate:
    """Exegol template class used to create a new container"""

    def __init__(self, name: str, image: ExegolImage, config: ContainerConfig):
        assert name is not None
        if (EnvInfo.isWindowsHost() or EnvInfo.isMacHost()) and not name.startswith("exegol-"):
            # Force container as lowercase because the filesystem of windows / mac are case-insensitive => https://github.com/ThePorgs/Exegol/issues/167
            name = name.lower()
        while name.startswith("exegol-"):
            name = name[7:]
        self.name: str = name
        self.image: ExegolImage = image
        self.config: ContainerConfig = config

    @classmethod
    async def newContainer(cls, name: str, image: ExegolImage, config: Optional[ContainerConfig] = None, hostname: Optional[str] = None) -> "ExegolContainerTemplate":
        container_name: str = name if name.startswith("exegol-") else f'exegol-{name}'
        if config is None:
            config = await ContainerConfig(container_name=container_name, hostname=hostname).configFromUser()
        return cls(name, image, config)

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"{self.name} - {self.image.getName()}{os.linesep}{self.config}"

    def prepare(self) -> None:
        """Prepare the model before creating the docker container"""
        self.config.prepareShare(self.name)

    def rollback(self) -> None:
        """Rollback change in case of container creation fail."""
        self.config.rollback_preparation(self.name)

    def getContainerName(self) -> str:
        return self.config.container_name

    def getDisplayName(self) -> str:
        """Getter of the container's name for TUI purpose"""
        if self.getContainerName() != self.config.hostname:
            return f"{self.name} [bright_black]({self.config.hostname})[/bright_black]"
        return self.name

    def isRunning(self) -> bool:
        """Interface for running status getter"""
        raise NotImplementedError

    def getTextStatus(self) -> str:
        return ""
