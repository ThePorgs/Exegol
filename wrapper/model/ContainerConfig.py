import os

from wrapper.utils.ExeLog import logger


class ContainerConfig:

    def __init__(self, container=None):
        self.enable_gui = True
        self.network_host = True
        self.ports = {}
        self.share_timezone = True
        self.common_resources = True
        self.privileged = False
        self.shares = []
        self.devices = []
        self.envs = []
        self.interactive = True
        self.tty = True
        if container is not None:
            self.__parseContainerConfig(container)

    def __parseContainerConfig(self, container):
        # Container Config section
        container_config = container.attrs.get("Config", {})
        self.tty = container_config.get("Tty", True)
        self.envs = container_config.get("Env", [])
        self.interactive = container_config.get("OpenStdin", True)
        self.enable_gui = False
        for env in self.envs:
            if "DISPLAY" in env:
                self.enable_gui = True
                break

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.privileged = host_config.get("Privileged", False)
        self.devices = host_config.get("Devices", [])

        # Volumes section
        self.shares = container.attrs.get("Mounts", [])
        self.share_timezone = False
        self.common_resources = False
        for share in self.shares:
            if "/etc/timezone" in share.get('Destination', ''):
                self.share_timezone = True
            if "/opt/resources" in share.get('Destination', ''):
                self.common_resources = True

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.network_host = "host" in network_settings["Networks"]
        self.ports = network_settings.get("Ports", {})

    def __str__(self):
        return f"Privileged: {self.privileged}{os.linesep}" \
               f"X: {self.enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {'host' if self.network_host else 'custom'}{os.linesep}" \
               f"Share timezone: {self.share_timezone}{os.linesep}" \
               f"Common resources: {self.common_resources}{os.linesep}" \
               f"Env ({len(self.envs)}): {self.envs}{os.linesep}" \
               f"Shares ({len(self.shares)}): {self.shares}{os.linesep}" \
               f"Devices ({len(self.devices)}): {self.devices}"

    def printConfig(self):
        logger.info(f"Current container config :{os.linesep}{self}")
