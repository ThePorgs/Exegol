"""Declared option registry and the layered option-resolution engine.

``OptionResolver`` returns the effective value of an option from the first tier with an opinion:

    1. CLI                  what the user typed (``ParametersManager``)
    2. profile              injected mapping (``loadProfile``)
    2b. profile-UserConfig  the profile's ``PROFILE_USER_CONFIG_MAP`` settings (``loadProfileUserConfig``)
    3. UserConfig           persistent defaults (``~/.exegol/config.yml``)
    4. builtin              the default declared in :data:`_REGISTRY`

Both profile tiers are disjoint and report :attr:`OptionSource.PROFILE`. Tiers test key
presence, not non-``None``: ``{key: None}`` is a declaration and wins.

Constraints:

* ``__init__`` touches no other ``MetaSingleton``: help strings are built inside
  ``ParametersManager.__init__`` and re-entering a spawning singleton raises.
* ``resolve()`` is pure and uncached, so provenance cannot leak across tests.
* no logging, no I/O, no parsing or validation: every action imports this module.
"""

import sys
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Tuple, Union

from exegol.config.EnvInfo import EnvInfo
from exegol.config.UserConfig import UserConfig
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.utils.MetaSingleton import MetaSingleton

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    # `enum.StrEnum` only exists from Python 3.11.
    class StrEnum(str, Enum):
        """Pre-3.11 stand-in for :class:`enum.StrEnum`."""
        # Render the value ("shell"), not "OptionKey.SHELL".
        __str__ = str.__str__
        # Same rebinding as CPython's StrEnum; mypy flags the renamed parameter.
        __format__ = str.__format__  # type: ignore[assignment]


@unique
class OptionKey(StrEnum):
    """The name of a registered option, one member per :data:`_REGISTRY` entry.

    Member values are matched against ``config.yml`` keys and profile fields: never edit
    them. Names are free. ``@unique`` prevents two options aliasing the same spec.
    :data:`RESOLVER_EXCLUDED` options deliberately have no member.
    """
    # -- container options at creation only ---------------------------------
    # Value matched by nothing persisted (no config.yml key; profiles map `display.share_x11` here).
    GUI = "gui"
    MY_RESOURCES = "my_resources"
    EXEGOL_RESOURCES = "exegol_resources"
    NETWORK = "network"
    SHARE_TIMEZONE = "share_timezone"
    UPDATE_FS_PERMS = "update_fs_perms"
    VOLUMES = "volumes"
    PORTS = "ports"
    PRIVILEGED = "privileged"
    DEVICES = "devices"
    SENTINEL = "sentinel"
    SENTINEL_PROFILE = "sentinel_profile"
    SENTINEL_STRATEGY = "sentinel_strategy"
    DESKTOP = "desktop"
    DESKTOP_CONFIG = "desktop_config"
    IMAGE_TAG = "imagetag"
    VPN = "vpn"
    VPN_AUTH = "vpn_auth"
    WORKSPACE_PATH = "workspace_path"
    HOSTNAME = "hostname"
    HOSTS_FILE = "hosts_file"
    COMMENT = "comment"
    # -- container options at creation OR start -----------------------------
    SHELL = "shell"
    LOG = "log"
    LOG_METHOD = "log_method"
    LOG_COMPRESS = "log_compress"
    ENVS = "envs"
    CAPABILITIES = "capabilities"
    # -- DEST-LESS: profile-backed `~/.exegol/config.yml` settings ----------------------
    # No CLI flag; the value is the dotted profile schema path.
    CUSTOM_IMAGES = "image.custom_images"
    NETWORK_DEDICATED_RANGE = "network.dedicated_range"
    NETWORK_DEFAULT_NETMASK = "network.default_netmask"
    MY_RESOURCES_PATH = "customization.my_resources_path"
    EXEGOL_RESOURCES_PATH = "volumes.exegol_resources_path"
    PRIVATE_WORKSPACE_PATH = "volumes.private_workspace_path"
    SENTINEL_GID = "sentinel.gid"
    SENTINEL_LOGS_HOST_PATH = "sentinel.sentinel_logs_host_path"
    SENTINEL_LOG_ROTATION_ENABLED = "sentinel.log_rotation.enabled"
    SENTINEL_LOG_ROTATION_MAX_SIZE = "sentinel.log_rotation.max_size"
    SENTINEL_LOG_ROTATION_MAX_FILES = "sentinel.log_rotation.max_files"
    SENTINEL_LOG_ROTATION_COMPRESS = "sentinel.log_rotation.compress"
    SENTINEL_LOG_OUTPUT_ENABLED = "sentinel.log_output.enabled"
    SENTINEL_LOG_OUTPUT_MAX_SIZE = "sentinel.log_output.max_size"
    SENTINEL_LOG_OUTPUT_TRUNCATION = "sentinel.log_output.truncation"
    # -- DEST-LESS: the inline-hosts field ---------------------------------------------
    HOSTS = "network.hosts"
    # -- DEST-LESS: profile-only interactive flags --------------------------------------
    # No CLI flag and no `config.yml` key: these exist only inside a container profile. Each
    # decides who supplies the value of the field beside it, never what that value is, so a
    # shared profile can carry a naming policy without hard-coding one operator's answer.
    HOSTNAME_ASK_USER = "network.hostname_ask_user"
    COMMENT_ASK_USER = "metadata.comment_ask_user"
    # -- DEST-LESS: UserConfig-ONLY settings, profile tier permanently dead -------------
    # Registered so `get()` is the only way to read them; each has a reason in
    # `ProfileFieldMap.PROFILE_TIER_DEAD`. The value is the `config.yml` key.
    #
    # Per-segment defaults for `configureDesktop()`, which overwrites them with the
    # non-empty segments of `--desktop-config`.
    DESKTOP_DEFAULT_PROTO = "desktop_default_proto"
    DESKTOP_DEFAULT_LOCALHOST = "desktop_default_localhost"
    # Wrapper-behaviour settings, outside the container-profile schema.
    EXEGOL_IMAGES_PATH = "exegol_images_path"
    AUTO_REMOVE_IMAGES = "auto_remove_images"
    AUTO_CHECK_UPDATES = "auto_check_updates"
    # Not `EXEGOL_RESOURCES` (the container toggle): only decides whether to warn after a
    # failed resources download.
    ENABLE_EXEGOL_RESOURCES = "enable_exegol_resources"
    # Discovery paths/sources: a profile setting them would choose which profile is read.
    SENTINEL_PROFILE_PATH = "sentinel_profile_path"
    PROFILE_COMPONENT_PATH = "profile_component_path"
    SENTINEL_SOURCES = "sentinel_sources"
    PROFILE_SOURCES = "profile_sources"
    # -- PROCESS CONTROL and ACTION-SPECIFIC options ------------------------------------
    # They govern this invocation, not a container. Registered so `get()` is the single
    # read path; not profilable (reasons in `ProfileFieldMap.PROFILE_TIER_DEAD`).
    QUIET = "quiet"
    VERBOSITY = "verbosity"
    ARCH = "arch"
    OFFLINE_MODE = "offline_mode"
    ACCEPT_EULA = "accept_eula"
    SELECT_ALL = "select_all"
    FORCE_MODE = "force_mode"
    SENTINEL_REFRESH = "sentinel_refresh"
    DAEMON = "daemon"
    TMP = "tmp"
    EXEC = "exec"
    SELECTOR = "selector"
    BUILD_LOG = "build_log"
    BUILD_PATH = "build_path"
    # `exegol update` target selectors (`-i/--images` reuses `IMAGE_TAG`).
    UPDATE_WRAPPER = "update_wrapper"
    UPDATE_RESOURCES = "update_resources"
    # Not the excluded `profile` selector: a boolean asking `exegol update` to refresh
    # container-profile sources.
    UPDATE_PROFILE = "update_profile"
    # Not `SENTINEL` (the container toggle): asks `exegol update` to refresh Sentinel
    # profile sources.
    UPDATE_SENTINEL = "update_sentinel"
    NO_BACKUP = "no_backup"
    # Not `IMAGE_TAG` ("imagetag", the start positional): `exegol upgrade --image`, the
    # target image of an existing container. The values differ by one underscore only.
    UPGRADE_IMAGE_TAG = "image_tag"
    INFO_CONFIG = "info_config"
    INFO_SOURCES = "info_sources"
    # Not `SELECT_ALL`: same `--all` spelling, but means "show every info section".
    INFO_ALL = "info_all"
    REVOKE = "revoke"
    API_KEY = "api_key"
    LICENSE_ID = "license_id"
    # `exegol completion [SHELL]`: which shell dialect to emit the completion script for.
    # A positional, so its wire form is the attribute name argparse uses as the dest.
    SHELL_TYPE = "shell_type"


