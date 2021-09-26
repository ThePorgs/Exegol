from docker.models.containers import Container

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolImage import ExegolImage
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate


class ExegolContainer(ExegolContainerTemplate):

    def __init__(self, docker_container: Container):
        self.__container: Container = docker_container
        self.__id = docker_container.id
        super().__init__(docker_container.name,
                         config=ContainerConfig(docker_container),
                         image=ExegolImage(docker_image=docker_container.image))

    def __str__(self):
        return f"{self.name} - {self.getStatus()} - {self.image.getName()} ({self.config})"

    def __getState(self):
        # self.__container.reload()
        return self.__container.attrs.get("State", {})

    def getStatus(self):
        return self.__getState().get("Status", "Unknown")

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def exec(self):
        raise NotImplementedError

    def remove(self):
        raise NotImplementedError
