
class ContainerConfig:

    def __init__(self, container=None):
        self.enable_x = True
        self.network_host = True
        self.ports = {}
        self.host_timezone = True
        self.bind_ressources = True
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

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.privileged = host_config.get("Privileged", False)

        # Volumes section
        self.shares = container.attrs.get("Mounts", [])

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        networks = network_settings.get("Networks", {})
        self.network_host = len(networks) > 0 and list(networks.keys())[0] == "host"
        self.ports = network_settings.get("Ports", {})

        # TODO container parsing :
        # self.enable_x
        # self.host_timezone
        # self.bind_ressources
        # self.devices
        # self.interactive

    def __str__(self):
        return f"Privileged: {self.privileged}, X: {self.enable_x}, TTY: {self.tty}, Network host: {'host' if self.network_host else 'custom'}, Share timezone: {self.host_timezone}"