class OptionSource(Enum):
    """Which tier supplied the effective value of an option."""
    CLI = "cli"
    PROFILE = "profile"
    USER_CONFIG = "user_config"
    BUILTIN = "builtin"


class MergePolicy(Enum):
    """How a higher tier combines with the tiers below it.

    ``OVERRIDE`` — the highest tier with an opinion wins outright (every scalar/bool).
    ``APPEND``   — every tier contributes and the lists are concatenated, CLI last.
    """
    OVERRIDE = "override"
    APPEND = "append"


class OptionScope(Enum):
    """When an option is meaningful.

    Declarative only — nothing enforces scope, because doing so would change ``restart`` /
    ``exec`` behaviour.
    """
    CREATION_ONLY = "creation_only"
    CREATION_OR_START = "creation_or_start"


class Resolved(NamedTuple):
    """An effective option value together with the tier that supplied it."""
    value: Any
    source: OptionSource

    @property
    def stated(self) -> bool:
        """True when the CLI or the profile supplied a non-``None`` value.

        Stricter than :meth:`OptionResolver.isExplicitOrProfile`: a YAML null written in the
        profile is a present key but states nothing. The ``value is not None`` test only
        matters for the profile tier (the CLI branch is never ``None``).

        Limitation: on ``APPEND`` options a profile null becomes ``[]``, so this degrades to
        presence alone. What a null list should mean is undecided.
        """
        if self.source is OptionSource.CLI:
            return True
        return self.source is OptionSource.PROFILE and self.value is not None


@dataclass(frozen=True)
class OptionSpec:
    """The declared shape of one resolvable option.

    ``flags`` and ``metavar`` mirror the live ``Option(...)`` declaration so warning
    messages can name an option the way the user typed it, without re-instantiating a
    throwaway ``Command`` to re-read its argparse kwargs.
    """
    dest: str
    flags: Tuple[str, ...]
    metavar: Optional[str]
    builtin_default: Any
    user_config_attr: Optional[str]
    merge_policy: MergePolicy
    scope: OptionScope

    @property
    def display_name(self) -> str:
        """How this option is named to the user: its metavar, else its flags."""
        return self.metavar if self.metavar else " / ".join(self.flags)


