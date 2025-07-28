import asyncio
import errno
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from enum import IntFlag, auto as enum_auto
from pathlib import Path
from typing import Optional, Dict, Sequence, Tuple, Union, List

from docker.errors import NotFound, ImageNotFound, APIError
from docker.models.containers import Container

from exegol.config.EnvInfo import EnvInfo
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation, ObjectNotFound
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.ContainerLogStream import ContainerLogStream
from exegol.utils.ExeLog import logger
from exegol.utils.GuiUtils import GuiUtils
from exegol.utils.SessionHandler import SessionHandler
from exegol.utils.imgsync.ImageScriptSync import ImageScriptSync


class ExegolContainer(ExegolContainerTemplate, SelectableInterface):
    """Class of an exegol container already create in docker"""

    class Filters(IntFlag):
        STARTED = enum_auto()
        OUTDATED = enum_auto()

    BACKUP_DIRECTORY = "/workspace/.ExegolUpgradeBackupAuto"

    def __init__(self, docker_container: Container, model: Optional[ExegolContainerTemplate] = None):
        logger.debug(f"Loading container: {docker_container.name}")
        self.__container: Container = docker_container
        self.__id: str = docker_container.id
        self.__xhost_applied = False
        self.__post_start_applied = False
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
            super().__init__(str(docker_container.name),
                             config=ContainerConfig(container=docker_container),
                             image=ExegolImage(name=image_name, docker_image=docker_image))
            self.image.syncContainerData(docker_container)
            # At this stage, the container image object has an unknown status because no synchronization with a registry has been done.
            # This could be done afterwards (with container.image.autoLoad()) if necessary because it takes time.
            self.__new_container = False
        else:
            # Create Exegol container from a newly created docker container with its object template.
            super().__init__(str(docker_container.name),
                             config=ContainerConfig(container=docker_container),
                             # Rebuild config from docker object to update workspace path
                             image=model.image)
            self.__new_container = True
        self.image.syncStatus()

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"{self.getRawStatus()} - {super().__str__()}"

    def filter(self, filters: int) -> bool:
        """
        Apply bitwise filter
        :param filters:
        :return:
        """
        match = True
        if match and filters & self.Filters.STARTED:
            match = self.isRunning()
        if match and filters & self.Filters.OUTDATED:
            match = self.image.isLocked()
        return match

    def __getState(self) -> Dict:
        """Technical getter of the container status dict"""
        try:
            self.__container.reload()
        except NotFound:
            return {"State": "Removed"}
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

    async def start(self) -> None:
        """Start the docker container"""
        if not self.isRunning():
            logger.info(f"Starting container {self.name}")
            await self.__start_container()
            await self.__postStartSetup()

    async def __start_container(self) -> None:
        """
        This method starts the container and displays startup status updates to the user.
        :return:
        """
        async with ExegolStatus(f"Waiting to start {self.name}", spinner_style="blue") as progress:
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

    async def stop(self, timeout: int = 10) -> None:
        """Stop the docker container"""
        if self.isRunning():
            logger.info(f"Stopping container {self.name}")
            async with ExegolStatus(f"Waiting to stop ({timeout}s timeout)", spinner_style="blue"):
                self.__container.stop(timeout=timeout)

    async def spawnShell(self) -> None:
        """Spawn a shell on the docker container"""
        self.__check_start_version()
        logger.info(f"Location of the exegol workspace on the host : {self.config.getHostWorkspacePath()}")
        for device in self.config.getDevices():
            logger.info(f"Shared host device: {device.split(':')[0]}")
        spawn_all_capabilities = (not self.config.getPrivileged() and
                                  "ALL" not in self.config.getCapabilities() and
                                  ParametersManager().capabilities and
                                  "ALL" in ParametersManager().capabilities)
        if not self.__new_container and not spawn_all_capabilities and ParametersManager().capabilities and len(ParametersManager().capabilities) > 0:
            if set(ParametersManager().capabilities).issubset(self.config.getCapabilities()):
                if not self.config.getPrivileged() and "ALL" not in self.config.getCapabilities():
                    logger.warning("Can't set specific capability on existing containers, ignoring. Use [green]--cap ALL[/green] instead if needed.")
            else:
                logger.critical("Can't set specific capability on existing containers. Use [green]--cap ALL[/green] instead if needed.")
        logger.success(f"Opening [blue]{ParametersManager().shell}[/blue] shell in Exegol [green]{self.name}[/green]"
                       f"{' with [orange3]all capabilities[/orange3]' if spawn_all_capabilities or self.config.getPrivileged() or 'ALL' in self.config.getCapabilities() else ''}")
        # In case of multi-user environment, xhost must be set before opening each session to be sure
        await self.__applyX11ACLs()
        # Using system command to attach the shell to the user terminal (stdin / stdout / stderr)
        envs = self.config.getShellEnvs()
        options = ""
        if len(envs) > 0:
            options += f" -e {' -e '.join(envs)}"
        if spawn_all_capabilities:
            options += " --privileged"
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

    async def exec(self, command: Union[str, Sequence[str]], as_daemon: bool = True, quiet: bool = False, is_tmp: bool = False, show_output: bool = True) -> int:
        """Execute a command / process on the docker container.
        Set as_daemon to not follow the command stream and detach the execution
        Set quiet to disable logs message
        Set is_tmp if the container will automatically be removed after execution"""
        if not self.isRunning():
            await self.start()
        if not quiet:
            logger.info("Executing command on Exegol")
            if logger.getEffectiveLevel() > logger.VERBOSE and not ParametersManager().daemon:
                logger.info("Hint: use verbose mode to see command output (-v).")
        exec_payload, str_cmd = ExegolContainer.formatShellCommand(command, quiet)
        stream = self.__container.exec_run(exec_payload, environment={"CMD": str_cmd, "DISABLE_AUTO_UPDATE": "true"}, detach=as_daemon, stream=not as_daemon and not quiet)
        if as_daemon:
            if not quiet:
                logger.success("Command successfully executed in background")
            return 0
        else:
            try:
                # stream[0] : exit code
                # stream[1] : text stream
                if type(stream.output) is bytes:
                    # When quiet is True, stream is False, so we receive all the logs at the end of the command execution
                    if stream.exit_code is not None and stream.exit_code != 0:
                        logger.debug(f"An error occurred while executing the command: [error {stream.exit_code}] {command}")
                    if len(stream.output) > 0 and show_output:
                        if stream.exit_code is None or stream.exit_code == 0:
                            logger.raw(stream.output.decode("utf-8"))
                        else:
                            logger.error(stream.output.decode("utf-8"))
                else:
                    # When quiet is False, stream is True, so we directly receive a log stream
                    for log in stream[1]:
                        if type(log) is bytes:
                            log = log.decode("utf-8")
                        logger.raw(log)
                if not quiet:
                    logger.success("End of the command")
                return 0 if stream.exit_code is None else stream.exit_code
            except KeyboardInterrupt:
                if not quiet and not is_tmp:
                    logger.info("Detaching process logging")
                    logger.warning("Exiting this command does [red]NOT[/red] stop the process in the container")
        return 0

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

    async def remove(self, container_only: bool = False, backup_history: Optional[List[str]] = None) -> None:
        """Stop and remove the docker container.
        :param container_only: If True, only the container will be removed, not the workspace volume or the network.
        :param backup_history: List for backup containers ID to remove too
        """
        if not container_only:
            await self.__removeVolume()
        await self.stop(timeout=2)
        have_backup = backup_history is not None and len(backup_history) > 0
        backup_text = f" and {len(backup_history)} backup containers" if have_backup and backup_history is not None else ""
        logger.info(f"Removing container {self.name}{backup_text}")
        try:
            self.__container.remove()
            logger.success(f"Container {self.name} successfully removed.")
        except NotFound:
            logger.error(f"The container {self.name} has already been removed (probably created as a temporary container).")
        if not container_only:
            # Must be imported locally to avoid circular importation
            from exegol.utils.DockerUtils import DockerUtils
            if have_backup and backup_history is not None:
                for c_id in backup_history:
                    try:
                        DockerUtils().removeContainerById(c_id)
                    except ObjectNotFound:
                        continue
            nets = self.config.getNetworks()
            for net in nets:
                if net.shouldBeRemoved():
                    logger.debug(f"Network {net.getNetworkName()} will be removed.")
                    DockerUtils().removeNetwork(net.getNetworkName())

    def getExistingBackupContainers(self) -> List[Tuple[str, str]]:
        """
        Get container's backup history and filter existing containers only.
        :return: List of tuple of legacy container. For each entry the first element is the container id and the second is the container name.
        """
        raw_backup_history = self.config.getBackupHistory()
        backup_history = [] if raw_backup_history is None else raw_backup_history.split(',')
        result = []
        if len(backup_history) > 0:
            from exegol.utils.DockerUtils import DockerUtils
            for container_id in backup_history:
                # Check if the previous container still exists
                bak_container = DockerUtils().isContainerExist(container_id)
                if bak_container is not None:
                    result.append((container_id, bak_container[7:]))
        return result

    async def __removeVolume(self) -> None:
        """Remove private workspace volume directory if exist"""
        volume_path = self.config.getPrivateVolumePath()
        # TODO add backup
        if volume_path != '':
            if volume_path.startswith('/wsl/') or volume_path.startswith('\\wsl\\'):
                # Docker volume defines from WSL don't return the real path, they cannot be automatically removed
                # TODO review WSL workspace volume
                logger.warning("Warning: WSL workspace directory cannot be removed automatically.")
                return
            logger.debug(f"Removing volume {volume_path}")
            force_remove = False
            try:
                have_files = False
                for _ in Path(volume_path).iterdir():
                    have_files = True
                    break
            except (PermissionError, OSError) as e:
                if type(e) is OSError:
                    logger.warning(f"Error during workspace files access: {e}")
                    message = f"Exegol cannot access the workspace files [magenta]{volume_path}[/magenta], do you want to delete your container's workspace?"
                else:
                    message = f"Insufficient permission to view workspace files [magenta]{volume_path}[/magenta], do you want to delete your container's workspace?"
                if await ExegolRich.Confirm(message, default=False):
                    # Set have_files to skip directly to rmtree
                    have_files = True
                    # Set force_remove to skip user prompt confirmation again
                    force_remove = True
                else:
                    return
            except FileNotFoundError:
                logger.debug("This workspace has already been removed.")
                return
            try:
                try:
                    if have_files:
                        raise OSError
                    logger.info(f"Removing empty workspace volume")
                    os.rmdir(volume_path)  # This function can only remove an empty directory as failsafe
                except OSError as e:
                    if e.errno is not None and e.errno != errno.ENOTEMPTY:
                        logger.error(f"Receive an error during workspace removal: {e}")
                    # Directory is not empty
                    if (not force_remove and
                            not await ExegolRich.Confirm(f"Workspace [magenta]{volume_path}[/magenta] is not empty, do you want to delete it?",
                                                         default=False)):
                        # User can choose not to delete the workspace on the host
                        return
                    logger.verbose(f"Removing workspace volume")
                    # Try to remove files from the host with user permission (work only without sub-directory)
                    shutil.rmtree(volume_path)
            except PermissionError:
                logger.info(f"Deleting the workspace files from the [green]{self.name}[/green] container as root")
                if not self.isRunning():
                    await self.__start_container()
                # If the host can't remove the container's file and folders, the rm command is exec from the container itself as root
                await self.exec("rm -rf /workspace", as_daemon=False, quiet=True)
                try:
                    shutil.rmtree(volume_path)
                except PermissionError:
                    logger.warning(f"I don't have the rights to remove [magenta]{volume_path}[/magenta] (do it yourself)")
                    return
            logger.success("Private workspace volume removed successfully")
        else:
            logger.warning(f"Externally managed workspaces are [red]NOT[/red] automatically removed by exegol. You can manually remove the directory if it's no longer needed: [magenta]{self.config.getHostWorkspacePath()}[/magenta]")

    async def __postStartSetup(self) -> None:
        """
        Operation to be performed after starting a container
        :return:
        """
        if not self.__post_start_applied:
            self.__post_start_applied = True
            await self.__applyX11ACLs()

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

    async def postCreateSetup(self, is_temporary: bool = False) -> None:
        """
        Operation to be performed after creating a container
        :return:
        """
        # if not a temporary container, apply custom config
        if not is_temporary:
            # Update entrypoint script in the container
            self.__container.put_archive("/", ImageScriptSync.getImageSyncTarData(include_entrypoint=True))
            if self.__container.status.lower() == "created":
                await self.__start_container()
            try:
                await self.__updatePasswd()
            except APIError as e:
                if "is not running" in e.explanation:
                    logger.critical("An unexpected error occurred. Exegol cannot start the container after its creation...")
        # Run post start container actions
        await self.__postStartSetup()

    async def __applyX11ACLs(self) -> None:
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
                    async with ExegolStatus(f"Starting XQuartz...", spinner_style="blue"):
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
            if display_host == "localhost" and not self.config.isNetworkHost():
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
                await self.exec(f"xauth add {xauthEntry}", as_daemon=False, quiet=True)
                logger.debug(f"Removing {tmpXauthority}")
                os.remove(tmpXauthority)
            else:
                logger.warning(f"No xauth cookie corresponding to the current display was found.")

    async def __updatePasswd(self) -> None:
        """
        If configured, update the password of the user inside the container.
        :return:
        """
        if self.config.getPasswd() is not None:
            logger.debug(f"Updating the {self.config.getUsername()} password inside the container")
            await self.exec(f"echo '{self.config.getUsername()}:{self.config.getPasswd()}' | chpasswd", quiet=True)

    def rename_as_old(self):
        import re
        old_match = re.search(r"(.*-bak)(\d*)$", self.getContainerName())
        i = 0 if not old_match else ((int(old_match.group(2)) if old_match.group(2) else 0) + 1)
        base_name = self.getContainerName() + "-bak" if not old_match else old_match.group(1)
        while True:
            new_name = base_name
            if i > 0:
                new_name += str(i)
            logger.debug(f"Renaming container {self.getContainerName()} as {new_name}")
            try:
                self.__container.rename(new_name)
                logger.success(f"Your previous container [orange3]{self.name}[/orange3] has been renamed to [green]{new_name[7:]}[/green] as a backup. You will need to delete it manually when it is no longer needed.")
                return
            except APIError as e:
                if e.status_code == 409 and "is already in use by" in e.explanation:
                    i += 1
                    logger.debug(f"Container {new_name} already exists, trying again")
                    continue
                else:
                    logger.error(e.explanation)
                    logger.critical(f"An unexpected error occurred from docker. Exegol cannot rename the container [green]{self.name}[/green]. Aborting the operation.")

    async def backup(self, backup_exh: bool) -> None:
        """
        This function automatically backup the exegol workspace and history to the workspace directory.
        :return:
        """
        if not SessionHandler().pro_feature_access():
            logger.critical("Exegol backup is only available for Pro or Enterprise users.")
        async with ExegolStatus(f"Ongoing backup of container [green]{self.name}[/green]", spinner_style="blue"):
            result = await self.exec(f"mkdir {self.BACKUP_DIRECTORY}", quiet=True, as_daemon=False)
            if result != 0:
                logger.error(f"The directory {self.BACKUP_DIRECTORY} already exist in the container [green]{self.name}[/green]. "
                             f"It needs to be removed manually before trying to backup this container again.")
                raise CancelOperation

            backup_tasks = [
                # Backup bash/zsh history
                self.exec(f"tail -n +$(($(grep -n '# -=-=-=-=-=-=-=- YOUR COMMANDS BELOW -=-=-=-=-=-=-=- #' ~/.zsh_history | tail -n1 | cut -d ':' -f1) + 1)) ~/.zsh_history > {self.BACKUP_DIRECTORY}/zsh_history", quiet=True, as_daemon=False),
                self.exec(f"tail -n +$(($(grep -n '# -=-=-=-=-=-=-=- YOUR COMMANDS BELOW -=-=-=-=-=-=-=- #' ~/.bash_history | tail -n1 | cut -d ':' -f1) + 1)) ~/.bash_history > {self.BACKUP_DIRECTORY}/bash_history", quiet=True, as_daemon=False),
                # Backup files
                self.exec(f"cp -a /etc/hosts {self.BACKUP_DIRECTORY}/hosts", quiet=True, as_daemon=False),
                self.exec(f"cp -a /etc/resolv.conf {self.BACKUP_DIRECTORY}/resolv.conf", quiet=True, as_daemon=False),
                self.exec(f"cp -a /etc/proxychains.conf {self.BACKUP_DIRECTORY}/proxychains.conf", quiet=True, as_daemon=False),
                self.exec(f"triliumnext-stop && "
                          f"mkdir {self.BACKUP_DIRECTORY}/triliumnext_data && "
                          f"cp -a /opt/tools/triliumnext/data/document.db* {self.BACKUP_DIRECTORY}/triliumnext_data/ && "
                          f"cp -a /opt/tools/triliumnext/data/session_secret.txt {self.BACKUP_DIRECTORY}/triliumnext_data/ && "
                          f"cp -a /opt/tools/triliumnext/data/sessions {self.BACKUP_DIRECTORY}/triliumnext_data/", quiet=True, as_daemon=False),
                self.exec(f"[ $(sed-comment-line /opt/tools/Exegol-history/profile.sh | sed-empty-line | wc -l) -gt 0 ] || return 0 && cp -a /opt/tools/Exegol-history/profile.sh {self.BACKUP_DIRECTORY}/exh_profile.sh", quiet=True, as_daemon=False),
            ]
            if backup_exh:
                # Backup exegol-history
                backup_tasks.append(
                    self.exec(f"[ -d ~/.exegol_history ] || return 0 && exh export creds --format CSV --file {self.BACKUP_DIRECTORY}/exegol_history_creds.csv && exh export hosts --format CSV --file {self.BACKUP_DIRECTORY}/exegol_history_hosts.csv", quiet=True, as_daemon=False),
                )

            results = await asyncio.gather(*backup_tasks)
            for r in results:
                if r != 0:
                    logger.error(f"An error occurred during backup creation of [green]{self.name}[/green] container. Please check the logs above for more information.")
                    raise CancelOperation

    async def restore(self) -> bool:
        """
        This function automatically restores a backup from the exegol workspace.
        :return:
        """
        if not SessionHandler().pro_feature_access():
            logger.critical("Exegol restore is only available for Pro or Enterprise users.")

        async with ExegolStatus(f"Restoring backup of container [green]{self.name}[/green]", spinner_style="blue"):
            results = await asyncio.gather(
                self.exec(f"cat {self.BACKUP_DIRECTORY}/zsh_history >> ~/.zsh_history", quiet=True, as_daemon=False),
                self.exec(f"cat {self.BACKUP_DIRECTORY}/bash_history >> ~/.bash_history", quiet=True, as_daemon=False),
                self.exec(f"cp -a {self.BACKUP_DIRECTORY}/hosts /etc/hosts", quiet=True, as_daemon=False),
                self.exec(f"cp -a {self.BACKUP_DIRECTORY}/resolv.conf /etc/resolv.conf", quiet=True, as_daemon=False),
                self.exec(f"mv {self.BACKUP_DIRECTORY}/proxychains.conf /etc/proxychains.conf ", quiet=True, as_daemon=False),
                self.exec(f"rm /opt/tools/triliumnext/data/document.db* && "
                          f"mv {self.BACKUP_DIRECTORY}/triliumnext_data/document.db* /opt/tools/triliumnext/data/ && "
                          f"mv {self.BACKUP_DIRECTORY}/triliumnext_data/session_secret.txt /opt/tools/triliumnext/data/session_secret.txt && "
                          f"rm -r /opt/tools/triliumnext/data/sessions && "
                          f"mv {self.BACKUP_DIRECTORY}/triliumnext_data/sessions /opt/tools/triliumnext/data/sessions", quiet=True, as_daemon=False),
                self.exec(f"[ -f {self.BACKUP_DIRECTORY}/exh_profile.sh ] || return 0 && mv {self.BACKUP_DIRECTORY}/exh_profile.sh /opt/tools/Exegol-history/profile.sh", quiet=True, as_daemon=False),
                self.exec(f"[ -f {self.BACKUP_DIRECTORY}/exegol_history_creds.csv ] || return 0 && exh version 2> /dev/null || (echo 'This image is not up-to-date, [green]exegol-history[/green] cannot restore your creds database. Backup can be found in your container here: {self.BACKUP_DIRECTORY}/exegol_history_creds.csv' && return 1) && exh import creds --format CSV --file {self.BACKUP_DIRECTORY}/exegol_history_creds.csv", quiet=True, as_daemon=False),
                self.exec(f"[ -f {self.BACKUP_DIRECTORY}/exegol_history_hosts.csv ] || return 0 && exh version 2> /dev/null || (echo 'This image is not up-to-date, [green]exegol-history[/green] cannot restore your hosts database. Backup can be found in your container here: {self.BACKUP_DIRECTORY}/exegol_history_hosts.csv' && return 1) && exh import hosts --format CSV --file {self.BACKUP_DIRECTORY}/exegol_history_hosts.csv", quiet=True, as_daemon=False),
            )

            for r in results:
                if r != 0:
                    logger.error(f"An error occurred during backup restoration, aborting. Please check the logs above for more information.")
                    logger.error(f"{self.BACKUP_DIRECTORY} backup directory will not be removed automatically, you will have to remove it manually inside the container. ")
                    return False

            await self.exec(f"rm -rf {self.BACKUP_DIRECTORY}", quiet=True, as_daemon=False)
            return True
