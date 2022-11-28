import base64
import os
import shutil
from typing import Optional, Dict, Sequence, Tuple

from docker.errors import NotFound, ImageNotFound
from docker.models.containers import Container

from exegol.console.ExegolPrompt import Confirm
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, console


class ExegolContainer(ExegolContainerTemplate, SelectableInterface):
    """Class of an exegol container already create in docker"""

    def __init__(self, docker_container: Container, model: Optional[ExegolContainerTemplate] = None):
        logger.debug(f"== Loading container : {docker_container.name}")
        self.__container: Container = docker_container
        self.__id: str = docker_container.id
        self.__xhost_applied = False
        if model is None:
            image_name = ""
            try:
                # Try to find the attached docker image
                docker_image = docker_container.image
            except ImageNotFound:
                # If it is not found, the user has probably forcibly deleted it manually
                logger.warning(f"Some images were forcibly removed by docker when they were used by existing containers!")
                logger.error(f"The '{docker_container.name}' containers might not work properly anymore and should also be deleted and recreated with a new image.")
                docker_image = None
                image_name = "[red bold]BROKEN[/red bold]"
            # Create Exegol container from an existing docker container
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             image=ExegolImage(name=image_name, docker_image=docker_image))
            self.image.syncContainerData(docker_container)
            # At this stage, the container image object has an unknown status because no synchronization with a registry has been done.
            # This could be done afterwards (with container.image.autoLoad()) if necessary because it takes time.
            self.__new_container = False
        else:
            # Create Exegol container from a newly created docker container with its object template.
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             # Rebuild config from docker object to update workspace path
                             image=model.image)
            self.__new_container = True
        self.image.syncStatus()

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
            return "Unknown"
        elif status == "exited":
            return "[red]Stopped"
        elif status == "running":
            return "[green]Running"
        return status

    def isNew(self) -> bool:
        """Check if the container has just been created or not"""
        return self.__new_container

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
            self.preStartSetup()
            with console.status(f"Waiting to start {self.name}", spinner_style="blue"):
                self.__container.start()

    def stop(self, timeout: int = 10):
        """Stop the docker container"""
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            with console.status(f"Waiting to stop ({timeout}s timeout)", spinner_style="blue"):
                self.__container.stop(timeout=timeout)

    def spawnShell(self):
        """Spawn a shell on the docker container"""
        logger.info(f"Location of the exegol workspace on the host : {self.config.getHostWorkspacePath()}")
        for device in self.config.getDevices():
            logger.info(f"Shared host device: {device.split(':')[0]}")
        logger.success(f"Opening shell in Exegol '{self.name}'")
        # In case of multi-user environment, xhost must be set before opening each session to be sure
        self.__applyXhostACL()
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        envs = self.config.getShellEnvs()
        options = ""
        if len(envs) > 0:
            options += f" -e {' -e '.join(envs)}"
        cmd = f"docker exec{options} -ti {self.getFullId()} {self.config.getShellCommand()}"
        logger.debug(f"Opening shell with: {cmd}")
        os.system(cmd)
        # Docker SDK doesn't support (yet) stdin properly
        # result = self.__container.exec_run(ParametersManager().shell, stdout=True, stderr=True, stdin=True, tty=True,
        #                                    environment=self.config.getShellEnvs())
        # logger.debug(result)

    def exec(self, command: Sequence[str], as_daemon: bool = True, quiet: bool = False, is_tmp: bool = False):
        """Execute a command / process on the docker container.
        Set as_daemon to not follow the command stream and detach the execution
        Set quiet to disable logs message
        Set is_tmp if the container will automatically be removed after execution"""
        if not self.isRunning():
            self.start()
        if not quiet:
            logger.info("Executing command on Exegol")
            if logger.getEffectiveLevel() > logger.VERBOSE and not ParametersManager().daemon:
                logger.info("Hint: use verbose mode to see command output (-v).")
        exec_payload, str_cmd = ExegolContainer.formatShellCommand(command, quiet)
        stream = self.__container.exec_run(exec_payload, environment={"CMD": str_cmd, "DISABLE_AUTO_UPDATE": "true"}, detach=as_daemon, stream=not as_daemon)
        if as_daemon and not quiet:
            logger.success("Command successfully executed in background")
        else:
            try:
                # stream[0] : exit code
                # stream[1] : text stream
                for log in stream[1]:
                    logger.raw(log.decode("utf-8"))
                if not quiet:
                    logger.success("End of the command")
            except KeyboardInterrupt:
                if not quiet and not is_tmp:
                    logger.info("Detaching process logging")
                    logger.warning("Exiting this command does [red]NOT[/red] stop the process in the container")

    @staticmethod
    def formatShellCommand(command: Sequence[str], quiet: bool = False, entrypoint_mode: bool = False) -> Tuple[str, str]:
        """Generic method to format a shell command and support zsh aliases.
        Set quiet to disable any logging here.
        Set entrypoint_mode to start the command with the entrypoint.sh config loader.
        - The first return argument is the payload to execute with every pre-routine for zsh.
        - The second return argument is the command itself in str format."""
        # Using base64 to escape special characters
        str_cmd = ' '.join(command)
        if not quiet:
            logger.success(f"Command received: {str_cmd}")
        # ZSH pre-routine: Load zsh aliases and call eval to force aliases interpretation
        cmd = f'autoload -Uz compinit; compinit; source ~/.zshrc; eval $CMD'
        if not entrypoint_mode:
            # For direct execution, the full command must be supplied not just the zsh argument
            cmd = f"zsh -c '{cmd}'"
        return cmd, str_cmd

    def remove(self):
        """Stop and remove the docker container"""
        self.__removeVolume()
        self.stop(timeout=2)
        logger.info(f"Removing container {self.name}")
        try:
            self.__container.remove()
            logger.success(f"Container {self.name} successfully removed.")
        except NotFound:
            logger.error(
                f"The container {self.name} has already been removed (probably created as a temporary container).")

    def __removeVolume(self):
        """Remove private workspace volume directory if exist"""
        volume_path = self.config.getPrivateVolumePath()
        # TODO add backup
        if volume_path != '':
            if volume_path.startswith('/wsl/') or volume_path.startswith('\\wsl\\'):
                # Docker volume defines from WSL don't return the real path, they cannot be automatically removed
                # TODO review WSL workspace volume
                logger.warning("Warning: WSL workspace directory cannot be removed automatically.")
                return
            logger.verbose("Removing workspace volume")
            logger.debug(f"Removing volume {volume_path}")
            try:
                is_file_present = os.listdir(volume_path)
            except PermissionError:
                if Confirm(f"Insufficient permission to view workspace files {volume_path}, "
                           f"do you still want to delete them?", default=False):
                    # Set is_file_present as false to skip user prompt again
                    is_file_present = False
                else:
                    return
            try:
                if is_file_present:
                    # Directory is not empty
                    if not Confirm(f"Workspace [magenta]{volume_path}[/magenta] is not empty, do you want to delete it?",
                                   default=False):
                        # User can choose not to delete the workspace on the host
                        return
                # Try to remove files from the host with user permission (work only without sub-directory)
                shutil.rmtree(volume_path)
            except PermissionError:
                logger.info(f"Deleting the workspace files from the [green]{self.name}[/green] container as root")
                # If the host can't remove the container's file and folders, the rm command is exec from the container itself as root
                self.exec(["rm", "-rf", "/workspace"], as_daemon=False, quiet=True)
                try:
                    shutil.rmtree(volume_path)
                except PermissionError:
                    logger.warning(f"I don't have the rights to remove [magenta]{volume_path}[/magenta] (do it yourself)")
                    return
            except Exception as err:
                logger.error(err)
                return
            logger.success("Private workspace volume removed successfully")

    def preStartSetup(self):
        """
        Operation to be performed before starting a container
        :return:
        """
        self.__applyXhostACL()

    def postCreateSetup(self):
        """
        Operation to be performed after creating a container
        :return:
        """
        self.__applyXhostACL()

    def __applyXhostACL(self):
        """
        If GUI is enabled, allow X11 access on host ACL (if not already allowed) for linux and mac.
        On Windows host, WSLg X11 don't have xhost ACL.
        :return:
        """
        if self.config.isGUIEnable() and not self.__xhost_applied and not EnvInfo.isWindowsHost():
            self.__xhost_applied = True  # Can be applied only once per execution
            logger.debug(f"Adding xhost ACL to local:{self.hostname}")
            if EnvInfo.isMacHost():
                # add xquartz inet ACL
                with console.status(f"Starting XQuartz...", spinner_style="blue"):
                    os.system(f"xhost + localhost > /dev/null")
            else:
                # add linux local ACL
                os.system(f"xhost +local:{self.hostname} > /dev/null")