# ---------------------------------------------------------------------------
# Declared registry.
#
# `dest`, `flags` and `metavar` are copied from the `Option(...)` calls in
# GenericParameters.py / ExegolParameters.py, and a drift test fails when they diverge.
# `user_config_attr` and `merge_policy` are declared, not inferred. `scope` is
# informational only.
#
# Dest-less entries (`dest=""`, `flags=()`) have no CLI flag: `ParametersManager` returns
# None for an empty dest, so the normal tier walk applies. Their `metavar` holds the
# dotted schema path or the `config.yml` key so `display_name` still names them.
# ---------------------------------------------------------------------------
_REGISTRY: Dict[OptionKey, OptionSpec] = {
    # -- container options at creation only ---------------------------------
    OptionKey.GUI: OptionSpec(
        dest="gui",
        flags=("--gui", "--no-gui"),
        metavar=None,
        builtin_default=True,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.MY_RESOURCES: OptionSpec(
        dest="my_resources",
        flags=("--my-resources", "--no-my-resources"),
        metavar=None,
        builtin_default=True,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.EXEGOL_RESOURCES: OptionSpec(
        dest="exegol_resources",
        flags=("--exegol-resources", "--no-exegol-resources"),
        metavar=None,
        builtin_default=True,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # `network` already ships with `default=None` and a UserConfig fallback — the
    # reference shape every other entry follows.
    OptionKey.NETWORK: OptionSpec(
        dest="network",
        flags=("--network",),
        metavar=None,
        builtin_default=None,
        user_config_attr="network_default_mode",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SHARE_TIMEZONE: OptionSpec(
        dest="share_timezone",
        flags=("--share-timezone", "--no-share-timezone"),
        metavar=None,
        builtin_default=True,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.UPDATE_FS_PERMS: OptionSpec(
        dest="update_fs_perms",
        flags=("-fs", "--update-fs", "--no-update-fs"),
        metavar=None,
        builtin_default=False,
        user_config_attr="auto_update_workspace_fs",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.VOLUMES: OptionSpec(
        dest="volumes",
        flags=("-V", "--volume"),
        metavar=None,
        builtin_default=[],
        user_config_attr=None,
        merge_policy=MergePolicy.APPEND,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.PORTS: OptionSpec(
        dest="ports",
        flags=("-p", "--port"),
        metavar=None,
        builtin_default=[],
        user_config_attr=None,
        merge_policy=MergePolicy.APPEND,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.PRIVILEGED: OptionSpec(
        dest="privileged",
        flags=("--privileged", "--no-privileged"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.DEVICES: OptionSpec(
        dest="devices",
        flags=("-d", "--device"),
        metavar=None,
        builtin_default=[],
        user_config_attr=None,
        merge_policy=MergePolicy.APPEND,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL: OptionSpec(
        dest="sentinel",
        flags=("-S", "--sentinel", "--no-sentinel"),
        metavar=None,
        builtin_default=False,
        user_config_attr="sentinel_enabled_by_default",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_PROFILE: OptionSpec(
        dest="sentinel_profile",
        flags=("-SP", "--sentinel-profile"),
        metavar="SENTINEL_PROFILE",
        builtin_default="",
        user_config_attr="sentinel_default_profile",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_STRATEGY: OptionSpec(
        dest="sentinel_strategy",
        flags=("--sentinel-strategy",),
        metavar="STRATEGY",
        builtin_default=SentinelUpdateStrategy.ON_RESTART.value,
        user_config_attr="sentinel_update_strategy",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.DESKTOP: OptionSpec(
        dest="desktop",
        flags=("--desktop", "--no-desktop"),
        metavar=None,
        builtin_default=False,
        user_config_attr="desktop_default_enable",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # Builtin default is the empty string, NOT None: configureDesktop() calls
    # desktop_config.split(":") and would raise AttributeError on None.
    OptionKey.DESKTOP_CONFIG: OptionSpec(
        dest="desktop_config",
        flags=("--desktop-config",),
        metavar=None,
        builtin_default="",
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # `flags` lists every spelling of this dest: the image positional and `exegol update -i/--images`.
    OptionKey.IMAGE_TAG: OptionSpec(
        dest="imagetag",
        flags=("imagetag", "-i", "--images"),
        metavar="IMAGE",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.VPN: OptionSpec(
        dest="vpn",
        flags=("--vpn",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.VPN_AUTH: OptionSpec(
        dest="vpn_auth",
        flags=("--vpn-auth",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.WORKSPACE_PATH: OptionSpec(
        dest="workspace_path",
        flags=("-w", "--workspace"),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.HOSTNAME: OptionSpec(
        dest="hostname",
        flags=("--hostname",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.HOSTS_FILE: OptionSpec(
        dest="hosts_file",
        flags=("--hosts-file",),
        metavar="HOSTS_FILE",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.COMMENT: OptionSpec(
        dest="comment",
        flags=("--comment",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # -- container options at creation OR start -----------------------------
    OptionKey.SHELL: OptionSpec(
        dest="shell",
        flags=("-s", "--shell"),
        metavar=None,
        builtin_default="zsh",
        user_config_attr="default_start_shell",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.LOG: OptionSpec(
        dest="log",
        flags=("-l", "--log", "--no-log"),
        metavar=None,
        builtin_default=False,
        user_config_attr="always_enable_shell_logging",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.LOG_METHOD: OptionSpec(
        dest="log_method",
        flags=("--log-method",),
        metavar=None,
        builtin_default="asciinema",
        user_config_attr="shell_logging_method",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `True` mirrors `UserConfig.shell_logging_compress`, which ships enabled.
    OptionKey.LOG_COMPRESS: OptionSpec(
        dest="log_compress",
        flags=("--log-compress", "--no-log-compress"),
        metavar=None,
        builtin_default=True,
        user_config_attr="shell_logging_compress",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.ENVS: OptionSpec(
        dest="envs",
        flags=("-e", "--env"),
        metavar=None,
        builtin_default=[],
        user_config_attr=None,
        merge_policy=MergePolicy.APPEND,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.CAPABILITIES: OptionSpec(
        dest="capabilities",
        flags=("--cap",),
        metavar="CAPABILITY",
        builtin_default=[],
        user_config_attr=None,
        merge_policy=MergePolicy.APPEND,
        scope=OptionScope.CREATION_OR_START,
    ),
    # -- DEST-LESS: profile-backed `~/.exegol/config.yml` settings ---------------------
    #
    # CREATION_ONLY: they shape how the container is built. They cannot be typed, so they
    # are not in CREATION_ONLY_WARNING_SURFACE.
    #
    # `builtin_default` mirrors `UserConfig.__init__` but is unreachable (UserConfig always
    # answers). Host paths use `None`: computing them would need I/O at import and duplicate
    # UserConfig's defaults.
    OptionKey.CUSTOM_IMAGES: OptionSpec(
        dest="",
        flags=(),
        metavar="image.custom_images",
        builtin_default=[],
        user_config_attr="custom_images",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.NETWORK_DEDICATED_RANGE: OptionSpec(
        dest="",
        flags=(),
        metavar="network.dedicated_range",
        builtin_default="",
        user_config_attr="network_dedicated_range",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.NETWORK_DEFAULT_NETMASK: OptionSpec(
        dest="",
        flags=(),
        metavar="network.default_netmask",
        builtin_default=28,
        user_config_attr="network_default_netmask",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.MY_RESOURCES_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="customization.my_resources_path",
        builtin_default=None,
        user_config_attr="my_resources_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.EXEGOL_RESOURCES_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="volumes.exegol_resources_path",
        builtin_default=None,
        user_config_attr="exegol_resources_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # Dotted path and UserConfig attribute names differ here.
    OptionKey.PRIVATE_WORKSPACE_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="volumes.private_workspace_path",
        builtin_default=None,
        user_config_attr="private_volume_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_GID: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.gid",
        builtin_default=-1,
        user_config_attr="sentinel_gid",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOGS_HOST_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.sentinel_logs_host_path",
        builtin_default=None,
        user_config_attr="sentinel_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOG_ROTATION_ENABLED: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_rotation.enabled",
        builtin_default=True,
        user_config_attr="sentinel_log_rotation_enabled",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # `UserConfig._DEFAULT_LOG_ROTATION_MAX_SIZE`, spelled out to avoid a UserConfig read at import.
    OptionKey.SENTINEL_LOG_ROTATION_MAX_SIZE: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_rotation.max_size",
        builtin_default="100MB",
        user_config_attr="sentinel_log_rotation_max_size",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOG_ROTATION_MAX_FILES: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_rotation.max_files",
        builtin_default=0,
        user_config_attr="sentinel_log_rotation_max_files",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOG_ROTATION_COMPRESS: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_rotation.compress",
        builtin_default=True,
        user_config_attr="sentinel_log_rotation_compress",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOG_OUTPUT_ENABLED: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_output.enabled",
        builtin_default=True,
        user_config_attr="sentinel_log_output_enabled",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # `UserConfig._DEFAULT_LOG_OUTPUT_MAX_SIZE`, spelled out to avoid a UserConfig read at import.
    OptionKey.SENTINEL_LOG_OUTPUT_MAX_SIZE: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_output.max_size",
        builtin_default="4KB",
        user_config_attr="sentinel_log_output_max_size",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_LOG_OUTPUT_TRUNCATION: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel.log_output.truncation",
        builtin_default="both",
        user_config_attr="sentinel_log_output_truncation",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # -- DEST-LESS: the inline-hosts field ---------------------------------------------
    # OVERRIDE: the value is a mapping. Merging with `network.hosts_file` happens in
    # `ContainerConfig` (inline entries win).
    OptionKey.HOSTS: OptionSpec(
        dest="",
        flags=(),
        metavar="network.hosts",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # -- DEST-LESS: profile-only interactive flags --------------------------------------
    #
    # `builtin_default=False`, not `None`: this is a boolean switch whose OFF state is
    # meaningful, and there is no tier below the profile to defer to (no flag, no
    # `config.yml` key). A declared `False` and an omitted key therefore mean the same
    # thing — do not prompt — which is exactly what the call sites test.
    #
    # Not in CREATION_ONLY_WARNING_SURFACE: that warning names options the user TYPED, and a
    # dest-less option cannot be typed.
    OptionKey.HOSTNAME_ASK_USER: OptionSpec(
        dest="",
        flags=(),
        metavar="network.hostname_ask_user",
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.COMMENT_ASK_USER: OptionSpec(
        dest="",
        flags=(),
        metavar="metadata.comment_ask_user",
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    # -- DEST-LESS: UserConfig-ONLY, profile tier permanently dead ----------------------
    #
    # `metavar` is the `config.yml` key. Scope follows the actual read sites: CREATION_OR_START
    # for settings also read outside container creation (updates, discovery, completion).
    # `builtin_default` mirrors `UserConfig.__init__`; paths use `None` as above.
    OptionKey.DESKTOP_DEFAULT_PROTO: OptionSpec(
        dest="",
        flags=(),
        metavar="desktop_default_proto",
        builtin_default="http",
        user_config_attr="desktop_default_proto",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.DESKTOP_DEFAULT_LOCALHOST: OptionSpec(
        dest="",
        flags=(),
        metavar="desktop_default_localhost",
        builtin_default=True,
        user_config_attr="desktop_default_localhost",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.EXEGOL_IMAGES_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="exegol_images_path",
        builtin_default=None,
        user_config_attr="exegol_images_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.AUTO_REMOVE_IMAGES: OptionSpec(
        dest="",
        flags=(),
        metavar="auto_remove_images",
        builtin_default=True,
        user_config_attr="auto_remove_images",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.AUTO_CHECK_UPDATES: OptionSpec(
        dest="",
        flags=(),
        metavar="auto_check_updates",
        builtin_default=True,
        user_config_attr="auto_check_updates",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.ENABLE_EXEGOL_RESOURCES: OptionSpec(
        dest="",
        flags=(),
        metavar="enable_exegol_resources",
        builtin_default=True,
        user_config_attr="enable_exegol_resources",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_ONLY,
    ),
    OptionKey.SENTINEL_PROFILE_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel_profile_path",
        builtin_default=None,
        user_config_attr="sentinel_profile_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.PROFILE_COMPONENT_PATH: OptionSpec(
        dest="",
        flags=(),
        metavar="profile_component_path",
        builtin_default=None,
        user_config_attr="profile_component_path",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # OVERRIDE: the value is a name-keyed mapping, which `_resolveList` cannot concatenate.
    OptionKey.SENTINEL_SOURCES: OptionSpec(
        dest="",
        flags=(),
        metavar="sentinel_sources",
        builtin_default={},
        user_config_attr="sentinel_sources",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # OVERRIDE: the value is a name-keyed mapping, which `_resolveList` cannot concatenate.
    OptionKey.PROFILE_SOURCES: OptionSpec(
        dest="",
        flags=(),
        metavar="profile_sources",
        builtin_default={},
        user_config_attr="profile_sources",
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # -- PROCESS CONTROL and ACTION-SPECIFIC options ------------------------------------
    #
    # - No `user_config_attr`: per-invocation options have no persistent tier.
    # - CREATION_OR_START: meaningful on every invocation, so the ignored-parameter warning
    #   never flags them on an existing container.
    # - Options with a non-null argparse default always resolve from the CLI tier; this is
    #   expected. `builtin_default` mirrors that argparse default.
    # - Positionals (`exec`, `selector`) put their name in `flags`.
    OptionKey.QUIET: OptionSpec(
        dest="quiet",
        flags=("-q", "--quiet"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `action="count"`, so the argparse default is the INTEGER zero rather than a boolean.
    OptionKey.VERBOSITY: OptionSpec(
        dest="verbosity",
        flags=("-v", "--verbose"),
        metavar=None,
        builtin_default=0,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # Same default as `--arch`; `EnvInfo.arch` comes from `platform.machine()`, no I/O.
    OptionKey.ARCH: OptionSpec(
        dest="arch",
        flags=("--arch",),
        metavar=None,
        builtin_default=EnvInfo.arch,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # Can flip at runtime: `WebRegistryUtils` sets it when a registry request fails. Tier 1
    # reads the live parameters, so later `get()` calls see the change.
    OptionKey.OFFLINE_MODE: OptionSpec(
        dest="offline_mode",
        flags=("--offline",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.ACCEPT_EULA: OptionSpec(
        dest="accept_eula",
        flags=("--accept-eula",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.SELECT_ALL: OptionSpec(
        dest="select_all",
        flags=("--all",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.FORCE_MODE: OptionSpec(
        dest="force_mode",
        flags=("-F", "--force"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.SENTINEL_REFRESH: OptionSpec(
        dest="sentinel_refresh",
        flags=("--sentinel-refresh",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.DAEMON: OptionSpec(
        dest="daemon",
        flags=("-b", "--background"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.TMP: OptionSpec(
        dest="tmp",
        flags=("--tmp",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # List-shaped but OVERRIDE: no lower tier has a command fragment to contribute.
    OptionKey.EXEC: OptionSpec(
        dest="exec",
        flags=("exec",),
        metavar="COMMAND",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.SELECTOR: OptionSpec(
        dest="selector",
        flags=("selector",),
        metavar="CONTAINER or IMAGE",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.BUILD_LOG: OptionSpec(
        dest="build_log",
        flags=("--build-log",),
        metavar="LOGFILE_PATH",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.BUILD_PATH: OptionSpec(
        dest="build_path",
        flags=("--build-path",),
        metavar="DOCKERFILES_PATH",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol update` target selectors, combinable.
    OptionKey.UPDATE_WRAPPER: OptionSpec(
        dest="update_wrapper",
        flags=("-w", "--wrapper"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.UPDATE_RESOURCES: OptionSpec(
        dest="update_resources",
        flags=("-r", "--resources"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol update --profiles`, not the excluded `profile` selector.
    OptionKey.UPDATE_PROFILE: OptionSpec(
        dest="update_profile",
        flags=("-P", "--profiles"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol update --sentinel`, not the `SENTINEL` container toggle.
    OptionKey.UPDATE_SENTINEL: OptionSpec(
        dest="update_sentinel",
        flags=("-S", "--sentinel"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.NO_BACKUP: OptionSpec(
        dest="no_backup",
        flags=("--no-backup",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol upgrade --image`, not the `exegol start` image positional.
    OptionKey.UPGRADE_IMAGE_TAG: OptionSpec(
        dest="image_tag",
        flags=("--image",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol info` section selectors; `info_` prefixed to avoid clashing with container-shape dests.
    OptionKey.INFO_CONFIG: OptionSpec(
        dest="info_config",
        flags=("-c", "--config"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.INFO_SOURCES: OptionSpec(
        dest="info_sources",
        flags=("-s", "--sources"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # `exegol info --all`, not `SELECT_ALL`.
    OptionKey.INFO_ALL: OptionSpec(
        dest="info_all",
        flags=("-a", "--all"),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.REVOKE: OptionSpec(
        dest="revoke",
        flags=("--revoke",),
        metavar=None,
        builtin_default=False,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # Credentials: the argparse default reads the environment. The builtin stays `None` so no
    # secret is frozen into this module-level table; the CLI tier already carries the env value.
    # No profile may ever supply them.
    OptionKey.API_KEY: OptionSpec(
        dest="api_key",
        flags=("--api",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    OptionKey.LICENSE_ID: OptionSpec(
        dest="license_id",
        flags=("--license-id",),
        metavar=None,
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
    # Positional, so `flags` carries the positional NAME rather than an option string.
    OptionKey.SHELL_TYPE: OptionSpec(
        dest="shell_type",
        flags=("shell_type",),
        metavar="SHELL",
        builtin_default=None,
        user_config_attr=None,
        merge_policy=MergePolicy.OVERRIDE,
        scope=OptionScope.CREATION_OR_START,
    ),
}


# ---------------------------------------------------------------------------
# Options deliberately not resolvable, each with a mandatory written reason.
#
# With _REGISTRY this must cover every CLI `dest` exactly once, which a drift test checks.
# Options that merely must not be profilable belong in _REGISTRY with a reason in
# `ProfileFieldMap.PROFILE_TIER_DEAD`. Only these stay here:
#   * `mount_current_dir` (security: would bind-mount the launch directory) and `profile`
#     (circular: it selects the profile tier). Never register them.
#   * the four positionals, which select targets rather than configure one.
# ---------------------------------------------------------------------------
RESOLVER_EXCLUDED: Dict[str, str] = {
    # -- positionals: explicit-set detection differs -------------------------
    "containertag": "Positional, not a flag: argparse gives it no `dest` kwarg and "
                    "'the user typed it' cannot be detected the same way as for an "
                    "optional. It selects WHICH container to act on, not how one is "
                    "configured.",
    "multicontainertag": "Positional target list for the multi-selector actions "
                         "(stop / remove / upgrade). It names WHICH containers to act "
                         "on, not how one is configured.",
    "multiimagetag": "Positional target list for the image multi-selector actions "
                     "(uninstall). Selects targets rather than configuring one.",
    "build_profile": "Positional naming the local build profile for `exegol build`. It "
                     "selects a Dockerfile stage, not a container-shape default.",
    # -- security boundary: never registered, under any refactor --------------
    "mount_current_dir": "Already neutral — `default=None`, so there is nothing left to "
                         "convert. It is excluded rather than registered "
                         "because `-cwd` / `--cwd-mount` expands to the process working "
                         "directory: per-invocation state, not a container-shape default. "
                         "A shareable profile able to set it would bind-mount whichever "
                         "host directory exegol happened to be launched from — a home, a "
                         "credentials tree, an unrelated engagement — into the container, "
                         "read-write, without the operator ever naming it. The null "
                         "default must stay: the ignored-parameter warning reads this dest "
                         "through its non-registered branch, where 'the user typed it' "
                         "means simply non-null.",
    # -- process control, not container shape --------------------------------
    "profile": "Selector, not a value: `--profile` names WHICH container profile supplies "
               "the profile tier, so it can never itself be resolved THROUGH that tier — "
               "a profile able to set it would choose which profile is read, which is "
               "circular. Structural, not a preference; the same selector role `-S` plays "
               "for Sentinel. One entry covers both `exegol info --profile` and the "
               "`exegol start --profile` flag, because this table is keyed by dest and "
               "both actions declare the same one.",
}


# ---------------------------------------------------------------------------
# The creation-only warning surface.
#
# Options `ExegolManager.__checkUselessParameters()` warns about when typed for an existing
# container, in argparse declaration order. `(OptionKey, None)` takes the registry's
# display name; `(dest, name)` is an excluded dest (`containertag`, `mount_current_dir`)
# read directly with its own display name.
#
# Declared so production never rebuilds the Command classes; a drift test checks it against
# the live command.
# ---------------------------------------------------------------------------
CREATION_ONLY_WARNING_SURFACE: Tuple[Tuple[Union[OptionKey, str], Optional[str]], ...] = (
    ("containertag", "CONTAINER"),
    (OptionKey.IMAGE_TAG, None),
    (OptionKey.GUI, None),
    (OptionKey.MY_RESOURCES, None),
    (OptionKey.EXEGOL_RESOURCES, None),
    (OptionKey.NETWORK, None),
    (OptionKey.SHARE_TIMEZONE, None),
    ("mount_current_dir", "-cwd / --cwd-mount"),
    (OptionKey.WORKSPACE_PATH, None),
    (OptionKey.UPDATE_FS_PERMS, None),
    (OptionKey.VOLUMES, None),
    (OptionKey.PORTS, None),
    (OptionKey.HOSTNAME, None),
    (OptionKey.PRIVILEGED, None),
    (OptionKey.DEVICES, None),
    (OptionKey.HOSTS_FILE, None),
    (OptionKey.COMMENT, None),
    (OptionKey.SENTINEL, None),
    (OptionKey.SENTINEL_PROFILE, None),
    (OptionKey.SENTINEL_STRATEGY, None),
    (OptionKey.VPN, None),
    (OptionKey.VPN_AUTH, None),
    (OptionKey.DESKTOP, None),
    (OptionKey.DESKTOP_CONFIG, None),
)


class OptionResolver(metaclass=MetaSingleton):
    """Resolves any registered option through the CLI > profile > UserConfig > builtin chain."""

    def __init__(self) -> None:
        # Must not touch another MetaSingleton: this runs at parser-build time.
        self.__profile: Optional[Mapping[str, Any]] = None
        self.__profile_user_config: Optional[Mapping[str, Any]] = None

    # -- tiers --------------------------------------------------------------

    def __cliValue(self, dest: str) -> Any:
        """Tier 1: what the user typed, or ``None``.

        The import is function-local so help-string construction cannot reach this tier.
        """
        from exegol.console.cli.ParametersManager import ParametersManager
        return getattr(ParametersManager(), dest)

    # -- public API ---------------------------------------------------------

    def resolve(self, name: OptionKey) -> Resolved:
        """Effective value of ``name`` plus the tier that supplied it.

        Raises ``KeyError`` for an unregistered name (a developer error).
        """
        spec = _REGISTRY[name]
        if spec.merge_policy is MergePolicy.APPEND:
            return self._resolveList(name, spec)

        cli = self.__cliValue(spec.dest)
        if cli is not None:
            return Resolved(cli, OptionSource.CLI)
        # Key presence, not non-None: a profile may declare `network: null`.
        if self.__profile is not None and name in self.__profile:
            return Resolved(self.__profile[name], OptionSource.PROFILE)
        # Key presence again. Same source as above: both mappings come from the profile file.
        if self.__profile_user_config is not None and name in self.__profile_user_config:
            return Resolved(self.__profile_user_config[name], OptionSource.PROFILE)
        if spec.user_config_attr is not None:
            user_value = getattr(UserConfig(), spec.user_config_attr, None)
            if user_value is not None:
                return Resolved(user_value, OptionSource.USER_CONFIG)
        return Resolved(spec.builtin_default, OptionSource.BUILTIN)

    def _resolveList(self, name: OptionKey, spec: OptionSpec, include_profile: bool = True) -> Resolved:
        """Additive option: every tier contributes, the CLI appends last.

        CLI last matters because Docker keeps the last duplicate volume/port target.
        ``include_profile=False`` drops both profile tiers (for :meth:`resolveWithoutProfile`).
        The profile tiers are keyed by ``name``, not ``spec.dest``. The reported source is the
        highest contributing tier only.
        """
        parts: List[Any] = []
        sources: List[OptionSource] = []

        base = spec.builtin_default or []
        if base:
            parts.extend(base)
            sources.append(OptionSource.BUILTIN)
        if spec.user_config_attr is not None:
            # Unused today: no list-valued UserConfig attribute is registered.
            user_value = getattr(UserConfig(), spec.user_config_attr, None)
            if user_value:
                parts.extend(user_value)
                sources.append(OptionSource.USER_CONFIG)
        if include_profile and self.__profile is not None and name in self.__profile:
            # Shape check only: `extend` on a string would add one entry per character.
            contribution = self.__profile[name]
            if contribution is None:
                contribution = []
            elif isinstance(contribution, (str, bytes)) or not isinstance(contribution, (list, tuple)):
                raise TypeError(f"Profile value for additive option '{name}' must be a list, "
                                f"got {type(contribution).__name__}")
            parts.extend(contribution)
            sources.append(OptionSource.PROFILE)
        if include_profile and self.__profile_user_config is not None and name in self.__profile_user_config:
            # Same shape check. Also profile-supplied, hence gated on `include_profile`.
            contribution = self.__profile_user_config[name]
            if contribution is None:
                contribution = []
            elif isinstance(contribution, (str, bytes)) or not isinstance(contribution, (list, tuple)):
                raise TypeError(f"Profile value for additive option '{name}' must be a list, "
                                f"got {type(contribution).__name__}")
            parts.extend(contribution)
            sources.append(OptionSource.PROFILE)
        cli = self.__cliValue(spec.dest)
        if cli is not None:
            parts.extend(cli)
            sources.append(OptionSource.CLI)

        return Resolved(parts, sources[-1] if sources else OptionSource.BUILTIN)

    def defaultFor(self, name: OptionKey) -> Any:
        """Effective default of ``name`` (profile > UserConfig > builtin), for ``--help`` and completers.

        Never reads the CLI tier: help strings and completers run while ``ParametersManager``
        is being constructed, and touching it there raises. In practice no profile is loaded
        yet at that point, so help shows the ``config.yml`` or builtin default.

        Raises ``KeyError`` for an unregistered name.
        """
        spec = _REGISTRY[name]
        # Key presence, same order as resolve().
        if self.__profile is not None and name in self.__profile:
            return self.__profile[name]
        if self.__profile_user_config is not None and name in self.__profile_user_config:
            return self.__profile_user_config[name]
        if spec.user_config_attr is not None:
            user_value = getattr(UserConfig(), spec.user_config_attr, None)
            if user_value is not None:
                return user_value
        # Copy lists: the frozen dataclass does not protect the registry's list from mutation.
        default = spec.builtin_default
        return list(default) if isinstance(default, list) else default

    def get(self, name: OptionKey) -> Any:
        """Effective value of ``name``, without provenance."""
        return self.resolve(name).value

    def cliValue(self, name: OptionKey) -> Any:
        """Tier 1 only: what the user typed, for sites asking "what was requested but cannot be honoured?".

        Additive options return ``[]`` instead of ``None``. Raises ``KeyError`` for an unregistered name.
        """
        spec = _REGISTRY[name]
        cli = self.__cliValue(spec.dest)
        if spec.merge_policy is MergePolicy.APPEND:
            return list(cli) if cli else []
        return cli

    def userConfigValue(self, name: OptionKey) -> Any:
        """Tier 3 only: what ``~/.exegol/config.yml`` says, or ``None`` if it has no say.

        For advisory messages and logging only (e.g. "set X in your config"); container
        shaping goes through :meth:`get`. Raises ``KeyError`` for an unregistered name.
        """
        spec = _REGISTRY[name]
        if spec.user_config_attr is None:
            return None
        return getattr(UserConfig(), spec.user_config_attr, None)

    def resolveWithoutProfile(self, name: OptionKey) -> Resolved:
        """The chain without the profile tiers: CLI, then ``UserConfig``, then builtin.

        Building block of :meth:`resolveOmittingBlankProfile`; direct calls are for
        advisory use only. Raises ``KeyError`` for an unregistered name.
        """
        spec = _REGISTRY[name]
        if spec.merge_policy is MergePolicy.APPEND:
            return self._resolveList(name, spec, include_profile=False)

        cli = self.__cliValue(spec.dest)
        if cli is not None:
            return Resolved(cli, OptionSource.CLI)
        if spec.user_config_attr is not None:
            user_value = self.userConfigValue(name)
            if user_value is not None:
                return Resolved(user_value, OptionSource.USER_CONFIG)
        return Resolved(spec.builtin_default, OptionSource.BUILTIN)

    def resolveOmittingBlankProfile(self, name: OptionKey, blank: Tuple[Any, ...] = (None,)) -> Resolved:
        """Like :meth:`resolve`, but a profile value in ``blank`` counts as an omitted key.

        A YAML null is a present key, so on nullable fields it would otherwise shadow the
        lower tiers. ``blank`` is chosen per call site: ``sentinel.enabled`` uses ``(None,)``
        (a profile ``False`` is a real off-switch), ``sentinel.profile`` uses ``(None, "")``.
        Matching is exact membership, no stripping or truthiness.

        On ``APPEND`` options a null becomes ``[]``, so this is a plain :meth:`resolve`.
        Raises ``KeyError`` for an unregistered name.
        """
        resolved = self.resolve(name)
        if resolved.source is OptionSource.PROFILE and resolved.value in blank:
            return self.resolveWithoutProfile(name)
        return resolved

    def registryForScope(self, scope: OptionScope) -> List[OptionSpec]:
        """Registered specs with this ``scope``, in declaration order. Reads no tier.

        Excluded options are not listed; ``CREATION_ONLY_WARNING_SURFACE`` is the complete
        creation-only set.
        """
        return [spec for spec in _REGISTRY.values() if spec.scope is scope]

    def isExplicit(self, name: OptionKey) -> bool:
        """True only when the CLI tier supplied (or, for a list, contributed to) the value."""
        return self.resolve(name).source is OptionSource.CLI

    def isExplicitOrProfile(self, name: OptionKey) -> bool:
        """True when the CLI or the selected profile supplied the value (deliberate choices).

        Used by ``ContainerConfig.enableVPN()`` to honour a profile's ``network: host``.
        ``__checkUselessParameters()`` must keep using :meth:`isExplicit`, or every resume
        with a profile would warn. Raises ``KeyError`` for an unregistered name.
        """
        return self.resolve(name).source in (OptionSource.CLI, OptionSource.PROFILE)

    def _injectProfile(self, profile: Optional[Mapping[str, Any]]) -> None:
        """Install the profile tier (test-facing injector).

        Keys are ``str``: ``OptionKey`` members hash as their value, and tests install
        non-member keys on purpose. ``Mapping`` is invariant in its key, hence the casts at
        call sites.
        """
        self.__profile = profile

    def loadProfile(self, profile: Optional[Mapping[str, Any]]) -> None:
        """Install the profile tier (public entry point)."""
        self._injectProfile(profile)

    def _injectProfileUserConfig(self, profile_user_config: Optional[Mapping[str, Any]]) -> None:
        """Install the profile-supplied ``UserConfig``-settings tier. Test-facing injector."""
        self.__profile_user_config = profile_user_config

    def loadProfileUserConfig(self, profile_user_config: Optional[Mapping[str, Any]]) -> None:
        """Install the profile's ``PROFILE_USER_CONFIG_MAP`` settings, keyed by :class:`OptionKey` (public entry point).

        Stays installed for the lifetime of the process.
        """
        self._injectProfileUserConfig(profile_user_config)
