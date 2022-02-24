import os
import re
from pathlib import Path, PurePath
from typing import Optional, List, Dict, Union, Tuple, cast

from docker.models.containers import Container
from docker.types import Mount
from rich.prompt import Prompt

from wrapper.console.ConsoleFormat import boolFormatter, getColor
from wrapper.console.ExegolPrompt import Confirm
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.exceptions.ExegolExceptions import ProtocolNotSupported
from wrapper.utils import FsUtils
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.EnvInfo import EnvInfo
from wrapper.utils.ExeLog import logger, ExeLog
from wrapper.utils.GuiUtils import GuiUtils


# Configuration class of an exegol container
class ContainerConfig:

    def __init__(self, container: Optional[Container] = None):
        """Container config default value"""
        self.__enable_gui: bool = False
        self.__share_timezone: bool = False
        self.__common_resources: bool = False
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
        self.shm_size: str = '64M'
        self.__workspace_custom_path: Optional[str] = None
        self.__workspace_dedicated_path: Optional[str] = None
        self.__disable_workspace: bool = False
        self.__container_command: str = "bash"
        self.__vpn_name: Optional[str] = None
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
        devices = host_config.get("Devices", [])
        if devices is not None:
            for device in devices:
                self.__devices.append(
                    f"{device.get('PathOnHost', '?')}:{device.get('PathInContainer', '?')}:{device.get('CgroupPermissions', '?')}")
        logger.debug(f"Load devices : {self.__devices}")

        # Volumes section
        self.__share_timezone = False
        self.__common_resources = False
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
                self.__common_resources = True
            elif "/workspace" in share.get('Destination', ''):
                # Workspace are always bind mount
                assert src_path is not None
                obj_path = cast(PurePath, src_path)
                logger.debug(f"Loading workspace volume source : {obj_path}")
                self.__disable_workspace = False
                if obj_path is not None and obj_path.name == name and obj_path.parent.name == "shared-data-volumes":
                    logger.debug("Private workspace detected")
                    self.__workspace_dedicated_path = str(obj_path)
                else:
                    logger.debug("Custom workspace detected")
                    self.__workspace_custom_path = str(obj_path)
            elif "/vpn" in share.get('Destination', ''):
                # VPN are always bind mount
                assert src_path is not None
                obj_path = cast(PurePath, src_path)
                self.__vpn_name = obj_path.name
                logger.debug(f"Loading VPN config: {self.__vpn_name}")

    def interactiveConfig(self):
        logger.info("Starting interactive configuration")

        # Workspace config
        if Confirm("Do you want to share your [green]current working directory[/green] in the new container?",
                   default=False):
            self.enableCwdShare()
        elif Confirm("Do you want to share a [green]workspace directory[/green] in the new container?", default=False):
            while True:
                workspace_path = Prompt.ask("Enter the path of your workspace")
                if os.path.isdir(workspace_path):
                    break
                else:
                    logger.error("The provided path is not a folder or does not exist.")
            self.setWorkspaceShare(workspace_path)

        # GUI Config
        if self.__enable_gui:
            # TODO add disable gui option
            pass
        elif Confirm("Do you want to [green]enable GUI[/green]?", False):
            self.enableGUI()

        # Timezone config
        if self.__share_timezone:
            # TODO add disable share timezone option
            pass
        elif Confirm("Do you want to share your [green]host's timezone[/green]?", False):
            self.enableSharedTimezone()

        # Common resources config
        if self.__common_resources:
            # TODO add disable common resources
            pass
        elif Confirm("Do you want to activate the [green]shared resources[/green]?", False):
            self.enableCommonVolume()

        # Network config
        if self.__network_host:
            if Confirm("Do you want to use a [green]dedicated private network[/green]?", False):
                self.setNetworkMode(False)
        elif Confirm("Do you want to share the [green]host's networks[/green]?", False):
            self.setNetworkMode(True)

        # VPN config
        if self.__vpn_name is None and Confirm("Do you want to [green]use a VPN[/green] in this container", False):
            while True:
                vpn_path = Prompt.ask('Enter the path to the OpenVPN config file')
                if os.path.isfile(vpn_path):
                    self.enableVPN(vpn_path)
                    break
                else:
                    logger.error("No config files were found.")

    def enableGUI(self):
        """Procedure to enable GUI feature"""
        if not GuiUtils.isGuiAvailable():
            logger.error("GUI feature is not available on your environment. Skipping.")
            return
        if not self.__enable_gui:
            self.__enable_gui = True
            logger.verbose("Config : Enabling display sharing")
            self.addVolume(GuiUtils.getX11SocketPath(), "/tmp/.X11-unix")
            self.addEnv("DISPLAY", GuiUtils.getDisplayEnv())
            self.addEnv("QT_X11_NO_MITSHM", "1")
            # TODO support pulseaudio

    def enableSharedTimezone(self):
        """Procedure to enable shared timezone feature"""
        if not EnvInfo.is_linux_shell:
            # TODO review timezone config
            logger.warning("Timezone sharing is inconsistent on Windows. May be inaccurate.")
        if not self.__share_timezone:
            self.__share_timezone = True
            logger.verbose("Config : Enabling host timezones")
            self.addVolume("/etc/timezone", "/etc/timezone", read_only=True)
            self.addVolume("/etc/localtime", "/etc/localtime", read_only=True)

    def enablePrivileged(self, status: bool = True):
        """Set container as privileged"""
        logger.verbose("Config : Setting container as privileged")
        logger.warning("Setting container as privileged (this exposes the host to security risks)")
        self.__privileged = status

    def enableCommonVolume(self):
        """Procedure to enable common volume feature"""
        if not self.__common_resources:
            logger.verbose("Config : Enabling common resources volume")
            self.__common_resources = True
            # Adding volume config
            self.addVolume(ConstantConfig.COMMON_SHARE_NAME, '/opt/resources', volume_type='volume')

    def enableCwdShare(self):
        """Procedure to share Current Working Directory with the /workspace of the container"""
        logger.verbose("Config : Sharing current working directory")
        self.__workspace_custom_path = os.getcwd()

    def setWorkspaceShare(self, host_directory):
        """Procedure to share a specific directory with the /workspace of the container"""
        path = Path(host_directory).absolute()
        if not path.is_dir():
            logger.critical("The specified workspace is not a directory")
        logger.verbose(f"Config : Sharing workspace directory {path}")
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
                f"bash -c 'cd /vpn/config; openvpn {ovpn_parameters} | tee /var/log/vpn.log; bash'")

    def __prepareVpnVolumes(self, config_path: Optional[str]) -> Optional[str]:
        """Volumes must be prepared to share OpenVPN configuration files with the container.
        Depending on the user's settings, different configurations can be applied.
        With or without username / password authentication via auth-user-pass.
        OVPN config file directly supplied or a config directory,
        the directory feature is useful when the configuration depends on multiple file like certificate, keys etc."""
        ovpn_parameters = []

        # VPN Auth creds file
        input_vpn_auth = ParametersManager().vpn_auth
        vpn_auth = None
        if input_vpn_auth is not None:
            vpn_auth = Path(input_vpn_auth)

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
        vpn_path = Path(config_path if config_path else ParametersManager().vpn)

        logger.debug(f"Adding VPN from: {str(vpn_path.absolute())}")
        self.__vpn_name = vpn_path.name
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
            volume_path = str(ConstantConfig.private_volume_path.joinpath(share_name))
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

    def __addCapability(self, cap_string):
        """Add a linux capability to the container"""
        if cap_string in self.__capabilities:
            logger.warning("Capability already setup. Skipping.")
            return
        self.__capabilities.append(cap_string)

    def __addSysctl(self, sysctl_key, config):
        """Add a linux sysctl to the container"""
        if sysctl_key in self.__sysctls.keys():
            logger.warning(f"Sysctl {sysctl_key} already setup to '{self.__sysctls[sysctl_key]}'. Skipping.")
            return
        self.__sysctls[sysctl_key] = config

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

    def isCommonResourcesEnable(self) -> bool:
        """Return if the feature 'common resources' is enabled in this container config"""
        return self.__common_resources

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
                  read_only: bool = False,
                  volume_type: str = 'bind'):
        """Add a volume to the container configuration"""
        if volume_type == 'bind':
            try:
                os.makedirs(host_path, exist_ok=True)
            except PermissionError:
                logger.error("Unable to create the volume folder on the filesystem locally.")
                logger.critical(f"Insufficient permission to create the folder: {host_path}")
            except FileExistsError:
                # The volume targets a file that already exists on the file system
                pass
        mount = Mount(container_path, host_path, read_only=read_only, type=volume_type)
        self.__mounts.append(mount)

    def addRawVolume(self, volume_string):
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
            logger.error(f"Volume '{volume_string}' cannot be parsed. Skipping the volume.")

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

    def getDevices(self) -> List[str]:
        """Devices config getter"""
        return self.__devices

    def addEnv(self, key: str, value: str):
        """Add an environment variable to the container configuration"""
        self.__envs[key] = value

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
        if self.__vpn_name is None:
            return "[bright_black]N/A[/bright_black]   "
        return f"[deep_sky_blue3]{self.__vpn_name}[/deep_sky_blue3]"

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
            result += f"{getColor(self.__privileged)[0]}Privileged: {'On :fire:' if self.__privileged else '[red]Off :cross_mark:[/red]'}{getColor(self.__privileged)[1]}{os.linesep}"
        if verbose or not self.__enable_gui:
            result += f"{getColor(self.__enable_gui)[0]}GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}"
        if verbose or not self.__network_host:
            result += f"[green]Network mode: [/green]{'host' if self.__network_host else 'custom'}{os.linesep}"
        if verbose or not self.__share_timezone:
            result += f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}"
        if verbose or not self.__common_resources:
            result += f"{getColor(self.__common_resources)[0]}Common resources: {boolFormatter(self.__common_resources)}{getColor(self.__common_resources)[1]}{os.linesep}"
        if self.__vpn_name is not None:
            result += f"[green]VPN: [/green]{self.__vpn_name}{os.linesep}"
        return result

    def getTextMounts(self, verbose: bool = False) -> str:
        """Text formatter for Mounts configurations. The verbose mode does not exclude technical volumes."""
        result = ''
        for mount in self.__mounts:
            # Blacklist technical mount
            if not verbose and mount.get('Target') in ['/tmp/.X11-unix', '/opt/resources', '/etc/localtime',
                                                       '/etc/timezone']:
                continue
            result += f"{mount.get('Source')} :right_arrow: {mount.get('Target')} {'(RO)' if mount.get('ReadOnly') else ''}{os.linesep}"
        return result

    def getTextDevices(self, verbose: bool = False) -> str:
        """Text formatter for Devices configurations. The verbose mode show full device configuration."""
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
        """Text formatter for Envs configurations. The verbose mode does not exclude technical variables."""
        result = ''
        for k, v in self.__envs.items():
            # Blacklist technical variables, only shown in verbose
            if not verbose and k in ["QT_X11_NO_MITSHM", "DISPLAY", "PATH"]:
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
               f"Common resources: {self.__common_resources}{os.linesep}" \
               f"Env ({len(self.__envs)}): {self.__envs}{os.linesep}" \
               f"Shares ({len(self.__mounts)}): {self.__mounts}{os.linesep}" \
               f"Devices ({len(self.__devices)}): {self.__devices}{os.linesep}" \
               f"VPN: {self.__vpn_name}"

    def printConfig(self):
        """Log current object state, debug only"""
        logger.info(f"Current container config :{os.linesep}{self}")
