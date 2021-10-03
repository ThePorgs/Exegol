from docker.models.containers import Container

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage


class ExegolContainer(ExegolContainerTemplate):

    def __init__(self, docker_container: Container, model: ExegolContainerTemplate = None):
        self.__container: Container = docker_container
        self.__id = docker_container.id
        if model is None:
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             image=ExegolImage(docker_image=docker_container.image))
        else:
            super().__init__(docker_container.name,
                             config=model.config,
                             image=model.image)

    def __str__(self):
        return f"{self.name} - {self.getTextStatus()} - {self.image.getName()} ({self.config})"

    def __getState(self):
        # self.__container.reload()
        return self.__container.attrs.get("State", {})

    def getTextStatus(self):
        return self.__getState().get("Status", "Unknown")

    def getStatus(self):
        status = self.getTextStatus().lower()
        if status == "unknown":
            return "[red]:question:[/red] Unknown"
        elif status == "exited":
            return ":stop_sign: Stopped"
        elif status == "running":
            return ":green_circle: Running"
        return status

    def getFullId(self):
        return self.__id

    def getId(self):
        return self.__id[:12]

    def start(self):
        self.__container.start()
        raise NotImplementedError

    def stop(self):
        self.__container.stop()
        raise NotImplementedError

    def exec(self):
        raise NotImplementedError

    def remove(self):
        raise NotImplementedError
