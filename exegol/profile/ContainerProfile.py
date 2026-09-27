"""Schema of a container configuration profile — a named set of container-shape defaults.

Keys are user-facing names (``network.mode``), not argparse dests, grouped into sections
that mirror the option groups of ``exegol start --help``. ``PROFILE_FIELD_MAP``
(``exegol.profile.ProfileFieldMap``) translates each field to its ``OptionKey``;
``Field(alias=...)`` is not used because the mapping table is needed either way.

A field defined here is only schema-valid: taking effect also requires a ``_REGISTRY``
entry and a ``PROFILE_FIELD_MAP`` mapping (or a ``PROFILE_PENDING_REGISTRATION`` entry).

Every field is ``Optional[T] = None``: a profile declares only what the user wrote
(``model_dump(exclude_unset=True)``), and defaults belong to ``UserConfig`` and the resolver.
There is no ``mount_current_dir`` field and no field accepts credential contents.
"""

from ipaddress import ip_address
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from exegol.config.UserConfig import UserConfig
from exegol.config.YamlConfigLoader import StrictYamlModel
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.sentinel.SentinelProfile import TRUNCATION_MODES
from exegol.utils.ExeLog import logger
from exegol.utils.NetworkUtils import NetworkUtils


def _normalize_key_value_list(value: Any) -> Any:
    """Convert a ``{KEY: value}`` dict into the canonical ``["KEY=value"]`` list.

    Any other input is passed through for normal validation.
    """
    if isinstance(value, dict):
        return [f"{key}={val}" for key, val in value.items()]
    return value


def _normalize_hostname_ip_list(value: Any) -> Any:
    """Convert a list of ``"hostname=ip"`` strings into the canonical mapping.

    A malformed list is returned unchanged so validation reports a plain type error.
    """
    if isinstance(value, list):
        normalized: Dict[str, str] = {}
        for entry in value:
            if not isinstance(entry, str) or "=" not in entry:
                return value
            hostname, _, ip = entry.partition("=")
            normalized[hostname] = ip
        return normalized
    return value


class ImageSection(StrictYamlModel):
    """Which image a container is created from, and which extra images are known."""

    # OptionKey.IMAGE_TAG — only the `exegol start` positional is overridable by a profile.
    tag: Optional[str] = None
    # UserConfig.custom_images
    custom_images: Optional[List[str]] = None


