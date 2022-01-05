import os
import shutil
from typing import Optional, Dict

from docker.errors import NotFound
from docker.models.containers import Container

from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.model.SelectableInterface import SelectableInterface
from wrapper.utils.ExeLog import logger


# Class of an existing exegol container
class ExegolContainer(ExegolContainerTemplate, SelectableInterface):

    def __init__(self, docker_container: Container, model: Optional[ExegolContainerTemplate] = None):
        logger.debug(f"== Loading container : {docker_container.name}")
        self.__container: Container = docker_container
        self.__id: str = docker_container.id
        if model is None:
            # Create Exegol container from an existing docker container
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             image=ExegolImage(docker_image=docker_container.image))
            self.image.syncContainer(docker_container)
        else:
            # Create Exegol container from a newly created docker container with his object template.
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             # Rebuild config from docker object to update workspace path
                             image=model.image)

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.getRawStatus()} - {super().__str__()}"

    def __getState(self) -> Dict:
        """Technical getter of the container status dict"""
        self.__container.reload()
        return self.__container.attrs.get("State", {})

    def getRawStatus(self) -> str:
        """Raw text getter of the container status"""
        return self.__getState().get("Status", "unknown")

    def getTextStatus(self) -> str:
        """Formatted text getter of the container status"""
        status = self.getRawStatus().lower()
        if status == "unknown":
            return "[red]:question:[/red] Unknown"
        elif status == "exited":
            return ":stop_sign: [red]Stopped"
        elif status == "running":
            return "[green]:play_button: [green]Running"
        return status

    def isRunning(self) -> bool:
        """Check is the container is running. Return bool."""
        return self.getRawStatus() == "running"

    def getFullId(self) -> str:
        """Container's id getter"""
        return self.__id

    def getId(self) -> str:
        """Container's short id getter"""
        return self.__container.short_id

    def getKey(self) -> str:
        """Universal unique key getter (from SelectableInterface)"""
        return self.name

    def start(self):
        """Start the docker container"""
        if not self.isRunning():
            logger.info(f"Starting container {self.name}")
            self.__container.start()

    def stop(self, timeout: int = 10):
        """Stop the docker container"""
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            self.__container.stop(timeout=timeout)

    def spawnShell(self):
        """Spawn a shell on the docker container"""
        logger.info(f"Location of the exegol workspace on the host : {self.config.getHostWorkspacePath()}")
        logger.success(f"Opening shell in Exegol '{self.name}'")
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        os.system("docker exec -ti {} {}".format(self.getFullId(), ParametersManager().shell))
        # Docker SDK dont support (yet) stdin properly
        # result = self.__container.exec_run("zsh", stdout=True, stderr=True, stdin=True, tty=True)
        # logger.debug(result)

    def exec(self, command: str, as_daemon: bool = True):
        """Execute a command / process on the docker container"""
        if not self.isRunning():
            self.start()
        logger.info("Executing command on Exegol")
        if logger.getEffectiveLevel() > logger.VERBOSE:
            logger.info("Hint: use verbose mode to see command output (-v).")
        # TODO fix ' char eval bug
        cmd = "zsh -c \"source /opt/.zsh_aliases; eval \'{}\'\"".format(
            command.replace("\"", "\\\"").replace("\'", "\\\'"))
        logger.debug(cmd)
        stream = self.__container.exec_run(cmd, detach=as_daemon, stream=not as_daemon)
        if as_daemon:
            logger.success("Command successfully executed in background")
        else:
            try:
                # stream[0] : exit code
                # stream[1] : text stream
                for log in stream[1]:
                    logger.raw(log.decode("utf-8"))
                logger.success("End of the command")
            except KeyboardInterrupt:
                logger.info("Detaching process logging")
                logger.warning("Exiting this command do NOT stop the process in the container")

    def remove(self):
        """Stop and remove the docker container"""
        self.stop(2)
        logger.info(f"Removing container {self.name}")
        try:
            self.__container.remove()
            logger.success(f"Container {self.name} successfully removed.")
        except NotFound:
            logger.error(
                f"The container {self.name} has already been removed (probably created as a temporary container).")
        self.__removeVolume()

    def __removeVolume(self):
        """Remove private workspace volume directory if exist"""
        volume_path = self.config.getPrivateVolumePath()
        if volume_path is not None:
            logger.verbose("Removing workspace volume")
            logger.debug(f"Removing volume {volume_path}")
            try:
                shutil.rmtree(volume_path)
                logger.success("Private workspace volume removed successfully")
            except PermissionError:
                logger.warning(f"I don't have the rights to remove {volume_path} (do it yourself)")
            except Exception as err:
                logger.error(err)
