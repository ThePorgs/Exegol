import ipaddress
from typing import Union, Set, List, Optional

import ifaddr
from rich.prompt import Prompt

from exegol.model.ExegolNetwork import ExegolNetworkMode
from exegol.utils.ExeLog import logger, console


class NetworkUtils:
    adapters = ifaddr.get_adapters()

    @classmethod
    def get_host_addresses(cls) -> Set[str]:
        result = set()
        for adapter in cls.adapters:
            for ip in adapter.ips:
                # Filter for IPv4
                if ip.is_IPv4:
                    result.add(str(ip.ip))
        return result

    @classmethod
    def get_default_large_range(cls) -> ipaddress.IPv4Network:
        available_networks = []
        for net in ipaddress.IPv4Network("172.16.0.0/12").subnets(new_prefix=16):
            if not cls.__test_conflict(net):
                available_networks.append(net)
        if len(available_networks) > 0:
            # Choose last network available to avoid conflict with docker
            selected_network = available_networks[-1]
        else:
            logger.error("Unable to automatically find an available network !")
            selected_network = cls.__user_select_network()
        logger.debug(f"Using exegol global network: {selected_network}")
        return selected_network

    @classmethod
    def get_default_large_range_text(cls) -> str:
        return str(cls.get_default_large_range())

    @classmethod
    def __user_select_network(cls) -> ipaddress.IPv4Network:
        while True:
            net_input = Prompt.ask(prompt="Please choose manually a network range for dedicated exegol networks (CIDR format):", console=console)
            try:
                net_user = ipaddress.IPv4Network(net_input)
                if not net_user.is_private:
                    logger.error("Only private IP can be used.")
                else:
                    number_subnet = len([n for n in net_user.subnets(new_prefix=28)])
                    if cls.__test_conflict(net_user):
                        logger.error("This network is already in use on your machine. Please choose another available network.")
                    else:
                        if number_subnet <= 16:
                            logger.warning(f"The selected network can only have {number_subnet} exegol dedicated networks. You can change this setting from the Exegol config file.")
                        return net_user
            except ipaddress.AddressValueError:
                logger.error("The supplied network isn't a valid IPv4 network")
            except ipaddress.NetmaskValueError:
                logger.error("The supplied netmask isn't valid for an IPv4 address")
            except ValueError:
                logger.error("The supplied IPv4 isn't a network address.")

    @classmethod
    def __test_conflict(cls, network: ipaddress.IPv4Network, docker_networks: Optional[List[str]] = None) -> bool:
        """Test if the supplied network has conflict with any existing network card on the host"""
        for adapter in cls.adapters:
            # print("IPs of network adapter " + adapter.nice_name)
            for ip in adapter.ips:
                if ip.is_IPv6:
                    continue
                if ipaddress.ip_network(f"{ip.ip}/{ip.network_prefix}", strict=False).overlaps(network):
                    return True
        if docker_networks is not None:
            for docker_net in docker_networks:
                if ipaddress.ip_network(docker_net, strict=False).overlaps(network):
                    return True
        return False

    @classmethod
    def get_next_available_range(cls, large_range: str, network_size: int, docker_subnets: List[str]) -> ipaddress.IPv4Network :
        exegol_network = ipaddress.IPv4Network(large_range)
        for net in exegol_network.subnets(new_prefix=network_size):
            if not cls.__test_conflict(net, docker_subnets):
                return net
        raise ValueError("No more sub-network available. Please remove some network or change the exegol network configuration.")

    @classmethod
    def parse_netmask(cls, netmask: Union[int, str], default: int) -> int:
        if type(netmask) is int:
            if 32 >= netmask >= 0:
                return netmask
        else:
            assert type(netmask) is str
            if netmask.startswith("/"):
                netmask = netmask[1:]
            try:
                result = int(netmask)
                if 0 > result > 32:
                    raise ValueError()
                return result
            except ValueError:
                try:
                    return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
                except ipaddress.NetmaskValueError:
                    pass
        logger.error(f"The supplied netmask is invalid (must be IPv4): {netmask}")
        return default

    @classmethod
    def get_options(cls) -> Set[str]:
        options = [x.name for x in ExegolNetworkMode if x != ExegolNetworkMode.attached]

        return set(options)
