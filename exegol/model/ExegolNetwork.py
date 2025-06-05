from enum import Enum
from typing import Optional, Union, List, Tuple


class DockerDrivers(Enum):
    """Enum for Docker driver type"""
    Disabled = 'none'
    Host = 'host'
    Bridge = 'bridge'


class ExegolNetworkMode(Enum):
    """Enum for user display"""
    disabled = 'Disabled'
    host = 'Host'
    docker = 'Docker'
    nat = 'NAT'  # need pre-process
    attached = 'External'  # need pre-process


class ExegolNetwork:
    DEFAULT_DOCKER_NETWORK = [d.value for d in DockerDrivers]

    __DEFAULT_NETWORK_DRIVER = DockerDrivers.Bridge

    def __init__(self, net_mode: ExegolNetworkMode = ExegolNetworkMode.host, net_name: Optional[str] = None) -> None:
        self.__net_mode: ExegolNetworkMode = net_mode
        try:
            # Handle Disable and Host drivers
            self.__docker_net_mode = DockerDrivers[self.__net_mode.value]
        except KeyError:
            self.__docker_net_mode = self.__DEFAULT_NETWORK_DRIVER
        self.__net_name = net_name if net_name else self.__docker_net_mode.value

    @classmethod
    def instance_network(cls, mode: Union[ExegolNetworkMode, str], container_name: str) -> "ExegolNetwork":
        if type(mode) is str:
            return cls(net_mode=ExegolNetworkMode.attached, net_name=mode)
        else:
            assert type(mode) is ExegolNetworkMode
            if mode in [ExegolNetworkMode.host, ExegolNetworkMode.docker]:
                return cls(net_mode=mode)
            elif mode == ExegolNetworkMode.nat:
                return cls(net_mode=mode, net_name=container_name)
            elif mode == ExegolNetworkMode.disabled:
                raise ValueError("Network disable cannot be created")
        raise NotImplementedError("This network type is not implemented yet.")

    @classmethod
    def parse_networks(cls, networks: dict, container_name: str) -> List["ExegolNetwork"]:
        results = []
        for network, config in networks.items():
            if network == DockerDrivers.Host.value:
                net_mode = ExegolNetworkMode.host
            elif network == DockerDrivers.Bridge.value:
                net_mode = ExegolNetworkMode.docker
            elif network == container_name:
                net_mode = ExegolNetworkMode.nat
            else:
                net_mode = ExegolNetworkMode.attached
            results.append(cls(net_mode=net_mode, net_name=network))

        return results

    def getNetworkConfig(self) -> Tuple[str, str]:
        return self.__net_name, self.__docker_net_mode.value

    def getNetworkMode(self) -> ExegolNetworkMode:
        return self.__net_mode

    def getNetworkDriver(self) -> DockerDrivers:
        return self.__docker_net_mode

    def getNetworkName(self) -> str:
        return self.__net_name

    def getTextNetworkMode(self) -> str:
        if self.__net_mode is ExegolNetworkMode.attached:
            return self.__net_name
        return self.__net_mode.value

    def shouldBeRemoved(self) -> bool:
        return self.__net_mode == ExegolNetworkMode.nat

    def __repr__(self) -> str:
        repr_str = self.__net_mode.value
        if self.__net_mode in [ExegolNetworkMode.nat, ExegolNetworkMode.attached]:
            repr_str += f" ({self.__net_name} : {self.__docker_net_mode.value})"
        return repr_str
