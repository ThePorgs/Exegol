import os
import shutil

from docker.models.containers import Container

from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.model.SelectableInterface import SelectableInterface
from wrapper.utils.ExeLog import logger


class ExegolContainer(ExegolContainerTemplate, SelectableInterface):

    def __init__(self, docker_container: Container, model: ExegolContainerTemplate = None):
        self.__container: Container = docker_container
        self.__id = docker_container.id
        if model is None:
            # Create Exegol container from an existing docker container
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             image=ExegolImage(docker_image=docker_container.image))
        else:
            # Create Exegol container from a newly created docker container with his object template.
            super().__init__(docker_container.name,
                             config=model.config,
                             image=model.image)

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.getRawStatus()} - {super().__str__()}"

    def __getState(self):
        """Technical getter of the container status dict"""
        self.__container.reload()
        return self.__container.attrs.get("State", {})

    def getRawStatus(self):
        """Raw text getter of the container status"""
        return self.__getState().get("Status", "unknown")

    def getTextStatus(self):
        """Formatted text getter of the container status"""
        status = self.getRawStatus().lower()
        if status == "unknown":
            return "[red]:question:[/red] Unknown"
        elif status == "exited":
            return ":stop_sign: [red]Stopped"
        elif status == "running":
            return "[green]:play_button: [green]Running"
        return status

    def isRunning(self):
        """Check is the container is running. Return bool."""
        return self.getRawStatus() == "running"

    def getFullId(self):
        """Container's id getter"""
        return self.__id

    def getId(self):
        """Container's short id getter"""
        return self.__container.short_id

    def getKey(self):
        """Universal unique key getter (from SelectableInterface)"""
        return self.name

    def start(self):
        """Start the docker container"""
        logger.info(f"Starting container {self.name}")
        self.__container.start()

    def stop(self, timeout=10):
        """Stop the docker container"""
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            self.__container.stop(timeout=timeout)

    def spawnShell(self):
        """Spawn a shell on the docker container"""
        logger.info(f"Location of the exegol workspace on the host : {self.config.getHostWorkspacePath()}")
        logger.success(f"Opening shell in Exegol '{self.name}'")
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        os.system("docker exec -ti {} {}".format(self.getFullId(), "zsh"))  # TODO Add shell option
        # Docker SDK dont support (yet) stdin properly
        # result = self.__container.exec_run("zsh", stdout=True, stderr=True, stdin=True, tty=True)
        # logger.debug(result)

    def exec(self, command, as_daemon=True):
        """Execute a command / process on the docker container"""
        if not self.isRunning():
            self.start()
        logger.info("Executing command on Exegol")
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
        logger.verbose("Removing container")
        self.__container.remove()
        logger.success(f"Container {self.name} successfully removed.")
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
