import errno
import json
import logging
import os
import random
import re
import shlex
import shutil
import socket
import stat
import string
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePath
from typing import Optional, List, Dict, Union, Tuple, cast

from docker.models.containers import Container
from docker.types import Mount

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver, OptionSource
from exegol.config.UserConfig import UserConfig
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.config.StaticContainerPath import StaticContainerPath, StaticFileName
from exegol.console.ConsoleFormat import boolFormatter, getColor
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.console.cli.SyntaxFormat import SyntaxFormat
from exegol.exceptions.ExegolExceptions import ProtocolNotSupported, CancelOperation, InteractiveError
from exegol.model.ExegolModules import ExegolModules
from exegol.model.ExegolNetwork import ExegolNetwork, ExegolNetworkMode, DockerDrivers
from exegol.model.LicensesTypes import LicenseFeature
from exegol.profile.ProfileAskUser import ask_user_for_value
from exegol.sentinel.SentinelProfileManager import SentinelProfileManager
from exegol.utils import FsUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.FsUtils import SCRATCH_SUFFIX, check_sysctl_value, mkdir, scratch_prefix, sweep_stale_scratch
from exegol.utils.GuiUtils import GuiUtils
from exegol.utils.SessionHandler import SessionHandler


class ContainerConfig:
    """Configuration class of an exegol container"""

    # Default hardcoded value
    __default_entrypoint = ["/bin/bash", StaticContainerPath.EXEGOL_ENTRYPOINT.value]
    __default_shm_size = "64M"
    # resolver-exempt: import-time class-body read, before any profile exists; the fallback is host policy, absent from the profile schema.
    __fallback_network_mode = ExegolNetworkMode[UserConfig().network_fallback_mode.lower()]

    # Reference static config data
    __static_gui_envs = {"_JAVA_AWT_WM_NONREPARENTING": "1", "QT_X11_NO_MITSHM": "1"}
    __default_desktop_port = {"http": 6080, "vnc": 5900}

    # Verbose only filters
    __verbose_only_envs = ["DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_RUNTIME_DIR", "PATH", "TZ", "_JAVA_OPTIONS"]
    __verbose_only_mounts = ['/tmp/.X11-unix',
                             StaticContainerPath.EXEGOL_RESOURCES.value,
                             '/etc/localtime',
                             '/etc/timezone',
                             '/my-resources',
                             StaticContainerPath.MY_RESOURCES.value,
                             StaticContainerPath.EXEGOL_ENTRYPOINT.value,
                             StaticContainerPath.EXEGOL_SPAWN.value,
                             '/tmp/wayland-0',
                             '/tmp/wayland-1',
                             StaticContainerPath.SENTINEL_ZSH_HOOKS.value,
                             StaticContainerPath.SENTINEL_BASH_HOOKS.value,
                             StaticContainerPath.SENTINEL_LOGGER.value,
                             StaticContainerPath.SENTINEL_DIRECTORY.value
                             ]

    # Whitelist device for Docker Desktop
    __whitelist_dd_devices = ["/dev/net/tun", "/dev/fuse"]

    class ExegolFeatures(Enum):
        shell_logging = "org.exegol.feature.shell_logging"
        desktop = "org.exegol.feature.desktop"

        @classmethod
        def values(cls):
            return list(map(lambda c: c.value, cls))

    class ExegolMetadata(Enum):
        creation_date = "org.exegol.metadata.creation_date"
        comment = "org.exegol.metadata.comment"
        password = "org.exegol.metadata.passwd"
        backups = "org.exegol.metadata.backups"
        sentinel = "org.exegol.metadata.sentinel"
        sentinel_strategy = "org.exegol.metadata.sentinel.strategy"

        @classmethod
        def values(cls):
            return list(map(lambda c: c.value, cls))

    class ExegolEnv(Enum):
        # feature
        exegol_name = "EXEGOL_NAME"  # Supply the name of the container to itself when overriding the hostname
        randomize_service_port = "EXEGOL_RANDOMIZE_SERVICE_PORTS"  # Enable the randomize port feature when using exegol is network host mode
        # config
        user_shell = "EXEGOL_START_SHELL"
        exegol_user = "EXEGOL_USERNAME"
        shell_logging_method = "EXEGOL_START_SHELL_LOGGING"  # Enable and select the shell logging method
        shell_logging_compress = "EXEGOL_START_SHELL_COMPRESS"  # Configure if the logs must be compressed at the end of the shell
        desktop_protocol = "EXEGOL_DESKTOP_PROTO"  # Configure which desktop module must be started
        desktop_host = "EXEGOL_DESKTOP_HOST"  # Select the host / ip to expose the desktop service on (container side)
        desktop_port = "EXEGOL_DESKTOP_PORT"  # Select the port to expose the desktop service on (container side)

    # Label features (label name / wrapper method to enable the feature)
    __label_features = {ExegolFeatures.shell_logging.value: "enableShellLogging",
                        ExegolFeatures.desktop.value: "configureDesktop"}
    # Label metadata (label name / [setter method to set the value, getter method to update labels])
    __label_metadata = {ExegolMetadata.creation_date.value: ["setCreationDate", "getCreationDate"],
                        ExegolMetadata.comment.value: ["setComment", "getComment"],
                        ExegolMetadata.password.value: ["setPasswd", "getPasswd"],
                        ExegolMetadata.backups.value: ["setBackupHistory", "getBackupHistory"],
                        ExegolMetadata.sentinel.value: ["setSentinelProfile", "getSentinelProfile"],
                        ExegolMetadata.sentinel_strategy.value: ["setSentinelStrategy", "getSentinelStrategy"]
                        }

    def __init__(self, container: Optional[Container] = None, container_name: Optional[str] = None, hostname: Optional[str] = None):
        """Container config default value"""
        if container_name is None:
            self.container_name: str = ""
        elif container_name.startswith("exegol-"):
            self.container_name = container_name
        else:
            self.container_name = f'exegol-{container_name}'
        self.__enable_gui: bool = False
        self.__gui_engine: List[str] = []
        self.__share_timezone: bool = False
        self.__my_resources: bool = False
        self.__my_resources_path: str = StaticContainerPath.MY_RESOURCES.value
        self.__exegol_resources: bool = False
        self.__networks: List[ExegolNetwork] = []
        self.__privileged: bool = False
        self.__wrapper_start_enabled: bool = False
        self.__mounts: List[Mount] = []
        self.__devices: List[str] = []
        self.__capabilities: List[str] = []
        self.__sysctls: Dict[str, str] = {}
        self.__envs: Dict[str, str] = {}
        self.__labels: Dict[str, str] = {}
        self.__ports: Dict[str, Optional[Union[int, Tuple[str, int], List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]]]]] = {}
        self.__extra_host: Dict[str, str] = {}
        self.interactive: bool = False
        self.tty: bool = False
        self.shm_size: str = self.__default_shm_size
        self.__workspace_custom_path: Optional[str] = None
        self.__workspace_dedicated_path: Optional[str] = None
        self.__disable_workspace: bool = False
        self.__container_entrypoint: List[str] = self.__default_entrypoint
        self.__vpn_path: Optional[Path] = None
        self.__shell_logging: bool = False
        self.__sentinel_path: Optional[Path] = None
        self.__sentinel_profile: Optional[str] = None
        self.__sentinel_strategy: Optional[str] = None
        # Entrypoint features
        self.legacy_entrypoint: bool = True
        self.__vpn_mode: Optional[str] = None
        self.__vpn_parameters: Optional[str] = None
        self.__run_cmd: bool = False
        self.__endless_container: bool = True
        self.__desktop_proto: Optional[str] = None
        self.__desktop_host: Optional[str] = None
        self.__desktop_port: Optional[int] = None
        # Metadata attributes
        self.__creation_date: Optional[str] = None
        self.__backup_history: Optional[str] = None
        self.__comment: Optional[str] = None
        self.__username: str = "root"
        self.__passwd: Optional[str] = self.generateRandomPassword()
        if hostname is not None:
            self.hostname = hostname
            if container is None:  # if this is a new container
                self.addEnv(ContainerConfig.ExegolEnv.exegol_name.value, self.container_name)
        else:
            self.hostname = self.container_name

        if container is not None:
            self.__parseContainerConfig(container)
        else:
            self.__wrapper_start_enabled = True
            self.addVolume(str(ConstantConfig.spawn_context_path_obj), StaticContainerPath.EXEGOL_SPAWN.value, read_only=True, must_exist=True)
            # After __init__, await self.configFromUser() should be called

    # ===== Config parsing section =====

    def __parseContainerConfig(self, container: Container) -> None:
        """Parse Docker object to setup self configuration"""
        # Reset default attributes
        self.__passwd = None
        self.__share_timezone = False
        self.__my_resources = False
        self.__enable_gui = False
        # Container Config section
        self.container_name = container.name
        container_config = container.attrs.get("Config", {})
        self.hostname = container_config.get('Hostname', self.container_name)
        self.tty = container_config.get("Tty", True)
        self.__parseEnvs(container_config.get("Env", []))
        self.__parseLabels(container_config.get("Labels", {}))
        self.interactive = container_config.get("OpenStdin", True)
        self.legacy_entrypoint = container_config.get("Entrypoint") is None

        # Host Config section
        host_config = container.attrs.get("HostConfig", {})
        self.__privileged = host_config.get("Privileged", False)
        caps = host_config.get("CapAdd", [])
        if caps is not None:
            self.__capabilities = caps
        logger.debug(f"└── Capabilities : {self.__capabilities}")
        self.__sysctls = host_config.get("Sysctls", {})
        devices = host_config.get("Devices", [])
        if devices is not None:
            for device in devices:
                self.__devices.append(
                    f"{device.get('PathOnHost', '?')}:{device.get('PathInContainer', '?')}:{device.get('CgroupPermissions', '?')}")
        logger.debug(f"└── Load devices : {self.__devices}")
        extra_hosts = host_config.get("ExtraHosts", [])
        for entry in extra_hosts:
            hostname, ip = entry.rsplit(":", 1)
            self.setExtraHost(hostname, ip)

        # Volumes section
        container_name = container.name[7:] if container.name.startswith("exegol-") else container.name
        self.__parseMounts(container.attrs.get("Mounts", []), container_name)

        # Network section
        network_settings = container.attrs.get("NetworkSettings", {})
        self.__networks = ExegolNetwork.parse_networks(network_settings["Networks"], container_name=self.container_name)
        self.__ports = network_settings.get("Ports", {})

    def __parseEnvs(self, envs: List[str]) -> None:
        """Parse envs object syntax"""
        for env in envs:
            logger.debug(f"└── Parsing envs : {env}")
            # Removing " and ' at the beginning and the end of the string before splitting key / value
            self.addRawEnv(env.strip("'").strip('"'))
        envs_key = self.__envs.keys()
        if "DISPLAY" in envs_key:
            self.__enable_gui = True
            self.__gui_engine.append("X11")
        if "WAYLAND_DISPLAY" in envs_key:
            self.__enable_gui = True
            self.__gui_engine.append("Wayland")
        if "TZ" in envs_key:
            self.__share_timezone = True

    def __parseLabels(self, labels: Dict[str, str]) -> None:
        """Parse envs object syntax"""
        for key, value in labels.items():
            if not key.startswith("org.exegol."):
                continue
            logger.debug(f"└── Parsing label : {key}")
            if key in self.ExegolMetadata.values():
                # Find corresponding feature and attributes
                refs = self.__label_metadata.get(key)  # Setter
                if refs is not None:
                    # reflective execution of setter method (set metadata value to the corresponding attribute)
                    getattr(self, refs[0])(value)
            elif key in self.ExegolFeatures.values():
                self.addLabel(key, value)
                # Find corresponding feature and function
                enable_function = self.__label_features.get(key)
                if enable_function is not None:
                    # reflective execution of the feature enable method (add label & set attributes)
                    if value == "Enabled":
                        value = ""
                    getattr(self, enable_function)(value)

    def __parseMounts(self, mounts: Optional[List[Dict]], name: str) -> None:
        """Parse Mounts object"""
        if mounts is None:
            mounts = []
        self.__disable_workspace = True
        ovpn_parameters = []
        for share in mounts:
            logger.debug(f"└── Parsing mount : {share}")
            src_path: Optional[PurePath] = None
            obj_path: PurePath
            if share.get('Type', 'volume') == "volume":
                source = f"Docker {share.get('Driver', '')} volume '{share.get('Name', 'unknown')}'"
            else:
                source = share.get("Source", '')
                src_path = FsUtils.parseDockerVolumePath(source)

                # When debug is disabled, exegol print resolved windows path of mounts
                if logger.getEffectiveLevel() > ExeLog.ADVANCED:
                    source = str(src_path)

            self.__mounts.append(Mount(source=source,
                                       target=share.get('Destination'),
                                       type=share.get('Type', 'volume'),
                                       read_only=(not share.get("RW", True)),
                                       propagation=share.get('Propagation', '')))

            destination = share.get('Destination', '')
            if destination in ["/etc/timezone", "/etc/localtime"]:
                self.__share_timezone = True
            elif StaticContainerPath.EXEGOL_RESOURCES.value in destination:
                self.__exegol_resources = True
            elif StaticContainerPath.MY_RESOURCES.value in destination:
                self.__my_resources = True
                self.__my_resources_path = destination
            elif "/workspace" in destination:
                # Workspace are always bind mount
                assert src_path is not None
                logger.debug(f"└── Loading workspace volume source : {src_path}")
                self.__disable_workspace = False
                # TODO use label to identify manage workspace and support cross env removing
                if src_path is not None and src_path.name == name and \
                        (src_path.parent.name == "shared-data-volumes" or src_path.parent == OptionResolver().get(OptionKey.PRIVATE_WORKSPACE_PATH)):  # Check legacy path and new custom path
                    logger.debug("└── Private workspace detected")
                    self.__workspace_dedicated_path = str(src_path)
                else:
                    logger.debug("└── Custom workspace detected")
                    self.__workspace_custom_path = str(src_path)
            elif "/.exegol/vpn" in destination or destination.startswith("/etc/wireguard/"):
                # VPN are always bind mount
                assert src_path is not None
                self.__vpn_path = Path(src_path)
                if self.__vpn_path.suffix == ".ovpn":
                    self.__vpn_mode = "ovpn"
                    ovpn_parameters.append(f"--config {destination}")
                elif self.__vpn_path.suffix == ".conf":
                    self.__vpn_mode = "wgconf"
                    self.__vpn_parameters = Path(destination).name[:-5]
                logger.debug(f"└── Loading VPN config: {self.__vpn_path.name}")
            elif destination == StaticContainerPath.OPENVPN_CREDS_FILE.value:
                ovpn_parameters.append(f"--auth-user-pass " + StaticContainerPath.OPENVPN_CREDS_FILE.value)
            elif destination == StaticContainerPath.EXEGOL_SPAWN.value:
                self.__wrapper_start_enabled = True
            elif destination == StaticContainerPath.SENTINEL_DIRECTORY.value:
                # Sentinel logs are always bind mount
                assert src_path is not None
                self.__sentinel_path = Path(src_path)
        if len(ovpn_parameters) > 0:
            self.__vpn_parameters = ' '.join(ovpn_parameters)

    # ===== Config init section =====

    async def configFromUser(self) -> "ContainerConfig":
        """Create Exegol configuration from user input"""
        # Container configuration from user CLI options
        try:
            # Container configuration from user CLI options
            if OptionResolver().get(OptionKey.GUI):
                await self.enableGUI()
            if OptionResolver().get(OptionKey.SHARE_TIMEZONE):
                self.enableSharedTimezone()
            await self.setNetworkMode(OptionResolver().get(OptionKey.NETWORK))
            for port in OptionResolver().get(OptionKey.PORTS):
                await self.addRawPort(port)
            if OptionResolver().get(OptionKey.MY_RESOURCES):
                self.enableMyResources()
            if OptionResolver().get(OptionKey.EXEGOL_RESOURCES):
                await self.enableExegolResources()
            if OptionResolver().get(OptionKey.LOG):
                # Resolved once each: resolve() is not memoised, and method and compression
                # describe a single logging session.
                log_method = OptionResolver().get(OptionKey.LOG_METHOD)
                log_compress = OptionResolver().get(OptionKey.LOG_COMPRESS)
                self.enableShellLogging(log_method, log_compress)
            # `-S` decides whether Sentinel is on; `-SP` names the audit profile (read in
            # enableSentinel()). Not plain get(): a profile's `sentinel.enabled: null` must
            # fall through to `sentinel_enabled_by_default` rather than disable audit logging.
            # Keep the default blank set `(None,)`: a profile `False` is a real off-switch.
            sentinel_resolved = OptionResolver().resolveOmittingBlankProfile(OptionKey.SENTINEL)
            sentinel_enabled = sentinel_resolved.value
            # Naming an audit profile (CLI or profile file) without saying "enable" enables.
            # `Resolved.stated` reads a written null as omitted and ignores config.yml's
            # `sentinel_default_profile`, which would otherwise enable Sentinel everywhere.
            # A typed `-SP ""` still enables. Each option is resolved once, below.
            sentinel_profile_resolved = OptionResolver().resolve(OptionKey.SENTINEL_PROFILE)
            profile_named = bool(sentinel_profile_resolved.stated
                                 and sentinel_profile_resolved.value)
            named_on_cli = sentinel_profile_resolved.source is OptionSource.CLI
            stated_on_cli = sentinel_resolved.source is OptionSource.CLI
            sentinel_stated = sentinel_resolved.stated
            if (named_on_cli and not stated_on_cli) or (profile_named and not sentinel_stated):
                sentinel_enabled = True
            if named_on_cli and stated_on_cli and not sentinel_enabled:
                # The command line contradicts itself: the explicit disable wins, with a
                # warning naming the flags (never the typed value, which could break markup).
                # A self-contradicting profile stays silent: its author may not be the operator.
                logger.warning("Sentinel is disabled by [green]--no-sentinel[/green], so the audit profile named "
                               "with [green]-SP[/green] / [green]--sentinel-profile[/green] is not applied.")
            if sentinel_enabled:
                self.enableSentinel()
            # Tier 1 only: `mount_current_dir` is RESOLVER_EXCLUDED, since
            # a shareable profile able to set it would mount a host directory the operator
            # never named. A resolver read of an excluded name is a KeyError by design.
            # resolver-exempt: security boundary, `mount_current_dir` is RESOLVER_EXCLUDED so no shareable profile can bind-mount the process working directory.
            mount_cwd = ParametersManager().mount_current_dir
            # One observation shared by the conflict warning and the share.
            workspace_path = OptionResolver().get(OptionKey.WORKSPACE_PATH)
            if workspace_path:
                if mount_cwd:
                    logger.warning(f'Workspace conflict detected (-cwd cannot be use with -w). Using: {workspace_path}')
                self.setWorkspaceShare(workspace_path)
            elif mount_cwd:
                self.enableCwdShare()
            if OptionResolver().get(OptionKey.PRIVILEGED):
                self.setPrivileged()
            else:
                for cap in OptionResolver().get(OptionKey.CAPABILITIES):
                    self.addCapability(cap)
            for volume in OptionResolver().get(OptionKey.VOLUMES):
                await self.addRawVolume(volume)
            for device in OptionResolver().get(OptionKey.DEVICES):
                self.addUserDevice(device)
            # `is not None`, not truthiness: an empty string requests VPN capabilities
            # without a connection, which enableVPN() handles.
            vpn_config = OptionResolver().get(OptionKey.VPN)
            if vpn_config is not None:
                await self.enableVPN(vpn_config, auth_path=OptionResolver().get(OptionKey.VPN_AUTH))
            for env in OptionResolver().get(OptionKey.ENVS):
                self.addRawEnv(env)
            # On/off and its configuration are one choice, resolved together.
            desktop_enabled = OptionResolver().get(OptionKey.DESKTOP)
            desktop_config = OptionResolver().get(OptionKey.DESKTOP_CONFIG)
            if desktop_enabled:
                await self.enableDesktop(desktop_config)
            # `metadata.comment_ask_user` turns this into a prompt offering the profile's own
            # `metadata.comment` as the default. No fallback default: an unanswered comment is
            # legitimately absent, and the `if` below keeps an empty answer meaning "no comment".
            comment = await ask_user_for_value(OptionKey.COMMENT_ASK_USER,
                                               OptionKey.COMMENT,
                                               "Enter the container comment")
            if comment:
                self.addComment(comment)
            hosts_file = OptionResolver().get(OptionKey.HOSTS_FILE)
            if hosts_file:
                self.loadHostsFile(hosts_file)
            # Must stay below loadHostsFile(): setExtraHost() is last-write-wins, so inline
            # `network.hosts` entries override hosts-file entries.
            inline_hosts = OptionResolver().get(OptionKey.HOSTS)
            # Truthiness is enough: HOSTS has no lower tier, so omitted and null both mean "add nothing".
            if inline_hosts:
                # Shape check, not validation: loadProfile() accepts any mapping, so get()
                # may return a non-dict.
                if not isinstance(inline_hosts, dict):
                    raise TypeError(f"Profile value for '{OptionKey.HOSTS}' must be a mapping, "
                                    f"got {type(inline_hosts).__name__}")
                for hostname, ip in inline_hosts.items():
                    self.setExtraHost(hostname, ip)
        except InteractiveError:
            logger.critical(f"Aborting new container creation.")
            raise
        except CancelOperation as e:
            logger.critical(f"Unable to create a new container: {e}")
            raise e
        return self

    async def interactiveConfig(self, container_name: str, profile_name: Optional[str]) -> List[str]:
        """Interactive procedure allowing the user to configure its new container.

        ``profile_name`` is the RESOLVED name of the applied container profile (never the
        raw ``--profile`` value), or ``None``. Required so no caller can forget it.
        """
        logger.info("Starting interactive configuration")

        command_options = []

        # Command builder info. The profile comes first: it is the basis every other flag
        # overrides, and it reproduces profile values that have no recap flag.
        # Quoted because a profile name is a filename. Markup escaping happens at render
        # time, so `command_options` stays `shlex.split`-able.
        if profile_name:
            command_options.append(f"--profile {shlex.quote(profile_name)}")

        # Workspace config
        if await ExegolRich.Confirm(
                "Do you want to [green]share[/green] your [blue]current host working directory[/blue] in the new container's workspace?",
                default=False):
            self.enableCwdShare()
            command_options.append("-cwd")
        elif await ExegolRich.Confirm(
                f"Do you want to [green]share[/green] a [blue]host directory[/blue] in the new container's workspace [blue]different than the default one[/blue] ([magenta]{OptionResolver().get(OptionKey.PRIVATE_WORKSPACE_PATH) / container_name}[/magenta])?",
                default=False):
            while True:
                workspace_path = await ExegolRich.Ask("Enter the path of your workspace")
                if EnvInfo.expand_user(workspace_path).is_dir():
                    break
                else:
                    logger.error("The provided path is not a folder or does not exist.")
            self.setWorkspaceShare(workspace_path)
            command_options.append(f"-w {workspace_path}")

        # Network config
        if self.isNetworkHost():
            if await ExegolRich.Confirm(f"Do you want to [green]use[/green] a [blue]{'dedicated ' if self.__fallback_network_mode is ExegolNetworkMode.nat else ''}private network[/blue]?", False):
                await self.setNetworkMode(self.__fallback_network_mode)
        elif await ExegolRich.Confirm("Do you want to share the [green]host's[/green] [blue]networks[/blue]?", False):
            await self.setNetworkMode(ExegolNetworkMode.host)
        # Command builder info. `--network` is emitted only when the mode differs from what
        # a replay would resolve (host included); a missing default never matches, so the
        # flag is redundant rather than missing.
        # Known limitation: a profile naming a Docker network yields `--network attached`,
        # which does not parse.
        network_mode_name = (self.__networks[0].getNetworkMode().name if len(self.__networks) > 0
                             else ExegolNetworkMode.disabled.name)
        if network_mode_name != OptionResolver().defaultFor(OptionKey.NETWORK):
            command_options.append(f"--network {network_mode_name}")

        # VPN config
        if self.__vpn_path is None and await ExegolRich.Confirm(
                "Do you want to [green]enable[/green] a [blue]VPN[/blue] in this container", False):
            while True:
                vpn_path = EnvInfo.expand_user(await ExegolRich.Ask('Enter the [green]path[/green] to the [blue]VPN config file[/blue]'))
                if vpn_path.is_file():
                    try:
                        await self.enableVPN(vpn_path)
                        break
                    except InteractiveError:
                        pass
                else:
                    logger.error("No config files were found.")
        elif self.__vpn_path and await ExegolRich.Confirm(
                "Do you want to [orange3]remove[/orange3] your [blue]VPN configuration[/blue] in this container", False):
            self.__disableVPN()
        if self.__vpn_path:
            command_options.append(f"--vpn {self.__vpn_path}")

        # Desktop Config
        if self.isDesktopEnabled():
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]Desktop[/blue]?", False):
                self.__disableDesktop()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] [blue]Desktop[/blue]?", False):
            await self.enableDesktop()
        # Command builder info. Rule for every boolean recap flag below: emit `--x` or `--no-x`
        # only when the value differs from `defaultFor()` (profile > config.yml > builtin), i.e.
        # from what a replay of this command line, `--profile` included, would get.
        # Value-carrying flags (`--profile`, `-w`, `--vpn`, `-cwd`) are emitted only when set.
        if self.isDesktopEnabled() != OptionResolver().defaultFor(OptionKey.DESKTOP):
            command_options.append("--desktop" if self.isDesktopEnabled() else "--no-desktop")

        # X11 sharing (GUI) config
        if self.__enable_gui:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]X11[/blue] (i.e. GUI apps)?", False):
                self.__disableGUI()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] [blue]X11[/blue] (i.e. GUI apps)?", False):
            await self.enableGUI()
        # Command builder info, under the rule stated at `--desktop` (no config.yml
        # setting: without a profile the basis is the builtin `True`).
        if self.__enable_gui != OptionResolver().defaultFor(OptionKey.GUI):
            command_options.append("--gui" if self.__enable_gui else "--no-gui")

        # Timezone config
        if self.__share_timezone:
            if await ExegolRich.Confirm("Do you want to [orange3]remove[/orange3] your [blue]shared timezone[/blue] config?", False):
                self.__disableSharedTimezone()
        elif await ExegolRich.Confirm("Do you want to [green]share[/green] your [blue]host's timezone[/blue]?", False):
            self.enableSharedTimezone()
        # Command builder info, under the rule stated at `--desktop` (builtin basis `True`).
        if self.__share_timezone != OptionResolver().defaultFor(OptionKey.SHARE_TIMEZONE):
            command_options.append("--share-timezone" if self.__share_timezone else "--no-share-timezone")

        # my-resources config
        if self.__my_resources:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] [blue]my-resources[/blue]?", False):
                self.__disableMyResources()
        elif await ExegolRich.Confirm("Do you want to [green]activate[/green] [blue]my-resources[/blue]?", False):
            self.enableMyResources()
        # Command builder info, under the rule stated at `--desktop` (builtin basis `True`).
        if self.__my_resources != OptionResolver().defaultFor(OptionKey.MY_RESOURCES):
            command_options.append("--my-resources" if self.__my_resources else "--no-my-resources")

        # Exegol resources config
        if self.__exegol_resources:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] the [blue]exegol resources[/blue]?", False):
                self.disableExegolResources()
        elif await ExegolRich.Confirm("Do you want to [green]activate[/green] the [blue]exegol resources[/blue]?", False):
            await self.enableExegolResources()
        # Command builder info, under the rule stated at `--desktop` (builtin basis `True`).
        if self.__exegol_resources != OptionResolver().defaultFor(OptionKey.EXEGOL_RESOURCES):
            command_options.append("--exegol-resources" if self.__exegol_resources else "--no-exegol-resources")

        # Shell logging config
        if self.__shell_logging:
            if await ExegolRich.Confirm("Do you want to [orange3]disable[/orange3] automatic [blue]shell logging[/blue]?", False):
                self.__disableShellLogging()
        elif await ExegolRich.Confirm("Do you want to [green]enable[/green] automatic [blue]shell logging[/blue]?", False):
            # Resolved through the tier chain, as in configFromUser(), so a profile's
            # logging method matches what the recap reproduces.
            log_method = OptionResolver().get(OptionKey.LOG_METHOD)
            log_compress = OptionResolver().get(OptionKey.LOG_COMPRESS)
            self.enableShellLogging(log_method, log_compress)
        # Command builder info, under the rule stated at `--desktop`. The profile tier must be
        # in the basis: otherwise a declined log under a logging-enabled profile loses `--no-log`.
        if self.__shell_logging != OptionResolver().defaultFor(OptionKey.LOG):
            command_options.append("--log" if self.__shell_logging else "--no-log")

        return command_options

    # ===== Feature section =====

    async def enableGUI(self) -> None:
        """Procedure to enable GUI feature"""
        x11_available = await GuiUtils.isX11GuiAvailable()
        wayland_available = GuiUtils.isWaylandGuiAvailable()
        if not x11_available and not wayland_available:
            logger.error("Console GUI feature (i.e. GUI apps) is [red]not available[/red] on your environment. [orange3]Skipping[/orange3].")
            return
        if not self.__enable_gui:
            logger.verbose("Config: Enabling display sharing")
            if x11_available:
                try:
                    host_path: Optional[Union[Path, str]] = GuiUtils.getX11SocketPath()
                    if host_path is not None:
                        assert type(host_path) is str
                        self.addVolume(host_path, GuiUtils.default_x11_path, must_exist=True)
                    # X11 can be used accros network without volume on Mac
                    self.addEnv("DISPLAY", GuiUtils.getDisplayEnv())
                    self.__gui_engine.append("X11")
                except CancelOperation as e:
                    logger.warning(f"Graphical X11 interface sharing could not be enabled: {e}")
            else:
                logger.warning("X11 cannot be shared, only wayland, some graphical applications might not work...")
            if wayland_available:
                try:
                    host_path = GuiUtils.getWaylandSocketPath()
                    if host_path is not None:
                        self.addVolume(host_path, f"/tmp/{host_path.name}", must_exist=True)
                        self.addEnv("XDG_SESSION_TYPE", "wayland")
                        self.addEnv("XDG_RUNTIME_DIR", "/tmp")
                        self.addEnv("WAYLAND_DISPLAY", GuiUtils.getWaylandEnv())
                        self.__gui_engine.append("Wayland")
                except CancelOperation as e:
                    logger.warning(f"Graphical Wayland interface sharing could not be enabled: {e}")
            # TODO support pulseaudio
            for k, v in self.__static_gui_envs.items():
                self.addEnv(k, v)

            # Fix XQuartz render: https://github.com/ThePorgs/Exegol/issues/229
            if EnvInfo.isMacHost():
                self.addEnv("_JAVA_OPTIONS", '-Dsun.java2d.xrender=false')

            self.__enable_gui = True

    def __disableGUI(self) -> None:
        """Procedure to disable X11 (GUI) feature (Only for interactive config)"""
        if self.__enable_gui:
            self.__enable_gui = False
            logger.verbose("Config: Disabling display sharing")
            self.removeVolume(container_path="/tmp/.X11-unix")
            self.removeEnv("DISPLAY")
            self.removeEnv("XDG_SESSION_TYPE")
            self.removeEnv("XDG_RUNTIME_DIR")
            self.removeEnv("WAYLAND_DISPLAY")
            for k in self.__static_gui_envs.keys():
                self.removeEnv(k)
            self.__gui_engine.clear()

    def __setup_timezone_env(self) -> bool:
        """Find the host timezone and share it with the container via a dedicated environment variable"""
        try:
            from tzlocal import get_localzone_name
            current_tz = get_localzone_name()
        except Exception as e:
            logger.debug(f"Unable to detect local timezone via tzlocal: {e}")
            logger.warning("Your system timezone cannot be shared.")
            return False
        if current_tz:
            logger.debug(f"Sharing timezone via TZ env var: '{current_tz}'")
            self.addEnv("TZ", current_tz)
            return True
        logger.warning("Your system timezone cannot be shared.")
        return False

    def enableSharedTimezone(self) -> None:
        """Procedure to enable shared timezone feature"""
        if not self.__share_timezone:
            logger.verbose("Config: Enabling host timezones")
            if EnvInfo.is_windows_shell or EnvInfo.is_mac_shell:
                if not self.__setup_timezone_env():
                    return
            else:
                # Try to share /etc/timezone (deprecated old timezone file)
                try:
                    self.addVolume("/etc/timezone", "/etc/timezone", read_only=True, must_exist=True)
                    logger.verbose("Volume was successfully added for [magenta]/etc/timezone[/magenta]")
                    timezone_loaded = True
                except CancelOperation:
                    logger.debug("File /etc/timezone is missing on host, cannot create volume for this.")
                    timezone_loaded = False
                # Try to share /etc/localtime (new timezone file)
                try:
                    self.addVolume("/etc/localtime", "/etc/localtime", read_only=True, must_exist=True)
                    logger.verbose("Volume was successfully added for [magenta]/etc/localtime[/magenta]")
                except CancelOperation as e:
                    if not timezone_loaded:
                        if not self.__setup_timezone_env():
                            # If neither file was found, disable the functionality
                            logger.error(f"The host's timezone could not be shared: {e}")
                            return
                        else:
                            logger.warning("File [magenta]/etc/localtime[/magenta] is [orange3]missing[/orange3] on host, "
                                           "cannot create volume for this. Relying instead on [magenta]TZ[/magenta] environment variable.")
                    else:
                        logger.warning("File [magenta]/etc/localtime[/magenta] is [orange3]missing[/orange3] on host, "
                                       "cannot create volume for this. Relying instead on [magenta]/etc/timezone[/magenta] [orange3](deprecated)[/orange3].")
            self.__share_timezone = True

    def __disableSharedTimezone(self) -> None:
        """Procedure to disable shared timezone feature (Only for interactive config)"""
        if self.__share_timezone:
            self.__share_timezone = False
            logger.verbose("Config: Disabling host timezones")
            self.removeVolume("/etc/timezone")
            self.removeVolume("/etc/localtime")

    def enableMyResources(self) -> None:
        """Procedure to enable shared volume feature"""
        if not self.__my_resources:
            logger.verbose("Config: Enabling my-resources volume")
            self.__my_resources = True
            # Adding volume config
            self.addVolume(OptionResolver().get(OptionKey.MY_RESOURCES_PATH), StaticContainerPath.MY_RESOURCES.value, enable_sticky_group=True, force_sticky_group=True)

    def __disableMyResources(self) -> None:
        """Procedure to disable shared volume feature (Only for interactive config)"""
        if self.__my_resources:
            logger.verbose("Config: Disabling my-resources volume")
            self.__my_resources = False
            self.removeVolume(container_path=StaticContainerPath.MY_RESOURCES.value)

    async def enableExegolResources(self) -> bool:
        """Procedure to enable exegol resources volume feature"""
        if not self.__exegol_resources:
            # Check if resources are installed / up-to-date
            try:
                if not await ExegolModules().isExegolResourcesReady():
                    raise CancelOperation
            except CancelOperation:
                # Error during installation, skipping operation.
                # ENABLE_EXEGOL_RESOURCES is the config.yml download consent (warn only if
                # given), distinct from the per-container EXEGOL_RESOURCES mount: do not merge.
                if OptionResolver().get(OptionKey.ENABLE_EXEGOL_RESOURCES):
                    logger.warning("Exegol resources have not been downloaded, the feature cannot be enabled yet")
                return False
            logger.verbose("Config: Enabling exegol resources volume")
            self.__exegol_resources = True
            # Adding volume config
            self.addVolume(OptionResolver().get(OptionKey.EXEGOL_RESOURCES_PATH), StaticContainerPath.EXEGOL_RESOURCES.value)
        return True

    def disableExegolResources(self) -> None:
        """Procedure to disable exegol resources volume feature (Only for interactive config)"""
        if self.__exegol_resources:
            logger.verbose("Config: Disabling exegol resources volume")
            self.__exegol_resources = False
            self.removeVolume(container_path=StaticContainerPath.EXEGOL_RESOURCES.value)

    def enableShellLogging(self, log_method: str, compress_mode: Optional[bool] = None) -> None:
        """Procedure to enable exegol shell logging feature"""
        if not self.__shell_logging:
            logger.verbose("Config: Enabling shell logging")
            self.__shell_logging = True
            self.addEnv(self.ExegolEnv.shell_logging_method.value, log_method)
            if compress_mode is not None:
                self.addEnv(self.ExegolEnv.shell_logging_compress.value, str(compress_mode))
            self.addLabel(self.ExegolFeatures.shell_logging.value, log_method)

    def __disableShellLogging(self) -> None:
        """Procedure to disable exegol shell logging feature"""
        if self.__shell_logging:
            logger.verbose("Config: Disabling shell logging")
            self.__shell_logging = False
            self.removeEnv(self.ExegolEnv.shell_logging_method.value)
            self.removeEnv(self.ExegolEnv.shell_logging_compress.value)
            self.removeLabel(self.ExegolFeatures.shell_logging.value)

    def enableSentinel(self, profile_name: Optional[str] = None) -> None:
        """Procedure to enable exegol Sentinel feature"""
        if not SessionHandler().enterprise_feature_access() or not SessionHandler().has_feature(LicenseFeature.Sentinel):
            logger.warning(SessionHandler.feature_access_message("Sentinel"))
            return
        if not self.isSentinelEnable():
            logger.verbose("Config: Enabling Sentinel")
            # Update strategy (CLI > profile > UserConfig > builtin), stored as a label (internal key).
            strategy = OptionResolver().get(OptionKey.SENTINEL_STRATEGY)
            if SentinelUpdateStrategy.from_value(strategy) is None:
                logger.critical(f"Invalid Sentinel update strategy '{strategy}'. "
                                f"Expected one of: {', '.join(SentinelUpdateStrategy.values())}")
            self.setSentinelStrategy(strategy)
            self.addVolume(ConstantConfig.sentinel_zsh_context_path_obj, StaticContainerPath.SENTINEL_ZSH_HOOKS.value, read_only=True, must_exist=True)
            self.addVolume(ConstantConfig.sentinel_bash_context_path_obj, StaticContainerPath.SENTINEL_BASH_HOOKS.value, read_only=True, must_exist=True)
            self.addVolume(ConstantConfig.sentinel_context_path_obj, StaticContainerPath.SENTINEL_LOGGER.value, read_only=True, must_exist=True)
            # Resolved once so every collision retry below targets the same log root.
            sentinel_root: Path = OptionResolver().get(OptionKey.SENTINEL_LOGS_HOST_PATH)
            host_log_path = sentinel_root / f"{self.container_name}_{int(datetime.now().timestamp())}"
            # Generate a sentinel directory that doesn't exist
            while host_log_path.exists():
                host_log_path = sentinel_root / f"{self.container_name}_{int(datetime.now().timestamp())}_{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))}"
            # Create parents directories if needed
            FsUtils.mkdir(host_log_path)
            if not EnvInfo.is_windows_shell:
                # Setup the directory with the right permission.
                # `sentinel_gid` is the effective group; `configured_sentinel_gid` keeps the
                # requested value (-1 = unset) for the warning below.
                configured_sentinel_gid: int = OptionResolver().get(OptionKey.SENTINEL_GID)
                sentinel_gid: int = configured_sentinel_gid
                user_uid, user_gid = FsUtils.get_user_id()
                if sentinel_gid == -1:
                    sentinel_gid = user_gid
                try:
                    os.chown(host_log_path, 0, sentinel_gid)
                    host_log_path.chmod(mode=stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_ISGID)
                except PermissionError:
                    # Mac user without can't chown to root
                    try:
                        os.chown(host_log_path, user_uid, sentinel_gid)
                        host_log_path.chmod(mode=stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_ISGID)
                    except PermissionError:
                        logger.debug("Exegol dont have the permission to update Sentinel file permission")
                        if configured_sentinel_gid == -1:
                            logger.warning("Cannot set the right permissions on the JSON log file, you can run [orange3]manually[/orange3] this command from your [red]host[/red]:")
                            logger.raw(f"sudo chown -R root:{sentinel_gid} {host_log_path}")
            if profile_name is None:
                # CLI > profile > config.yml `sentinel_default_profile` > "" (no audit profile).
                # Not plain get(): a blank profile `sentinel.profile` (null or "") must not
                # shadow the config.yml default and silently skip writing the config.
                profile_name = OptionResolver().resolveOmittingBlankProfile(
                    OptionKey.SENTINEL_PROFILE, blank=(None, "")).value
            if profile_name:
                try:
                    spm = SentinelProfileManager()
                    if spm.load_profiles():
                        # Resolve the selection (bare 'name' or 'source.name'); a bare name that
                        # several sources define is rejected with a critical, disambiguating error.
                        resolved = spm.resolve_profile_selection(profile_name)
                        if resolved is None:
                            raise CancelOperation(f"Sentinel profile '{profile_name}' not found or invalid.")
                        source_key, resolved_name = resolved
                        consolidated = spm.get_consolidated_config(resolved_name, current_source=source_key)
                        if consolidated:
                            # Store the fully-qualified name so restart-time regeneration is unambiguous.
                            self.__sentinel_profile = f"{source_key}.{resolved_name}"
                            try:
                                self.__writeSentinelConfig(host_log_path, consolidated)
                            except Exception as e:
                                raise CancelOperation(f"Failed to generate sentinel config: {e}")
                        else:
                            raise CancelOperation(f"Sentinel profile '{profile_name}' not found or invalid.")
                    else:
                        raise CancelOperation("Failed to load Sentinel profiles.")
                except CancelOperation as e:
                    shutil.rmtree(host_log_path)
                    logger.critical(str(e))
            else:
                # No audit profile at any tier: commands are still journaled but no
                # per-trigger collection runs, so warn (never invent a profile name).
                logger.warning("Sentinel is enabled but no audit profile is configured, so "
                               "no per-trigger collection will run. Command journaling is "
                               "unaffected. Set [green]sentinel_default_profile[/green] in "
                               "~/.exegol/config.yml or pass [green]-SP NAME[/green].")
                # The container must still receive a deployed config: the in-container
                # recorder gate and the logger both read `profile.config.log_output` out of
                # this file, so without it the machine default from `sentinel.log_output` is
                # unreachable. No image probe or capability check belongs here — spawn.sh is
                # the sole gate. The failure posture is deliberately asymmetric with the arm
                # above: a profile that was requested and failed to resolve is an error the
                # operator must see, whereas nothing was requested here, so a write failure
                # degrades to a warning rather than failing `exegol start`.
                try:
                    self.__writeSentinelConfig(host_log_path, SentinelProfileManager().get_default_config())
                except Exception as e:
                    logger.warning(f"Sentinel: failed to generate the default configuration ({e}). "
                                   f"The container will start without one; no command output will be captured.")

            self.addVolume(host_log_path, StaticContainerPath.SENTINEL_DIRECTORY.value)
            self.__sentinel_path = host_log_path

    def __writeSentinelConfig(self, target_dir: Path, consolidated: Dict) -> None:
        """Write the consolidated Sentinel config JSON into ``target_dir``.

        Errors propagate: the caller aborts creation or keeps the cached config.

        Write-then-rename, not open("w"): truncating the real path and streaming json.dump
        into it leaves a truncated JSON document behind on any failure part-way (ENOSPC, an
        interrupted `exegol restart`), and spawn.sh's recorder gate exits 1 on any parse
        error, so a half-written config fails closed into "recorder off, no output" —
        silently, for the life of that container. rename(2) within a directory is atomic; the
        fsync makes that hold across a host crash too.

        The scratch name is unique per writer, and that atomicity depends on it: a fixed
        `.tmp` is shared by every process touching the same instance directory, so two
        concurrent runs interleaved their json.dump output into it and one renamed the
        mixture into place, while the `except` handler had the loser unlink the winner's file
        mid-write.

        The mode is set explicitly: the rename installs a fresh inode, so the mode would
        otherwise be re-derived from the invoking user's umask at every restart (0600 under
        `umask 077`, which the host-side sentinel_gid agent cannot read). 0640 matches every
        other file in the sentinel tree.

        Abandoned scratch files are swept first: the `except: unlink` below covers exceptions
        only, and a SIGKILL between mkstemp and replace leaves a randomly-named scratch file
        in a directory bind-mounted into the container, which no later run has a fixed path
        to clean."""
        sweep_stale_scratch(target_dir, StaticFileName.SENTINEL_CONFIG.value)
        config_file = target_dir / StaticFileName.SENTINEL_CONFIG.value
        fd, tmp_name = tempfile.mkstemp(dir=str(target_dir),
                                        prefix=scratch_prefix(StaticFileName.SENTINEL_CONFIG.value),
                                        suffix=SCRATCH_SUFFIX)
        os.close(fd)
        tmp_file = Path(tmp_name)
        try:
            with tmp_file.open("w", encoding="utf-8") as f:
                json.dump(consolidated, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            if not EnvInfo.is_windows_shell:
                # Same guard as the instance-directory chmod above: Windows has no
                # POSIX mode to set, and the group model does not apply there.
                os.chmod(tmp_file, 0o640)
            tmp_file.replace(config_file)
        except Exception:
            # Never leave the scratch file behind: the next run would not clean it up, and
            # it sits in the directory bind-mounted into the container. Safe to unlink
            # unconditionally because the name belongs to this writer alone.
            tmp_file.unlink(missing_ok=True)
            raise

    def regenerateSentinelConfig(self) -> bool:
        """Regenerate the container's sentinel_config.json from the current host sources.

        Called at restart while the container is stopped. Uses only the container's own
        recorded profile name. Returns True when a config was written."""
        if not self.isSentinelEnable() or self.__sentinel_path is None:
            return False
        # A container created without an audit profile must not gain per-trigger collection
        # from the current config.yml at restart, so `sentinel_default_profile` is
        # deliberately not consulted here. The arm below still refreshes such a container's
        # config, which carries only the machine defaults, so the two rules do not conflict.
        profile_name = self.getSentinelProfile()
        spm = SentinelProfileManager()
        if not profile_name:
            # A container with no profile gets its config refreshed too, so an operator
            # who edits `sentinel.log_output` and restarts sees the new value without
            # recreating the container. Same shared writer as every other path.
            try:
                self.__writeSentinelConfig(self.__sentinel_path, spm.get_default_config())
            except Exception as e:
                logger.warning(f"Sentinel: failed to regenerate the default config: {e}")
                return False
            logger.verbose("Sentinel: regenerated the default config from host sources (no profile associated)")
            return True
        if not spm.load_profiles():
            logger.warning("Sentinel: failed to load profiles, keeping the existing container config")
            return False
        consolidated = spm.get_consolidated_config(profile_name)
        if not consolidated:
            # get_consolidated_config()/resolve_selection() has already said why -- not
            # found, ambiguous, or its source dropped for a parse error -- and this layer
            # cannot tell those apart. Report only what it knows: the consequence.
            logger.warning(f"Sentinel: keeping the existing container config for '{profile_name}' "
                           f"(see the error above).")
            return False
        try:
            self.__writeSentinelConfig(self.__sentinel_path, consolidated)
        except Exception as e:
            logger.warning(f"Sentinel: failed to regenerate config: {e}")
            return False
        logger.verbose(f"Sentinel: regenerated config from host sources for profile '{profile_name}'")
        return True

    def __disableSentinel(self) -> None:
        """Procedure to disable exegol Sentinel feature"""
        if self.isSentinelEnable():
            logger.verbose("Config: Disabling Sentinel")
            self.removeVolume(container_path=StaticContainerPath.SENTINEL_ZSH_HOOKS.value)
            self.removeVolume(container_path=StaticContainerPath.SENTINEL_BASH_HOOKS.value)
            self.removeVolume(container_path=StaticContainerPath.SENTINEL_LOGGER.value)
            self.removeVolume(container_path=StaticContainerPath.SENTINEL_DIRECTORY.value)
            if self.__sentinel_path and self.__sentinel_path.is_dir():
                shutil.rmtree(self.__sentinel_path)
            self.__sentinel_path = None
            self.__sentinel_profile = None

    def isDesktopEnabled(self) -> bool:
        return self.__desktop_proto is not None

    async def enableDesktop(self, desktop_config: str = "") -> None:
        """Procedure to enable exegol desktop feature"""
        if not self.isDesktopEnabled():
            if self.isNetworkDisabled():
                logger.error(f"The current network mode doesn't support the desktop feature.")
                return
            logger.verbose("Config: Enabling exegol desktop")
            self.configureDesktop(desktop_config, create_mode=True)
            assert self.__desktop_proto is not None
            assert self.__desktop_host is not None
            assert self.__desktop_port is not None
            self.addLabel(self.ExegolFeatures.desktop.value, f"{self.__desktop_proto}:{self.__desktop_host}:{self.__desktop_port}")
            # Env var are used to send these parameter to the desktop-start script
            self.addEnv(self.ExegolEnv.desktop_protocol.value, self.__desktop_proto)
            self.addEnv(self.ExegolEnv.exegol_user.value, self.getUsername())

            if self.isNetworkHost():
                self.addEnv(self.ExegolEnv.desktop_host.value, self.__desktop_host)
                self.addEnv(self.ExegolEnv.desktop_port.value, str(self.__desktop_port))
            else:
                # Container in bridge mode
                # If we do not specify the host to the container it will automatically choose eth0 interface
                # Using default port for the service
                self.addEnv(self.ExegolEnv.desktop_port.value, str(self.__default_desktop_port.get(self.__desktop_proto)))
                # Exposing desktop service
                await self.addPort(port_host=self.__desktop_port, port_container=self.__default_desktop_port[self.__desktop_proto], host_ip=self.__desktop_host)

    def configureDesktop(self, desktop_config: str, create_mode: bool = False) -> None:
        """Configure the exegol desktop feature from user parameters.
        Accepted format: 'proto:host:port'
        """
        # Apply default config.
        # Per-segment defaults overwritten below by `desktop_config`; reading DESKTOP_CONFIG
        # here instead would be circular.
        self.__desktop_proto = OptionResolver().get(OptionKey.DESKTOP_DEFAULT_PROTO)
        self.__desktop_host = "127.0.0.1" if OptionResolver().get(OptionKey.DESKTOP_DEFAULT_LOCALHOST) else "0.0.0.0"

        # Set config from user input
        for i, data in enumerate(desktop_config.split(":")):
            if not data:
                continue
            if i == 0:  # protocol
                logger.debug(f"Desktop proto set: {data}")
                data = data.lower()
                if data in UserConfig.desktop_available_proto:
                    self.__desktop_proto = data
                else:
                    logger.critical(f"The desktop mode '{data}' is not supported. Please choose a supported mode: [green]{', '.join(UserConfig.desktop_available_proto)}[/green].")
            elif i == 1 and data:  # host
                logger.debug(f"Desktop host set: {data}")
                self.__desktop_host = data
            elif i == 2:  # port
                logger.debug(f"Desktop port set: {data}")
                try:
                    self.__desktop_port = int(data)
                except ValueError:
                    logger.critical(f"Invalid desktop port: '{data}' is not a valid port.")
            else:
                logger.critical(f"Your configuration is invalid, please use the following format: {SyntaxFormat.desktop_config}")

        if self.__desktop_port is None:
            logger.debug(f"Desktop port will be set automatically")
            self.__desktop_port = self.__findAvailableRandomPort(self.__desktop_host)

        if create_mode:
            # Check if the port is available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self.__desktop_host, self.__desktop_port))
                except socket.error as e:
                    if e.errno == errno.EADDRINUSE:
                        logger.critical(f"The port {self.__desktop_host}:{self.__desktop_port} is already in use !")
                    elif e.errno == errno.EADDRNOTAVAIL:
                        logger.critical(f"The network {self.__desktop_host}:{self.__desktop_port} is not available !")
                    else:
                        logger.critical(f"The supplied network configuration {self.__desktop_host}:{self.__desktop_port} is not available ! ([{e.errno}] {e})")

    def __disableDesktop(self) -> None:
        """Procedure to disable exegol desktop feature"""
        if self.isDesktopEnabled():
            logger.verbose("Config: Disabling exegol desktop")
            assert self.__desktop_proto is not None
            if not self.isNetworkHost():
                self.__removePort(self.__default_desktop_port[self.__desktop_proto])
            self.__desktop_proto = None
            self.__desktop_host = None
            self.__desktop_port = None
            self.removeLabel(self.ExegolFeatures.desktop.value)
            self.removeEnv(self.ExegolEnv.desktop_protocol.value)
            self.removeEnv(self.ExegolEnv.exegol_user.value)
            self.removeEnv(self.ExegolEnv.desktop_host.value)
            self.removeEnv(self.ExegolEnv.desktop_port.value)

    def enableCwdShare(self) -> None:
        """Procedure to share Current Working Directory with the /workspace of the container"""
        self.__workspace_custom_path = os.getcwd()
        logger.verbose(f"Config: Sharing current workspace directory {self.__workspace_custom_path}")

    async def enableVPN(self, config_path: Optional[Union[str, PurePath]] = None, auth_path: Optional[str] = None, apply_only: bool = False) -> None:
        """Configure a VPN profile for container startup.

        ``auth_path`` mirrors ``config_path``: an explicit value wins, ``None`` lets the
        helpers resolve it."""
        # Check host mode : custom (allows you to isolate the VPN connection from the host's network)
        # Host mode is kept only when the CLI or a profile asked for it; an ambient default
        # still moves off host networking.
        if not apply_only and self.isNetworkHost() and not OptionResolver().isExplicitOrProfile(OptionKey.NETWORK):
            if EnvInfo.isLinuxHost():
                logger.info(f"Defaulting to [magenta]{self.__fallback_network_mode.value}[/magenta] to protect host from VPN. Use [blue]--network host[/blue] if you need to access VPN from your host.")
            await self.setNetworkMode(self.__fallback_network_mode)
        # Add NET_ADMIN capabilities, this privilege is necessary to mount network tunnels interfaces
        self.addCapability("NET_ADMIN")
        # Add sysctl ipv6 config, some VPN connection need IPv6 to be enabled
        # TODO test with ipv6 disable with kernel modules
        skip_sysctl = False
        if self.isNetworkHost() and EnvInfo.is_linux_shell:
            # Check if IPv6 have been disabled on the host with sysctl
            if check_sysctl_value("net.ipv6.conf.all.disable_ipv6", "0"):
                skip_sysctl = True
        if not skip_sysctl:
            self.__addSysctl("net.ipv6.conf.all.disable_ipv6", "0")

        # An explicit `config_path` wins, even '' (no path to mount); only `None` resolves.
        # Guards against treating '' as a path, which would bind-mount the cwd.
        resolved_vpn = config_path if config_path is not None else OptionResolver().get(OptionKey.VPN)
        if resolved_vpn:
            # VPN config path
            vpn_path = resolved_vpn if isinstance(resolved_vpn, Path) else EnvInfo.expand_user(resolved_vpn)

            logger.debug(f"Adding VPN from: {str(vpn_path.absolute())}")
            # Sharing VPN configuration with the container
            if vpn_path.is_dir() or (vpn_path.is_file() and vpn_path.suffix == ".ovpn"):
                # Add tun device, this device is needed to create OpenVPN tunnels
                self.__addDevice("/dev/net/tun", mknod=True)
                # OpenVPN config
                self.__vpn_mode = "ovpn"
                self.__vpn_parameters = await self.__prepareOpenVpnVolumes(vpn_path, skip_conf_checks=apply_only, auth_path=auth_path)
            elif vpn_path.is_file() and vpn_path.suffix == ".conf":
                # Wireguard config
                self.__addSysctl("net.ipv4.conf.all.src_valid_mark", "1")
                self.__vpn_mode = "wgconf"
                self.__vpn_parameters = self.__prepareWireguardVolumes(vpn_path, auth_path=auth_path)
            else:
                logger.error(f"Your VPN configuration [magenta]{vpn_path}[/magenta] is not an OpenVPN directory / [green].ovpn[/green] file or a WireGuard [green].conf[/green] file.")
                self.__disableVPN()
                raise InteractiveError
        else:
            # Add tun device, this device is needed to create OpenVPN tunnels
            self.__addDevice("/dev/net/tun", mknod=True)
            # Add sysctl for wireguard default gateway
            self.__addSysctl("net.ipv4.conf.all.src_valid_mark", "1")
            logger.success("Enabling VPN capabilities without managing a VPN connection")

    def __disableVPN(self) -> bool:
        """Remove a VPN profile for container startup (Only for interactive config)"""
        if self.__vpn_path:
            logger.verbose('Removing VPN configuration')
            self.__vpn_path = None
            self.__vpn_mode = None
            self.__vpn_parameters = None
            self.__removeCapability("NET_ADMIN")
            self.__removeSysctl("net.ipv6.conf.all.disable_ipv6")
            self.__removeSysctl("net.ipv4.conf.all.src_valid_mark")
            self.removeDevice("/dev/net/tun")
            # Try to remove each possible volume
            self.removeVolume(container_path=StaticContainerPath.OPENVPN_CREDS_FILE.value)
            self.removeVolume(container_path=StaticContainerPath.OPENVPN_CONFIG_FILE.value)
            self.removeVolume(container_path=StaticContainerPath.OPENVPN_CONFIG_DIR.value)
            self.removeVolume(container_path=StaticContainerPath.WIREGUARD_CONFIG_FILE.value)
            return True
        return False

    def disableDefaultWorkspace(self) -> None:
        """Allows you to disable the default workspace volume"""
        # If a custom workspace is not define, disable workspace
        if self.__workspace_custom_path is None:
            self.__disable_workspace = True

    def addComment(self, comment: str) -> None:
        """Procedure to add comment to a container"""
        if not self.__comment:
            logger.verbose("Config: Adding comment to container info")
            self.setComment(comment)

    # ===== Functional / technical methods section =====

    async def __prepareOpenVpnVolumes(self, vpn_path: Path, skip_conf_checks: bool, auth_path: Optional[str] = None) -> Optional[str]:
        """Volumes must be prepared to share OpenVPN configuration files with the container.
        Depending on the user's settings, different configurations can be applied.
        With or without username / password authentication via auth-user-pass.
        OVPN config file directly supplied or a config directory,
        the directory feature is useful when the configuration depends on multiple files like certificate, keys etc."""
        ovpn_parameters = []

        logger.debug(f"Configuring OpenVPN")
        self.__vpn_path = vpn_path
        if vpn_path.is_file():
            if not skip_conf_checks:
                await self.__checkVPNConfigDNS(vpn_path)
            # Configure VPN with single file
            self.addVolume(vpn_path, StaticContainerPath.OPENVPN_CONFIG_FILE.value, read_only=True)
            ovpn_parameters.append("--config /.exegol/vpn/config/client.ovpn")
        else:
            # Configure VPN with directory
            logger.verbose("Folder detected for VPN configuration. "
                           "Only the first *.ovpn file will be automatically launched when the container starts.")
            self.addVolume(vpn_path, StaticContainerPath.OPENVPN_CONFIG_DIR.value, read_only=True)
            vpn_filename = None
            # Try to find the config file in order to configure the autostart command of the container
            for file in vpn_path.glob('*.ovpn'):
                logger.info(f"Using VPN config: {file}")
                if not skip_conf_checks:
                    await self.__checkVPNConfigDNS(file)
                # Get filename only to match the future container path
                vpn_filename = file.name
                ovpn_parameters.append(f"--config /.exegol/vpn/config/{vpn_filename}")
                # If there is multiple match, only the first one is selected
                break
            if vpn_filename is None:
                logger.error(f"No [green].ovpn[/green] file were detected in the directory [magenta]{vpn_path}[magenta]. The VPN autostart will not work.")
                return None

        # VPN Auth creds file
        # An explicitly threaded path wins; an omitted one resolves. Only one VPN helper runs
        # per enableVPN() call, so this cannot disagree with the WireGuard read.
        input_vpn_auth = auth_path if auth_path is not None else OptionResolver().get(OptionKey.VPN_AUTH)
        vpn_auth = None
        if input_vpn_auth is not None:
            vpn_auth = EnvInfo.expand_user(input_vpn_auth)

        if vpn_auth is not None:
            if vpn_auth.is_file():
                logger.info(f"Adding VPN credentials from: {str(vpn_auth.absolute())}")
                self.addVolume(vpn_auth, StaticContainerPath.OPENVPN_CREDS_FILE.value, read_only=True)
                ovpn_parameters.append("--auth-user-pass " + StaticContainerPath.OPENVPN_CREDS_FILE.value)
            else:
                # Supply a directory instead of a file for VPN authentication is not supported.
                logger.critical(
                    f"The path provided to the VPN connection credentials ({str(vpn_auth)}) does not lead to a file. Aborting operation.")

        return ' '.join(ovpn_parameters)

    def __prepareWireguardVolumes(self, wireguard_path: Path, auth_path: Optional[str] = None) -> Optional[str]:
        """Volumes must be prepared to share WireGuard configuration files with the container.
        WireGuard config fil is .conf and include evry needed configuration like private key, public key, etc."""
        wg_parameters = []
        logger.debug(f"Configuring WireGuard")
        self.__vpn_path = wireguard_path
        # Same fallback as __prepareOpenVpnVolumes(), so a profile's vpn.auth_file gets the
        # same warning as a typed --vpn-auth.
        input_vpn_auth = auth_path if auth_path is not None else OptionResolver().get(OptionKey.VPN_AUTH)
        if input_vpn_auth is not None:
            logger.warning("WireGuard setup doesn't support --vpn-auth parameter. It will be ignored.")

        self.addVolume(wireguard_path, StaticContainerPath.WIREGUARD_CONFIG_FILE.value, read_only=True)
        wg_parameters.append("wg0")

        return ' '.join(wg_parameters)

    @staticmethod
    async def __checkVPNConfigDNS(vpn_path: Union[str, Path]) -> None:
        """Check if the OpenVPN configuration file contains DNS server dynamic update scripts"""
        logger.verbose("Checking OpenVPN config file")
        configs = ["script-security 2", "up /etc/openvpn/update-resolv-conf", "down /etc/openvpn/update-resolv-conf"]
        with open(vpn_path, 'r') as vpn_file:
            for line in vpn_file:
                line = line.strip()
                if line in configs:
                    configs.remove(line)
        if len(configs) > 0:
            logger.warning("Some OpenVPN config are [red]missing[/red] to support VPN [orange3]dynamic DNS servers[/orange3]! "
                           "Please add the following line to your configuration file:")
            logger.empty_line()
            logger.raw(os.linesep.join(configs), level=logging.WARNING)
            logger.empty_line()
            logger.empty_line()
            await ExegolRich.Acknowledge("Your VPN configuration won't support dynamic DNS servers.")

    def prepareShare(self, container_name: str) -> None:
        """Add workspace share before container creation.
        :param container_name: Name of the container defined by the user (without the exegol- part)
        """
        for mount in self.__mounts:
            if mount.get('Target') == '/workspace':
                # Volume is already prepared
                return
        if self.__workspace_custom_path is not None:
            self.addVolume(self.__workspace_custom_path, '/workspace', enable_sticky_group=True)
        elif self.__disable_workspace:
            # Skip default volume workspace if disabled
            return
        else:
            # Add dedicated private workspace bind volume
            volume_path = str(OptionResolver().get(OptionKey.PRIVATE_WORKSPACE_PATH).joinpath(container_name))
            self.addVolume(volume_path, '/workspace', enable_sticky_group=True)

    def rollback_preparation(self, share_name: str) -> None:
        """Undo preparation in case of container creation failure"""
        if self.__workspace_custom_path is None and not self.__disable_workspace:
            # Remove dedicated workspace volume
            # Independent read from prepareShare(): a separate invocation, after creation failed.
            directory_path = OptionResolver().get(OptionKey.PRIVATE_WORKSPACE_PATH).joinpath(share_name)
            if directory_path.is_dir() and len(list(directory_path.iterdir())) == 0:
                logger.info("Rollback: removing dedicated workspace directory")
                directory_path.rmdir()
            else:
                logger.warning("Rollback: the workspace directory isn't empty, it will NOT be removed automatically")

    def entrypointRunCmd(self, endless_mode: bool = False) -> None:
        """Enable the run_cmd feature of the entrypoint. This feature execute the command stored in the $CMD container environment variables.
        The endless_mode parameter can specify if the container must stay alive after command execution or not"""
        self.__run_cmd = True
        self.__endless_container = endless_mode

    def getEntrypointCommand(self) -> Tuple[Optional[List[str]], Union[List[str], str]]:
        """Get container entrypoint/command arguments.
        The default container_entrypoint is '/bin/bash /.exegol/entrypoint.sh' and the default container_command is ['load_setups', 'endless']."""
        entrypoint_actions = []
        if self.__my_resources:
            entrypoint_actions.append("load_setups")
        if self.isDesktopEnabled():
            entrypoint_actions.append("desktop")
        if self.__vpn_path is not None:
            entrypoint_actions.append(f"{self.__vpn_mode} {self.__vpn_parameters}")
        if self.__run_cmd:
            entrypoint_actions.append("run_cmd")
        if self.__endless_container:
            entrypoint_actions.append("endless")
        else:
            entrypoint_actions.append("finish")
        return self.__container_entrypoint, entrypoint_actions

    @staticmethod
    def getShellCommand() -> str:
        """Get container command for opening a new shell"""
        # Use a spawn.sh script to handle features with the wrapper
        return StaticContainerPath.EXEGOL_SPAWN.value

    @staticmethod
    def generateRandomPassword(length: int = 30) -> str:
        """
        Generate a new random password.
        """
        charset = string.ascii_letters + string.digits
        return ''.join(random.choice(charset) for _ in range(length))

    @staticmethod
    def __findAvailableRandomPort(interface: str = 'localhost') -> int:
        """Find an available random port. Using the socket system to """
        logger.debug(f"Attempting to bind to interface {interface}")
        with socket.socket() as sock:
            try:
                sock.bind((interface, 0))  # Using port 0 let the system decide for a random port
            except OSError as e:
                logger.critical(f"Unable to bind a port to the interface {interface} ({e})")
            random_port = sock.getsockname()[1]
        logger.debug(f"Found available port {random_port}")
        return random_port

    # ===== Apply config section =====

    def setWorkspaceShare(self, host_directory: str) -> None:
        """Procedure to share a specific directory with the /workspace of the container"""
        path = EnvInfo.expand_user(host_directory).absolute()
        try:
            if not path.is_dir() and path.exists():
                logger.critical("The specified workspace is not a directory!")
        except PermissionError as e:
            logger.critical(f"Unable to use the supplied workspace directory: {e}")
        logger.verbose(f"Config: Sharing workspace directory {path}")
        self.__workspace_custom_path = str(path)

    def __setNetwork(self, network: Union[ExegolNetworkMode, str]) -> None:
        """Procedure to set the network mode of the container"""

        if type(network) is ExegolNetworkMode and network == ExegolNetworkMode.nat:
            if not SessionHandler().pro_feature_access():
                logger.critical(f"Isolated network mode [green]NAT[/green] is not available in the Community version of Exegol. You can use the [green]docker[/green] mode instead.")
                raise CancelOperation
            elif EnvInfo.isOrbstack():
                logger.warning("Orbstack doesn’t isolate networks. If you need improved security with [green]NAT[/green], use Docker Desktop. See https://github.com/orbstack/orbstack/issues/1944")

        self.__networks.clear()
        if type(network) is str or network != ExegolNetworkMode.disabled:
            self.__networks.append(ExegolNetwork.instance_network(network, self.container_name))

    async def setNetworkMode(self, network: Union[ExegolNetworkMode, str] = ExegolNetworkMode.host) -> None:
        """Set container's network mode, true for host, false for bridge.

        No "unset" fallback here: OptionResolver resolves the default network mode."""
        try:
            if type(network) is str:
                net_mode: Union[ExegolNetworkMode, str] = ExegolNetworkMode[network.lower()]
            else:
                net_mode = network
        except KeyError:
            net_mode = network

        # Feature that must be reloaded if the network setting is changed
        desktop_config = None
        if self.isDesktopEnabled():
            desktop_config = f"{self.__desktop_proto}:{self.__desktop_host}:{self.__desktop_port}"
            self.__disableDesktop()
        vpn_config = self.__vpn_path
        if vpn_config:
            self.__disableVPN()

        # Check for host mode incompatibility
        skipping = False
        if type(net_mode) is ExegolNetworkMode and net_mode == ExegolNetworkMode.host:
            if len(self.__ports) > 0:
                skipping = not self.isNetworkHost()
                logger.warning(f"Host mode cannot be set with NAT ports configured. {'Skipping' if skipping else 'Disabling the host network mode'}.")
                if not skipping:
                    net_mode = self.__fallback_network_mode
            if not skipping and EnvInfo.isDockerDesktop():
                if not EnvInfo.isHostNetworkAvailable():
                    net_mode = self.__fallback_network_mode
                else:
                    logger.warning("The network mode of the Docker desktop host has its limitations. It may not work as expected.")
                    logger.verbose("More information from the official documentation of Docker Desktop: https://docs.docker.com/network/drivers/host/#docker-desktop")

        if not skipping:
            self.__setNetwork(net_mode)

        # Reload feature after networks config change
        if desktop_config:
            await self.enableDesktop(desktop_config)
        if vpn_config:
            await self.enableVPN(vpn_config, apply_only=True)

    def setPrivileged(self, status: bool = True) -> None:
        """Set container as privileged"""
        logger.verbose(f"Config: Setting container privileged as {status}")
        if status:
            logger.warning("Setting container as privileged (this exposes the host to security risks)")
        self.__privileged = status

    def addCapability(self, cap_string: str) -> None:
        """Add a linux capability to the container"""
        if cap_string in self.__capabilities:
            logger.verbose("Capability already setup. Skipping.")
            return
        self.__capabilities.append(cap_string)

    def __removeCapability(self, cap_string: str) -> bool:
        """Remove a linux capability from the container's config"""
        try:
            self.__capabilities.remove(cap_string)
            return True
        except ValueError:
            # When the capability is not present
            return False

    def __addSysctl(self, sysctl_key: str, config: Union[str, int]) -> None:
        """Add a linux sysctl to the container"""
        if sysctl_key in self.__sysctls.keys():
            logger.verbose(f"Sysctl [magenta]{sysctl_key}[/magenta] already setup to [orange3]{self.__sysctls[sysctl_key]}[/orange3]. Skipping.")
            return
        # Docs of supported sysctl by linux / docker: https://docs.docker.com/reference/cli/docker/container/run/#currently-supported-sysctls
        if self.isNetworkHost() and sysctl_key.startswith('net.'):
            logger.warning(f"The sysctl container configuration is [red]not[/red] supported by docker in [blue]host[/blue] network mode.")
            logger.warning(f"Skipping the sysctl config: [magenta]{sysctl_key}[/magenta] = [orange3]{config}[/orange3].")
            if EnvInfo.isLinuxHost():
                logger.warning(f"If this configuration is mandatory in your situation, try to change it in sudo mode on your host.")
            return
        self.__sysctls[sysctl_key] = str(config)

    def __removeSysctl(self, sysctl_key: str) -> bool:
        """Remove a linux capability from the container's config"""
        try:
            self.__sysctls.pop(sysctl_key)
            return True
        except KeyError:
            # When the sysctl is not present
            return False

    def getNetwork(self) -> Tuple[Optional[str], Optional[str]]:
        """First Network getter for docker API on container creation"""
        if len(self.__networks) > 0:
            return self.__networks[0].getNetworkConfig()
        return None, None

    def getNetworks(self) -> List[ExegolNetwork]:
        """Networks getter"""
        return self.__networks

    def setExtraHost(self, host: str, ip: str) -> None:
        """Add or update an extra host to resolv inside the container."""
        self.__extra_host[host] = ip

    def removeExtraHost(self, host: str) -> bool:
        """Remove an extra host to resolv inside the container.
        Return true if the host was register in the extra_host configuration."""
        return self.__extra_host.pop(host, None) is not None

    def getExtraHost(self) -> Dict[str, str]:
        """Return the extra_host configuration for the container.
        Ensure in shared host environment that the container hostname will be correctly resolved to localhost.
        Return a dictionary of host and matching IP"""
        # When using host network mode, you need to add an extra_host to resolve $HOSTNAME
        if self.isNetworkHost() and self.hostname not in self.__extra_host.keys():
            self.setExtraHost(self.hostname, '127.0.0.1')
        return self.__extra_host

    def getPrivileged(self) -> bool:
        """Privileged getter"""
        return self.__privileged

    def getCapabilities(self) -> List[str]:
        """Capabilities getter"""
        return self.__capabilities

    def getSysctls(self) -> Dict[str, str]:
        """Sysctl custom rules getter"""
        return self.__sysctls

    def getWorkingDir(self) -> str:
        """Get default container's default working directory path"""
        return "/" if self.__disable_workspace else "/workspace"

    def getHostWorkspacePath(self) -> str:
        """Get private volume path (None if not set)"""
        if self.__workspace_custom_path:
            return FsUtils.resolvStrPath(self.__workspace_custom_path)
        elif self.__workspace_dedicated_path:
            return self.getPrivateVolumePath()
        return "not found :("

    def getPrivateVolumePath(self) -> str:
        """Get private volume path (None if not set)"""
        return FsUtils.resolvStrPath(self.__workspace_dedicated_path)

    def isMyResourcesEnable(self) -> bool:
        """Return if the feature 'my-resources' is enabled in this container config"""
        return self.__my_resources

    def getMyResourcesPath(self) -> str:
        """Return if the feature 'exegol resources' is enabled in this container config"""
        return self.__my_resources_path

    def isExegolResourcesEnable(self) -> bool:
        """Return if the feature 'exegol resources' is enabled in this container config"""
        return self.__exegol_resources

    def isShellLoggingEnable(self) -> bool:
        """Return if the feature 'shell logging' is enabled in this container config"""
        return self.__shell_logging

    def isSentinelEnable(self) -> bool:
        """Return if the feature 'sentinel' is enabled in this container config"""
        return self.__sentinel_path is not None

    def getSentinelPath(self) -> Optional[Path]:
        """Get host path to Sentinel logging file"""
        return self.__sentinel_path

    def isGUIEnable(self) -> bool:
        """Return if the feature 'GUI' is enabled in this container config"""
        return self.__enable_gui

    def isTimezoneShared(self) -> bool:
        """Return if the feature 'timezone' is enabled in this container config"""
        return self.__share_timezone

    def isWorkspaceCustom(self) -> bool:
        """Return if the workspace have a custom host volume"""
        return bool(self.__workspace_custom_path)

    def isNetworkHost(self) -> bool:
        """Return True if the container is attached to the host network"""
        for net in self.__networks:
            if net.getNetworkMode() == ExegolNetworkMode.host:
                return True
        return False

    def isNetworkBridge(self) -> bool:
        """Return True if the container is attached to the host network"""
        for net in self.__networks:
            if net.getNetworkDriver() == DockerDrivers.Bridge:
                return True
        return False

    def isNetworkDisabled(self) -> bool:
        """Return True if the container is not connected to any network"""
        return len(self.__networks) == 0

    def addVolume(self,
                  host_path: Union[str, Path],
                  container_path: str,
                  must_exist: bool = False,
                  read_only: bool = False,
                  enable_sticky_group: bool = False,
                  force_sticky_group: bool = False,
                  volume_type: str = 'bind') -> None:
        """Add a volume to the container configuration.
        When the host path does not exist (neither file nor folder):
        if must_exist is set, an CancelOperation exception will be thrown.
        Otherwise, a folder will attempt to be created at the specified path.
        if set_sticky_group is set (on a Linux host), the permission setgid will be added to every folder on the volume."""
        # The creation of the directory is ignored when it is a path to the remote drive
        if volume_type == 'bind' and not (type(host_path) is str and host_path.startswith("\\\\")):
            path: Path = host_path.absolute() if type(host_path) is Path else Path(host_path).absolute()
            host_path = path.as_posix()
            # Docker Desktop for Windows based on WSL2 don't have filesystem limitation
            if EnvInfo.isMacHost():
                # Add support for /etc
                if host_path.startswith("/opt/") and EnvInfo.isOrbstack():
                    msg = f"{EnvInfo.getDockerEngine().value} cannot mount directory from /opt/ host path."
                    if host_path.endswith("entrypoint.sh") or host_path.endswith("spawn.sh"):
                        msg += " Your exegol installation cannot be stored under this directory."
                        logger.critical(msg)
                    else:
                        msg += f" The volume {host_path} cannot be mounted to the container, please move it outside of this directory."
                    raise CancelOperation(msg)
                if EnvInfo.isDockerDesktop():
                    match = False
                    # Find a match
                    for resource in EnvInfo.getDockerDesktopResources():
                        if host_path.startswith(resource):
                            match = True
                            break
                    if not match:
                        logger.error(f"Bind volume from {host_path} is not possible, Docker Desktop configuration is [red]incorrect[/red].")
                        logger.critical(f"You need to modify the [green]Docker Desktop[/green] config and [green]add[/green] this path (or the root directory) in "
                                        f"[magenta]Docker Desktop > Preferences > Resources > File Sharing[/magenta] configuration.")
            # Choose to update fs directory perms if available and depending on user choice
            # if force_sticky_group is set, user choice is bypassed, fs will be updated.
            execute_update_fs = force_sticky_group or (enable_sticky_group and OptionResolver().get(OptionKey.UPDATE_FS_PERMS))
            try:
                if not path.exists():
                    if must_exist:
                        raise CancelOperation(f"{host_path} does not exist on your host.")
                    else:
                        # If the directory is created by exegol, bypass user preference and enable shared perms (if available)
                        execute_update_fs = force_sticky_group or enable_sticky_group
                        mkdir(path)
            except PermissionError:
                logger.error("Unable to create the volume folder on the filesystem locally.")
                logger.critical(f"Insufficient permissions to create the folder: {host_path}")
            except FileExistsError:
                # The volume targets a file that already exists on the file system
                pass
            # Update FS don't work on Windows and only for directory
            if not EnvInfo.is_windows_shell and path.is_dir():
                if execute_update_fs:
                    # Apply perms update
                    FsUtils.setGidPermission(path)
                elif enable_sticky_group:
                    # If user choose not to update, print tips.
                    # Names the tier that disabled the feature.
                    resolved_fs_perms = OptionResolver().resolve(OptionKey.UPDATE_FS_PERMS)
                    # The config.yml hint depends on the config.yml value only, not the resolved one.
                    saved_fs_perms = OptionResolver().userConfigValue(OptionKey.UPDATE_FS_PERMS)
                    logger.warning(f"The file sharing permissions between the container and the host will not be applied automatically by Exegol. "
                                   f"(disabled by the [blue]{resolved_fs_perms.source.value}[/blue] configuration; use the [green]--update-fs[/green] option"
                                   f"{' or set [green]auto_update_workspace_fs: true[/green] in your config' if not saved_fs_perms else ''} to enable the feature)")
        mount = Mount(container_path, str(host_path), read_only=read_only, type=volume_type)
        # Exact-duplicate guard: list options concatenate tiers, so a profile and `-V` can add
        # the same mount. A partial match is a tier conflict and is kept. Compared key by key:
        # mounts parsed from a live container carry an extra Propagation key.
        for existing_mount in self.__mounts:
            if (existing_mount.get("Source") == mount.get("Source") and
                    existing_mount.get("Target") == mount.get("Target") and
                    existing_mount.get("ReadOnly") == mount.get("ReadOnly") and
                    existing_mount.get("Type") == mount.get("Type")):
                logger.verbose("Volume already setup. Skipping.")
                return
        self.__mounts.append(mount)

    def removeVolume(self, host_path: Optional[str] = None, container_path: Optional[str] = None) -> bool:
        """Remove a volume from the container configuration (Only before container creation)"""
        if host_path is None and container_path is None:
            # This is a dev problem
            raise ValueError('At least one parameter must be set')
        for i in range(len(self.__mounts)):
            # For each Mount object compare the host_path if supplied or the container_path si supplied
            if host_path is not None and self.__mounts[i].get("Source") == host_path:
                # When the right object is found, remove it from the list
                self.__mounts.pop(i)
                return True
            if container_path is not None and self.__mounts[i].get("Target") == container_path:
                # When the right object is found, remove it from the list
                self.__mounts.pop(i)
                return True
        return False

    def getVolumes(self) -> List[Mount]:
        """Volume config getter"""
        return self.__mounts

    def __addDevice(self,
                    device_source: str,
                    device_dest: Optional[str] = None,
                    readonly: bool = False,
                    mknod: bool = False) -> None:
        """Add a device to the container configuration"""
        if device_dest is None:
            device_dest = device_source
        perm = 'r'
        if not readonly:
            perm += 'w'
        if mknod:
            perm += 'm'
        device_config = f"{device_source}:{device_dest}:{perm}"
        # Exact-duplicate guard (tiers concatenate), on the full value including permissions,
        # so a differing dest or permission is never merged.
        if device_config in self.__devices:
            logger.verbose("Device already setup. Skipping.")
            return
        self.__devices.append(device_config)

    def removeDevice(self, device_source: str) -> bool:
        """Remove a device from the container configuration (Only before container creation)"""
        for i in range(len(self.__devices)):
            # For each device, compare source device
            if self.__devices[i].split(':')[0] == device_source:
                # When found, remove it from the config list
                self.__devices.pop(i)
                return True
        return False

    def getDevices(self) -> List[str]:
        """Devices config getter"""
        return self.__devices

    def addEnv(self, key: str, value: str) -> None:
        """Add or update an environment variable to the container configuration"""
        self.__envs[key] = value

    def removeEnv(self, key: str) -> bool:
        """Remove an environment variable to the container configuration (Only before container creation)"""
        try:
            self.__envs.pop(key)
            return True
        except KeyError:
            # When the Key is not present in the dictionary
            return False

    def getEnvs(self) -> Dict[str, str]:
        """Envs config getter"""
        # When using host network mode, service port must be randomized to avoid conflict between services and container
        if self.isNetworkHost():
            self.addEnv(self.ExegolEnv.randomize_service_port.value, "true")
        return self.__envs

    def getShellEnvs(self) -> List[str]:
        """Overriding envs when opening a shell"""
        # Resolved once so the shell reads below agree.
        shell = OptionResolver().get(OptionKey.SHELL)
        result = [f"{self.ExegolEnv.user_shell.value}={shell}"]
        # Select default shell to use
        if shell in ["zsh", "bash", "sh"]:
            # tmux dynamically set SHELL variable and should be excluded here
            result.append(f"SHELL=/bin/{shell}")
        # Update X11 DISPLAY socket if needed
        if self.__enable_gui:
            current_display = GuiUtils.getDisplayEnv()

            # If the default DISPLAY environment in the container is not the same as the DISPLAY of the user's session,
            # the environment variable will be updated in the exegol shell.
            if current_display and self.__envs.get('DISPLAY', '') != current_display:
                # This case can happen when the container is created from a local desktop
                # but exegol can be launched from remote access via ssh with X11 forwarding
                # (Be careful, an .Xauthority file may be needed).
                result.append(f"DISPLAY={current_display}")
        # Handle shell logging
        # If shell logging was enabled at container creation, it'll always be enabled for every shell.
        # If not, it can be activated per shell basic
        if self.__shell_logging or OptionResolver().get(OptionKey.LOG):
            result.append(f"{self.ExegolEnv.shell_logging_method.value}={OptionResolver().get(OptionKey.LOG_METHOD)}")
            result.append(f"{self.ExegolEnv.shell_logging_compress.value}={OptionResolver().get(OptionKey.LOG_COMPRESS)}")
        # Overwrite env from user parameters
        for env in OptionResolver().get(OptionKey.ENVS):
            key, value = self.__parseUserEnv(env)
            logger.debug(f"Add env to current shell: {env}")
            result.append(f"{key}={value}")
        return result

    def loadHostsFile(self, hosts_file_path: str) -> None:
        """Load hosts file into extra_hosts (format: IP HOSTNAME [HOSTNAME2 ...]).
        Supports multiple spaces/tabs as separators and multiple hostnames per IP."""
        if not hosts_file_path:
            return
        hosts_path = Path(FsUtils.resolvStrPath(hosts_file_path))
        if not hosts_path.exists():
            logger.critical(f"Hosts file not found: {hosts_file_path}")
            return
        if not hosts_path.is_file():
            logger.critical(f"Invalid hosts file path: {hosts_file_path}")
            return
        try:
            with open(hosts_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    # Remove leading/trailing whitespace
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Remove inline comments
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    # Parse line using regex to handle multiple spaces/tabs
                    # Format: IP HOSTNAME [HOSTNAME2 HOSTNAME3 ...]
                    parts = re.split(r'[\s\t]+', line)
                    if len(parts) < 2:
                        logger.warning(f"Invalid hosts entry at line {line_num}: {line}")
                        continue
                    ip = parts[0]
                    # Add all hostnames (parts[1:]) for this IP
                    for hostname in parts[1:]:
                        if hostname:  # Skip empty strings
                            self.setExtraHost(hostname, ip)
        except Exception as e:
            logger.critical(f"Error reading hosts file: {e}")

    async def addPort(self,
                      port_host: int,
                      port_container: Union[int, str],
                      protocol: str = 'tcp',
                      host_ip: str = '0.0.0.0') -> None:
        """Add port NAT config, only applicable on bridge network mode."""
        if self.isNetworkHost():
            logger.warning("Port sharing is configured, disabling the host network mode.")
            await self.setNetworkMode(self.__fallback_network_mode)
        if protocol.lower() not in ['tcp', 'udp', 'sctp']:
            raise ProtocolNotSupported(f"Unknown protocol '{protocol}'")
        logger.debug(f"Adding port {host_ip}:{port_host} -> {port_container}/{protocol}")
        # Casting type because at this stage, the data is only controlled by the wrapper itself.
        existing_config = self.__ports.get(f"{port_container}/{protocol}", [])
        assert type(existing_config) is list
        # Exact-duplicate guard (tiers concatenate): the whole (host_ip, port_host) tuple is
        # compared so distinct publishes are kept. After protocol validation on purpose.
        if (host_ip, port_host) in existing_config:
            logger.verbose("Port already setup. Skipping.")
            return
        existing_config.append((host_ip, port_host))
        self.__ports[f"{port_container}/{protocol}"] = existing_config

    def getPorts(self) -> Dict[str, Optional[Union[int, Tuple[str, int], List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]]]]]:
        """Ports config getter"""
        return self.__ports

    def __removePort(self, container_port: Union[int, str], protocol: str = 'tcp') -> None:
        self.__ports.pop(f"{container_port}/{protocol}", None)

    def addLabel(self, key: str, value: str) -> None:
        """Add a custom label to the container configuration"""
        self.__labels[key] = value

    def removeLabel(self, key: str) -> bool:
        """Remove a custom label from the container configuration (Only before container creation)"""
        try:
            self.__labels.pop(key)
            return True
        except KeyError:
            # When the Key is not present in the dictionary
            return False

    def getLabels(self) -> Dict[str, str]:
        """Labels config getter"""
        # Update metadata (from getter method) to the labels (on container creation)
        for label_name, refs in self.__label_metadata.items():  # Getter
            data = getattr(self, refs[1])()
            if data is not None:
                self.addLabel(label_name, data)
        return self.__labels

    def isWrapperStartShared(self) -> bool:
        """Return True if the /.exegol/spawn.sh is a volume from the up-to-date wrapper script."""
        return self.__wrapper_start_enabled

    # ===== Metadata labels getter / setter section =====

    def setCreationDate(self, creation_date: str) -> None:
        """Set the container creation date parsed from the labels of an existing container."""
        self.__creation_date = creation_date

    def getCreationDate(self) -> str:
        """Get container creation date.
        If the creation has not been set before, init as right now."""
        if self.__creation_date is None:
            self.__creation_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        return self.__creation_date

    def setBackupHistory(self, backup_history: Optional[str]) -> None:
        """Set the container backup history parsed from the labels of an existing container."""
        self.__backup_history = backup_history

    def getBackupHistory(self) -> Optional[str]:
        """Get container backup history.
        If no backup history has been supplied, returns None."""
        return self.__backup_history

    def setSentinelProfile(self, profile: Optional[str]) -> None:
        """Set the container sentinel profile parsed from the labels of an existing container."""
        self.__sentinel_profile = profile

    def getSentinelProfile(self) -> Optional[str]:
        """Get the container sentinel profile.
        If no sentinel profile has been supplied, returns None."""
        return self.__sentinel_profile

    def setSentinelStrategy(self, strategy: Optional[str]) -> None:
        """Set the container sentinel update strategy parsed from the labels of an existing container.
        Stores the internal strategy KEY (e.g. 'on_restart' / 'disabled'), never the display name."""
        self.__sentinel_strategy = strategy

    def getSentinelStrategy(self) -> Optional[str]:
        """Get the container sentinel update strategy (internal key).
        If no strategy has been supplied, returns None."""
        return self.__sentinel_strategy

    def setComment(self, comment: str) -> None:
        """Set the container comment parsed from the labels of an existing container."""
        self.__comment = comment

    def getComment(self) -> Optional[str]:
        """Get the container comment.
        If no comment has been supplied, returns None."""
        return self.__comment

    def setPasswd(self, passwd: str) -> None:
        """Set the container root password parsed from an existing container's labels.

        Storing it in a label is acceptable: reading a label needs the docker socket, which
        already grants access to the container without the password.
        """
        self.__passwd = passwd

    def getPasswd(self) -> Optional[str]:
        """
        Get the container password.
        """
        return self.__passwd

    def getUsername(self) -> str:
        """
        Get the container username.
        """
        return self.__username

    # ===== User parameter parsing section =====

    async def addRawVolume(self, volume_string: str) -> None:
        """Add a volume to the container configuration from raw text input.
        Expected format is one of:
        /source/path:/target/mount:rw
        C:\\source\\path:/target/mount:ro
        ./relative/path:target/mount"""
        logger.debug(f"Parsing raw volume config: {volume_string}")
        parsing = re.match(r'^((\w:|\.|~)?([\\/][\w .,:\-|()&;]*)+):(([\\/][\w .,\-|()&;]*)+)(:(ro|rw))?$', volume_string)
        if parsing:
            host_path = parsing.group(1)
            container_path = parsing.group(4)
            mode = parsing.group(7)
            if mode is None or mode == "rw":
                readonly = False
            elif mode == "ro":
                readonly = True
            else:
                logger.error(f"Error on volume config, mode: {mode} not recognized.")
                readonly = False
            full_host_path = EnvInfo.expand_user(host_path)
            logger.debug(
                f"Adding a volume from '{full_host_path.as_posix()}' to '{container_path}' as {'readonly' if readonly else 'read/write'}")
            try:
                self.addVolume(full_host_path, container_path, read_only=readonly)
            except CancelOperation as e:
                logger.error(f"The following volume couldn't be created [magenta]{volume_string}[/magenta]. {e}")
                if not await ExegolRich.Confirm("Do you want to continue without this volume ?", False):
                    exit(0)
        else:
            logger.critical(f"Volume '{volume_string}' cannot be parsed. Exiting.")

    def addUserDevice(self, user_device_config: str) -> None:
        """Add a device from a user parameters"""
        if (EnvInfo.isDockerDesktop() or EnvInfo.isOrbstack()) and user_device_config not in self.__whitelist_dd_devices:
            if not user_device_config.startswith("/dev/loop"):
                if EnvInfo.isDockerDesktop():
                    logger.warning("Docker desktop (Windows & macOS) does not support USB device passthrough.")
                    logger.verbose("Official doc: https://docs.docker.com/desktop/faqs/#can-i-pass-through-a-usb-device-to-a-container")
                elif EnvInfo.isOrbstack():
                    logger.warning("Orbstack does not support (yet) USB device passthrough.")
                    logger.verbose("Official doc: https://docs.orbstack.dev/machines/#usb-devices")
                logger.critical("Device configuration cannot be applied, aborting operation.")
        self.__addDevice(user_device_config)

    async def addRawPort(self, user_test_port: str) -> None:
        """Add port config or range of ports from user input.
        Format must be [<host_ipv4>:]<host_port>[-<end_host_port>][:<container_port>[-<end_container_port>]][:<protocol>]
        If host_ipv4 is not set, default to 0.0.0.0
        If container_port is not set, the same port(s) as host port(s) will be used
        If protocol is not set, default is 'tcp'"""
        # Regex to capture port ranges and protocols correctly
        match = re.search(r"^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):)?(\d+)(-(\d+))?:?(\d+)?(-(\d+))?:?(udp|tcp|sctp)?$", user_test_port)
        if match is None:
            logger.critical(f"Incorrect port syntax ({user_test_port}). Please use this format: '{SyntaxFormat.port_sharing}'")
            return
        host_ip = "0.0.0.0" if match.group(2) is None else match.group(2)
        protocol = match.group(9) if match.group(9) else 'tcp'
        try:
            start_host_port = int(match.group(3))
            end_host_port = int(match.group(5)) if match.group(5) else start_host_port
            start_container_port_defined = match.group(6) is not None
            end_container_port_defined = match.group(8) is not None
            start_container_port = int(match.group(6)) if start_container_port_defined else start_host_port
            # If start_container_port is not defined, use end_host_port, otherwise use start_container_port or end_container_port if defined
            if not start_container_port_defined:
                end_container_port = end_host_port
            else:
                end_container_port = int(match.group(8)) if match.group(8) else start_container_port
            # check port consistency
            if (len(range(start_host_port, end_host_port)) != len(range(start_container_port, end_container_port))) or (
                    start_host_port != end_host_port and (not start_container_port_defined and end_container_port_defined)) or (
                    start_host_port != end_host_port and (start_container_port_defined and not end_container_port_defined)):
                logger.info(
                    f"Port sharing configuration does not respect standard usage ({user_test_port}). The configuration in the 'Container sumamry' below will be applied. Please consult the help section for more information on using the -p/--port option.")
            # Check if start port is lower than end port
            if end_host_port < start_host_port or end_container_port < start_container_port:
                raise ValueError("End port cannot be less than start port.")
            # Check if any port in the range exceeds the valid range
            if end_host_port > 65535 or end_container_port > 65535:
                raise ValueError(f"The syntax for opening port in NAT is incorrect. The ports must be numbers between 0 and 65535. ({end_host_port}:{end_container_port})")
        except ValueError as e:
            logger.critical(e)
            return
        for host_port, container_port in zip(range(start_host_port, end_host_port + 1), range(start_container_port, end_container_port + 1)):
            await self.addPort(host_port, container_port, protocol=protocol, host_ip=host_ip)

    def addRawEnv(self, env: str) -> None:
        """Parse and add an environment variable from raw user input"""
        key, value = self.__parseUserEnv(env)
        self.addEnv(key, value)

    @classmethod
    def __parseUserEnv(cls, env: str) -> Tuple[str, str]:
        env_args = env.split('=')
        key = env_args[0]
        if len(env_args) < 2:
            value = EnvInfo.get_env(env, '')
            if not value:
                logger.critical(f"Incorrect env syntax ({env}). Please use this format: KEY=value")
            else:
                logger.success(f"Using system value for env {env}.")
        else:
            value = '='.join(env_args[1:])
        return key, value

    # ===== Display / text formatting section =====

    def getTextFeatures(self, verbose: bool = False) -> str:
        """Text formatter for features configurations (Privileged, X11, Network, Timezone, Shares)
        Print config only if they are different from their default config (or print everything in verbose mode)"""
        result = ""
        if verbose or self.__privileged:
            result += f"{getColor(not self.__privileged)[0]}Privileged: {'On :fire:' if self.__privileged else '[green]Off :heavy_check_mark:[/green]'}{getColor(not self.__privileged)[1]}{os.linesep}"
        if verbose or self.isDesktopEnabled():
            result += f"{getColor(self.isDesktopEnabled())[0]}Remote Desktop: {self.getDesktopConfig()}{getColor(self.isDesktopEnabled())[1]}{os.linesep}"
        if verbose or not self.__enable_gui:
            result += f"{getColor(self.__enable_gui)[0]}Console GUI: {boolFormatter(self.__enable_gui)}{getColor(self.__enable_gui)[1]}{os.linesep}"
        if verbose or not self.isNetworkHost():
            result += f"[green]Network mode: [/green]{self.getTextNetworkMode()}{os.linesep}"
        if self.__vpn_path is not None:
            result += f"[green]VPN: [/green]{self.getVpnName()}{os.linesep}"
        if verbose or not self.__share_timezone:
            result += f"{getColor(self.__share_timezone)[0]}Share timezone: {boolFormatter(self.__share_timezone)}{getColor(self.__share_timezone)[1]}{os.linesep}"
        if verbose or not self.__exegol_resources:
            result += f"{getColor(self.__exegol_resources)[0]}Exegol resources: {boolFormatter(self.__exegol_resources)}{getColor(self.__exegol_resources)[1]}{os.linesep}"
        if verbose or not self.__my_resources:
            result += f"{getColor(self.__my_resources)[0]}My resources: {boolFormatter(self.__my_resources)}{getColor(self.__my_resources)[1]}{os.linesep}"
        if verbose or self.__shell_logging:
            result += f"{getColor(self.__shell_logging)[0]}Shell logging: {boolFormatter(self.__shell_logging)}{getColor(self.__shell_logging)[1]}{os.linesep}"
        if verbose or self.isSentinelEnable():
            result += f"{getColor(self.isSentinelEnable())[0]}Sentinel: {boolFormatter(self.isSentinelEnable())}{getColor(self.isSentinelEnable())[1]}{os.linesep}"
        result = result.strip()
        if not result:
            return "[i][bright_black]Default configuration[/bright_black][/i]"
        return result

    def getVpnConfigPath(self) -> Optional[Path]:
        """Get VPN Config path"""
        return self.__vpn_path

    def getVpnName(self) -> str:
        """Get VPN Config name"""
        if self.__vpn_path is None:
            return "[bright_black]N/A[/bright_black]   "
        return f"[deep_sky_blue3]{self.__vpn_path.name}[/deep_sky_blue3]"

    def getDesktopConfig(self) -> str:
        """Get Desktop feature status / config"""
        if not self.isDesktopEnabled():
            return boolFormatter(False)
        config = (f"{self.__desktop_proto}://"
                  f"{'localhost' if self.__desktop_host == '127.0.0.1' else self.__desktop_host}:{self.__desktop_port}")
        return f"[link={config}][deep_sky_blue3]{config}[/deep_sky_blue3][/link]"

    def getTextGuiSockets(self) -> str:
        if self.__enable_gui:
            return f"[bright_black]({' + '.join(self.__gui_engine)})[/bright_black]"
        else:
            return ""

    def getTextNetworkMode(self) -> str:
        """Network mode, text getter"""
        network_mode = ', '.join([n.getTextNetworkMode() for n in self.__networks]) if len(self.__networks) > 0 else f"[bright_black]{ExegolNetworkMode.disabled.value}[/bright_black]"
        if self.__vpn_path:
            network_mode += " (with VPN)"
        return network_mode

    def getTextCreationDate(self) -> str:
        """Get the container creation date.
        If the creation date has not been supplied on the container, return empty string."""
        if self.__creation_date is None:
            return ""
        return datetime.strptime(self.__creation_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y %H:%M")

    def getTextMounts(self, verbose: bool = False) -> str:
        """Text formatter for Mounts configurations. The verbose mode does not exclude technical volumes."""
        result = ''
        for mount in self.__mounts:
            # Not showing technical mounts
            if not verbose and mount.get('Target') in self.__verbose_only_mounts:
                continue
            read_only_text = f"[bright_black](RO)[/bright_black] " if verbose else ''
            read_write_text = f"[orange3](RW)[/orange3] " if verbose else ''
            result += f"{read_only_text if mount.get('ReadOnly') else read_write_text}{mount.get('Source')} :right_arrow: {mount.get('Target')}{os.linesep}"
        return result

    def getTextDevices(self, verbose: bool = False) -> str:
        """Text formatter for Devices configuration. The verbose mode show full device configuration."""
        result = ''
        for device in self.__devices:
            if verbose:
                result += f"{device}{os.linesep}"
            else:
                src, dest = device.split(':')[:2]
                if src == dest:
                    result += f"{src}{os.linesep}"
                else:
                    result += f"{src}:right_arrow:{dest}{os.linesep}"
        return result

    def getTextEnvs(self, verbose: bool = False) -> str:
        """Text formatter for Envs configuration. The verbose mode does not exclude technical variables."""
        result = ''
        for k, v in self.__envs.items():
            # Blacklist technical variables, only shown in verbose
            if not verbose and k in list(self.__static_gui_envs.keys()) + [v.value for v in self.ExegolEnv] + self.__verbose_only_envs:
                continue
            result += f"{k}={v}{os.linesep}"
        return result

    def getTextPorts(self, is_running: bool = True) -> str:
        """Text formatter for Ports configuration.
        Dict Port key = container port/protocol
        Dict Port Values:
          None = Random port
          int = open port on the host
          tuple = (host_ip, port)
          list of int = open multiple host port
          list of dict = open one or more ports on host, key ('HostIp' / 'HostPort') and value ip or port"""

        # Port configuration cannot be fetched from docker until container startup
        if self.isNetworkBridge() and len(self.__ports) == 0 and not is_running:
            return "[bright_black]Container must be started first[/bright_black]"

        result = ''

        start_host_ip: Optional[str] = None
        start_host_port: Optional[Union[int, str]] = None
        previous_host_port: Optional[Union[str, int]] = None

        start_container_protocol: Optional[str] = None
        start_container_port: Optional[int] = None
        previous_container_port: Optional[int] = None

        previous_entry = None

        for container_config, host_config in self.__ports.items():
            # Parse config
            current_container_port = int(container_config.split('/')[0])
            current_container_protocole = container_config.split('/')[-1]
            # We might have multiple host context config at the same time for the same container config
            current_host_contexts: List[Dict[str, Union[str, int]]] = []
            # Init range context, container side
            if start_container_port is None:
                start_container_port = current_container_port
                previous_container_port = current_container_port
                start_container_protocol = current_container_protocole

            # Parse host config multiple format
            if host_config is None:
                current_host_contexts.append({"ip": "0.0.0.0",
                                              "port": "<Random port>"})
            else:
                if type(host_config) is list:
                    host_configs: List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]] = host_config
                else:
                    host_configs = cast(List[Union[int, Tuple[str, int], Dict[str, Union[int, str]]]], [host_config])

                for current_host_config in host_configs:
                    if type(current_host_config) is int:
                        current_host_contexts.append({"ip": "0.0.0.0",
                                                      "port": current_host_config})
                    elif type(current_host_config) is tuple:
                        assert len(current_host_config) == 2
                        current_host_contexts.append({"ip": current_host_config[0],
                                                      "port": int(current_host_config[1])})
                    elif type(current_host_config) is dict:
                        sub_port = current_host_config.get('HostPort')
                        if sub_port is None:
                            sub_port = "<Random port>"
                        elif type(sub_port) is str:
                            sub_port = int(sub_port)
                        current_host_contexts.append({"ip": current_host_config.get('HostIp', '0.0.0.0'),
                                                      "port": sub_port})
                    else:
                        logger.debug(f"Unknown port config: {type(host_config)}={host_config} :right_arrow: {container_config}")
                        continue

            for current_context in current_host_contexts:
                current_host_port = current_context.get("port")
                current_host_ip: Optional[str] = cast(Optional[str], current_context.get('ip'))
                if current_host_port is None or current_host_ip is None:
                    continue

                # Init range context
                if start_host_port is None:
                    start_host_port = current_host_port
                    previous_host_port = current_host_port
                    start_host_ip = current_host_ip
                # Check if range continue
                elif (previous_host_port is not None and
                      previous_container_port is not None and
                      start_host_ip == current_host_ip and
                      current_container_protocole == start_container_protocol and
                      (current_host_port == previous_host_port or
                       (type(previous_host_port) is int and current_host_port == previous_host_port + 1)) and
                      (current_container_port == previous_container_port or
                       (type(previous_container_port) is int and current_container_port == previous_container_port + 1))):
                    previous_host_port = current_host_port
                    previous_container_port = current_container_port
                # If range exit, submit previous entry + reset new range context
                else:
                    # Register previous range
                    if previous_entry:
                        result += previous_entry
                    # reset context host and container side
                    start_host_port = current_host_port
                    previous_host_port = current_host_port
                    start_host_ip = current_host_ip
                    start_container_port = current_container_port
                    previous_container_port = current_container_port
                    start_container_protocol = current_container_protocole

                # Register last range
                range_host_port = ""
                if type(start_host_port) is int:
                    assert type(previous_host_port) is int
                    range_host_port = "" if previous_host_port - start_host_port <= 0 else f"-{previous_host_port}"
                if previous_container_port is not None and start_container_port is not None:
                    range_container_port = "" if previous_container_port - start_container_port <= 0 else f"-{previous_container_port}"
                    previous_entry = (f"{start_host_ip}:{start_host_port}{range_host_port} :right_arrow: "
                                      f"{start_container_port}{range_container_port}/{start_container_protocol}{os.linesep}")

        # Submit last entry is any
        if previous_entry:
            result += previous_entry

        return result

    def getTextExtraHosts(self, verbose: bool = False) -> str:
        """Text formatter for Extra Hosts configuration.
        Excludes self.hostname as it is automatically added in Host network mode."""
        result = ''
        for hostname, ip in self.__extra_host.items():
            # Skip the container's hostname as it's auto-added in Host network mode
            if not verbose and hostname == self.hostname:
                continue
            result += f"{hostname} :right_arrow: {ip}{os.linesep}"
        return result

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"Privileged: {self.__privileged}{os.linesep}" \
               f"Capabilities: {self.__capabilities}{os.linesep}" \
               f"Sysctls: {self.__sysctls}{os.linesep}" \
               f"X: {self.__enable_gui}{os.linesep}" \
               f"TTY: {self.tty}{os.linesep}" \
               f"Network host: {self.getTextNetworkMode()}{os.linesep}" \
               f"Ports: {self.__ports}{os.linesep}" \
               f"Share timezone: {self.__share_timezone}{os.linesep}" \
               f"Common resources: {self.__my_resources}{os.linesep}" \
               f"Envs ({len(self.__envs)}): {os.linesep.join(self.__envs)}{os.linesep}" \
               f"Labels ({len(self.__labels)}): {os.linesep.join(self.__labels)}{os.linesep}" \
               f"Shares ({len(self.__mounts)}): {os.linesep.join([str(x) for x in self.__mounts])}{os.linesep}" \
               f"Devices ({len(self.__devices)}): {os.linesep.join(self.__devices)}{os.linesep}" \
               f"VPN: {self.getVpnName()}"

    def printConfig(self) -> None:
        """Log current object state, debug only"""
        logger.info(f"Current container config :{os.linesep}{self}")
