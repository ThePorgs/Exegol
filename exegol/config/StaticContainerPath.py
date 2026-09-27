from enum import Enum


class StaticContainerPath(Enum):
    # Exegol
    EXEGOL_SPAWN = '/.exegol/spawn.sh'
    EXEGOL_ENTRYPOINT = '/.exegol/entrypoint.sh'

    # Ressources
    EXEGOL_RESOURCES = '/opt/resources'
    MY_RESOURCES = '/opt/my-resources'

    # OpenVPN
    OPENVPN_CREDS_FILE = '/.exegol/vpn/auth/creds.txt'
    OPENVPN_CONFIG_DIR = '/.exegol/vpn/config'
    OPENVPN_CONFIG_FILE = '/.exegol/vpn/config/client.ovpn'
    # Wireguard
    WIREGUARD_CONFIG_FILE = '/etc/wireguard/wg0.conf'

    # Sentinel
    SENTINEL_LOGGER = '/.exegol/sentinel'
    SENTINEL_DIRECTORY = '/var/log/exegol/sentinel'
    SENTINEL_ZSH_HOOKS = '/etc/zsh.d/shell_logging'
    SENTINEL_BASH_HOOKS = '/etc/bash.d/shell_logging'


class StaticFileName(Enum):
    """Bare (directory-less) file names shared across the host wrapper.

    These are combined with a directory computed at runtime, so unlike
    StaticContainerPath they carry no leading path."""
    # Consolidated Sentinel profile config written host-side into the container's sentinel directory
    SENTINEL_CONFIG = 'sentinel_config.json'

    # Sentinel audit data produced INSIDE the container
    SENTINEL_LIVE_LOG = 'logs.json'
