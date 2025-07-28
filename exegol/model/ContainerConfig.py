import errno
import logging
import os
import random
import re
import socket
import string
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePath
from typing import Optional, List, Dict, Union, Tuple, cast

from docker.models.containers import Container
from docker.types import Mount

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.UserConfig import UserConfig
from exegol.console.ConsoleFormat import boolFormatter, getColor
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.console.cli.SyntaxFormat import SyntaxFormat
from exegol.exceptions.ExegolExceptions import ProtocolNotSupported, CancelOperation
from exegol.model.ExegolModules import ExegolModules
from exegol.model.ExegolNetwork import ExegolNetwork, ExegolNetworkMode, DockerDrivers
from exegol.utils import FsUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.FsUtils import check_sysctl_value, mkdir
from exegol.utils.GuiUtils import GuiUtils
from exegol.utils.SessionHandler import SessionHandler

if EnvInfo.is_windows_shell or EnvInfo.is_mac_shell:
    from tzlocal import get_localzone_name


class ContainerConfig:
    """Configuration class of an exegol container"""

    # Default hardcoded value
    __default_entrypoint = ["/bin/bash", "/.exegol/entrypoint.sh"]
    __default_shm_size = "64M"
    __fallback_network_mode = ExegolNetworkMode[UserConfig().network_fallback_mode.lower()]

    # Reference static config data
    __static_gui_envs = {"_JAVA_AWT_WM_NONREPARENTING": "1", "QT_X11_NO_MITSHM": "1"}
    __default_desktop_port = {"http": 6080, "vnc": 5900}

    # Verbose only filters
    __verbose_only_envs = ["DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_RUNTIME_DIR", "PATH", "TZ", "_JAVA_OPTIONS"]
    __verbose_only_mounts = ['/tmp/.X11-unix', '/opt/resources', '/etc/localtime',
                             '/etc/timezone', '/my-resources', '/opt/my-resources',
                             '/.exegol/entrypoint.sh', '/.exegol/spawn.sh', '/tmp/wayland-0', '/tmp/wayland-1']

    # Whitelist device for Docker Desktop
    __whitelist_dd_devices = ["/dev/net/tun", "/dev/fuse"]

    class ExegolFeatures(Enum):
        shell_logging = "org.exegol.feature.shell_logging"
        desktop = "org.exegol.feature.desktop"

        @classmethod
        def values(cls):
            return list(map(lambda c: c.value, cls))

    class ExegolMetadata(Enum):
        creation_date = "org.exegol.metadata.creation_date"
        comment = "org.exegol.metadata.comment"
        password = "org.exegol.metadata.passwd"
        backups = "org.exegol.metadata.backups"

        @classmethod
        def values(cls):
            return list(map(lambda c: c.value, cls))

    class ExegolEnv(Enum):
        # feature
        exegol_name = "EXEGOL_NAME"  # Supply the name of the container to itself when overriding the hostname
        randomize_service_port = "EXEGOL_RANDOMIZE_SERVICE_PORTS"  # Enable the randomize port feature when using exegol is network host mode
        # config
        user_shell = "EXEGOL_START_SHELL"  # Set the default shell to use
        exegol_user = "EXEGOL_USERNAME"  # Select the username of the container
        shell_logging_method = "EXEGOL_START_SHELL_LOGGING"  # Enable and select the shell logging method
        shell_logging_compress = "EXEGOL_START_SHELL_COMPRESS"  # Configure if the logs must be compressed at the end of the shell
        desktop_protocol = "EXEGOL_DESKTOP_PROTO"  # Configure which desktop module must be started
        desktop_host = "EXEGOL_DESKTOP_HOST"  # Select the host / ip to expose the desktop service on (container side)
        desktop_port = "EXEGOL_DESKTOP_PORT"  # Select the port to expose the desktop service on (container side)

    # Label features (label name / wrapper method to enable the feature)
    __label_features = {ExegolFeatures.shell_logging.value: "enableShellLogging",
                        ExegolFeatures.desktop.value: "configureDesktop"}
    # Label metadata (label name / [setter method to set the value, getter method to update labels])
    __label_metadata = {ExegolMetadata.creation_date.value: ["setCreationDate", "getCreationDate"],
                        ExegolMetadata.comment.value: ["setComment", "getComment"],
                        ExegolMetadata.password.value: ["setPasswd", "getPasswd"],
                        ExegolMetadata.backups.value: ["setBackupHistory", "getBackupHistory"]}

    def __init__(self, container: Optional[Container] = None, container_name: Optional[str] = None, hostname: Optional[str] = None):
        """Container config default value"""
        if container_name is None:
            self.container_name: str = ""
        elif container_name.startswith("exegol-"):
            self.container_name = container_name
        else:
            self.container_name = f'exegol-{container_name}'
        self.__enable_gui: bool = False
        self.__gui_engine: List[str] = []
        self.__share_timezone: bool = False
        self.__my_resources: bool = False
        self.__my_resources_path: str = "/opt/my-resources"
        self.__exegol_resources: bool = False
        self.__networks: List[ExegolNetwork] = []
        self.__privileged: bool = False
        self.__wrapper_start_enabled: bool = False
        self.__mounts: List[Mount] = []
        self.__devices: List[str] = []
        self.__capabilities: List[str] = []
        self.__sysctls: Dict[str, str] = {}
        self.__envs: Dict[str, str] = {}
        self.__labels: Dict[str, str] = {}
        self.__ports: Dict[str, Optional[Union[int, Tuple[str, int], List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]]]]] = {}
        self.__extra_host: Dict[str, str] = {}
        self.interactive: bool = False
        self.tty: bool = False
        self.shm_size: str = self.__default_shm_size
        self.__workspace_custom_path: Optional[str] = None
        self.__workspace_dedicated_path: Optional[str] = None
        self.__disable_workspace: bool = False
        self.__container_entrypoint: List[str] = self.__default_entrypoint
        self.__vpn_path: Optional[Union[Path, PurePath]] = None
        self.__shell_logging: bool = False
        # Entrypoint features
        self.legacy_entrypoint: bool = True
        self.__vpn_mode: Optional[str] = None
        self.__vpn_parameters: Optional[str] = None
        self.__run_cmd: bool = False
        self.__endless_container: bool = True
        self.__desktop_proto: Optional[str] = None
        self.__desktop_host: Optional[str] = None
        self.__desktop_port: Optional[int] = None
        # Metadata attributes
        self.__creation_date: Optional[str] = None
        self.__backup_history: Optional[str] = None
        self.__comment: Optional[str] = None
        self.__username: str = "root"
        self.__passwd: Optional[str] = self.generateRandomPassword()
        if hostname is not None:
            self.hostname = hostname
            if container is None:  # if this is a new container
                self.addEnv(ContainerConfig.ExegolEnv.exegol_name.value, self.container_name)
        else:
            self.hostname = self.container_name

        if container is not None:
            self.__parseContainerConfig(container)
        else:
            self.__wrapper_start_enabled = True
            self.addVolume(str(ConstantConfig.spawn_context_path_obj), "/.exegol/spawn.sh", read_only=True, must_exist=True)
            # After __init__, await self.configFromUser() should be called

    # ===== Config parsing section =====

    def __parseContainerConfig(self, container: Container) -> None:
        """Parse Docker object to setup self configuration"""
        # Reset default attributes
        self.__passwd = None
        self.__share_timezone = False
        self.__my_resources = False
        self.__enable_gui = False
        # Container Config section
        self.container_name = container.name
        container_config = container.attrs.get("Config", {})
        self.hostname = container_config.get('Hostname', self.container_name)
        self.tty = container_config.get("Tty", True)
        self.__parseEnvs(container_config.get("Env", []))
        self.__parseLabels(container_config.get("Labels", {}))
        self.interactive = container_config.get("OpenStdin", True)
        self.legacy_entrypoint = container_config.get("Entrypoint") is None

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.__privileged = host_config.get("Privileged", False)
        caps = host_config.get("CapAdd", [])
        if caps is not None:
            self.__capabilities = caps
        logger.debug(f"└── Capabilities : {self.__capabilities}")
        self.__sysctls = host_config.get("Sysctls", {})
        devices = host_config.get("Devices", [])
        if devices is not None:
            for device in devices:
                self.__devices.append(
                    f"{device.get('PathOnHost', '?')}:{device.get('PathInContainer', '?')}:{device.get('CgroupPermissions', '?')}")
        logger.debug(f"└── Load devices : {self.__devices}")

        # Volumes section
        container_name = container.name[7:] if container.name.startswith("exegol-") else container.name
        self.__parseMounts(container.attrs.get("Mounts", []), container_name)

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.__networks = ExegolNetwork.parse_networks(network_settings["Networks"], container_name=self.container_name)
        self.__ports = network_settings.get("Ports", {})

    def __parseEnvs(self, envs: List[str]) -> None:
        """Parse envs object syntax"""
        for env in envs:
            logger.debug(f"└── Parsing envs : {env}")
            # Removing " and ' at the beginning and the end of the string before splitting key / value
            self.addRawEnv(env.strip("'").strip('"'))
        envs_key = self.__envs.keys()
        if "DISPLAY" in envs_key:
            self.__enable_gui = True
            self.__gui_engine.append("X11")
        if "WAYLAND_DISPLAY" in envs_key:
            self.__enable_gui = True
            self.__gui_engine.append("Wayland")
        if "TZ" in envs_key:
            self.__share_timezone = True

    def __parseLabels(self, labels: Dict[str, str]) -> None:
        """Parse envs object syntax"""
        for key, value in labels.items():
            if not key.startswith("org.exegol."):
                continue
            logger.debug(f"└── Parsing label : {key}")
            if key in self.ExegolMetadata.values():
                # Find corresponding feature and attributes
                refs = self.__label_metadata.get(key)  # Setter
                if refs is not None:
                    # reflective execution of setter method (set metadata value to the corresponding attribute)
                    getattr(self, refs[0])(value)
            elif key in self.ExegolFeatures.values():
                self.addLabel(key, value)
                # Find corresponding feature and function
                enable_function = self.__label_features.get(key)
                if enable_function is not None:
                    # reflective execution of the feature enable method (add label & set attributes)
                    if value == "Enabled":
                        value = ""
                    getattr(self, enable_function)(value)

    def __parseMounts(self, mounts: Optional[List[Dict]], name: str) -> None:
        """Parse Mounts object"""
        if mounts is None:
            mounts = []
        self.__disable_workspace = True
        ovpn_parameters = []
        for share in mounts:
            logger.debug(f"└── Parsing mount : {share}")
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

            destination = share.get('Destination', '')
            if destination in ["/etc/timezone", "/etc/localtime"]:
                self.__share_timezone = True
            elif "/opt/resources" in destination:
                self.__exegol_resources = True
            elif "/opt/my-resources" in destination:
                self.__my_resources = True
                self.__my_resources_path = destination
            elif "/workspace" in destination:
                # Workspace are always bind mount
                assert src_path is not None
                obj_path = cast(PurePath, src_path)
                logger.debug(f"└── Loading workspace volume source : {obj_path}")
                self.__disable_workspace = False
                # TODO use label to identify manage workspace and support cross env removing
                if obj_path is not None and obj_path.name == name and \
                        (obj_path.parent.name == "shared-data-volumes" or obj_path.parent == UserConfig().private_volume_path):  # Check legacy path and new custom path
                    logger.debug("└── Private workspace detected")
                    self.__workspace_dedicated_path = str(obj_path)
                else:
                    logger.debug("└── Custom workspace detected")
                    self.__workspace_custom_path = str(obj_path)
            elif "/.exegol/vpn" in destination or destination.startswith("/etc/wireguard/"):
                # VPN are always bind mount
                assert src_path is not None
                self.__vpn_path = Path(src_path)
                if self.__vpn_path.suffix == ".ovpn":
                    self.__vpn_mode = "ovpn"
                    ovpn_parameters.append(f"--config {destination}")
                elif self.__vpn_path.suffix == ".conf":
                    self.__vpn_mode = "wgconf"
                    self.__vpn_parameters = Path(destination).name[:-5]
                logger.debug(f"└── Loading VPN config: {self.__vpn_path.name}")
            elif destination == "/.exegol/vpn/auth/creds.txt":
                ovpn_parameters.append(f"--auth-user-pass /.exegol/vpn/auth/creds.txt")
            elif destination == "/.exegol/spawn.sh":
                self.__wrapper_start_enabled = True
        if len(ovpn_parameters) > 0:
            self.__vpn_parameters = ' '.join(ovpn_parameters)

    # ===== Config init section =====

    async def configFromUser(self) -> "ContainerConfig":
        """Create Exegol configuration from user input"""
        # Container configuration from user CLI options
        try:
            # Container configuration from user CLI options
            if ParametersManager().X11:
                await self.enableGUI()
            if ParametersManager().share_timezone:
                self.enableSharedTimezone()
            self.setNetworkMode(ParametersManager().network)
            if ParametersManager().ports is not None:
                for port in ParametersManager().ports:
                    self.addRawPort(port)
            if ParametersManager().my_resources:
                self.enableMyResources()
            if ParametersManager().exegol_resources:
                await self.enableExegolResources()
            if ParametersManager().log or UserConfig().always_enable_shell_logging:
                self.enableShellLogging(ParametersManager().log_method,
                                        UserConfig().shell_logging_compress ^ ParametersManager().log_compress)
            if ParametersManager().workspace_path:
                if ParametersManager().mount_current_dir:
                    logger.warning(f'Workspace conflict detected (-cwd cannot be use with -w). Using: {ParametersManager().workspace_path}')
                self.setWorkspaceShare(ParametersManager().workspace_path)
            elif ParametersManager().mount_current_dir:
                self.enableCwdShare()
            if ParametersManager().privileged:
                self.setPrivileged()
            elif ParametersManager().capabilities is not None:
                for cap in ParametersManager().capabilities:
                    self.addCapability(cap)
            if ParametersManager().volumes is not None:
                for volume in ParametersManager().volumes:
                    await self.addRawVolume(volume)
            if ParametersManager().devices is not None:
                for device in ParametersManager().devices:
                    self.addUserDevice(device)
            if ParametersManager().vpn is not None:
                await self.enableVPN()
            if ParametersManager().envs is not None:
                for env in ParametersManager().envs:
                    self.addRawEnv(env)
            if UserConfig().desktop_default_enable ^ ParametersManager().desktop:
                self.enableDesktop(ParametersManager().desktop_config)
            if ParametersManager().comment:
                self.addComment(ParametersManager().comment)
        except CancelOperation as e:
            logger.critical(f"Unable to create a new container: {e}")
            raise e
        return self

    # ===== Feature section =====

    async def interactiveConfig(self, container_name: str) -> List[str]:
        """Interactive procedure allowing the user to configure its new container"""
        logger.info("Starting interactive configuration")

        command_options = []

        # Workspace config
        if await ExegolRich.Confirm(
                "Do you want to [green]share[/green] your [blue]current host working directory[/blue] in the new container's worskpace?",
                default=False):
            self.enableCwdShare()
            command_options.append("-cwd")
        elif await ExegolRich.Confirm(
                f"Do you want to [green]share[/green] [blue]a host directory[/blue] in the new container's workspace [blue]different than the default one[/blue] ([magenta]{UserConfig().private_volume_path / container_name}[/magenta])?",
                default=False):
            while True:
                workspace_path = await ExegolRich.Ask("Enter the path of your workspace")
                if Path(workspace_path).expanduser().is_dir():
                    break
                else:
                    logger.error("The provided path is not a folder or does not exist.")
            self.setWorkspaceShare(workspace_path)
            command_options.append(f"-w {workspace_path}")

        # X11 sharing (GUI) config
        if self.__enable_gui:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]X11[/blue] (i.e. GUI apps)?", False):
                self.__disableGUI()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] [blue]X11[/blue] (i.e. GUI apps)?", False):
            await self.enableGUI()
        # Command builder info
        if not self.__enable_gui:
            command_options.append("--disable-X11")

        # Desktop Config
        if self.isDesktopEnabled():
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]Desktop[/blue]?", False):
                self.__disableDesktop()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] [blue]Desktop[/blue]?", False):
            self.enableDesktop()
        # Command builder info
        if self.isDesktopEnabled():
            command_options.append("--desktop")

        # Timezone config
        if self.__share_timezone:
            if await ExegolRich.Confirm("Do you want to [orange3]remove[/orange3] your [blue]shared timezone[/blue] config?", False):
                self.__disableSharedTimezone()
        elif await ExegolRich.Confirm("Do you want to [green]share[/green] your [blue]host's timezone[/blue]?", False):
            self.enableSharedTimezone()
        # Command builder info
        if not self.__share_timezone:
            command_options.append("--disable-shared-timezones")

        # my-resources config
        if self.__my_resources:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]my-resources[/blue]?", False):
                self.__disableMyResources()
        elif await ExegolRich.Confirm("Do you want to [green]activate[/green] [blue]my-resources[/blue]?", False):
            self.enableMyResources()
        # Command builder info
        if not self.__my_resources:
            command_options.append("--disable-my-resources")

        # Exegol resources config
        if self.__exegol_resources:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] the [blue]exegol resources[/blue]?", False):
                self.disableExegolResources()
        elif await ExegolRich.Confirm("Do you want to [green]activate[/green] the [blue]exegol resources[/blue]?", False):
            await self.enableExegolResources()
        # Command builder info
        if not self.__exegol_resources:
            command_options.append("--disable-exegol-resources")

        # Network config
        if self.__networks[0].getNetworkMode() == ExegolNetworkMode.host:
            if await ExegolRich.Confirm("Do you want to use a [blue]dedicated private network[/blue]?", False):
                self.setNetworkMode(self.__fallback_network_mode)
        elif await ExegolRich.Confirm("Do you want to share the [green]host's[/green] [blue]networks[/blue]?", False):
            self.setNetworkMode(ExegolNetworkMode.host)
        # Command builder info
        if self.__networks[0] != ExegolNetworkMode.host:
            command_options.append(f"--network nat")

        # Shell logging config
        if self.__shell_logging:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] automatic [blue]shell logging[/blue]?", False):
                self.__disableShellLogging()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] automatic [blue]shell logging[/blue]?", False):
            self.enableShellLogging(UserConfig().shell_logging_method, UserConfig().shell_logging_compress)
        # Command builder info
        if self.__shell_logging:
            command_options.append("--log")

        # VPN config
        if self.__vpn_path is None and await ExegolRich.Confirm(
                "Do you want to [green]enable[/green] a [blue]VPN[/blue] for this container", False):
            while True:
                vpn_path = await ExegolRich.Ask('Enter the path to the OpenVPN config file')
                if Path(vpn_path).expanduser().is_file():
                    await self.enableVPN(vpn_path)
                    break
                else:
                    logger.error("No config files were found.")
        elif self.__vpn_path and await ExegolRich.Confirm(
                "Do you want to [orange3]remove[/orange3] your [blue]VPN configuration[/blue] in this container", False):
            self.__disableVPN()
        if self.__vpn_path:
            command_options.append(f"--vpn {self.__vpn_path}")

        return command_options

    async def enableGUI(self) -> None:
        """Procedure to enable GUI feature"""
        x11_available = await GuiUtils.isX11GuiAvailable()
        wayland_available = GuiUtils.isWaylandGuiAvailable()
        if not x11_available and not wayland_available:
            logger.error("Console GUI feature (i.e. GUI apps) is [red]not available[/red] on your environment. [orange3]Skipping[/orange3].")
            return
        if not self.__enable_gui:
            logger.verbose("Config: Enabling display sharing")
            if x11_available:
                try:
                    host_path: Optional[Union[Path, str]] = GuiUtils.getX11SocketPath()
                    if host_path is not None:
                        assert type(host_path) is str
                        self.addVolume(host_path, GuiUtils.default_x11_path, must_exist=True)
                    # X11 can be used accros network without volume on Mac
                    self.addEnv("DISPLAY", GuiUtils.getDisplayEnv())
                    self.__gui_engine.append("X11")
                except CancelOperation as e:
                    logger.warning(f"Graphical X11 interface sharing could not be enabled: {e}")
            else:
                logger.warning("X11 cannot be shared, only wayland, some graphical applications might not work...")
            if wayland_available:
                try:
                    host_path = GuiUtils.getWaylandSocketPath()
                    if host_path is not None:
                        self.addVolume(host_path, f"/tmp/{host_path.name}", must_exist=True)
                        self.addEnv("XDG_SESSION_TYPE", "wayland")
                        self.addEnv("XDG_RUNTIME_DIR", "/tmp")
                        self.addEnv("WAYLAND_DISPLAY", GuiUtils.getWaylandEnv())
                        self.__gui_engine.append("Wayland")
                except CancelOperation as e:
                    logger.warning(f"Graphical Wayland interface sharing could not be enabled: {e}")
            # TODO support pulseaudio
            for k, v in self.__static_gui_envs.items():
                self.addEnv(k, v)

            # Fix XQuartz render: https://github.com/ThePorgs/Exegol/issues/229
            if EnvInfo.isMacHost():
                self.addEnv("_JAVA_OPTIONS", '-Dsun.java2d.xrender=false')

            self.__enable_gui = True

    def __disableGUI(self) -> None:
        """Procedure to disable X11 (GUI) feature (Only for interactive config)"""
        if self.__enable_gui:
            self.__enable_gui = False
            logger.verbose("Config: Disabling display sharing")
            self.removeVolume(container_path="/tmp/.X11-unix")
            self.removeEnv("DISPLAY")
            self.removeEnv("XDG_SESSION_TYPE")
            self.removeEnv("XDG_RUNTIME_DIR")
            self.removeEnv("WAYLAND_DISPLAY")
            for k in self.__static_gui_envs.keys():
                self.removeEnv(k)
            self.__gui_engine.clear()

    def enableSharedTimezone(self) -> None:
        """Procedure to enable shared timezone feature"""
        if not self.__share_timezone:
            logger.verbose("Config: Enabling host timezones")
            if EnvInfo.is_windows_shell or EnvInfo.is_mac_shell:
                current_tz = get_localzone_name()
                if current_tz:
                    logger.debug(f"Sharing timezone via TZ env var: '{current_tz}'")
                    self.addEnv("TZ", current_tz)
                else:
                    logger.warning("Your system timezone cannot be shared.")
                    return
            else:
                # Try to share /etc/timezone (deprecated old timezone file)
                try:
                    self.addVolume("/etc/timezone", "/etc/timezone", read_only=True, must_exist=True)
                    logger.verbose("Volume was successfully added for [magenta]/etc/timezone[/magenta]")
                    timezone_loaded = True
                except CancelOperation:
                    logger.verbose("File /etc/timezone is missing on host, cannot create volume for this.")
                    timezone_loaded = False
                # Try to share /etc/localtime (new timezone file)
                try:
                    self.addVolume("/etc/localtime", "/etc/localtime", read_only=True, must_exist=True)
                    logger.verbose("Volume was successfully added for [magenta]/etc/localtime[/magenta]")
                except CancelOperation as e:
                    if not timezone_loaded:
                        # If neither file was found, disable the functionality
                        logger.error(f"The host's timezone could not be shared: {e}")
                        return
                    else:
                        logger.warning("File [magenta]/etc/localtime[/magenta] is [orange3]missing[/orange3] on host, "
                                       "cannot create volume for this. Relying instead on [magenta]/etc/timezone[/magenta] [orange3](deprecated)[/orange3].")
            self.__share_timezone = True

    def __disableSharedTimezone(self) -> None:
        """Procedure to disable shared timezone feature (Only for interactive config)"""
        if self.__share_timezone:
            self.__share_timezone = False
            logger.verbose("Config: Disabling host timezones")
            self.removeVolume("/etc/timezone")
            self.removeVolume("/etc/localtime")

    def enableMyResources(self) -> None:
        """Procedure to enable shared volume feature"""
        if not self.__my_resources:
            logger.verbose("Config: Enabling my-resources volume")
            self.__my_resources = True
            # Adding volume config
            self.addVolume(UserConfig().my_resources_path, '/opt/my-resources', enable_sticky_group=True, force_sticky_group=True)

    def __disableMyResources(self) -> None:
        """Procedure to disable shared volume feature (Only for interactive config)"""
        if self.__my_resources:
            logger.verbose("Config: Disabling my-resources volume")
            self.__my_resources = False
            self.removeVolume(container_path='/opt/my-resources')

    async def enableExegolResources(self) -> bool:
        """Procedure to enable exegol resources volume feature"""
        if not self.__exegol_resources:
            # Check if resources are installed / up-to-date
            try:
                if not await ExegolModules().isExegolResourcesReady():
                    raise CancelOperation
            except CancelOperation:
                # Error during installation, skipping operation
                if UserConfig().enable_exegol_resources:
                    logger.warning("Exegol resources have not been downloaded, the feature cannot be enabled yet")
                return False
            logger.verbose("Config: Enabling exegol resources volume")
            self.__exegol_resources = True
            # Adding volume config
            self.addVolume(UserConfig().exegol_resources_path, '/opt/resources')
        return True

    def disableExegolResources(self) -> None:
        """Procedure to disable exegol resources volume feature (Only for interactive config)"""
        if self.__exegol_resources:
            logger.verbose("Config: Disabling exegol resources volume")
            self.__exegol_resources = False
            self.removeVolume(container_path='/opt/resources')

    def enableShellLogging(self, log_method: str, compress_mode: Optional[bool] = None) -> None:
        """Procedure to enable exegol shell logging feature"""
        if not self.__shell_logging:
            logger.verbose("Config: Enabling shell logging")
            self.__shell_logging = True
            self.addEnv(self.ExegolEnv.shell_logging_method.value, log_method)
            if compress_mode is not None:
                self.addEnv(self.ExegolEnv.shell_logging_compress.value, str(compress_mode))
            self.addLabel(self.ExegolFeatures.shell_logging.value, log_method)

    def __disableShellLogging(self) -> None:
        """Procedure to disable exegol shell logging feature"""
        if self.__shell_logging:
            logger.verbose("Config: Disabling shell logging")
            self.__shell_logging = False
            self.removeEnv(self.ExegolEnv.shell_logging_method.value)
            self.removeEnv(self.ExegolEnv.shell_logging_compress.value)
            self.removeLabel(self.ExegolFeatures.shell_logging.value)

    def isDesktopEnabled(self) -> bool:
        return self.__desktop_proto is not None

    def enableDesktop(self, desktop_config: str = "") -> None:
        """Procedure to enable exegol desktop feature"""
        if not self.isDesktopEnabled():
            if self.isNetworkDisabled():
                logger.error(f"The current network mode doesn't support the desktop feature.")
                return
            logger.verbose("Config: Enabling exegol desktop")
            self.configureDesktop(desktop_config, create_mode=True)
            assert self.__desktop_proto is not None
            assert self.__desktop_host is not None
            assert self.__desktop_port is not None
            self.addLabel(self.ExegolFeatures.desktop.value, f"{self.__desktop_proto}:{self.__desktop_host}:{self.__desktop_port}")
            # Env var are used to send these parameter to the desktop-start script
            self.addEnv(self.ExegolEnv.desktop_protocol.value, self.__desktop_proto)
            self.addEnv(self.ExegolEnv.exegol_user.value, self.getUsername())

            if self.isNetworkHost():
                self.addEnv(self.ExegolEnv.desktop_host.value, self.__desktop_host)
                self.addEnv(self.ExegolEnv.desktop_port.value, str(self.__desktop_port))
            else:
                # Container in bridge mode
                # If we do not specify the host to the container it will automatically choose eth0 interface
                # Using default port for the service
                self.addEnv(self.ExegolEnv.desktop_port.value, str(self.__default_desktop_port.get(self.__desktop_proto)))
                # Exposing desktop service
                self.addPort(port_host=self.__desktop_port, port_container=self.__default_desktop_port[self.__desktop_proto], host_ip=self.__desktop_host)

    def configureDesktop(self, desktop_config: str, create_mode: bool = False) -> None:
        """Configure the exegol desktop feature from user parameters.
        Accepted format: 'proto:host:port'
        """
        # Apply default config
        self.__desktop_proto = UserConfig().desktop_default_proto
        self.__desktop_host = "127.0.0.1" if UserConfig().desktop_default_localhost else "0.0.0.0"

        # Set config from user input
        for i, data in enumerate(desktop_config.split(":")):
            if not data:
                continue
            if i == 0:  # protocol
                logger.debug(f"Desktop proto set: {data}")
                data = data.lower()
                if data in UserConfig.desktop_available_proto:
                    self.__desktop_proto = data
                else:
                    logger.critical(f"The desktop mode '{data}' is not supported. Please choose a supported mode: [green]{', '.join(UserConfig.desktop_available_proto)}[/green].")
            elif i == 1 and data:  # host
                logger.debug(f"Desktop host set: {data}")
                self.__desktop_host = data
            elif i == 2:  # port
                logger.debug(f"Desktop port set: {data}")
                try:
                    self.__desktop_port = int(data)
                except ValueError:
                    logger.critical(f"Invalid desktop port: '{data}' is not a valid port.")
            else:
                logger.critical(f"Your configuration is invalid, please use the following format: {SyntaxFormat.desktop_config}")

        if self.__desktop_port is None:
            logger.debug(f"Desktop port will be set automatically")
            self.__desktop_port = self.__findAvailableRandomPort(self.__desktop_host)

        if create_mode:
            # Check if the port is available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self.__desktop_host, self.__desktop_port))
                except socket.error as e:
                    if e.errno == errno.EADDRINUSE:
                        logger.critical(f"The port {self.__desktop_host}:{self.__desktop_port} is already in use !")
                    elif e.errno == errno.EADDRNOTAVAIL:
                        logger.critical(f"The network {self.__desktop_host}:{self.__desktop_port} is not available !")
                    else:
                        logger.critical(f"The supplied network configuration {self.__desktop_host}:{self.__desktop_port} is not available ! ([{e.errno}] {e})")

    def __disableDesktop(self) -> None:
        """Procedure to disable exegol desktop feature"""
        if self.isDesktopEnabled():
            logger.verbose("Config: Disabling exegol desktop")
            assert self.__desktop_proto is not None
            if self.isNetworkHost():
                self.__removePort(self.__default_desktop_port[self.__desktop_proto])
            self.__desktop_proto = None
            self.__desktop_host = None
            self.__desktop_port = None
            self.removeLabel(self.ExegolFeatures.desktop.value)
            self.removeEnv(self.ExegolEnv.desktop_protocol.value)
            self.removeEnv(self.ExegolEnv.exegol_user.value)
            self.removeEnv(self.ExegolEnv.desktop_host.value)
            self.removeEnv(self.ExegolEnv.desktop_port.value)

    def enableCwdShare(self) -> None:
        """Procedure to share Current Working Directory with the /workspace of the container"""
        self.__workspace_custom_path = os.getcwd()
        logger.verbose(f"Config: Sharing current workspace directory {self.__workspace_custom_path}")

    async def enableVPN(self, config_path: Optional[str] = None) -> None:
        """Configure a VPN profile for container startup"""
        # Check host mode : custom (allows you to isolate the VPN connection from the host's network)
        if self.isNetworkHost() and ParametersManager().network is None:
            if EnvInfo.isLinuxHost():
                logger.info(f"Defaulting to [magenta]{self.__fallback_network_mode.value}[/magenta] to protect host from VPN. Use [blue]--network host[/blue] if you need to access VPN from your host.")
            self.setNetworkMode(self.__fallback_network_mode)
        # Add NET_ADMIN capabilities, this privilege is necessary to mount network tunnels interfaces
        self.addCapability("NET_ADMIN")
        # Add sysctl ipv6 config, some VPN connection need IPv6 to be enabled
        # TODO test with ipv6 disable with kernel modules
        skip_sysctl = False
        if self.isNetworkHost() and EnvInfo.is_linux_shell:
            # Check if IPv6 have been disabled on the host with sysctl
            if check_sysctl_value("net.ipv6.conf.all.disable_ipv6", "0"):
                skip_sysctl = True
        if not skip_sysctl:
            self.__addSysctl("net.ipv6.conf.all.disable_ipv6", "0")

        if config_path is not None or ParametersManager().vpn != '':
            # VPN config path
            vpn_path = Path(config_path if config_path else ParametersManager().vpn).expanduser()

            logger.debug(f"Adding VPN from: {str(vpn_path.absolute())}")
            # Sharing VPN configuration with the container
            if vpn_path.is_dir() or (vpn_path.is_file() and vpn_path.suffix == ".ovpn"):
                # Add tun device, this device is needed to create OpenVPN tunnels
                self.__addDevice("/dev/net/tun", mknod=True)
                # OpenVPN config
                self.__vpn_mode = "ovpn"
                self.__vpn_parameters = await self.__prepareOpenVpnVolumes(vpn_path)
            elif vpn_path.is_file() and vpn_path.suffix == ".conf":
                if not SessionHandler().pro_feature_access():
                    logger.error("WireGuard VPN support is exclusive to Pro/Enterprise users. Coming soon to Community.")
                    self.__disableVPN()
                    return
                # Wireguard config
                self.__addSysctl("net.ipv4.conf.all.src_valid_mark", "1")
                self.__vpn_mode = "wgconf"
                self.__vpn_parameters = self.__prepareWireguardVolumes(vpn_path)
            else:
                logger.critical(f"Your VPN configuration {vpn_path} is not an OpenVPN directory / [green].ovpn[/green] file or a WireGuard [green].conf[/green] file.")
        else:
            # Add tun device, this device is needed to create OpenVPN tunnels
            self.__addDevice("/dev/net/tun", mknod=True)
            # Add sysctl for wireguard default gateway
            self.__addSysctl("net.ipv4.conf.all.src_valid_mark", "1")
            logger.success("Enabling VPN capabilities without managing a VPN connection")

    def __disableVPN(self) -> bool:
        """Remove a VPN profile for container startup (Only for interactive config)"""
        if self.__vpn_path:
            logger.verbose('Removing VPN configuration')
            self.__vpn_path = None
            self.__vpn_mode = None
            self.__vpn_parameters = None
            self.__removeCapability("NET_ADMIN")
            self.__removeSysctl("net.ipv6.conf.all.disable_ipv6")
            self.__removeSysctl("net.ipv4.conf.all.src_valid_mark")
            self.removeDevice("/dev/net/tun")
            # Try to remove each possible volume
            self.removeVolume(container_path="/.exegol/vpn/auth/creds.txt")
            self.removeVolume(container_path="/.exegol/vpn/config/client.ovpn")
            self.removeVolume(container_path="/.exegol/vpn/config")
            self.removeVolume(container_path="/etc/wireguard/wg0.conf")
            return True
        return False

    def disableDefaultWorkspace(self) -> None:
        """Allows you to disable the default workspace volume"""
        # If a custom workspace is not define, disable workspace
        if self.__workspace_custom_path is None:
            self.__disable_workspace = True

    def addComment(self, comment: str) -> None:
        """Procedure to add comment to a container"""
        if not self.__comment:
            logger.verbose("Config: Adding comment to container info")
            self.setComment(comment)

    # ===== Functional / technical methods section =====

    async def __prepareOpenVpnVolumes(self, vpn_path: Path) -> Optional[str]:
        """Volumes must be prepared to share OpenVPN configuration files with the container.
        Depending on the user's settings, different configurations can be applied.
        With or without username / password authentication via auth-user-pass.
        OVPN config file directly supplied or a config directory,
        the directory feature is useful when the configuration depends on multiple files like certificate, keys etc."""
        ovpn_parameters = []

        logger.debug(f"Configuring OpenVPN")
        self.__vpn_path = vpn_path
        if vpn_path.is_file():
            await self.__checkVPNConfigDNS(vpn_path)
            # Configure VPN with single file
            self.addVolume(vpn_path, "/.exegol/vpn/config/client.ovpn", read_only=True)
            ovpn_parameters.append("--config /.exegol/vpn/config/client.ovpn")
        else:
            # Configure VPN with directory
            logger.verbose("Folder detected for VPN configuration. "
                           "Only the first *.ovpn file will be automatically launched when the container starts.")
            self.addVolume(vpn_path, "/.exegol/vpn/config", read_only=True)
            vpn_filename = None
            # Try to find the config file in order to configure the autostart command of the container
            for file in vpn_path.glob('*.ovpn'):
                logger.info(f"Using VPN config: {file}")
                await self.__checkVPNConfigDNS(file)
                # Get filename only to match the future container path
                vpn_filename = file.name
                ovpn_parameters.append(f"--config /.exegol/vpn/config/{vpn_filename}")
                # If there is multiple match, only the first one is selected
                break
            if vpn_filename is None:
                logger.error("No *.ovpn files were detected. The VPN autostart will not work.")
                return None

        # VPN Auth creds file
        input_vpn_auth = ParametersManager().vpn_auth
        vpn_auth = None
        if input_vpn_auth is not None:
            vpn_auth = Path(input_vpn_auth).expanduser()

        if vpn_auth is not None:
            if vpn_auth.is_file():
                logger.info(f"Adding VPN credentials from: {str(vpn_auth.absolute())}")
                self.addVolume(vpn_auth, "/.exegol/vpn/auth/creds.txt", read_only=True)
                ovpn_parameters.append("--auth-user-pass /.exegol/vpn/auth/creds.txt")
            else:
                # Supply a directory instead of a file for VPN authentication is not supported.
                logger.critical(
                    f"The path provided to the VPN connection credentials ({str(vpn_auth)}) does not lead to a file. Aborting operation.")

        return ' '.join(ovpn_parameters)

    def __prepareWireguardVolumes(self, wireguard_path: Path) -> Optional[str]:
        """Volumes must be prepared to share WireGuard configuration files with the container.
        WireGuard config fil is .conf and include evry needed configuration like private key, public key, etc."""
        wg_parameters = []
        logger.debug(f"Configuring WireGuard")
        self.__vpn_path = wireguard_path
        if ParametersManager().vpn_auth is not None:
            logger.warning("WireGuard setup doesn't support --vpn-auth parameter. It will be ignored.")

        self.addVolume(wireguard_path, "/etc/wireguard/wg0.conf", read_only=True)
        wg_parameters.append("wg0")

        return ' '.join(wg_parameters)

    @staticmethod
    async def __checkVPNConfigDNS(vpn_path: Union[str, Path]) -> None:
        logger.verbose("Checking OpenVPN config file")
        configs = ["script-security 2", "up /etc/openvpn/update-resolv-conf", "down /etc/openvpn/update-resolv-conf"]
        with open(vpn_path, 'r') as vpn_file:
            for line in vpn_file:
                line = line.strip()
                if line in configs:
                    configs.remove(line)
        if len(configs) > 0:
            logger.warning("Some OpenVPN config are [red]missing[/red] to support VPN [orange3]dynamic DNS servers[/orange3]! "
                           "Please add the following line to your configuration file:")
            logger.empty_line()
            logger.raw(os.linesep.join(configs), level=logging.WARNING)
            logger.empty_line()
            logger.empty_line()
            await ExegolRich.Acknowledge("Your VPN configuration won't support dynamic DNS servers.")

    def prepareShare(self, share_name: str) -> None:
        """Add workspace share before container creation"""
        for mount in self.__mounts:
            if mount.get('Target') == '/workspace':
                # Volume is already prepared
                return
        if self.__workspace_custom_path is not None:
            self.addVolume(self.__workspace_custom_path, '/workspace', enable_sticky_group=True)
        elif self.__disable_workspace:
            # Skip default volume workspace if disabled
            return
        else:
            # Add dedicated private workspace bind volume
            volume_path = str(UserConfig().private_volume_path.joinpath(share_name))
            self.addVolume(volume_path, '/workspace', enable_sticky_group=True)

    def rollback_preparation(self, share_name: str) -> None:
        """Undo preparation in case of container creation failure"""
        if self.__workspace_custom_path is None and not self.__disable_workspace:
            # Remove dedicated workspace volume
            directory_path = UserConfig().private_volume_path.joinpath(share_name)
            if directory_path.is_dir() and len(list(directory_path.iterdir())) == 0:
                logger.info("Rollback: removing dedicated workspace directory")
                directory_path.rmdir()
            else:
                logger.warning("Rollback: the workspace directory isn't empty, it will NOT be removed automatically")

    def entrypointRunCmd(self, endless_mode: bool = False) -> None:
        """Enable the run_cmd feature of the entrypoint. This feature execute the command stored in the $CMD container environment variables.
        The endless_mode parameter can specify if the container must stay alive after command execution or not"""
        self.__run_cmd = True
        self.__endless_container = endless_mode

    def getEntrypointCommand(self) -> Tuple[Optional[List[str]], Union[List[str], str]]:
        """Get container entrypoint/command arguments.
        The default container_entrypoint is '/bin/bash /.exegol/entrypoint.sh' and the default container_command is ['load_setups', 'endless']."""
        entrypoint_actions = []
        if self.__my_resources:
            entrypoint_actions.append("load_setups")
        if self.isDesktopEnabled():
            entrypoint_actions.append("desktop")
        if self.__vpn_path is not None:
            entrypoint_actions.append(f"{self.__vpn_mode} {self.__vpn_parameters}")
        if self.__run_cmd:
            entrypoint_actions.append("run_cmd")
        if self.__endless_container:
            entrypoint_actions.append("endless")
        else:
            entrypoint_actions.append("finish")
        return self.__container_entrypoint, entrypoint_actions

    @staticmethod
    def getShellCommand() -> str:
        """Get container command for opening a new shell"""
        # Use a spawn.sh script to handle features with the wrapper
        return "/.exegol/spawn.sh"

    @staticmethod
    def generateRandomPassword(length: int = 30) -> str:
        """
        Generate a new random password.
        """
        charset = string.ascii_letters + string.digits
        return ''.join(random.choice(charset) for _ in range(length))

    @staticmethod
    def __findAvailableRandomPort(interface: str = 'localhost') -> int:
        """Find an available random port. Using the socket system to """
        logger.debug(f"Attempting to bind to interface {interface}")
        with socket.socket() as sock:
            try:
                sock.bind((interface, 0))  # Using port 0 let the system decide for a random port
            except OSError as e:
                logger.critical(f"Unable to bind a port to the interface {interface} ({e})")
            random_port = sock.getsockname()[1]
        logger.debug(f"Found available port {random_port}")
        return random_port

    # ===== Apply config section =====

    def setWorkspaceShare(self, host_directory: str) -> None:
        """Procedure to share a specific directory with the /workspace of the container"""
        path = Path(host_directory).expanduser().absolute()
        try:
            if not path.is_dir() and path.exists():
                logger.critical("The specified workspace is not a directory!")
        except PermissionError as e:
            logger.critical(f"Unable to use the supplied workspace directory: {e}")
        logger.verbose(f"Config: Sharing workspace directory {path}")
        self.__workspace_custom_path = str(path)

    def __setNetwork(self, network: Union[ExegolNetworkMode, str]) -> None:
        """Procedure to set the network mode of the container"""

        if type(network) is ExegolNetworkMode and network == ExegolNetworkMode.nat:
            if not SessionHandler().pro_feature_access():
                logger.critical(f"Isolated network mode [green]NAT[/green] is not available in the Community version of Exegol. You can use the [green]Docker[/green] mode instead.")
                raise CancelOperation
            elif EnvInfo.isOrbstack():
                logger.warning("Orbstack doesn’t isolate networks. If you need improved security with [green]NAT[/green], use Docker Desktop. See https://github.com/orbstack/orbstack/issues/1944")

        self.__networks.clear()
        if type(network) is str or network != ExegolNetworkMode.disabled:
            self.__networks.append(ExegolNetwork.instance_network(network, self.container_name))

    def setNetworkMode(self, network: Optional[Union[ExegolNetworkMode, str]] = ExegolNetworkMode.host) -> None:
        """Set container's network mode, true for host, false for bridge"""
        if network is None:
            # When --network is not set by the user, use default network
            network = UserConfig().network_default_mode
        try:
            if type(network) is str:
                net_mode: Union[ExegolNetworkMode, str] = ExegolNetworkMode[network.lower()]
            else:
                net_mode = network
        except KeyError:
            net_mode = network

        # Check for host mode incompatibility
        if type(net_mode) is ExegolNetworkMode and net_mode == ExegolNetworkMode.host:
            if len(self.__ports) > 0:
                logger.warning("Host mode cannot be set with NAT ports configured. Disabling the host network mode.")
                net_mode = self.__fallback_network_mode
            if EnvInfo.isDockerDesktop():
                if not EnvInfo.isHostNetworkAvailable():
                    net_mode = self.__fallback_network_mode
                else:
                    logger.warning("The network mode of the Docker desktop host has its limitations. It may not work as expected.")
                    logger.verbose("More information from the official documentation of Docker Desktop: https://docs.docker.com/network/drivers/host/#docker-desktop")

        self.__setNetwork(net_mode)

    def setPrivileged(self, status: bool = True) -> None:
        """Set container as privileged"""
        logger.verbose(f"Config: Setting container privileged as {status}")
        if status:
            logger.warning("Setting container as privileged (this exposes the host to security risks)")
        self.__privileged = status

    def addCapability(self, cap_string: str) -> None:
        """Add a linux capability to the container"""
        if cap_string in self.__capabilities:
            logger.warning("Capability already setup. Skipping.")
            return
        self.__capabilities.append(cap_string)

    def __removeCapability(self, cap_string: str) -> bool:
        """Remove a linux capability from the container's config"""
        try:
            self.__capabilities.remove(cap_string)
            return True
        except ValueError:
            # When the capability is not present
            return False

    def __addSysctl(self, sysctl_key: str, config: Union[str, int]) -> None:
        """Add a linux sysctl to the container"""
        if sysctl_key in self.__sysctls.keys():
            logger.warning(f"Sysctl {sysctl_key} already setup to '{self.__sysctls[sysctl_key]}'. Skipping.")
            return
        # Docs of supported sysctl by linux / docker: https://docs.docker.com/reference/cli/docker/container/run/#currently-supported-sysctls
        if self.isNetworkHost() and sysctl_key.startswith('net.'):
            logger.warning(f"The sysctl container configuration is [red]not[/red] supported by docker in [blue]host[/blue] network mode.")
            logger.warning(f"Skipping the sysctl config: [magenta]{sysctl_key}[/magenta] = [orange3]{config}[/orange3].")
            logger.warning(f"If this configuration is mandatory in your situation, try to change it in sudo mode on your host.")
            return
        self.__sysctls[sysctl_key] = str(config)

    def __removeSysctl(self, sysctl_key: str) -> bool:
        """Remove a linux capability from the container's config"""
        try:
            self.__sysctls.pop(sysctl_key)
            return True
        except KeyError:
            # When the sysctl is not present
            return False

    def getNetwork(self) -> Tuple[Optional[str], Optional[str]]:
        """First Network getter for docker API on container creation"""
        if len(self.__networks) > 0:
            return self.__networks[0].getNetworkConfig()
        return None, None

    def getNetworks(self) -> List[ExegolNetwork]:
        """Networks getter"""
        return self.__networks

    def setExtraHost(self, host: str, ip: str) -> None:
        """Add or update an extra host to resolv inside the container."""
        self.__extra_host[host] = ip

    def removeExtraHost(self, host: str) -> bool:
        """Remove an extra host to resolv inside the container.
        Return true if the host was register in the extra_host configuration."""
        return self.__extra_host.pop(host, None) is not None

    def getExtraHost(self) -> Dict[str, str]:
        """Return the extra_host configuration for the container.
        Ensure in shared host environment that the container hostname will be correctly resolved to localhost.
        Return a dictionary of host and matching IP"""
        # When using host network mode, you need to add an extra_host to resolve $HOSTNAME
        if self.isNetworkHost() and self.hostname not in self.__extra_host.keys():
            self.setExtraHost(self.hostname, '127.0.0.1')
        return self.__extra_host

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

    def getHostWorkspacePath(self) -> str:
        """Get private volume path (None if not set)"""
        if self.__workspace_custom_path:
            return FsUtils.resolvStrPath(self.__workspace_custom_path)
        elif self.__workspace_dedicated_path:
            return self.getPrivateVolumePath()
        return "not found :("

    def getPrivateVolumePath(self) -> str:
        """Get private volume path (None if not set)"""
        return FsUtils.resolvStrPath(self.__workspace_dedicated_path)

    def isMyResourcesEnable(self) -> bool:
        """Return if the feature 'my-resources' is enabled in this container config"""
        return self.__my_resources

    def getMyResourcesPath(self) -> str:
        """Return if the feature 'exegol resources' is enabled in this container config"""
        return self.__my_resources_path

    def isExegolResourcesEnable(self) -> bool:
        """Return if the feature 'exegol resources' is enabled in this container config"""
        return self.__exegol_resources

    def isShellLoggingEnable(self) -> bool:
        """Return if the feature 'shell logging' is enabled in this container config"""
        return self.__shell_logging

    def isGUIEnable(self) -> bool:
        """Return if the feature 'GUI' is enabled in this container config"""
        return self.__enable_gui

    def isTimezoneShared(self) -> bool:
        """Return if the feature 'timezone' is enabled in this container config"""
        return self.__share_timezone

    def isWorkspaceCustom(self) -> bool:
        """Return if the workspace have a custom host volume"""
        return bool(self.__workspace_custom_path)

    def isNetworkHost(self) -> bool:
        """Return True if the container is attached to the host network"""
        for net in self.__networks:
            if net.getNetworkMode() == ExegolNetworkMode.host:
                return True
        return False

    def isNetworkBridge(self) -> bool:
        """Return True if the container is attached to the host network"""
        for net in self.__networks:
            if net.getNetworkDriver() == DockerDrivers.Bridge:
                return True
        return False

    def isNetworkDisabled(self) -> bool:
        """Return True if the container is not connected to any network"""
        return len(self.__networks) == 0

    def addVolume(self,
                  host_path: Union[str, Path],
                  container_path: str,
                  must_exist: bool = False,
                  read_only: bool = False,
                  enable_sticky_group: bool = False,
                  force_sticky_group: bool = False,
                  volume_type: str = 'bind') -> None:
        """Add a volume to the container configuration.
        When the host path does not exist (neither file nor folder):
        if must_exist is set, an CancelOperation exception will be thrown.
        Otherwise, a folder will attempt to be created at the specified path.
        if set_sticky_group is set (on a Linux host), the permission setgid will be added to every folder on the volume."""
        # The creation of the directory is ignored when it is a path to the remote drive
        if volume_type == 'bind' and not (type(host_path) is str and host_path.startswith("\\\\")):
            path: Path = host_path.absolute() if type(host_path) is Path else Path(host_path).absolute()
            host_path = path.as_posix()
            # Docker Desktop for Windows based on WSL2 don't have filesystem limitation
            if EnvInfo.isMacHost():
                # Add support for /etc
                if host_path.startswith("/opt/") and EnvInfo.isOrbstack():
                    msg = f"{EnvInfo.getDockerEngine().value} cannot mount directory from /opt/ host path."
                    if host_path.endswith("entrypoint.sh") or host_path.endswith("spawn.sh"):
                        msg += " Your exegol installation cannot be stored under this directory."
                        logger.critical(msg)
                    else:
                        msg += f" The volume {host_path} cannot be mounted to the container, please move it outside of this directory."
                    raise CancelOperation(msg)
                if EnvInfo.isDockerDesktop():
                    match = False
                    # Find a match
                    for resource in EnvInfo.getDockerDesktopResources():
                        if host_path.startswith(resource):
                            match = True
                            break
                    if not match:
                        logger.error(f"Bind volume from {host_path} is not possible, Docker Desktop configuration is [red]incorrect[/red].")
                        logger.critical(f"You need to modify the [green]Docker Desktop[/green] config and [green]add[/green] this path (or the root directory) in "
                                        f"[magenta]Docker Desktop > Preferences > Resources > File Sharing[/magenta] configuration.")
            # Choose to update fs directory perms if available and depending on user choice
            # if force_sticky_group is set, user choice is bypassed, fs will be updated.
            execute_update_fs = force_sticky_group or (enable_sticky_group and (UserConfig().auto_update_workspace_fs ^ ParametersManager().update_fs_perms))
            try:
                if not path.exists():
                    if must_exist:
                        raise CancelOperation(f"{host_path} does not exist on your host.")
                    else:
                        # If the directory is created by exegol, bypass user preference and enable shared perms (if available)
                        execute_update_fs = force_sticky_group or enable_sticky_group
                        mkdir(path)
            except PermissionError:
                logger.error("Unable to create the volume folder on the filesystem locally.")
                logger.critical(f"Insufficient permissions to create the folder: {host_path}")
            except FileExistsError:
                # The volume targets a file that already exists on the file system
                pass
            # Update FS don't work on Windows and only for directory
            if not EnvInfo.is_windows_shell and path.is_dir():
                if execute_update_fs:
                    # Apply perms update
                    FsUtils.setGidPermission(path)
                elif enable_sticky_group:
                    # If user choose not to update, print tips
                    logger.warning(f"The file sharing permissions between the container and the host will not be applied automatically by Exegol. ("
                                   f"{'Currently enabled by default according to the user config' if UserConfig().auto_update_workspace_fs else 'Use the --update-fs option to enable the feature'})")
        mount = Mount(container_path, str(host_path), read_only=read_only, type=volume_type)
        self.__mounts.append(mount)

    def removeVolume(self, host_path: Optional[str] = None, container_path: Optional[str] = None) -> bool:
        """Remove a volume from the container configuration (Only before container creation)"""
        if host_path is None and container_path is None:
            # This is a dev problem
            raise ValueError('At least one parameter must be set')
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

    def __addDevice(self,
                    device_source: str,
                    device_dest: Optional[str] = None,
                    readonly: bool = False,
                    mknod: bool = False) -> None:
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

    def addEnv(self, key: str, value: str) -> None:
        """Add or update an environment variable to the container configuration"""
        self.__envs[key] = value

    def removeEnv(self, key: str) -> bool:
        """Remove an environment variable to the container configuration (Only before container creation)"""
        try:
            self.__envs.pop(key)
            return True
        except KeyError:
            # When the Key is not present in the dictionary
            return False

    def getEnvs(self) -> Dict[str, str]:
        """Envs config getter"""
        # When using host network mode, service port must be randomized to avoid conflict between services and container
        if self.isNetworkHost():
            self.addEnv(self.ExegolEnv.randomize_service_port.value, "true")
        return self.__envs

    def getShellEnvs(self) -> List[str]:
        """Overriding envs when opening a shell"""
        result = [f"{self.ExegolEnv.user_shell.value}={ParametersManager().shell}"]
        # Select default shell to use
        if ParametersManager().shell in ["zsh", "bash", "sh"]:
            # tmux dynamically set SHELL variable and should be excluded here
            result.append(f"SHELL=/bin/{ParametersManager().shell}")
        # Update X11 DISPLAY socket if needed
        if self.__enable_gui:
            current_display = GuiUtils.getDisplayEnv()

            # If the default DISPLAY environment in the container is not the same as the DISPLAY of the user's session,
            # the environment variable will be updated in the exegol shell.
            if current_display and self.__envs.get('DISPLAY', '') != current_display:
                # This case can happen when the container is created from a local desktop
                # but exegol can be launched from remote access via ssh with X11 forwarding
                # (Be careful, an .Xauthority file may be needed).
                result.append(f"DISPLAY={current_display}")
        # Handle shell logging
        # If shell logging was enabled at container creation, it'll always be enabled for every shell.
        # If not, it can be activated per shell basic
        if self.__shell_logging or ParametersManager().log or UserConfig().always_enable_shell_logging:
            result.append(f"{self.ExegolEnv.shell_logging_method.value}={ParametersManager().log_method}")
            result.append(f"{self.ExegolEnv.shell_logging_compress.value}={UserConfig().shell_logging_compress ^ ParametersManager().log_compress}")
        # Overwrite env from user parameters
        user_envs = ParametersManager().envs
        if user_envs is not None:
            for env in user_envs:
                key, value = self.__parseUserEnv(env)
                logger.debug(f"Add env to current shell: {env}")
                result.append(f"{key}={value}")
        return result

    def addPort(self,
                port_host: int,
                port_container: Union[int, str],
                protocol: str = 'tcp',
                host_ip: str = '0.0.0.0') -> None:
        """Add port NAT config, only applicable on bridge network mode."""
        if self.isNetworkHost():
            logger.warning("Port sharing is configured, disabling the host network mode.")
            self.setNetworkMode(self.__fallback_network_mode)
        if protocol.lower() not in ['tcp', 'udp', 'sctp']:
            raise ProtocolNotSupported(f"Unknown protocol '{protocol}'")
        logger.debug(f"Adding port {host_ip}:{port_host} -> {port_container}/{protocol}")
        # Casting type because at this stage, the data is only controlled by the wrapper itself.
        existing_config = self.__ports.get(f"{port_container}/{protocol}", [])
        assert type(existing_config) is list
        existing_config.append((host_ip, port_host))
        self.__ports[f"{port_container}/{protocol}"] = existing_config

    def getPorts(self) -> Dict[str, Optional[Union[int, Tuple[str, int], List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]]]]]:
        """Ports config getter"""
        return self.__ports

    def __removePort(self, container_port: Union[int, str], protocol: str = 'tcp') -> None:
        self.__ports.pop(f"{container_port}/{protocol}", None)

    def addLabel(self, key: str, value: str) -> None:
        """Add a custom label to the container configuration"""
        self.__labels[key] = value

    def removeLabel(self, key: str) -> bool:
        """Remove a custom label from the container configuration (Only before container creation)"""
        try:
            self.__labels.pop(key)
            return True
        except KeyError:
            # When the Key is not present in the dictionary
            return False

    def getLabels(self) -> Dict[str, str]:
        """Labels config getter"""
        # Update metadata (from getter method) to the labels (on container creation)
        for label_name, refs in self.__label_metadata.items():  # Getter
            data = getattr(self, refs[1])()
            if data is not None:
                self.addLabel(label_name, data)
        return self.__labels

    def isWrapperStartShared(self) -> bool:
        """Return True if the /.exegol/spawn.sh is a volume from the up-to-date wrapper script."""
        return self.__wrapper_start_enabled

    # ===== Metadata labels getter / setter section =====

    def setCreationDate(self, creation_date: str) -> None:
        """Set the container creation date parsed from the labels of an existing container."""
        self.__creation_date = creation_date

    def getCreationDate(self) -> str:
        """Get container creation date.
        If the creation has not been set before, init as right now."""
        if self.__creation_date is None:
            self.__creation_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        return self.__creation_date

    def setBackupHistory(self, backup_history: Optional[str]) -> None:
        """Set the container backup history parsed from the labels of an existing container."""
        self.__backup_history = backup_history

    def getBackupHistory(self) -> Optional[str]:
        """Get container backup history.
        If no backup history has been supplied, returns None."""
        return self.__backup_history

    def setComment(self, comment: str) -> None:
        """Set the container comment parsed from the labels of an existing container."""
        self.__comment = comment

    def getComment(self) -> Optional[str]:
        """Get the container comment.
        If no comment has been supplied, returns None."""
        return self.__comment

    def setPasswd(self, passwd: str) -> None:
        """
        Set the container root password parsed from the labels of an existing container.
        This secret data can be stored inside labels because it is accessible only from the docker socket
        which give direct access to the container anyway without password.
        """
        self.__passwd = passwd

    def getPasswd(self) -> Optional[str]:
        """
        Get the container password.
        """
        return self.__passwd

    def getUsername(self) -> str:
        """
        Get the container username.
        """
        return self.__username

    # ===== User parameter parsing section =====

    async def addRawVolume(self, volume_string: str) -> None:
        """Add a volume to the container configuration from raw text input.
        Expected format is one of:
        /source/path:/target/mount:rw
        C:\\source\\path:/target/mount:ro
        ./relative/path:target/mount"""
        logger.debug(f"Parsing raw volume config: {volume_string}")
        parsing = re.match(r'^((\w:|\.|~)?([\\/][\w .,:\-|()&;]*)+):(([\\/][\w .,\-|()&;]*)+)(:(ro|rw))?$', volume_string)
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
            full_host_path = Path(host_path).expanduser()
            logger.debug(
                f"Adding a volume from '{full_host_path.as_posix()}' to '{container_path}' as {'readonly' if readonly else 'read/write'}")
            try:
                self.addVolume(full_host_path, container_path, read_only=readonly)
            except CancelOperation as e:
                logger.error(f"The following volume couldn't be created [magenta]{volume_string}[/magenta]. {e}")
                if not await ExegolRich.Confirm("Do you want to continue without this volume ?", False):
                    exit(0)
        else:
            logger.critical(f"Volume '{volume_string}' cannot be parsed. Exiting.")

    def addUserDevice(self, user_device_config: str) -> None:
        """Add a device from a user parameters"""
        if (EnvInfo.isDockerDesktop() or EnvInfo.isOrbstack()) and user_device_config not in self.__whitelist_dd_devices:
            if not user_device_config.startswith("/dev/loop"):
                if EnvInfo.isDockerDesktop():
                    logger.warning("Docker desktop (Windows & macOS) does not support USB device passthrough.")
                    logger.verbose("Official doc: https://docs.docker.com/desktop/faqs/#can-i-pass-through-a-usb-device-to-a-container")
                elif EnvInfo.isOrbstack():
                    logger.warning("Orbstack does not support (yet) USB device passthrough.")
                    logger.verbose("Official doc: https://docs.orbstack.dev/machines/#usb-devices")
                logger.critical("Device configuration cannot be applied, aborting operation.")
        self.__addDevice(user_device_config)

    def addRawPort(self, user_test_port: str) -> None:
        """Add port config or range of ports from user input.
        Format must be [<host_ipv4>:]<host_port>[-<end_host_port>][:<container_port>[-<end_container_port>]][:<protocol>]
        If host_ipv4 is not set, default to 0.0.0.0
        If container_port is not set, the same port(s) as host port(s) will be used
        If protocol is not set, default is 'tcp'"""
        # Regex to capture port ranges and protocols correctly
        match = re.search(r"^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):)?(\d+)(-(\d+))?:?(\d+)?(-(\d+))?:?(udp|tcp|sctp)?$", user_test_port)
        if match is None:
            logger.critical(f"Incorrect port syntax ({user_test_port}). Please use this format: '{SyntaxFormat.port_sharing}'")
            return
        host_ip = "0.0.0.0" if match.group(2) is None else match.group(2)
        protocol = match.group(9) if match.group(9) else 'tcp'
        try:
            start_host_port = int(match.group(3))
            end_host_port = int(match.group(5)) if match.group(5) else start_host_port
            start_container_port_defined = match.group(6) is not None
            end_container_port_defined = match.group(8) is not None
            start_container_port = int(match.group(6)) if start_container_port_defined else start_host_port
            # If start_container_port is not defined, use end_host_port, otherwise use start_container_port or end_container_port if defined
            if not start_container_port_defined:
                end_container_port = end_host_port
            else:
                end_container_port = int(match.group(8)) if match.group(8) else start_container_port
            # check port consistency
            if (len(range(start_host_port, end_host_port)) != len(range(start_container_port, end_container_port))) or (
                    start_host_port != end_host_port and (not start_container_port_defined and end_container_port_defined)) or (
                    start_host_port != end_host_port and (start_container_port_defined and not end_container_port_defined)):
                logger.info(
                    f"Port sharing configuration does not respect standard usage ({user_test_port}). The configuration in the 'Container sumamry' below will be applied. Please consult the help section for more information on using the -p/--port option.")
            # Check if start port is lower than end port
            if end_host_port < start_host_port or end_container_port < start_container_port:
                raise ValueError("End port cannot be less than start port.")
            # Check if any port in the range exceeds the valid range
            if end_host_port > 65535 or end_container_port > 65535:
                raise ValueError(f"The syntax for opening port in NAT is incorrect. The ports must be numbers between 0 and 65535. ({end_host_port}:{end_container_port})")
        except ValueError as e:
            logger.critical(e)
            return
        for host_port, container_port in zip(range(start_host_port, end_host_port + 1), range(start_container_port, end_container_port + 1)):
            self.addPort(host_port, container_port, protocol=protocol, host_ip=host_ip)

    def addRawEnv(self, env: str) -> None:
        """Parse and add an environment variable from raw user input"""
        key, value = self.__parseUserEnv(env)
        self.addEnv(key, value)

    @classmethod
    def __parseUserEnv(cls, env: str) -> Tuple[str, str]:
        env_args = env.split('=')
        key = env_args[0]
        if len(env_args) < 2:
            value = os.getenv(env, '')
            if not value:
                logger.critical(f"Incorrect env syntax ({env}). Please use this format: KEY=value")
            else:
                logger.success(f"Using system value for env {env}.")
        else:
            value = '='.join(env_args[1:])
        return key, value

    # ===== Display / text formatting section =====

    def getTextFeatures(self, verbose: bool = False) -> str:
        """Text formatter for features configurations (Privileged, X11, Network, Timezone, Shares)
        Print config only if they are different from their default config (or print everything in verbose mode)"""
        result = ""
        if verbose or self.__privileged:
            result += f"{getColor(not self.__privileged)[0]}Privileged: {'On :fire:' if self.__privileged else '[green]Off :heavy_check_mark:[/green]'}{getColor(not self.__privileged)[1]}{os.linesep}"
        if verbose or self.isDesktopEnabled():
            result += f"{getColor(self.isDesktopEnabled())[0]}Remote Desktop: {self.getDesktopConfig()}{getColor(self.isDesktopEnabled())[1]}{os.linesep}"
        if verbose or not self.__enable_gui:
            result += f"{getColor(self.__enable_gui)[0]}Console GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}"
        if verbose or not self.isNetworkHost():
            result += f"[green]Network mode: [/green]{self.getTextNetworkMode()}{os.linesep}"
        if self.__vpn_path is not None:
            result += f"[green]VPN: [/green]{self.getVpnName()}{os.linesep}"
        if verbose or not self.__share_timezone:
            result += f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}"
        if verbose or not self.__exegol_resources:
            result += f"{getColor(self.__exegol_resources)[0]}Exegol resources: {boolFormatter(self.__exegol_resources)}{getColor(self.__exegol_resources)[1]}{os.linesep}"
        if verbose or not self.__my_resources:
            result += f"{getColor(self.__my_resources)[0]}My resources: {boolFormatter(self.__my_resources)}{getColor(self.__my_resources)[1]}{os.linesep}"
        if verbose or self.__shell_logging:
            result += f"{getColor(self.__shell_logging)[0]}Shell logging: {boolFormatter(self.__shell_logging)}{getColor(self.__shell_logging)[1]}{os.linesep}"
        result = result.strip()
        if not result:
            return "[i][bright_black]Default configuration[/bright_black][/i]"
        return result

    def getVpnName(self) -> str:
        """Get VPN Config name"""
        if self.__vpn_path is None:
            return "[bright_black]N/A[/bright_black]   "
        return f"[deep_sky_blue3]{self.__vpn_path.name}[/deep_sky_blue3]"

    def getDesktopConfig(self) -> str:
        """Get Desktop feature status / config"""
        if not self.isDesktopEnabled():
            return boolFormatter(False)
        config = (f"{self.__desktop_proto}://"
                  f"{'localhost' if self.__desktop_host == '127.0.0.1' else self.__desktop_host}:{self.__desktop_port}")
        return f"[link={config}][deep_sky_blue3]{config}[/deep_sky_blue3][/link]"

    def getTextGuiSockets(self) -> str:
        if self.__enable_gui:
            return f"[bright_black]({' + '.join(self.__gui_engine)})[/bright_black]"
        else:
            return ""

    def getTextNetworkMode(self) -> str:
        """Network mode, text getter"""
        network_mode = ', '.join([n.getTextNetworkMode() for n in self.__networks]) if len(self.__networks) > 0 else f"[bright_black]{ExegolNetworkMode.disabled.value}[/bright_black]"
        if self.__vpn_path:
            network_mode += " (with VPN)"
        return network_mode

    def getTextCreationDate(self) -> str:
        """Get the container creation date.
        If the creation date has not been supplied on the container, return empty string."""
        if self.__creation_date is None:
            return ""
        return datetime.strptime(self.__creation_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y %H:%M")

    def getTextMounts(self, verbose: bool = False) -> str:
        """Text formatter for Mounts configurations. The verbose mode does not exclude technical volumes."""
        result = ''
        for mount in self.__mounts:
            # Not showing technical mounts
            if not verbose and mount.get('Target') in self.__verbose_only_mounts:
                continue
            read_only_text = f"[bright_black](RO)[/bright_black] " if verbose else ''
            read_write_text = f"[orange3](RW)[/orange3] " if verbose else ''
            result += f"{read_only_text if mount.get('ReadOnly') else read_write_text}{mount.get('Source')} :right_arrow: {mount.get('Target')}{os.linesep}"
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
            if not verbose and k in list(self.__static_gui_envs.keys()) + [v.value for v in self.ExegolEnv] + self.__verbose_only_envs:
                continue
            result += f"{k}={v}{os.linesep}"
        return result

    def getTextPorts(self, is_running: bool = True) -> str:
        """Text formatter for Ports configuration.
        Dict Port key = container port/protocol
        Dict Port Values:
          None = Random port
          int = open port on the host
          tuple = (host_ip, port)
          list of int = open multiple host port
          list of dict = open one or more ports on host, key ('HostIp' / 'HostPort') and value ip or port"""

        # Port configuration cannot be fetched from docker until container startup
        if self.isNetworkBridge() and len(self.__ports) == 0 and not is_running:
            return "[bright_black]Container must be started first[/bright_black]"

        result = ''

        start_host_ip: Optional[str] = None
        start_host_port: Optional[Union[int, str]] = None
        previous_host_port: Optional[Union[str, int]] = None

        start_container_protocol: Optional[str] = None
        start_container_port: Optional[int] = None
        previous_container_port: Optional[int] = None

        previous_entry = None

        for container_config, host_config in self.__ports.items():
            # Parse config
            current_container_port = int(container_config.split('/')[0])
            current_container_protocole = container_config.split('/')[-1]
            # We might have multiple host context config at the same time for the same container config
            current_host_contexts: List[Dict[str, Union[str, int]]] = []
            # Init range context, container side
            if start_container_port is None:
                start_container_port = current_container_port
                previous_container_port = current_container_port
                start_container_protocol = current_container_protocole

            # Parse host config multiple format
            if host_config is None:
                current_host_contexts.append({"ip": "0.0.0.0",
                                              "port": "<Random port>"})
            else:
                if type(host_config) is list:
                    host_configs: List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]] = host_config
                else:
                    host_configs = cast(List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]], [host_config])

                for current_host_config in host_configs:
                    if type(current_host_config) is int:
                        current_host_contexts.append({"ip": "0.0.0.0",
                                                      "port": current_host_config})
                    elif type(current_host_config) is tuple:
                        assert len(current_host_config) == 2
                        current_host_contexts.append({"ip": current_host_config[0],
                                                      "port": int(current_host_config[1])})
                    elif type(current_host_config) is dict:
                        sub_port = current_host_config.get('HostPort')
                        if sub_port is None:
                            sub_port = "<Random port>"
                        elif type(sub_port) is str:
                            sub_port = int(sub_port)
                        current_host_contexts.append({"ip": current_host_config.get('HostIp', '0.0.0.0'),
                                                      "port": sub_port})
                    else:
                        logger.debug(f"Unknown port config: {type(host_config)}={host_config} :right_arrow: {container_config}")
                        continue

            for current_context in current_host_contexts:
                current_host_port = current_context.get("port")
                current_host_ip: Optional[str] = cast(Optional[str], current_context.get('ip'))
                if current_host_port is None or current_host_ip is None:
                    continue

                # Init range context
                if start_host_port is None:
                    start_host_port = current_host_port
                    previous_host_port = current_host_port
                    start_host_ip = current_host_ip
                # Check if range continue
                elif (previous_host_port is not None and
                      previous_container_port is not None and
                      start_host_ip == current_host_ip and
                      current_container_protocole == start_container_protocol and
                      (current_host_port == previous_host_port or
                       (type(previous_host_port) is int and current_host_port == previous_host_port + 1)) and
                      (current_container_port == previous_container_port or
                       (type(previous_container_port) is int and current_container_port == previous_container_port + 1))):
                    previous_host_port = current_host_port
                    previous_container_port = current_container_port
                # If range exit, submit previous entry + reset new range context
                else:
                    # Register previous range
                    if previous_entry:
                        result += previous_entry
                    # reset context host and container side
                    start_host_port = current_host_port
                    previous_host_port = current_host_port
                    start_host_ip = current_host_ip
                    start_container_port = current_container_port
                    previous_container_port = current_container_port
                    start_container_protocol = current_container_protocole

                # Register last range
                range_host_port = ""
                if type(start_host_port) is int:
                    assert type(previous_host_port) is int
                    range_host_port = "" if previous_host_port - start_host_port <= 0 else f"-{previous_host_port}"
                if previous_container_port is not None and start_container_port is not None:
                    range_container_port = "" if previous_container_port - start_container_port <= 0 else f"-{previous_container_port}"
                    previous_entry = (f"{start_host_ip}:{start_host_port}{range_host_port} :right_arrow: "
                                      f"{start_container_port}{range_container_port}/{start_container_protocol}{os.linesep}")

        # Submit last entry is any
        if previous_entry:
            result += previous_entry

        return result

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"Privileged: {self.__privileged}{os.linesep}" \
               f"Capabilities: {self.__capabilities}{os.linesep}" \
               f"Sysctls: {self.__sysctls}{os.linesep}" \
               f"X: {self.__enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {self.getTextNetworkMode()}{os.linesep}" \
               f"Ports: {self.__ports}{os.linesep}" \
               f"Share timezone: {self.__share_timezone}{os.linesep}" \
               f"Common resources: {self.__my_resources}{os.linesep}" \
               f"Envs ({len(self.__envs)}): {os.linesep.join(self.__envs)}{os.linesep}" \
               f"Labels ({len(self.__labels)}): {os.linesep.join(self.__labels)}{os.linesep}" \
               f"Shares ({len(self.__mounts)}): {os.linesep.join([str(x) for x in self.__mounts])}{os.linesep}" \
               f"Devices ({len(self.__devices)}): {os.linesep.join(self.__devices)}{os.linesep}" \
               f"VPN: {self.getVpnName()}"

    def printConfig(self) -> None:
        """Log current object state, debug only"""
        logger.info(f"Current container config :{os.linesep}{self}")
