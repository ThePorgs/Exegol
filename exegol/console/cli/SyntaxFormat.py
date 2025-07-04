from enum import Enum


class SyntaxFormat(Enum):
    port_sharing = "[default green not bold][<host_ipv4>:]<host_port>[-<end_host_port>][:<container_port>[-<end_container_port>]][:<protocol>][/default green not bold]"
    desktop_config = "[blue]proto[:ip[:port]][/blue]"
    volume = "/path/on/host/:/path/in/container/[blue][:ro|rw][/blue]"

    def __str__(self) -> str:
        return self.value
