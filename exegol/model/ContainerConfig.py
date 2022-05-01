import os
import re
from pathlib import Path, PurePath
from typing import Optional, List, Dict, Union, Tuple, cast

from docker.models.containers import Container
from docker.types import Mount
from rich.prompt import Prompt

from exegol.console.ConsoleFormat import boolFormatter, getColor
from exegol.console.ExegolPrompt import Confirm
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ProtocolNotSupported, CancelOperation
from exegol.model.ExegolModules import ExegolModules
from exegol.utils import FsUtils
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.GuiUtils import GuiUtils
from exegol.utils.UserConfig import UserConfig


class ContainerConfig:
    """Configuration class of an exegol container"""

    # Default hardcoded value
    __default_entrypoint = "bash"
    __default_shm_size = "64M"

    def __init__(self, container: Optional[Container] = None):
        """Container config default value"""
        self.__enable_gui: bool = False
        self.__share_timezone: bool = False
        self.__shared_resources: bool = False
        self.__exegol_resources: bool = False
        self.__network_host: bool = True
        self.__privileged: bool = False
        self.__mounts: List[Mount] = []
        self.__devices: List[str] = []
        self.__capabilities: List[str] = []
        self.__sysctls: Dict[str, str] = {}
        self.__envs: Dict[str, str] = {}
        self.__ports: Dict[str, Optional[Union[int, Tuple[str, int], List[int]]]] = {}
        self.interactive: bool = True
        self.tty: bool = True
        self.shm_size: str = self.__default_shm_size
        self.__workspace_custom_path: Optional[str] = None
        self.__workspace_dedicated_path: Optional[str] = None
        self.__disable_workspace: bool = False
        self.__container_command: str = self.__default_entrypoint
        self.__vpn_path: Optional[Union[Path, PurePath]] = None
        if container is not None:
            self.__parseContainerConfig(container)

    def __parseContainerConfig(self, container: Container):
        """Parse Docker object to setup self configuration"""
        # Container Config section
        container_config = container.attrs.get("Config", {})
        self.tty = container_config.get("Tty", True)
        self.__parseEnvs(container_config.get("Env", []))
        self.interactive = container_config.get("OpenStdin", True)
        self.__enable_gui = False
        for env in self.__envs:
            if "DISPLAY" in env:
                self.__enable_gui = True
                break

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.__privileged = host_config.get("Privileged", False)
        caps = host_config.get("CapAdd", [])
        if caps is not None:
            self.__capabilities = caps
        logger.debug(f"Capabilities : {self.__capabilities}")
        self.__sysctls = host_config.get("Sysctls", {})
        devices = host_config.get("Devices", [])
        if devices is not None:
            for device in devices:
                self.__devices.append(
                    f"{device.get('PathOnHost', '?')}:{device.get('PathInContainer', '?')}:{device.get('CgroupPermissions', '?')}")
        logger.debug(f"Load devices : {self.__devices}")

        # Volumes section
        self.__share_timezone = False
        self.__shared_resources = False
        self.__parseMounts(container.attrs.get("Mounts", []), container.name.replace('exegol-', ''))

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.__network_host = "host" in network_settings["Networks"]
        self.__ports = network_settings.get("Ports", {})

    def __parseEnvs(self, envs: List[str]):
        """Parse envs object syntax"""
        for env in envs:
            logger.debug(f"Parsing envs : {env}")
            # Removing " and ' at the beginning and the end of the string before splitting key / value
            self.addRawEnv(env.strip("'").strip('"'))

    def __parseMounts(self, mounts: Optional[List[Dict]], name: str):
        """Parse Mounts object"""
        if mounts is None:
            mounts = []
        self.__disable_workspace = True
        for share in mounts:
            logger.debug(f"Parsing mount : {share}")
            src_path: Optional[PurePath] = None
            obj_path: PurePath
            if share.get('Type', 'volume') == "volume":
                source = f"Docker {share.get('Driver', '')} volume '{share.get('Name', 'unknown')}'"
            else:
                source = share.get("Source", '')
                src_path = FsUtils.parseDockerVolumePath(source)

                # When debug is disabled, exegol print resolved windows path of mounts
                if logger.getEffectiveLevel() > ExeLog.ADVANCED:
                    source = str(src_path)

            self.__mounts.append(Mount(source=source,
                                       target=share.get('Destination'),
                                       type=share.get('Type', 'volume'),
                                       read_only=(not share.get("RW", True)),
                                       propagation=share.get('Propagation', '')))
            if "/etc/timezone" in share.get('Destination', ''):
                self.__share_timezone = True
            elif "/opt/resources" in share.get('Destination', ''):
                self.__exegol_resources = True
            elif "/my-resources" in share.get('Destination', ''):
                self.__shared_resources = True
            elif "/workspace" in share.get('Destination', ''):
                # Workspace are always bind mount
                assert src_path is not None
                obj_path = cast(PurePath, src_path)
                logger.debug(f"Loading workspace volume source : {obj_path}")
                self.__disable_workspace = False
                if obj_path is not None and obj_path.name == name and \
                        (obj_path.parent.name == "shared-data-volumes" or obj_path.parent == UserConfig().private_volume_path):  # Check legacy path and new custom path
                    logger.debug("Private workspace detected")
                    self.__workspace_dedicated_path = str(obj_path)
                else:
                    logger.debug("Custom workspace detected")
                    self.__workspace_custom_path = str(obj_path)
            elif "/vpn" in share.get('Destination', ''):
                # VPN are always bind mount
                assert src_path is not None
                obj_path = cast(PurePath, src_path)
                self.__vpn_path = obj_path
                logger.debug(f"Loading VPN config: {self.__vpn_path.name}")

    def interactiveConfig(self, container_name: str) -> List[str]:
        """Interactive procedure allowing the user to configure its new container"""
        logger.info("Starting interactive configuration")

        command_options = []

        # Workspace config
        if Confirm(
                "Do you want to [green]share[/green] your [blue]current host working directory[/blue] in the new container's worskpace?",
                default=False):
            self.enableCwdShare()
            command_options.append("-cwd")
        elif Confirm(
                f"Do you want to [green]share[/green] [blue]a host directory[/blue] in the new container's workspace [blue]different than the default one[/blue] ([magenta]{UserConfig().private_volume_path / container_name}[/magenta])?",
                default=False):
            while True:
                workspace_path = Prompt.ask("Enter the path of your workspace")
                if Path(workspace_path).expanduser().is_dir():
                    break
                else:
                    logger.error("The provided path is not a folder or does not exist.")
            self.setWorkspaceShare(workspace_path)
            command_options.append(f"-w {workspace_path}")

        # GUI Config
        if self.__enable_gui:
            if Confirm("Do you want to [orange3]disable[/orange3] [blue]GUI[/blue]?", False):
                self.__disableGUI()
        elif Confirm("Do you want to [green]enable[/green] [blue]GUI[/blue]?", False):
            self.enableGUI()
        # Command builder info
        if not self.__enable_gui:
            command_options.append("--disable-X11")

        # Timezone config
        if self.__share_timezone:
            if Confirm("Do you want to [orange3]remove[/orange3] your [blue]shared timezone[/blue] config?", False):
                self.__disableSharedTimezone()
        elif Confirm("Do you want to [green]share[/green] your [blue]host's timezone[/blue]?", False):
            self.enableSharedTimezone()
        # Command builder info
        if not self.__share_timezone:
            command_options.append("--disable-shared-timezones")

        # Shared resources config
        if self.__shared_resources:
            if Confirm("Do you want to [orange3]disable[/orange3] the [blue]shared resources[/blue]?", False):
                self.__disableSharedResources()
        elif Confirm("Do you want to [green]activate[/green] the [blue]shared resources[/blue]?", False):
            self.enableSharedResources()
        # Command builder info
        if not self.__shared_resources:
            command_options.append("--disable-shared-resources")

        # Exegol resources config
        if self.__exegol_resources:
            if Confirm("Do you want to [orange3]disable[/orange3] the [blue]exegol resources[/blue]?", False):
                self.disableExegolResources()
        elif Confirm("Do you want to [green]activate[/green] the [blue]exegol resources[/blue]?", False):
            self.enableExegolResources()
        # Command builder info
        if not self.__exegol_resources:
            command_options.append("--disable-exegol-resources")

        # Network config
        if self.__network_host:
            if Confirm("Do you want to use a [blue]dedicated private network[/blue]?", False):
                self.setNetworkMode(False)
        elif Confirm("Do you want to share the [green]host's[/green] [blue]networks[/blue]?", False):
            self.setNetworkMode(True)
        # Command builder info
        if not self.__network_host:
            command_options.append("--disable-shared-network")

        # VPN config
        if self.__vpn_path is None and Confirm(
                "Do you want to [green]enable[/green] a [blue]VPN[/blue] for this container", False):
            while True:
                vpn_path = Prompt.ask('Enter the path to the OpenVPN config file')
                if Path(vpn_path).expanduser().is_file():
                    self.enableVPN(vpn_path)
                    break
                else:
                    logger.error("No config files were found.")
        elif self.__vpn_path and Confirm(
                "Do you want to [orange3]remove[/orange3] your [blue]VPN configuration[/blue] in this container", False):
            self.__disableVPN()
        if self.__vpn_path:
            command_options.append(f"--vpn {self.__vpn_path}")

        return command_options

    def enableGUI(self):
        """Procedure to enable GUI feature"""
        if not GuiUtils.isGuiAvailable():
            logger.error("GUI feature is [red]not available[/red] on your environment. [orange3]Skipping[/orange3].")
            return
        if not self.__enable_gui:
            logger.verbose("Config: Enabling display sharing")
            try:
                self.addVolume(GuiUtils.getX11SocketPath(), "/tmp/.X11-unix", must_exist=True)
            except CancelOperation as e:
                logger.warning(f"Graphical interface sharing could not be enabled: {e}")
                return
            # TODO support pulseaudio
            self.addEnv("DISPLAY", GuiUtils.getDisplayEnv())
            self.addEnv("QT_X11_NO_MITSHM", "1")
            self.addEnv("_JAVA_AWT_WM_NONREPARENTING", "1")
            self.__enable_gui = True

    def __disableGUI(self):
        """Procedure to enable GUI feature (Only for interactive config)"""
        if self.__enable_gui:
            self.__enable_gui = False
            logger.verbose("Config: Disabling display sharing")
            self.removeVolume(container_path="/tmp/.X11-unix")
            self.removeEnv("DISPLAY")
            self.removeEnv("QT_X11_NO_MITSHM")
            self.removeEnv("_JAVA_AWT_WM_NONREPARENTING")

    def enableSharedTimezone(self):
        """Procedure to enable shared timezone feature"""
        if EnvInfo.is_windows_shell:
            logger.warning("Timezone sharing is not supported from a Windows shell. Skipping.")
            return
        if not self.__share_timezone:
            logger.verbose("Config: Enabling host timezones")
            # Try to share /etc/timezone (deprecated old timezone file)
            try:
                self.addVolume("/etc/timezone", "/etc/timezone", read_only=True, must_exist=True)
                timezone_loaded = True
            except CancelOperation:
                logger.verbose("File /etc/timezone is missing on your host.")
                timezone_loaded = False
            # Try to share /etc/localtime (new timezone file)
            try:
                self.addVolume("/etc/localtime", "/etc/localtime", read_only=True, must_exist=True)
            except CancelOperation as e:
                if not timezone_loaded:
                    # If neither file was found, disable the functionality
                    logger.error(f"The host's timezone could not be shared: {e}")
                    return
                else:
                    logger.warning("File /etc/localtime is missing on your host. Only using /etc/timezone (deprecated).")
            self.__share_timezone = True

    def __disableSharedTimezone(self):
        """Procedure to disable shared timezone feature (Only for interactive config)"""
        if self.__share_timezone:
            self.__share_timezone = False
            logger.verbose("Config: Disabling host timezones")
            self.removeVolume("/etc/timezone")
            self.removeVolume("/etc/localtime")

    def setPrivileged(self, status: bool = True):
        """Set container as privileged"""
        logger.verbose(f"Config: Setting container privileged as {status}")
        if status:
            logger.warning("Setting container as privileged (this exposes the host to security risks)")
        self.__privileged = status

    def enableSharedResources(self):
        """Procedure to enable shared volume feature"""
        if not self.__shared_resources:
            logger.verbose("Config: Enabling shared resources volume")
            self.__shared_resources = True
            # Adding volume config
            self.addVolume(UserConfig().shared_resources_path, '/my-resources')

    def __disableSharedResources(self):
        """Procedure to disable shared volume feature (Only for interactive config)"""
        if self.__shared_resources:
            logger.verbose("Config: Disabling shared resources volume")
            self.__shared_resources = False
            self.removeVolume(container_path='/my-resources')

    def enableExegolResources(self) -> bool:
        """Procedure to enable exegol resources volume feature"""
        if not self.__exegol_resources:
            # Check if resources are installed / up-to-date
            try:
                if not ExegolModules().isExegolResourcesReady():
                    raise CancelOperation
            except CancelOperation:
                # Error during installation, skipping operation
                logger.warning("Exegol resources have not been downloaded, the feature cannot be enabled")
                return False
            logger.verbose("Config: Enabling exegol resources volume")
            self.__exegol_resources = True
            # Adding volume config
            self.addVolume(str(UserConfig().exegol_resources_path), '/opt/resources')
        return True

    def disableExegolResources(self):
        """Procedure to disable exegol resources volume feature (Only for interactive config)"""
        if self.__exegol_resources:
            logger.verbose("Config: Disabling exegol resources volume")
            self.__exegol_resources = False
            self.removeVolume(container_path='/opt/resources')

    def enableCwdShare(self):
        """Procedure to share Current Working Directory with the /workspace of the container"""
        self.__workspace_custom_path = os.getcwd()
        logger.verbose(f"Config: Sharing current workspace directory {self.__workspace_custom_path}")

    def setWorkspaceShare(self, host_directory):
        """Procedure to share a specific directory with the /workspace of the container"""
        path = Path(host_directory).expanduser().absolute()
        if not path.is_dir():
            logger.critical("The specified workspace is not a directory")
        logger.verbose(f"Config: Sharing workspace directory {path}")
        self.__workspace_custom_path = str(path)

    def enableVPN(self, config_path: Optional[str] = None):
        """Configure a VPN profile for container startup"""
        # Check host mode : custom (allows you to isolate the VPN connection from the host's network)
        if self.__network_host:
            logger.warning("Using the host network mode with a VPN profile is not recommended.")
            if not Confirm(f"Are you sure you want to configure a VPN container based on the host's network?",
                           default=False):
                logger.info("Changing network mode to custom")
                self.setNetworkMode(False)
        # Add NET_ADMIN capabilities, this privilege is necessary to mount network tunnels
        self.__addCapability("NET_ADMIN")
        if not self.__network_host:
            # Add sysctl ipv6 config, some VPN connection need IPv6 to be enabled
            self.__addSysctl("net.ipv6.conf.all.disable_ipv6", "0")
        # Add tun device, this device is needed to create VPN tunnels
        self.addDevice("/dev/net/tun", mknod=True)
        # Sharing VPN configuration with the container
        ovpn_parameters = self.__prepareVpnVolumes(config_path)
        # Execution of the VPN daemon at container startup
        if ovpn_parameters is not None:
            self.setContainerCommand(
                f"bash -c 'cd /vpn/config; openvpn {ovpn_parameters} | tee /var/log/vpn.log; bash'")  # TODO add log rotation on image config

    def __prepareVpnVolumes(self, config_path: Optional[str]) -> Optional[str]:
        """Volumes must be prepared to share OpenVPN configuration files with the container.
        Depending on the user's settings, different configurations can be applied.
        With or without username / password authentication via auth-user-pass.
        OVPN config file directly supplied or a config directory,
        the directory feature is useful when the configuration depends on multiple files like certificate, keys etc."""
        ovpn_parameters = []

        # VPN Auth creds file
        input_vpn_auth = ParametersManager().vpn_auth
        vpn_auth = None
        if input_vpn_auth is not None:
            vpn_auth = Path(input_vpn_auth).expanduser()

        if vpn_auth is not None:
            if vpn_auth.is_file():
                logger.info(f"Adding VPN credentials from: {str(vpn_auth.absolute())}")
                self.addVolume(str(vpn_auth.absolute()), "/vpn/auth/creds.txt", read_only=True)
                ovpn_parameters.append("--auth-user-pass /vpn/auth/creds.txt")
            else:
                # Supply a directory instead of a file for VPN authentication is not supported.
                logger.critical(
                    f"The path provided to the VPN connection credentials ({str(vpn_auth)}) does not lead to a file. Aborting operation.")

        # VPN config path
        vpn_path = Path(config_path if config_path else ParametersManager().vpn).expanduser()

        logger.debug(f"Adding VPN from: {str(vpn_path.absolute())}")
        self.__vpn_path = vpn_path
        if vpn_path.is_file():
            # Configure VPN with single file
            self.addVolume(str(vpn_path.absolute()), "/vpn/config/client.ovpn", read_only=True)
            ovpn_parameters.append("--config /vpn/config/client.ovpn")
        else:
            # Configure VPN with directory
            logger.verbose(
                "Folder detected for VPN configuration. only the first *.ovpn file will be automatically launched when the container starts.")
            self.addVolume(str(vpn_path.absolute()), "/vpn/config", read_only=True)
            vpn_filename = None
            # Try to find the config file in order to configure the autostart command of the container
            for file in vpn_path.glob('*.ovpn'):
                logger.info(f"Using VPN config: {file}")
                # Get filename only to match the future container path
                vpn_filename = file.name
                ovpn_parameters.append(f"--config /vpn/config/{vpn_filename}")
                # If there is multiple match, only the first one is selected
                break
            if vpn_filename is None:
                logger.error("No *.ovpn files were detected. The VPN autostart will not work.")
                return None

        return ' '.join(ovpn_parameters)

    def __disableVPN(self) -> bool:
        """Remove a VPN profile for container startup (Only for interactive config)"""
        if self.__vpn_path:
            logger.verbose('Removing VPN configuration')
            self.__vpn_path = None
            self.__removeCapability("NET_ADMIN")
            self.__removeSysctl("net.ipv6.conf.all.disable_ipv6")
            self.removeDevice("/dev/net/tun")
            # Try to remove each possible volume
            self.removeVolume(container_path="/vpn/auth/creds.txt")
            self.removeVolume(container_path="/vpn/config/client.ovpn")
            self.removeVolume(container_path="/vpn/config")
            self.__restoreEntrypoint()
            return True
        return False

    def disableDefaultWorkspace(self):
        """Allows you to disable the default workspace volume"""
        # If a custom workspace is not define, disable workspace
        if self.__workspace_custom_path is None:
            self.__disable_workspace = True

    def prepareShare(self, share_name: str):
        """Add workspace share before container creation"""
        for mount in self.__mounts:
            if mount.get('Target') == '/workspace':
                # Volume is already prepared
                return
        if self.__workspace_custom_path is not None:
            self.addVolume(self.__workspace_custom_path, '/workspace')
        elif self.__disable_workspace:
            # Skip default volume workspace if disabled
            return
        else:
            # Add shared-data-volumes private workspace bind volume
            volume_path = str(UserConfig().private_volume_path.joinpath(share_name))
            self.addVolume(volume_path, '/workspace')

    def setNetworkMode(self, host_mode: bool):
        """Set container's network mode, true for host, false for bridge"""
        if host_mode is None:
            host_mode = True
        self.__network_host = host_mode

    def setContainerCommand(self, cmd: str):
        """Set the entrypoint command of the container. This command is executed at each startup.
        This parameter is applied to the container at creation."""
        self.__container_command = cmd

    def __restoreEntrypoint(self):
        """Restore container's entrypoint to its default configuration"""
        self.__container_command = self.__default_entrypoint

    def __addCapability(self, cap_string: str):
        """Add a linux capability to the container"""
        if cap_string in self.__capabilities:
            logger.warning("Capability already setup. Skipping.")
            return
        self.__capabilities.append(cap_string)

    def __removeCapability(self, cap_string: str):
        """Remove a linux capability from the container's config"""
        try:
            self.__capabilities.remove(cap_string)
            return True
        except ValueError:
            # When the capability is not present
            return False

    def __addSysctl(self, sysctl_key: str, config: str):
        """Add a linux sysctl to the container"""
        if sysctl_key in self.__sysctls.keys():
            logger.warning(f"Sysctl {sysctl_key} already setup to '{self.__sysctls[sysctl_key]}'. Skipping.")
            return
        self.__sysctls[sysctl_key] = config

    def __removeSysctl(self, sysctl_key: str):
        """Remove a linux capability from the container's config"""
        try:
            self.__sysctls.pop(sysctl_key)
            return True
        except KeyError:
            # When the sysctl is not present
            return False

    def getNetworkMode(self) -> str:
        """Network mode, text getter"""
        return "host" if self.__network_host else "bridge"

    def getPrivileged(self) -> bool:
        """Privileged getter"""
        return self.__privileged

    def getCapabilities(self) -> List[str]:
        """Capabilities getter"""
        return self.__capabilities

    def getSysctls(self) -> Dict[str, str]:
        """Sysctl custom rules getter"""
        return self.__sysctls

    def getWorkingDir(self) -> str:
        """Get default container's default working directory path"""
        return "/" if self.__disable_workspace else "/workspace"

    def getContainerCommand(self) -> str:
        """Get container entrypoint path"""
        return self.__container_command

    def getHostWorkspacePath(self) -> str:
        """Get private volume path (None if not set)"""
        if self.__workspace_custom_path:
            return FsUtils.resolvStrPath(self.__workspace_custom_path)
        elif self.__workspace_dedicated_path:
            return FsUtils.resolvStrPath(self.__workspace_dedicated_path)
        return "not found :("

    def getPrivateVolumePath(self) -> str:
        """Get private volume path (None if not set)"""
        return FsUtils.resolvStrPath(self.__workspace_dedicated_path)

    def isSharedResourcesEnable(self) -> bool:
        """Return if the feature 'shared resources' is enabled in this container config"""
        return self.__shared_resources

    def isExegolResourcesEnable(self) -> bool:
        """Return if the feature 'exegol resources' is enabled in this container config"""
        return self.__exegol_resources

    def isGUIEnable(self) -> bool:
        """Return if the feature 'GUI' is enabled in this container config"""
        return self.__enable_gui

    def isTimezoneShared(self) -> bool:
        """Return if the feature 'timezone' is enabled in this container config"""
        return self.__share_timezone

    def isWorkspaceCustom(self) -> bool:
        """Return if the workspace have a custom host volume"""
        return bool(self.__workspace_custom_path)

    def addVolume(self,
                  host_path: str,
                  container_path: str,
                  must_exist: bool = False,
                  read_only: bool = False,
                  volume_type: str = 'bind'):
        """Add a volume to the container configuration.
        When the host path does not exist (neither file nor folder):
        if must_exist is set, an CancelOperation exception will be thrown.
        Otherwise, a folder will attempt to be created at the specified path"""
        # The creation of the directory is ignored when it is a path to the remote drive
        if volume_type == 'bind' and not host_path.startswith("\\\\"):
            try:
                path = Path(host_path)
                if not (path.is_file() or path.is_dir()):
                    if must_exist:
                        raise CancelOperation(f"{host_path} does not exist on your host.")
                    else:
                        os.makedirs(host_path, exist_ok=True)
            except PermissionError:
                logger.error("Unable to create the volume folder on the filesystem locally.")
                logger.critical(f"Insufficient permissions to create the folder: {host_path}")
            except FileExistsError:
                # The volume targets a file that already exists on the file system
                pass
        mount = Mount(container_path, host_path, read_only=read_only, type=volume_type)
        self.__mounts.append(mount)

    def addRawVolume(self, volume_string):
        """Add a volume to the container configuration from raw text input.
        Expected format is: /source/path:/target/mount:rw"""
        logger.debug(f"Parsing raw volume config: {volume_string}")
        parsing = re.match(r'^((\w:)?([\\/][\w .,:\-|()&;]*)+):(([\\/][\w .,\-|()&;]*)+)(:(ro|rw))?$',
                           volume_string)
        if parsing:
            host_path = parsing.group(1)
            container_path = parsing.group(4)
            mode = parsing.group(7)
            if mode is None or mode == "rw":
                readonly = False
            elif mode == "ro":
                readonly = True
            else:
                logger.error(f"Error on volume config, mode: {mode} not recognized.")
                readonly = False
            logger.debug(
                f"Adding a volume from '{host_path}' to '{container_path}' as {'readonly' if readonly else 'read/write'}")
            self.addVolume(host_path, container_path, readonly)
        else:
            logger.critical(f"Volume '{volume_string}' cannot be parsed. Exiting.")

    def removeVolume(self, host_path: Optional[str] = None, container_path: Optional[str] = None) -> bool:
        """Remove a volume from the container configuration (Only before container creation)"""
        if host_path is None and container_path is None:
            # This is a dev problem
            raise ReferenceError('At least one parameter must be set')
        for i in range(len(self.__mounts)):
            # For each Mount object compare the host_path if supplied or the container_path si supplied
            if host_path is not None and self.__mounts[i].get("Source") == host_path:
                # When the right object is found, remove it from the list
                self.__mounts.pop(i)
                return True
            if container_path is not None and self.__mounts[i].get("Target") == container_path:
                # When the right object is found, remove it from the list
                self.__mounts.pop(i)
                return True
        return False

    def getVolumes(self) -> List[Mount]:
        """Volume config getter"""
        return self.__mounts

    def addDevice(self,
                  device_source: str,
                  device_dest: Optional[str] = None,
                  readonly: bool = False,
                  mknod: bool = False):
        """Add a device to the container configuration"""
        if device_dest is None:
            device_dest = device_source
        perm = 'r'
        if not readonly:
            perm += 'w'
        if mknod:
            perm += 'm'
        self.__devices.append(f"{device_source}:{device_dest}:{perm}")

    def removeDevice(self, device_source: str) -> bool:
        """Remove a device from the container configuration (Only before container creation)"""
        for i in range(len(self.__devices)):
            # For each device, compare source device
            if self.__devices[i].split(':')[0] == device_source:
                # When found, remove it from the config list
                self.__devices.pop(i)
                return True
        return False

    def getDevices(self) -> List[str]:
        """Devices config getter"""
        return self.__devices

    def addEnv(self, key: str, value: str):
        """Add an environment variable to the container configuration"""
        self.__envs[key] = value

    def removeEnv(self, key: str) -> bool:
        """Remove an environment variable to the container configuration (Only before container creation)"""
        try:
            self.__envs.pop(key)
            return True
        except KeyError:
            # When the Key is not present in the dictionary
            return False

    def addRawEnv(self, env: str):
        """Parse and add an environment variable from raw user input"""
        env_args = env.split('=')
        if len(env_args) < 2:
            logger.critical(f"Incorrect env syntax ({env}). Please use this format: KEY=value")
        key = env_args[0]
        value = '='.join(env_args[1:])
        logger.debug(f"Adding env {key}={value}")
        self.addEnv(key, value)

    def getEnvs(self) -> Dict[str, str]:
        """Envs config getter"""
        return self.__envs

    def getShellEnvs(self) -> List[str]:
        """Overriding envs when opening a shell"""
        result = []
        if self.__enable_gui:
            current_display = GuiUtils.getDisplayEnv()
            # If the default DISPLAY environment in the container is not the same as the DISPLAY of the user's session,
            # the environment variable will be updated in the exegol shell.
            if current_display and self.__envs.get('DISPLAY', '') != current_display:
                # This case can happen when the container is created from a local desktop
                # but exegol can be launched from remote access via ssh with X11 forwarding
                # (Be careful, an .Xauthority file may be needed).
                result.append(f"DISPLAY={current_display}")
        # TODO PATH common volume bin folder
        # Overwrite env from user parameters
        user_envs = ParametersManager().envs
        if user_envs is not None:
            for env in user_envs:
                if len(env.split('=')) < 2:
                    logger.critical(f"Incorrect env syntax ({env}). Please use this format: KEY=value")
                logger.debug(f"Add env to current shell: {env}")
                result.append(env)
        return result

    def getVpnName(self):
        """Get VPN Config name"""
        if self.__vpn_path is None:
            return "[bright_black]N/A[/bright_black]   "
        return f"[deep_sky_blue3]{self.__vpn_path.name}[/deep_sky_blue3]"

    def addPort(self,
                port_host: Union[int, str],
                port_container: Union[int, str],
                protocol: str = 'tcp',
                host_ip: str = '0.0.0.0'):
        """Add port NAT config, only applicable on bridge network mode."""
        if self.__network_host:
            logger.warning(
                "This container is configured to share the network with the host. You cannot open specific ports. Skipping.")
            logger.warning("Please set network mode to bridge in order to expose specific network ports.")
            return
        if protocol.lower() not in ['tcp', 'udp', 'sctp']:
            raise ProtocolNotSupported(f"Unknown protocol '{protocol}'")
        self.__ports[f"{port_container}/{protocol}"] = (host_ip, int(port_host))

    def getPorts(self) -> Dict[str, Optional[Union[int, Tuple[str, int], List[int]]]]:
        """Ports config getter"""
        return self.__ports

    def getTextFeatures(self, verbose: bool = False) -> str:
        """Text formatter for features configurations (Privileged, GUI, Network, Timezone, Shares)
        Print config only if they are different from their default config (or print everything in verbose mode)"""
        result = ""
        if verbose or self.__privileged:
            result += f"{getColor(not self.__privileged)[0]}Privileged: {'On :fire:' if self.__privileged else '[green]Off :heavy_check_mark:[/green]'}{getColor(not self.__privileged)[1]}{os.linesep}"
        if verbose or not self.__enable_gui:
            result += f"{getColor(self.__enable_gui)[0]}GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}"
        if verbose or not self.__network_host:
            result += f"[green]Network mode: [/green]{'host' if self.__network_host else 'custom'}{os.linesep}"
        if self.__vpn_path is not None:
            result += f"[green]VPN: [/green]{self.getVpnName()}{os.linesep}"
        if verbose or not self.__share_timezone:
            result += f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}"
        if verbose or not self.__exegol_resources:
            result += f"{getColor(self.__exegol_resources)[0]}Exegol resources: {boolFormatter(self.__exegol_resources)}{getColor(self.__exegol_resources)[1]}{os.linesep}"
        if verbose or not self.__shared_resources:
            result += f"{getColor(self.__shared_resources)[0]}My resources: {boolFormatter(self.__shared_resources)}{getColor(self.__shared_resources)[1]}{os.linesep}"
        return result.strip()

    def getTextMounts(self, verbose: bool = False) -> str:
        """Text formatter for Mounts configurations. The verbose mode does not exclude technical volumes."""
        result = ''
        for mount in self.__mounts:
            # Blacklist technical mount
            if not verbose and mount.get('Target') in ['/tmp/.X11-unix', '/opt/resources', '/etc/localtime',
                                                       '/etc/timezone', '/my-resources']:
                continue
            result += f"{mount.get('Source')} :right_arrow: {mount.get('Target')} {'(RO)' if mount.get('ReadOnly') else ''}{os.linesep}"
        return result

    def getTextDevices(self, verbose: bool = False) -> str:
        """Text formatter for Devices configuration. The verbose mode show full device configuration."""
        result = ''
        for device in self.__devices:
            if verbose:
                result += f"{device}{os.linesep}"
            else:
                src, dest = device.split(':')[:2]
                if src == dest:
                    result += f"{src}{os.linesep}"
                else:
                    result += f"{src}:right_arrow:{dest}{os.linesep}"
        return result

    def getTextEnvs(self, verbose: bool = False) -> str:
        """Text formatter for Envs configuration. The verbose mode does not exclude technical variables."""
        result = ''
        for k, v in self.__envs.items():
            # Blacklist technical variables, only shown in verbose
            if not verbose and k in ["_JAVA_AWT_WM_NONREPARENTING", "QT_X11_NO_MITSHM", "DISPLAY", "PATH"]:
                continue
            result += f"{k}={v}{os.linesep}"
        return result

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"Privileged: {self.__privileged}{os.linesep}" \
               f"Capabilities: {self.__capabilities}{os.linesep}" \
               f"Sysctls: {self.__sysctls}{os.linesep}" \
               f"X: {self.__enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {'host' if self.__network_host else 'custom'}{os.linesep}" \
               f"Share timezone: {self.__share_timezone}{os.linesep}" \
               f"Common resources: {self.__shared_resources}{os.linesep}" \
               f"Env ({len(self.__envs)}): {self.__envs}{os.linesep}" \
               f"Shares ({len(self.__mounts)}): {self.__mounts}{os.linesep}" \
               f"Devices ({len(self.__devices)}): {self.__devices}{os.linesep}" \
               f"VPN: {self.getVpnName()}"

    def printConfig(self):
        """Log current object state, debug only"""
        logger.info(f"Current container config :{os.linesep}{self}")