class NetworkSection(StrictYamlModel):
    """Networking defaults a profile may supply.

    There is no fallback-mode field: if ``mode`` cannot be honoured on a host, that host's
    ``~/.exegol/config.yml`` fallback policy decides.
    """

    # OptionKey.NETWORK
    mode: Optional[str] = None
    # OptionKey.PORTS
    ports: Optional[List[str]] = None
    # OptionKey.HOSTNAME
    hostname: Optional[str] = None
    # OptionKey.HOSTNAME_ASK_USER — when true, container creation asks for the hostname and
    # offers `hostname` above as the prompt default. It chooses who supplies the value, not
    # what the value is.
    hostname_ask_user: Optional[bool] = None
    # OptionKey.HOSTS_FILE — a path to an "IP HOSTNAME" file.
    hosts_file: Optional[str] = None
    # Profile-only hostname -> IP entries, merged over `hosts_file` (these win on collision).
    # Also accepts a list of "hostname=ip" strings.
    hosts: Optional[Dict[str, str]] = None
    # UserConfig.network_dedicated_range
    dedicated_range: Optional[str] = None
    # UserConfig.network_default_netmask
    default_netmask: Optional[int] = Field(default=None, gt=0, le=32)

    @field_validator("mode")
    @classmethod
    def _warn_on_unknown_mode(cls, value: Optional[str]) -> Optional[str]:
        """Warn (never reject) when the mode is not one of the CLI's `-N/--network` choices.

        An unknown value is treated as a Docker network name, so a typo would silently
        attach to the wrong network.
        """
        if value is not None and value not in NetworkUtils.get_options():
            logger.warning(f"Profile field [blue]network.mode[/blue]: {value!r} is not one of the known network "
                            f"modes ({sorted(NetworkUtils.get_options())}). If this is a typo, the container may "
                            f"attach to an unintended Docker network.")
        return value

    @field_validator("hosts", mode="before")
    @classmethod
    def _normalize_hosts_shape(cls, value: Any) -> Any:
        return _normalize_hostname_ip_list(value)

    @field_validator("hosts")
    @classmethod
    def _validate_hosts(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Reject invalid hostnames and IPs early, and return each IP stripped.

        Stripping matters: a padded IP would reach Docker's `ExtraHosts` verbatim and fail there.
        """
        if value is None:
            return value
        normalized: Dict[str, str] = {}
        for hostname, ip in value.items():
            if not hostname.strip() or any(character.isspace() for character in hostname):
                raise ValueError(f"invalid hostname {hostname!r}: must be non-empty and contain no whitespace")
            try:
                ip_address(ip.strip())
            except ValueError:
                raise ValueError(f"host {hostname!r} maps to {ip!r}, which is not a valid IP address")
            normalized[hostname] = ip.strip()
        return normalized


class VolumesSection(StrictYamlModel):
    """What is mounted into the container, and from where on the host.

    There is deliberately no ``mount_current_dir`` / ``-cwd`` field: it expands to the
    launch directory, so a shared profile could bind-mount an arbitrary host tree.
    """

    # OptionKey.VOLUMES
    mounts: Optional[List[str]] = None
    # OptionKey.WORKSPACE_PATH
    workspace_path: Optional[str] = None
    # OptionKey.EXEGOL_RESOURCES
    share_exegol_resources: Optional[bool] = None
    # OptionKey.UPDATE_FS_PERMS
    update_fs_perms: Optional[bool] = None
    # UserConfig.exegol_resources_path
    exegol_resources_path: Optional[str] = None
    # UserConfig.private_volume_path
    private_workspace_path: Optional[str] = None


class CustomizationSection(StrictYamlModel):
    """The my-resources volume: the user's personal tool/environment customisation space."""

    # OptionKey.MY_RESOURCES
    share_my_resources: Optional[bool] = None
    # UserConfig.my_resources_path
    my_resources_path: Optional[str] = None


class DesktopSection(StrictYamlModel):
    """The Exegol desktop feature and how it is exposed.

    ``proto``, ``listen_ip`` and ``port`` are the split form of the CLI's
    ``"proto:host:port"`` string; declare ``proto`` alongside the other two.
    """

    enabled: Optional[bool] = None
    proto: Optional[str] = None
    listen_ip: Optional[str] = None
    # Falls back to the protocol's default port when unset.
    port: Optional[int] = Field(default=None, gt=0, le=65535)


class DisplaySection(StrictYamlModel):
    """GUI sharing: X11 passthrough and the desktop feature."""

    # OptionKey.GUI — the field keeps its `share_x11` name so existing profile files stay valid.
    share_x11: Optional[bool] = None
    desktop: Optional[DesktopSection] = None


class VpnSection(StrictYamlModel):
    """VPN configuration, referenced BY PATH only.

    Paths are not expanded nor checked when the file is read, only at container creation.
    No field accepts credential contents: ``auth_file`` names a file, never a secret.
    """

    # Path to an .ovpn / WireGuard .conf file.
    config: Optional[str] = None
    # Path to a credentials file — never the credentials themselves.
    auth_file: Optional[str] = None


class ShellSection(StrictYamlModel):
    """Which shell starts, and what environment it starts with."""

    # OptionKey.SHELL
    default: Optional[str] = None
    # OptionKey.ENVS — canonical form is a "KEY=value" list; a mapping is also accepted.
    # The list stays canonical because list -> mapping is lossy (repeated keys).
    env: Optional[List[str]] = None

    @field_validator("default")
    @classmethod
    def _warn_on_unknown_shell(cls, value: Optional[str]) -> Optional[str]:
        """Typo detection: reuses the CLI's `-s/--shell` choices (`UserConfig.start_shell_options`)."""
        if value is not None and value not in UserConfig.start_shell_options:
            logger.warning(f"Profile field [blue]shell.default[/blue]: {value!r} is not one of the known shells "
                            f"({sorted(UserConfig.start_shell_options)}). Check for a typo.")
        return value

    @field_validator("env", mode="before")
    @classmethod
    def _normalize_env_shape(cls, value: Any) -> Any:
        return _normalize_key_value_list(value)


class LoggingSection(StrictYamlModel):
    """Shell logging (commands and outputs recorded to /workspace/logs/)."""

    # OptionKey.LOG
    enabled: Optional[bool] = None
    # OptionKey.LOG_METHOD
    method: Optional[str] = None
    # OptionKey.LOG_COMPRESS
    compress: Optional[bool] = None

    @field_validator("method")
    @classmethod
    def _warn_on_unknown_method(cls, value: Optional[str]) -> Optional[str]:
        """Typo detection: reuses the CLI's `--log-method` choices (`UserConfig.shell_logging_method_options`)."""
        if value is not None and value not in UserConfig.shell_logging_method_options:
            logger.warning(f"Profile field [blue]logging.method[/blue]: {value!r} is not one of the known logging "
                            f"methods ({sorted(UserConfig.shell_logging_method_options)}). Check for a typo.")
        return value


class SystemSection(StrictYamlModel):
    """Host-level sharing and container privileges."""

    # OptionKey.SHARE_TIMEZONE
    share_timezone: Optional[bool] = None
    # OptionKey.PRIVILEGED
    privileged: Optional[bool] = None
    # OptionKey.DEVICES
    devices: Optional[List[str]] = None
    # OptionKey.CAPABILITIES
    capabilities: Optional[List[str]] = None

    @field_validator("capabilities")
    @classmethod
    def _warn_on_unknown_capabilities(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """Typo detection: reuses the CLI's `--cap` choices (`UserConfig.capability_options`)."""
        if value is not None:
            unknown = [item for item in value if item not in UserConfig.capability_options]
            if unknown:
                logger.warning(f"Profile field [blue]system.capabilities[/blue]: {unknown} not in the known "
                                f"capabilities ({sorted(UserConfig.capability_options)}). Check for a typo.")
        return value


class LogRotationSection(StrictYamlModel):
    """Sentinel log rotation, mirroring ``UserConfig.sentinel_log_rotation_*``."""

    # UserConfig.sentinel_log_rotation_enabled
    enabled: Optional[bool] = None
    # UserConfig.sentinel_log_rotation_max_size — bytes as an int, or a "100MB" string.
    max_size: Optional[str] = None
    # UserConfig.sentinel_log_rotation_max_files
    max_files: Optional[int] = None
    # UserConfig.sentinel_log_rotation_compress
    compress: Optional[bool] = None


class LogOutputSection(StrictYamlModel):
    """Inline terminal-output capture, mirroring the profilable ``UserConfig.sentinel_log_output_*``.

    All three keys are profile-overridable, ``enabled`` included, because what they set is a
    default rather than a control: these values are backfilled into the deployed config only
    when the selected Sentinel audit profile declares no ``log_output`` block of its own, and
    an audit profile that declares one replaces them wholesale. So an audit profile can always
    turn inline capture on or off over the top of ``~/.exegol/config.yml`` — that path is
    documented — and withholding ``enabled`` here would not have closed that capability, only
    made this family inconsistent and blocked an org-wide container profile from enabling
    auditing by default.

    ``enabled`` is nevertheless the one key here whose direction matters, so an unreadable or
    unrecognised value resolves to capture off.
    """

    # UserConfig.sentinel_log_output_enabled
    enabled: Optional[bool] = None
    # UserConfig.sentinel_log_output_max_size — bytes as an int, or a "4KB" string.
    max_size: Optional[str] = None
    # UserConfig.sentinel_log_output_truncation
    truncation: Optional[str] = None

    @field_validator("truncation")
    @classmethod
    def _warn_on_unknown_truncation(cls, value: Optional[str]) -> Optional[str]:
        """Typo detection: reuses the audit schema's own choice set (``TRUNCATION_MODES``)."""
        if value is not None and value not in TRUNCATION_MODES:
            logger.warning(f"Profile field [blue]sentinel.log_output.truncation[/blue]: {value!r} is not "
                           f"one of the known modes ({list(TRUNCATION_MODES)}). Check for a typo.")
        return value


class SentinelSection(StrictYamlModel):
    """Sentinel audit logging. ``profile`` names a Sentinel audit profile, not a container profile.

    * ``enabled: true``, no ``profile``    -> enabled with the default audit profile
    * ``enabled: true``, ``profile: NAME`` -> enabled with that audit profile
    * ``enabled: false``                   -> disabled; ``profile`` is ignored
    * ``profile: NAME``, ``enabled`` unset -> enabled with that audit profile (like ``-SP NAME``)

    A null value is read as an omitted key, and ``profile: ""`` as no profile: both fall
    through to ``sentinel_enabled_by_default`` / ``sentinel_default_profile``. So a profile
    file cannot express "Sentinel on, no audit profile" when a default audit profile is
    configured; only ``-SP ""`` on the command line can.
    """

    enabled: Optional[bool] = None
    profile: Optional[str] = None
    update_strategy: Optional[str] = None

    @field_validator("update_strategy")
    @classmethod
    def _warn_on_unknown_update_strategy(cls, value: Optional[str]) -> Optional[str]:
        """Typo detection: reuses the CLI's `--sentinel-strategy` choices (`SentinelUpdateStrategy.values()`)."""
        if value is not None and value not in SentinelUpdateStrategy.values():
            logger.warning(f"Profile field [blue]sentinel.update_strategy[/blue]: {value!r} is not one of the "
                            f"known strategies ({SentinelUpdateStrategy.values()}). Check for a typo.")
        return value
    # UserConfig.sentinel_gid
    gid: Optional[int] = None
    # UserConfig.sentinel_path — host directory receiving the Sentinel audit logs.
    sentinel_logs_host_path: Optional[str] = None
    log_rotation: Optional[LogRotationSection] = None
    log_output: Optional[LogOutputSection] = None


class MetadataSection(StrictYamlModel):
    """Free-form annotation: ``description`` describes the profile, ``comment`` is carried onto the container."""

    # Tied to no OptionKey: this describes the profile, never the container, so it has no
    # dest, no `_REGISTRY` entry and no `PROFILE_FIELD_MAP` entry. Displayed by
    # `exegol info --profile` and by the interactive picker, and declared in
    # `_METADATA_ONLY_FIELDS` so a bulk-registration pass cannot sweep it up.
    description: Optional[str] = None
    # OptionKey.COMMENT
    comment: Optional[str] = None
    # OptionKey.COMMENT_ASK_USER — when true, container creation asks for the comment and
    # offers `comment` above as the prompt default. Like its `network` twin it chooses who
    # supplies the value, not what the value is.
    comment_ask_user: Optional[bool] = None


class ContainerProfile(StrictYamlModel):
    """Root model of a container profile file: one document, one profile.

    ``version`` is schema-format metadata reserved for future structural changes; absent
    means version 1.
    """

    version: Optional[int] = None
    image: Optional[ImageSection] = None
    network: Optional[NetworkSection] = None
    volumes: Optional[VolumesSection] = None
    customization: Optional[CustomizationSection] = None
    display: Optional[DisplaySection] = None
    vpn: Optional[VpnSection] = None
    shell: Optional[ShellSection] = None
    logging: Optional[LoggingSection] = None
    system: Optional[SystemSection] = None
    sentinel: Optional[SentinelSection] = None
    metadata: Optional[MetadataSection] = None
