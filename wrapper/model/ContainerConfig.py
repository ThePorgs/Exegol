import os
import platform

from docker.types import Mount

from wrapper.exceptions.ExegolExceptions import ProtocolNotSupported
from wrapper.utils.ExeLog import logger


class ContainerConfig:

    def __init__(self, container=None):
        self.__enable_gui = False
        self.__share_timezone = False
        self.__common_resources = False
        self.network_host = True
        self.ports = {}
        self.privileged = False
        self.mounts = []
        self.devices = []
        self.envs = {}
        self.interactive = True
        self.tty = True
        self.shm_size = '1G'
        self.__share_cwd = None
        if container is not None:
            self.__parseContainerConfig(container)

    def __parseContainerConfig(self, container):
        # Container Config section
        container_config = container.attrs.get("Config", {})
        self.tty = container_config.get("Tty", True)
        self.__parseEnvs(container_config.get("Env", []))
        self.interactive = container_config.get("OpenStdin", True)
        self.__enable_gui = False
        for env in self.envs:
            if "DISPLAY" in env:
                self.__enable_gui = True
                break

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.privileged = host_config.get("Privileged", False)
        self.devices = host_config.get("Devices", [])

        # Volumes section
        self.__share_timezone = False
        self.__common_resources = False
        self.__parseMounts(container.attrs.get("Mounts", []))

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.network_host = "host" in network_settings["Networks"]
        self.ports = network_settings.get("Ports", {})

    def __parseEnvs(self, envs):
        for env in envs:
            key, value = env.split('=')
            self.envs[key] = value

    def __parseMounts(self, mounts):
        for share in mounts:
            self.mounts.append(Mount(source=share.get("Source"),
                                     target=share.get('Destination'),
                                     type=share.get('Type', 'volume'),
                                     read_only=(not share.get("RW", True)),
                                     propagation=share.get('Propagation', '')))
            if "/etc/timezone" in share.get('Destination', ''):
                self.__share_timezone = True
            elif "/opt/resources" in share.get('Destination', ''):
                self.__common_resources = True
            elif "/workspace" in share.get('Destination', ''):
                self.__share_cwd = share.get('Source', '')

    def enableGUI(self):
        if platform.system() == "Windows" or "microsoft" in platform.release():
            # TODO Investigate X11 sharing on Windows with container
            logger.error("Display sharing is not (yet) supported on Windows. Skipping.")
            return
        if not self.__enable_gui:
            self.__enable_gui = True
            logger.verbose("Enabling display sharing")
            self.addVolume("/tmp/.X11-unix", "/tmp/.X11-unix")
            self.addEnv("QT_X11_NO_MITSHM", "1")
            self.addEnv("DISPLAY", f"unix{os.getenv('DISPLAY')}")

    def shareTimezone(self):
        if platform.system() == "Windows" or "microsoft" in platform.release():
            logger.error("Timezone sharing is not (yet) supported on Windows. Skipping.")
            return
        if not self.__share_timezone:
            self.__share_timezone = True
            logger.verbose("Enabling host timezones")
            self.addVolume("/etc/timezone", "/etc/timezone", read_only=True)
            self.addVolume("/etc/localtime", "/etc/localtime", read_only=True)

    def enableCommonShare(self):
        if not self.__common_resources:
            self.__common_resources = True
            raise NotImplementedError  # TODO test different mount / volume type for sharing volume between containers

    def setCwdShare(self):
        logger.info("Sharing current working directory")
        self.__share_cwd = os.getcwd()
        self.addVolume(self.__share_cwd, '/workspace')

    def getNetworkMode(self):
        return "host" if self.network_host else "bridge"

    def getWorkingDir(self):
        return "/workspace" if self.__share_cwd is not None else "/data"

    def addVolume(self, host_path, container_path, read_only=False, volume_type='bind'):
        mount = Mount(container_path, host_path, read_only=read_only, type=volume_type)
        self.mounts.append(mount)

    def addDevice(self, device_source: str, device_dest: str = None, readonly=False, mknod=True):
        if device_dest is None:
            device_dest = device_source
        perm = 'r'
        if not readonly:
            perm += 'w'
        if mknod:
            perm += 'm'
        self.devices.append(f"{device_source}:{device_dest}:{perm}")

    def addEnv(self, key, value):
        self.envs[key] = value

    def addPort(self, port_host, port_container=None, protocol='tcp', host_ip='0.0.0.0'):
        if protocol.lower() not in ['tcp', 'udp', 'sctp']:
            raise ProtocolNotSupported(f"Unknown protocol '{protocol}'")
        self.ports[f"{port_container}/{protocol}"] = [{'HostIp': host_ip, 'HostPort': port_host}]

    def __str__(self):
        return f"Privileged: {self.privileged}{os.linesep}" \
               f"X: {self.__enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {'host' if self.network_host else 'custom'}{os.linesep}" \
               f"Share timezone: {self.__share_timezone}{os.linesep}" \
               f"Common resources: {self.__common_resources}{os.linesep}" \
               f"Env ({len(self.envs)}): {self.envs}{os.linesep}" \
               f"Shares ({len(self.mounts)}): {self.mounts}{os.linesep}" \
               f"Devices ({len(self.devices)}): {self.devices}"

    def printConfig(self):
        logger.info(f"Current container config :{os.linesep}{self}")
