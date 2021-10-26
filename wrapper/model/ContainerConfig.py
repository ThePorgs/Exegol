import os
import re

from docker.types import Mount

from wrapper.console.ConsoleFormat import boolFormatter, getColor
from wrapper.exceptions.ExegolExceptions import ProtocolNotSupported
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


class ContainerConfig:

    def __init__(self, container=None):
        """Container config default value"""
        self.__enable_gui = False
        self.__share_timezone = False
        self.__common_resources = False
        self.__network_host = True
        self.__privileged = False
        self.__mounts = []
        self.__devices = []
        self.__envs = {}
        self.__ports = {}
        self.interactive = True
        self.tty = True
        self.shm_size = '1G'
        self.__share_cwd = None
        self.__share_private = None
        if container is not None:
            self.__parseContainerConfig(container)

    def __parseContainerConfig(self, container):
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
        self.__devices = host_config.get("Devices", [])
        if self.__devices is None:
            self.__devices = []
        logger.debug(f"Load devices : {self.__devices}")

        # Volumes section
        self.__share_timezone = False
        self.__common_resources = False
        self.__parseMounts(container.attrs.get("Mounts", []), container.name.replace('exegol-', ''))

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.__network_host = "host" in network_settings["Networks"]
        self.__ports = network_settings.get("Ports", {})

    def __parseEnvs(self, envs):
        """Parse envs object syntax"""
        for env in envs:
            logger.debug(f"Parsing envs : {env}")
            # Removing " and ' at the beginning and the end of the string before splitting key / value
            key, value = env.strip("'").strip('"').split('=')
            self.__envs[key] = value

    def __parseMounts(self, mounts, name):
        """Parse Mounts object"""
        if mounts is None:
            mounts = []
        for share in mounts:
            logger.debug(f"Parsing mount : {share}")
            if share.get('Type', 'volume') == "volume":
                source = f"Docker {share.get('Driver', '')} volume {share.get('Name', 'unknown')}"
            else:
                source = share.get("Source")
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
                src = share.get('Source', '')
                logger.debug(f"Loading workspace volume source : {src}")
                if src.endswith(f"shared-data-volumes/{name}"):
                    # Check if path is from Windows Docker Desktop
                    matches = re.match(r"^/run/desktop/mnt/host/[a-z](/.*)$", src, re.IGNORECASE)
                    if matches:
                        # Convert Windows Docker-VM style volume path to local OS path
                        self.__share_private = os.path.abspath(matches.group(1))
                        logger.debug(f"Windows style detected : {self.__share_private}")
                    else:
                        self.__share_private = src
                else:
                    self.__share_cwd = share.get('Source', '')

    def enableGUI(self):
        """Procedure to enable GUI feature"""
        if ConstantConfig.windows_host:
            # TODO Investigate X11 sharing on Windows with container
            logger.warning("Display sharing is not (yet) supported on Windows. Skipping.")
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
            logger.warning("Timezone sharing is not (yet) supported on Windows. Skipping.")
            return
        if not self.__share_timezone:
            self.__share_timezone = True
            logger.verbose("Config : Enabling host timezones")
            self.addVolume("/etc/timezone", "/etc/timezone", read_only=True)
            self.addVolume("/etc/localtime", "/etc/localtime", read_only=True)

    def enablePrivileged(self, status=True):
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

    def prepareShare(self, share_name):
        """Add workspace share before container creation"""
        for mount in self.__mounts:
            if mount.get('Target') == '/workspace':
                # Volume is already prepared
                return
        if self.__share_cwd is not None:
            self.addVolume(self.__share_cwd, '/workspace')
        else:
            volume_path = str(ConstantConfig.private_volume_path.joinpath(share_name))
            # TODO when SDK will be ready, change this to a volume to enable auto-remove
            self.addVolume(volume_path, '/workspace')

    def getNetworkMode(self) -> str:
        """Network mode, text getter"""
        return "host" if self.__network_host else "bridge"

    def getPrivileged(self) -> bool:
        """Privileged getter"""
        return self.__privileged

    def getWorkingDir(self) -> str:
        """Get default container's default working directory path"""
        return "/workspace"

    def getHostWorkspacePath(self):
        """Get private volume path (None if not set)"""
        if self.__share_cwd:
            return self.__share_cwd
        elif self.__share_private:
            return self.__share_private
        return "not found :("

    def getPrivateVolumePath(self):
        """Get private volume path (None if not set)"""
        return self.__share_private

    def isCommonResourcesEnable(self):
        """Return if the feature 'common resources' is enable in this config"""
        return self.__common_resources

    def addVolume(self, host_path, container_path, read_only=False, volume_type='bind'):
        """Add a volume to the container configuration"""
        if volume_type == 'bind':
            os.makedirs(host_path, exist_ok=True)
        mount = Mount(container_path, host_path, read_only=read_only, type=volume_type)
        self.__mounts.append(mount)

    def getVolumes(self):
        """Volume config getter"""
        return self.__mounts

    def addDevice(self, device_source: str, device_dest: str = None, readonly=False, mknod=True):
        """Add a device to the container configuration"""
        if device_dest is None:
            device_dest = device_source
        perm = 'r'
        if not readonly:
            perm += 'w'
        if mknod:
            perm += 'm'
        self.__devices.append(f"{device_source}:{device_dest}:{perm}")

    def getDevices(self):
        """Devices config getter"""
        return self.__devices

    def addEnv(self, key, value):
        """Add an environment variable to the container configuration"""
        self.__envs[key] = value

    def getEnvs(self):
        """Envs config getter"""
        return self.__envs

    def addPort(self, port_host, port_container=None, protocol='tcp', host_ip='0.0.0.0'):
        """Add port NAT config, only applicable on bridge network mode."""
        if self.__network_host:
            logger.warning(
                "This container is configured to share the network with the host. You cannot open specific ports. Skipping.")
            logger.warning("Please set network mode to bridge in order to expose specific network ports.")
            return
        if protocol.lower() not in ['tcp', 'udp', 'sctp']:
            raise ProtocolNotSupported(f"Unknown protocol '{protocol}'")
        self.__ports[f"{port_container}/{protocol}"] = [{'HostIp': host_ip, 'HostPort': port_host}]

    def getPorts(self):
        """Ports config getter"""
        return self.__ports

    def getTextFeatures(self, verbose=False):
        """Text formatter for features configurations (Privileged, GUI, Network, Timezone, Shares)"""
        # TODO implement verbose option
        return f"{getColor(self.__privileged)[0]}Privileged: {':fire:' if self.__privileged else '[red]:cross_mark:[/red]'}{getColor(self.__privileged)[1]}{os.linesep}" \
               f"{getColor(self.__enable_gui)[0]}GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}" \
               f"Network mode: {'host' if self.__network_host else 'custom'}{os.linesep}" \
               f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}" \
               f"{getColor(self.__common_resources)[0]}Common resources: {boolFormatter(self.__common_resources)}{getColor(self.__common_resources)[1]}{os.linesep}"

    def getTextMounts(self, verbose=False):
        """Text formatter for Mounts configurations. The verbose mode does not exclude technical volumes."""
        result = ''
        for mount in self.__mounts:
            # Blacklist technical mount
            if not verbose and mount.get('Target') in ['/tmp/.X11-unix', '/opt/resources']:
                continue
            result += f"{mount.get('Source')} :right_arrow: {mount.get('Target')} {'(RO)' if mount.get('ReadOnly') else ''}{os.linesep}"
        return result

    def getTextDevices(self, verbose=False):
        """Text formatter for Devices configurations. The verbose mode show full device configuration."""
        result = ''
        for device in self.__devices:
            if verbose:
                result += f"{device}{os.linesep}"
            else:
                result += f"{':right_arrow:'.join(device.split(':')[0:2])}{os.linesep}"
        return result

    def getTextEnvs(self, verbose=False):
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
               f"X: {self.__enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {'host' if self.__network_host else 'custom'}{os.linesep}" \
               f"Share timezone: {self.__share_timezone}{os.linesep}" \
               f"Common resources: {self.__common_resources}{os.linesep}" \
               f"Env ({len(self.__envs)}): {self.__envs}{os.linesep}" \
               f"Shares ({len(self.__mounts)}): {self.__mounts}{os.linesep}" \
               f"Devices ({len(self.__devices)}): {self.__devices}"

    def printConfig(self):
        """Log current object state, debug only"""
        logger.info(f"Current container config :{os.linesep}{self}")
