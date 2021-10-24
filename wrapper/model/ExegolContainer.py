import os

from docker.models.containers import Container

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ExeLog import logger


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
        return f"{self.name} - {self.getRawStatus()} - {self.image.getName()} ({self.config})"

    def __getState(self):
        self.__container.reload()
        return self.__container.attrs.get("State", {})

    def getRawStatus(self):
        return self.__getState().get("Status", "unknown")

    def getTextStatus(self):
        status = self.getRawStatus().lower()
        if status == "unknown":
            return "[red]:question:[/red] Unknown"
        elif status == "exited":
            return ":stop_sign: [red]Stopped"
        elif status == "running":
            return "[green]:play_button: [green]Running"
        return status

    def isRunning(self):
        return self.getRawStatus() == "running"

    def getFullId(self):
        return self.__id

    def getId(self):
        return self.__container.short_id

    def start(self):
        logger.info(f"Starting container {self.name}")
        self.__container.start()

    def stop(self):
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            self.__container.stop()

    def spawnShell(self):
        logger.success(f"Opening shell in Exegol '{self.name}'")
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        os.system("docker exec -ti {} {}".format(self.__id, "zsh"))  # TODO Add shell option
        # Docker SDK dont support (yet) stdin properly
        # result = self.__container.exec_run("zsh", stdout=True, stderr=True, stdin=True, tty=True)
        # logger.debug(result)

    def exec(self):
        raise NotImplementedError

    def remove(self):
        self.stop()
        logger.verbose("Removing container")
        self.__container.remove()
        logger.success(f"Container {self.name} successfully removed.")
