import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, Dict, Sequence, Tuple, Union

from docker.errors import NotFound, ImageNotFound, APIError
from docker.models.containers import Container

from exegol.config.EnvInfo import EnvInfo
from exegol.console.ExegolPrompt import Confirm
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.ContainerLogStream import ContainerLogStream
from exegol.utils.ExeLog import logger, console
from exegol.utils.GuiUtils import GuiUtils
from exegol.utils.imgsync.ImageScriptSync import ImageScriptSync


class ExegolContainer(ExegolContainerTemplate, SelectableInterface):
    """Class of an exegol container already create in docker"""

    def __init__(self, docker_container: Container, model: Optional[ExegolContainerTemplate] = None):
        logger.debug(f"Loading container: {docker_container.name}")
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
                             image=ExegolImage(name=image_name, docker_image=docker_image),
                             hostname=docker_container.attrs.get('Config', {}).get('Hostname'),
                             new_container=False)
            self.image.syncContainerData(docker_container)
            # At this stage, the container image object has an unknown status because no synchronization with a registry has been done.
            # This could be done afterwards (with container.image.autoLoad()) if necessary because it takes time.
            self.__new_container = False
        else:
            # Create Exegol container from a newly created docker container with its object template.
            super().__init__(docker_container.name,
                             config=ContainerConfig(docker_container),
                             # Rebuild config from docker object to update workspace path
                             image=model.image,
                             hostname=model.config.hostname,
                             new_container=False)
            self.__new_container = True
        self.image.syncStatus()

    def __str__(self) -> str:
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
            return "[red]Stopped[/red]"
        elif status == "running":
            return "[green]Running[/green]"
        return f"[orange3]{status}[/orange3]"

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

    def start(self) -> None:
        """Start the docker container"""
        if not self.isRunning():
            logger.info(f"Starting container {self.name}")
            self.__start_container()
            self.__postStartSetup()

    def __start_container(self) -> None:
        """
        This method starts the container and displays startup status updates to the user.
        :return:
        """
        with console.status(f"Waiting to start {self.name}", spinner_style="blue") as progress:
            start_date = datetime.now()
            try:
                self.__container.start()
            except APIError as e:
                logger.debug(e)
                logger.critical(f"Docker raised a critical error when starting the container [green]{self.name}[/green], error message is: {e.explanation}")
            if not self.config.legacy_entrypoint:  # TODO improve startup compatibility check
                try:
                    # Try to find log / startup messages. Will time out after 2 seconds if the image don't support status update through container logs.
                    for line in ContainerLogStream(self.__container, start_date=start_date, timeout=2):
                        # Once the last log "READY" is received, the startup sequence is over and the execution can continue
                        if line == "READY":
                            break
                        elif line.startswith('[INFO]'):
                            line = line.replace('[INFO]', '')
                            logger.info(line)
                        elif line.startswith('[VERBOSE]'):
                            line = line.replace('[VERBOSE]', '')
                            logger.verbose(line)
                        elif line.startswith('[ADVANCED]'):
                            line = line.replace('[ADVANCED]', '')
                            logger.advanced(line)
                        elif line.startswith('[DEBUG]'):
                            line = line.replace('[DEBUG]', '')
                            logger.debug(line)
                        elif line.startswith('[WARNING]'):
                            line = line.replace('[WARNING]', '')
                            logger.warning(line)
                        elif line.startswith('[ERROR]'):
                            line = line.replace('[ERROR]', '')
                            logger.error(line)
                        elif line.startswith('[SUCCESS]'):
                            line = line.replace('[SUCCESS]', '')
                            logger.success(line)
                        elif line.startswith('[PROGRESS]'):
                            line = line.replace('[PROGRESS]', '')
                            logger.verbose(line)
                            progress.update(status=f"[blue][Startup][/blue] {line}")
                        else:
                            logger.debug(line)
                    logger.verbose(f"Container started in {(datetime.now() - start_date).seconds} seconds")

                except KeyboardInterrupt:
                    # User can cancel startup logging with ctrl+C
                    logger.warning("Skipping startup status updates (user interruption). Spawning shell now.")

    def stop(self, timeout: int = 10) -> None:
        """Stop the docker container"""
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            with console.status(f"Waiting to stop ({timeout}s timeout)", spinner_style="blue"):
                self.__container.stop(timeout=timeout)

    def spawnShell(self) -> None:
        """Spawn a shell on the docker container"""
        self.__check_start_version()
        logger.info(f"Location of the exegol workspace on the host : {self.config.getHostWorkspacePath()}")
        for device in self.config.getDevices():
            logger.info(f"Shared host device: {device.split(':')[0]}")
        logger.success(f"Opening shell in Exegol '{self.name}'")
        # In case of multi-user environment, xhost must be set before opening each session to be sure
        self.__applyX11ACLs()
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        envs = self.config.getShellEnvs()
        options = ""
        if len(envs) > 0:
            options += f" -e {' -e '.join(envs)}"
        cmd = f"docker exec{options} -ti {self.getFullId()} {self.config.getShellCommand()}"
        logger.debug(f"Opening shell with: {cmd}")
        if EnvInfo.isDockerDesktop() and (EnvInfo.is_windows_shell or EnvInfo.is_mac_shell):
            # Disable "What's next?" Docker Desktop spam exit message
            os.environ['DOCKER_CLI_HINTS'] = "false"
        os.system(cmd)
        # Docker SDK doesn't support (yet) stdin properly
        # result = self.__container.exec_run(ParametersManager().shell, stdout=True, stderr=True, stdin=True, tty=True,
        #                                    environment=self.config.getShellEnvs())
        # logger.debug(result)

    def exec(self, command: Union[str, Sequence[str]], as_daemon: bool = True, quiet: bool = False, is_tmp: bool = False) -> None:
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
                    if type(log) is bytes:
                        log = log.decode("utf-8")
                    logger.raw(log)
                if not quiet:
                    logger.success("End of the command")
            except KeyboardInterrupt:
                if not quiet and not is_tmp:
                    logger.info("Detaching process logging")
                    logger.warning("Exiting this command does [red]NOT[/red] stop the process in the container")

    @staticmethod
    def formatShellCommand(command: Union[str, Sequence[str]], quiet: bool = False, entrypoint_mode: bool = False) -> Tuple[str, str]:
        """Generic method to format a shell command and support zsh aliases.
        Set quiet to disable any logging here.
        Set entrypoint_mode to start the command with the entrypoint.sh config loader.
        - The first return argument is the payload to execute with every pre-routine for zsh.
        - The second return argument is the command itself in str format."""
        # Using base64 to escape special characters
        str_cmd = command if type(command) is str else ' '.join(command)
        # str_cmd = str_cmd.replace('"', '\\"')  # This fix shoudn' be necessary plus it can alter data like passwd
        if not quiet:
            logger.success(f"Command received: {str_cmd}")
        # ZSH pre-routine: Load zsh aliases and call eval to force aliases interpretation
        cmd = f'autoload -Uz compinit; compinit; source ~/.zshrc; eval "$CMD"'
        if not entrypoint_mode:
            # For direct execution, the full command must be supplied not just the zsh argument
            cmd = f"zsh -c '{cmd}'"
        return cmd, str_cmd

    def remove(self) -> None:
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

    def __removeVolume(self) -> None:
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
                list_files = os.listdir(volume_path)
            except PermissionError:
                if Confirm(f"Insufficient permission to view workspace files {volume_path}, "
                           f"do you still want to delete them?", default=False):
                    # Set list_files as empty to skip user prompt again
                    list_files = []
                else:
                    return
            except FileNotFoundError:
                logger.debug("This workspace has already been removed.")
                return
            try:
                if len(list_files) > 0:
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
                self.exec("rm -rf /workspace", as_daemon=False, quiet=True)
                try:
                    shutil.rmtree(volume_path)
                except PermissionError:
                    logger.warning(f"I don't have the rights to remove [magenta]{volume_path}[/magenta] (do it yourself)")
                    return
            except Exception as err:
                logger.error(err)
                return
            logger.success("Private workspace volume removed successfully")

    def __postStartSetup(self) -> None:
        """
        Operation to be performed after starting a container
        :return:
        """
        self.__applyX11ACLs()

    def __check_start_version(self) -> None:
        """
        Check spawn.sh up-to-date status and update the script if needed
        :return:
        """
        # Up-to-date container have the script shared over a volume
        # But legacy container must be checked and the code must be pushed
        if not self.config.isWrapperStartShared():
            # If the spawn.sh if not shared, the version must be compared and the script updated
            current_start = ImageScriptSync.getCurrentStartVersion()
            # Try to parse the spawn version of the container. If an alpha or beta version is in use, the script will always be updated.
            spawn_parsing_cmd = ["/bin/bash", "-c", "egrep '^# Spawn Version:[0-9]+$' /.exegol/spawn.sh 2&>/dev/null || echo ':0' | cut -d ':' -f2"]
            container_version = self.__container.exec_run(spawn_parsing_cmd).output.decode("utf-8").strip()
            if current_start != container_version:
                logger.debug(f"Updating spawn.sh script from version {container_version} to version {current_start}")
                self.__container.put_archive("/", ImageScriptSync.getImageSyncTarData(include_spawn=True))

    def postCreateSetup(self, is_temporary: bool = False) -> None:
        """
        Operation to be performed after creating a container
        :return:
        """
        # if not a temporary container, apply custom config
        if not is_temporary:
            # Update entrypoint script in the container
            self.__container.put_archive("/", ImageScriptSync.getImageSyncTarData(include_entrypoint=True))
            if self.__container.status.lower() == "created":
                self.__start_container()
            try:
                self.__updatePasswd()
            except APIError as e:
                if "is not running" in e.explanation:
                    logger.critical("An unexpected error occurred. Exegol cannot start the container after its creation...")
        # Run post start container actions
        self.__postStartSetup()

    def __applyX11ACLs(self) -> None:
        """
        If X11 (GUI) is enabled, allow X11 access on host ACL (if not already allowed) for linux and mac.
        If the host is accessed by SSH, propagate xauth cookie authentication if applicable.
        On Windows host, WSLg X11 don't have xhost ACL.
        :return:
        """
        # On Windows host with WSLg no need to run xhost +local or xauth
        if self.config.isGUIEnable() and not self.__xhost_applied and not EnvInfo.isWindowsHost():
            self.__xhost_applied = True  # Can be applied only once per execution
            if shutil.which("xhost") is None:
                if EnvInfo.is_linux_shell:
                    debug_msg = "Try to install the package [green]xorg-xhost[/green] or maybe you don't have X11 on your host?"
                else:
                    debug_msg = "or you don't have one"
                logger.error(f"The [green]xhost[/green] command is not available on your [bold]host[/bold]. "
                             f"Exegol was unable to allow your container to access your graphical environment ({debug_msg}).")
                return

            logger.debug(f"DISPLAY variable: {GuiUtils.getDisplayEnv()}")
            # Extracts the left part of the display variable to determine if remote access is used
            display_host = GuiUtils.getDisplayEnv().split(':')[0]
            # Left part is empty, local access is used to start Exegol
            if display_host == '' or EnvInfo.isMacHost():
                logger.debug("Connecting to container from local GUI, no X11 forwarding to set up")
                # TODO verify that the display format is the same on macOS, otherwise might not set up xauth and xhost correctly
                if EnvInfo.isMacHost():
                    logger.debug(f"Adding xhost ACL to localhost")
                    # add xquartz inet ACL
                    with console.status(f"Starting XQuartz...", spinner_style="blue"):
                        os.system(f"xhost + localhost > /dev/null")
                elif not EnvInfo.isWindowsHost():
                    logger.debug(f"Adding xhost ACL to local:{self.config.getUsername()}")
                    # add linux local ACL
                    os.system(f"xhost +local:{self.config.getUsername()} > /dev/null")
                return

            if shutil.which("xauth") is None:
                if EnvInfo.is_linux_shell:
                    debug_msg = "Try to install the package [green]xorg-xauth[/green] to support X11 forwarding in your current environment?"
                else:
                    debug_msg = "or it might not be supported for now"
                logger.error(f"The [green]xauth[/green] command is not available on your [bold]host[/bold]. "
                             f"Exegol was unable to allow your container to access your graphical environment ({debug_msg}).")
                return

            # If the left part of the display variable is "localhost", x11 socket is exposed only on loopback and remote access is used
            # If the container is not in host mode, it won't be able to reach the loopback interface of the host
            if display_host == "localhost" and self.config.getNetworkMode() != "host":
                logger.warning("X11 forwarding won't work on a bridged container unless you specify \"X11UseLocalhost no\" in your host sshd_config")
                logger.warning("[red]Be aware[/red] changing \"X11UseLocalhost\" value can [red]expose your device[/red], correct firewalling is [red]required[/red]")
                # TODO Add documentation to restrict the exposure of the x11 socket to the docker subnet
                return

            # Extracting the xauth cookie corresponding to the current display to a temporary file and reading it from there (grep cannot be used because display names are not accurate enough)
            _, tmpXauthority = tempfile.mkstemp()
            logger.debug(f"Extracting xauth entries to {tmpXauthority}")
            os.system(f"xauth extract {tmpXauthority} $DISPLAY > /dev/null 2>&1")
            xauthEntry = subprocess.check_output(f"xauth -f {tmpXauthority} list 2>/dev/null", shell=True).decode()
            logger.debug(f"xauthEntry to propagate: {xauthEntry}")

            # Replacing the hostname with localhost to support loopback exposed x11 socket and container in host mode (loopback is the same)
            if display_host == "localhost":
                logger.debug("X11UseLocalhost directive is set to \"yes\" or unspecified, X11 connections can be received only on loopback")
                # Modifing the entry to convert <hostname>/unix:<display_number> to localhost:<display_number>
                xauthEntry = f"localhost:{xauthEntry.split(':')[1]}"
            else:
                # TODO latter implement a check to see if the x11 socket is correctly firewalled and warn the user if it is not
                logger.debug("X11UseLocalhost directive is set to \"no\", X11 connections can be received from anywhere")

            # Check if the host has a xauth entry corresponding to the current display.
            if xauthEntry:
                logger.debug(f"Adding xauth cookie to container: {xauthEntry}")
                self.exec(f"xauth add {xauthEntry}", as_daemon=False, quiet=True)
                logger.debug(f"Removing {tmpXauthority}")
                os.remove(tmpXauthority)
            else:
                logger.warning(f"No xauth cookie corresponding to the current display was found.")

    def __updatePasswd(self) -> None:
        """
        If configured, update the password of the user inside the container.
        :return:
        """
        if self.config.getPasswd() is not None:
            logger.debug(f"Updating the {self.config.getUsername()} password inside the container")
            self.exec(f"echo '{self.config.getUsername()}:{self.config.getPasswd()}' | chpasswd", quiet=True)
