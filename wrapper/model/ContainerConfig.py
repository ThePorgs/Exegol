import os
import re
from pathlib import Path, PurePosixPath
from typing import Optional, List, Dict, Union, Tuple

from docker.models.containers import Container
from docker.types import Mount
from rich.prompt import Confirm

from wrapper.console.ConsoleFormat import boolFormatter, getColor
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.exceptions.ExegolExceptions import ProtocolNotSupported
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger, ExeLog


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
        self.shm_size: str = '1G'
        self.__share_cwd: Optional[str] = None
        self.__share_private: Optional[str] = None
        self.__disable_workspace: bool = False
        self.__container_command: str = "bash"
        self.__vpn_name: str = None
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
        for device in self.__devices:
            logger.info(f"Shared host device: {device['PathOnHost']}")
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
            key, value = env.strip("'").strip('"').split('=')
            self.__envs[key] = value

    def __parseMounts(self, mounts: Optional[List[Dict]], name: str):
        """Parse Mounts object"""
        if mounts is None:
            mounts = []
        self.__disable_workspace = True
        for share in mounts:
            logger.debug(f"Parsing mount : {share}")
            src_path = None
            if share.get('Type', 'volume') == "volume":
                source = f"Docker {share.get('Driver', '')} volume '{share.get('Name', 'unknown')}'"
            else:
                source = share.get("Source")
                # Check if path is from Windows Docker Desktop
                matches = re.match(r"^/run/desktop/mnt/host/([a-z])(/.*)$", source, re.IGNORECASE)
                if matches:
                    # Convert Windows Docker-VM style volume path to local OS path
                    src_path = Path(f"{matches.group(1).upper()}:{matches.group(2)}")
                    logger.debug(f"Windows style detected : {src_path}")
                else:
                    # Remove docker mount path if exist
                    src_path = PurePosixPath(source.replace('/run/desktop/mnt/host', ''))
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
                logger.debug(f"Loading workspace volume source : {src_path}")
                self.__disable_workspace = False
                if src_path is not None and src_path.name == name and src_path.parent.name == "shared-data-volumes":
                    self.__share_private = source
                else:
                    self.__share_cwd = source
            elif "/vpn" in share.get('Destination', ''):
                self.__vpn_name = src_path.name
                logger.debug(f"Loading VPN config: {self.__vpn_name}")

    @staticmethod
    def __isGuiAvailable() -> bool:
        if ConstantConfig.windows_host:
            # TODO Investigate X11 sharing on Windows with container
            logger.warning("Display sharing is not (yet) supported on Windows.")
            return False
        return True

    def enableGUI(self):
        """Procedure to enable GUI feature"""
        if not self.__isGuiAvailable():
            logger.error("GUI feature is not available on your environment. Skipping.")
            return
        if not self.__enable_gui:
            self.__enable_gui = True
            logger.verbose("Config : Enabling display sharing")
            self.addVolume("/tmp/.X11-unix", "/tmp/.X11-unix")
            self.addEnv("QT_X11_NO_MITSHM", "1")
            self.addEnv("DISPLAY", f"unix{os.getenv('DISPLAY')}")

    def enableSharedTimezone(self):
        """Procedure to enable shared timezone feature"""
        if ConstantConfig.windows_host:
            logger.warning("Timezone sharing is inconsistent on Windows. May be inaccurate.")
        if not self.__share_timezone:
            self.__share_timezone = True
            logger.verbose("Config : Enabling host timezones")
            self.addVolume("/etc/timezone", "/etc/timezone", read_only=True)
            self.addVolume("/etc/localtime", "/etc/localtime", read_only=True)

    def enablePrivileged(self, status: bool = True):
        """Set container as privileged"""
        self.__privileged = status

    def enableCommonVolume(self):
        """Procedure to enable common volume feature"""
        if not self.__common_resources:
            logger.verbose("Config : Enable common resources volume")
            self.__common_resources = True
            # Adding volume config
            self.addVolume(ConstantConfig.COMMON_SHARE_NAME, '/opt/resources', volume_type='volume')

    def enableCwdShare(self):
        """Procedure to share Current Working Directory with the container"""
        logger.verbose("Config : Sharing current working directory")
        self.__share_cwd = os.getcwd()

    def enableVPN(self):
        """Configure a VPN profile for container startup"""
        # Check host mode : custom (allows you to isolate the VPN connection from the host's network)
        if self.__network_host:
            logger.warning("Using the host network mode with a VPN profile is not recommended.")
            if not Confirm.ask(
                    f"[blue][?][/blue] Are you sure you want to configure a VPN container based on the host's network? [bright_magenta]\[y/N][/bright_magenta]",
                    default=False,
                    show_choices=False,
                    show_default=False):
                logger.info("Changing network mode to custom")
                self.setNetworkMode(False)
        # Add NET_ADMIN capabilities, this privilege is necessary to mount network tunnels
        self.__addCapability("NET_ADMIN")
        if not self.__network_host:
            # Add sysctl ipv6 config, some VPN connection need IPv6 to be enabled
            self.__addSysctl("net.ipv6.conf.all.disable_ipv6", "0")
        # Add tun device, this device is needed to create VPN tunnels
        self.addDevice("/dev/net/tun")
        # Sharing VPN configuration with the container
        vpn_path = Path(ParametersManager().vpn)
        logger.debug(f"Adding VPN from: {str(vpn_path.absolute())}")
        self.__vpn_name = vpn_path.name
        if vpn_path.is_file():
            self.addVolume(str(vpn_path.absolute()), "/vpn/config.ovpn", read_only=True)
        else:
            # When VPN is dir
            logger.info(
                "Folder detected for VPN configuration, only the config.ovpn file will be automatically launched when the container starts.")
            self.addVolume(str(vpn_path.absolute()), "/vpn")
        # Execution of the VPN daemon at container startup
        # TODO add --auth-user-pass file
        self.setContainerCommand("bash -c 'openvpn /vpn/config.ovpn | tee /var/log/vpn.log; bash'")

    def disableDefaultWorkspace(self):
        """Allows you to disable the default workspace volume"""
        # If a custom workspace is not define, disable workspace
        if self.__share_cwd is None:
            self.__disable_workspace = True

    def prepareShare(self, share_name: str):
        """Add workspace share before container creation"""
        for mount in self.__mounts:
            if mount.get('Target') == '/workspace':
                # Volume is already prepared
                return
        if self.__share_cwd is not None:
            self.addVolume(self.__share_cwd, '/workspace')
        elif self.__disable_workspace:
            # Skip default volume workspace if disabled
            return
        else:
            volume_path = str(ConstantConfig.private_volume_path.joinpath(share_name))
            # TODO when SDK will be ready, change this to a volume to enable auto-remove
            self.addVolume(volume_path, '/workspace')

    def setNetworkMode(self, host_mode: bool):
        """Set container's network mode, true for host, false for bridge"""
        if host_mode is None:
            host_mode = True
        self.__network_host = host_mode

    def setContainerCommand(self, cmd: str):
        """Set container's entrypoint command on creation"""
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
        if self.__share_cwd:
            return self.__share_cwd
        elif self.__share_private:
            return self.__share_private
        return "not found :("

    def getPrivateVolumePath(self) -> Optional[str]:
        """Get private volume path (None if not set)"""
        return self.__share_private

    def isCommonResourcesEnable(self) -> bool:
        """Return if the feature 'common resources' is enabled in this config"""
        return self.__common_resources

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
                  mknod: bool = True):
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

    def getEnvs(self) -> Dict[str, str]:
        """Envs config getter"""
        return self.__envs

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
            result += f"{getColor(self.__privileged)[0]}Privileged: {':fire:' if self.__privileged else '[red]:cross_mark:[/red]'}{getColor(self.__privileged)[1]}{os.linesep}"
        if verbose or not self.__enable_gui:
            result += f"{getColor(self.__enable_gui)[0]}GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}"
        if verbose or not self.__network_host:
            result += f"Network mode: {'host' if self.__network_host else 'custom'}{os.linesep}"
        if verbose or not self.__share_timezone:
            result += f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}"
        if verbose or not self.__common_resources:
            result += f"{getColor(self.__common_resources)[0]}Common resources: {boolFormatter(self.__common_resources)}{getColor(self.__common_resources)[1]}{os.linesep}"
        if self.__vpn_name is not None:
            result += f"VPN: {self.__vpn_name}{os.linesep}"
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
