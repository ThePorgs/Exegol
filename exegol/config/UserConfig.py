import re
from pathlib import Path
from typing import Any, Dict, List, Pattern, Set, Tuple, cast

import yaml

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.console.ConsoleFormat import boolFormatter
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.model.ExegolNetwork import ExegolNetworkMode
from exegol.utils.DataFileUtils import DataFileUtils
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import mkdir
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.NetworkUtils import NetworkUtils
from exegol.utils.RegexUtils import is_valid_sentinel_git_url, is_valid_sentinel_ref, is_valid_sentinel_source_key
from exegol.utils.SizeUtils import SPLUNK_DEFAULT_TRUNCATE, parse_size_to_bytes


# The static leading block of UserConfig._build_file_content(): every byte is a literal, so it
# is identical in every config.yml this wrapper has ever generated, whatever the operator's
# paths are. A config.yml whose entire content is a proper prefix of it is a write that stopped
# part-way through the header -- a torn write -- and never a document an operator composed.
# See DataFileUtils._parse_config for what that distinction decides.
_TEMPLATE_HEADER = """# Exegol configuration
# Full documentation: https://docs.exegol.com/wrapper/configuration#configuration-file

# Volume path can be changed at any time but existing containers will not be affected by the update
volumes:
"""


# The end-of-template witness, and the other half of the provenance argument the header makes.
# A config.yml that reached the end of the bytes this wrapper generates is missing nothing below
# the cut, so an unterminated final line in it is a lost newline rather than a write that
# stopped -- see DataFileUtils._parse_config for why that second witness is required before "no
# trailing newline" may refuse anything.
#
# Not the trailing literal block, which was the wrong anchor: it is English prose and a URL, in
# a part of the file the template invites operators to edit, so the witness held only while they
# left it byte-for-byte alone. Deleting the `custom_images` block, rewording the footer comment
# or inlining `custom_images: []` each re-armed the wholesale refusal, with every key defaulted
# permanently, because __load_file suppresses the upgrade for a refused config so the state
# never self-heals.
#
# So the witness is two tolerant tests, either of which proves the end was reached:
#
# 1. The last key the template writes is present. Matching the key rather than the block
#    survives rewording the comment above it, inlining `[]`, and uncommenting the example line
#    below it. The quoted spelling is matched, like `__last_declaration`: YAML permits
#    `"custom_images": []`, and the operator's file is not the wrapper's output. No drift
#    tripwire can catch a gap here -- they compare against the wrapper's own output, which is
#    always the plain spelling -- so the parametrised spelling test is what covers it.
_TEMPLATE_LAST_KEY = re.compile(r"""(?m)^[ \t]*(?:'|")?custom_images(?:'|")?[ \t]*:""")

# 2. Or the document declares the last key the template writes above that one -- the last entry
#    of this tuple. This answers the deletion case, which no tail-shaped witness can: a
#    truncation removes a suffix, so a document declaring the last of these ran past every other
#    one by construction, and whatever it is missing is below them all.
#
#    The order of this tuple is load-bearing: it is the order the template writes the keys in,
#    and `_reached_template_end` reads `[-1]`. A tripwire test pins the tuple by equality against
#    the generated template, which is what keeps `[-1]` actually last when a key is added -- but
#    that pins only the constant, not the operator's own ordering, which `_reached_template_end`
#    checks against the document's text. Why the earlier entries are carried rather than all
#    required, and the residue the check cannot decide, are documented there.
#
#    Two deliberate omissions. `config.custom_images` is the key test 1 is about. Anything below
#    `config.sentinel.sources` is operator-populated -- they add, rename and remove sources -- so
#    requiring it would make this test fail for the operators it exists to serve; the `sources`
#    key itself is always written and so is required.
#
#    A literal for the same reason the header is: `_build_file_content()` interpolates live state
#    and resolves a dynamic default as a side effect, so calling it while parsing would mutate
#    the object under the parser.
_TEMPLATE_KEY_PATHS: Tuple[Tuple[str, ...], ...] = (
    ('volumes',),
    ('volumes', 'my_resources_path'),
    ('volumes', 'exegol_resources_path'),
    ('volumes', 'exegol_images_path'),
    ('volumes', 'private_workspace_path'),
    ('volumes', 'sentinel_path'),
    ('config',),
    ('config', 'auto_check_update'),
    ('config', 'interactive_update_warning'),
    ('config', 'auto_remove_image'),
    ('config', 'auto_update_workspace_fs'),
    ('config', 'default_start_shell'),
    ('config', 'enable_exegol_resources'),
    ('config', 'shell_logging'),
    ('config', 'shell_logging', 'always_enable'),
    ('config', 'shell_logging', 'logging_method'),
    ('config', 'shell_logging', 'enable_log_compression'),
    ('config', 'sentinel'),
    ('config', 'sentinel', 'enabled_by_default'),
    ('config', 'sentinel', 'log_group_gid'),
    ('config', 'sentinel', 'component_path'),
    ('config', 'sentinel', 'default_profile'),
    ('config', 'sentinel', 'update_strategy'),
    ('config', 'sentinel', 'log_rotation'),
    ('config', 'sentinel', 'log_rotation', 'enabled'),
    ('config', 'sentinel', 'log_rotation', 'max_size'),
    ('config', 'sentinel', 'log_rotation', 'max_files'),
    ('config', 'sentinel', 'log_rotation', 'compress'),
    ('config', 'sentinel', 'log_output'),
    ('config', 'sentinel', 'log_output', 'enabled'),
    ('config', 'sentinel', 'log_output', 'max_size'),
    ('config', 'sentinel', 'log_output', 'truncation'),
    ('config', 'sentinel', 'sources'),
    ('config', 'profile'),
    ('config', 'profile', 'component_path'),
    ('config', 'profile', 'sources'),
    ('config', 'profile', 'sources', 'local'),
    ('config', 'profile', 'sources', 'local', 'path'),
    ('config', 'desktop'),
    ('config', 'desktop', 'enabled_by_default'),
    ('config', 'desktop', 'default_protocol'),
    ('config', 'desktop', 'localhost_by_default'),
    ('config', 'network'),
    ('config', 'network', 'default_network'),
    ('config', 'network', 'fallback_network'),
    ('config', 'network', 'exegol_dedicated_range'),
    ('config', 'network', 'exegol_default_netmask'),
)


class UserConfig(DataFileUtils, metaclass=MetaSingleton):
    """This class allows loading user defined configurations"""

    # Static choices
    start_shell_options = {'zsh', 'bash', 'tmux'}
    shell_logging_method_options = {'script', 'asciinema'}
    desktop_available_proto = {'http', 'vnc'}
    # Single source for the `--cap` choices and ContainerProfile's `system.capabilities` typo warning.
    capability_options = {'NET_ADMIN', 'NET_BROADCAST', 'SYS_MODULE', 'SYS_PTRACE', 'SYS_RAWIO',
                           'SYS_ADMIN', 'LINUX_IMMUTABLE', 'MAC_ADMIN', 'SYSLOG', 'ALL'}

    # Log-rotation size default, used by `__init__` and as `_enforceLogRotationMaxSizePositive()`'s fallback.
    _DEFAULT_LOG_ROTATION_MAX_SIZE = "100MB"

    # Inline-output size default, used by `__init__` and as `_enforceLogOutputMaxSize()`'s fallback.
    _DEFAULT_LOG_OUTPUT_MAX_SIZE = "4KB"

    def __init__(self) -> None:
        # Defaults User config
        self.private_volume_path: Path = ConstantConfig.exegol_config_path / "workspaces"
        self.my_resources_path: Path = ConstantConfig.exegol_config_path / "my-resources"
        self.exegol_resources_path: Path = self.__default_resource_location('exegol-resources')
        self.exegol_images_path: Path = self.__default_resource_location('exegol-images')
        # Config
        self.auto_check_updates: bool = True
        self.interactive_update_warning: bool = True
        self.auto_remove_images: bool = True
        self.auto_update_workspace_fs: bool = False
        self.default_start_shell: str = "zsh"
        self.enable_exegol_resources: bool = True
        # Shell logging
        self.shell_logging_method: str = "asciinema"
        self.shell_logging_compress: bool = True
        self.always_enable_shell_logging: bool = False
        # Sentinel
        self.sentinel_path: Path = ConstantConfig.exegol_config_path / "sentinel"
        self.sentinel_profile_path: Path = ConstantConfig.exegol_config_path / "components" / "sentinel"
        self.sentinel_default_profile: str = ""
        self.sentinel_gid: int = -1
        self.sentinel_enabled_by_default: bool = False
        # Sentinel log rotation defaults
        self.sentinel_log_rotation_enabled: bool = True
        # Size in bytes, or a unit string like "100MB" / "512KB" (parsed to bytes).
        self.sentinel_log_rotation_max_size: str = self._DEFAULT_LOG_ROTATION_MAX_SIZE
        self.sentinel_log_rotation_max_files: int = 0
        self.sentinel_log_rotation_compress: bool = True
        # Sentinel inline output capture defaults
        self.sentinel_log_output_enabled: bool = True
        # Size in bytes, or a unit string like "4KB" / "64KB" (parsed to bytes).
        self.sentinel_log_output_max_size: str = self._DEFAULT_LOG_OUTPUT_MAX_SIZE
        # One of: head, tail, both
        self.sentinel_log_output_truncation: str = "both"
        # Sentinel profile sources: name-keyed git:+ref: or path: entries; the key is the
        # directory name under component_path. 'local' is seeded once into config.yml.
        self.sentinel_sources: Dict[str, Dict[str, str]] = {}
        # Whether `sentinel.sources` existed in config.yml; 'local' is seeded only if it did not.
        self.__sentinel_sources_present: bool = False
        self.sentinel_update_strategy: str = SentinelUpdateStrategy.ON_RESTART.value
        # Container profiles, distinct from Sentinel audit profiles and `exegol build` profiles.
        self.profile_component_path: Path = ConstantConfig.exegol_config_path / "components" / "profiles"
        # Container profile sources, same format and parser as `sentinel_sources`.
        self.profile_sources: Dict[str, Dict[str, str]] = {}
        # Whether `profile.sources` existed in config.yml; 'local' is seeded only if it did not.
        self.__profile_sources_present: bool = False
        # Whether the whole `sentinel:` / `profile:` section existed in config.yml. Not the same
        # question as the two `sources`-presence flags above: those drive the YAML seeding of a
        # 'local' entry, these drive the one-time creation of its directory on disk. Keeping them
        # apart means an operator who removed or emptied `sources` inside an existing section gets
        # the entry re-seeded into their file but no directory re-created behind their back.
        # False is the right default for a brand-new config: DataFileUtils.__load_file goes
        # straight to _create_config_file() without parsing, so these keep this value.
        self.__sentinel_section_present: bool = False
        self.__profile_section_present: bool = False
        # Desktop
        self.desktop_default_enable: bool = False
        self.desktop_default_localhost: bool = True
        self.desktop_default_proto: str = "http"
        # Network
        self.network_default_mode: str = ExegolNetworkMode.host.name
        self.network_fallback_mode: str = "nat"
        self.network_dedicated_range: str = ""  # Finding a default network can require a user interaction, loading only if needed from NetworkUtils.get_default_large_range_text().
        self.network_default_netmask: int = 28
        # Custom
        self.custom_images: List[str] = []

        # Dynamic default config
        dynamic_default = {"exegol_dedicated_range": NetworkUtils.get_default_large_range_text}
        super().__init__("config.yml", "yml", dynamic_default)

    def _renderSourcesBlock(self, sources: Dict[str, Dict[str, str]], sources_present: bool,
                            seed_local_path: Path, indent: int = 12) -> str:
        """Render a sources mapping as an indented YAML block for the config template.

        Shared by `sentinel.sources` and `profile.sources`. The default 'local' source is
        seeded only when the key never existed; afterwards the declared sources are kept
        verbatim (possibly empty), so a deletion survives config upgrades.
        """
        if not sources_present:
            sources = {ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY: {"path": str(seed_local_path)}}
        if not sources:
            return ""
        dumped = yaml.dump(sources, default_flow_style=False, sort_keys=True)
        padding = " " * indent
        # Indent each line so it sits under the 'sources:' key.
        return "".join(f"{padding}{line}\n" for line in dumped.splitlines())

    def __render_sentinel_sources_block(self) -> str:
        """Render the Sentinel sources block."""
        return self._renderSourcesBlock(
            self.sentinel_sources, self.__sentinel_sources_present,
            self.sentinel_profile_path / ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)

    def __render_profile_sources_block(self) -> str:
        """Render the container-profile sources block, seeded under the container profile path."""
        return self._renderSourcesBlock(
            self.profile_sources, self.__profile_sources_present,
            self.profile_component_path / ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)

    def __seedComponentDirectories(self) -> None:
        """Create the ``local`` drop-in directory for each section being written for the first time.

        Both sides from one loop, so Sentinel and container profiles cannot drift apart.

        The trigger is the whole section having been absent -- a brand-new config.yml, or one
        predating the section -- not the `sources` sub-key the YAML seeding keys on. An operator
        who has the section but deleted or emptied `sources` inside it gets the `local` entry
        re-seeded into their file and no directory created here.

        Best effort, never fatal: a read-only HOME must not abort the config write, and an
        exception escaping here would put a crash banner on every `exegol` invocation, including
        the ones that would fix it. Never `logger.critical` -- it calls `exit(1)`.

        `FsUtils.mkdir` handles recursive parents and the chown under `sudo exegol`, and already
        swallows `FileExistsError` / `FileNotFoundError` / `PermissionError`; `except OSError`
        covers the rest.
        """
        for section_present, component_path, label in (
                (self.__sentinel_section_present, self.sentinel_profile_path, "sentinel"),
                (self.__profile_section_present, self.profile_component_path, "container profile")):
            if section_present:
                continue
            local_dir = component_path / ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY
            try:
                mkdir(local_dir)
            except OSError as e:
                logger.warning(f"Could not create the {label} 'local' source directory "
                               f"({local_dir}): {e}")

    def _torn_write_header(self) -> str:
        """The template's static header, for the base class's torn-write test.

        Returning it (rather than the base class's ``None``) is what lets a
        ``config.yml`` truncated inside its own comment block be told apart from
        one an operator deliberately commented out: the first is a proper prefix
        of these bytes, the second is not.
        """
        return _TEMPLATE_HEADER

    def _torn_write_last_key(self) -> Pattern[str]:
        """The last key the template writes, as a pattern -- the header's counterpart.

        A document containing it reached the end of the generated bytes, so an
        unterminated final line is a missing newline rather than a write that
        stopped. A PATTERN and not the literal block that used to sit here: that
        block was prose an operator is invited to edit, and editing it re-armed
        the wholesale refusal (see `_TEMPLATE_LAST_KEY`).
        """
        return _TEMPLATE_LAST_KEY

    def _torn_write_required_keys(self) -> Tuple[Tuple[str, ...], ...]:
        """Every key path the template writes ABOVE that last key, IN TEMPLATE ORDER.

        The second, tolerant end-of-template witness. ``_reached_template_end``
        takes the LAST entry: a truncation removes a suffix, so a document
        declaring the last of these ran past all of them and cannot be a write
        that stopped anywhere it would have cost something. This is what lets an
        operator DELETE the trailing block -- the one edit no tail-shaped witness
        can survive -- and still have their config read, and asking for the last
        entry rather than all of them is what lets them delete a SECOND block at
        the same time (see `_TEMPLATE_KEY_PATHS` and ``_reached_template_end``).
        """
        return _TEMPLATE_KEY_PATHS

    def _build_file_content(self) -> str:
        # Dynamic default (if not already defined)
        if not self.network_dedicated_range:
            self.network_dedicated_range = cast(str, self._get_dynamic_default("exegol_dedicated_range"))
        # Preserve the user's declared sentinel sources across a config rewrite/upgrade.
        sentinel_sources_block = self.__render_sentinel_sources_block()
        # Same for container profile sources; seeding 'local' keeps existing profiles loading
        # through the upgrade rewrite.
        profile_sources_block = self.__render_profile_sources_block()
        # Create the drop-in directories the blocks above name. Here rather than in the renderers,
        # which stay pure: this method already mutates live state, is reached on exactly the two
        # occasions that matter (first creation and the upgrade rewrite), and runs once per write
        # because DataFileUtils.__load_file's post-upgrade re-parse does not rebuild the content.
        self.__seedComponentDirectories()

        # Config builder. The static header is a named constant, not inlined,
        # because _torn_write_header() below hands the same bytes to
        # DataFileUtils as the shape a partially-written config.yml would be a
        # prefix of. Inlining it lets the two drift, and the drift is silent:
        # the torn-write detector simply stops recognising torn writes.
        config = _TEMPLATE_HEADER + f"""    # The my-resources volume is a storage space dedicated to the user to customize his environment and tools. This volume can be shared across all exegol containers.
    # Attention! The permissions of this folder (and subfolders) will be updated to share read/write rights between the host (user) and the container (root). Do not modify this path to a folder on which the permissions (chmod) should not be modified.
    my_resources_path: {self._yamlLiteral(self.my_resources_path)}
    
    # Exegol resources are data and static tools downloaded in addition to docker images. These tools are complementary and are accessible directly from the host.
    exegol_resources_path: {self._yamlLiteral(self.exegol_resources_path)}
    
    # Exegol images are the source of the exegol environments. These sources are needed when locally building an exegol image.
    exegol_images_path: {self._yamlLiteral(self.exegol_images_path)}
    
    # When containers do not have an explicitly declared workspace, a dedicated folder will be created at this location to share the workspace with the host but also to save the data after deleting the container
    private_workspace_path: {self._yamlLiteral(self.private_volume_path)}
    
    # Folder on the host where the sentinel logs from the exegol containers will be stored. Please note that these logs may contain sensitive data. (Optional Enterprise feature)
    sentinel_path: {self._yamlLiteral(self.sentinel_path)}

config:
    # Enables automatic check for wrapper updates
    auto_check_update: {self.auto_check_updates}
    
    # Interactively ask the user to acknowledge the available wrapper update
    interactive_update_warning: {self.interactive_update_warning}
    
    # Automatically remove outdated image when they are no longer used
    auto_remove_image: {self.auto_remove_images}
    
    # Automatically modifies the permissions of folders and sub-folders in your workspace by default to enable file sharing between the container with your host user.
    auto_update_workspace_fs: {self.auto_update_workspace_fs}
    
    # Default shell command to start
    default_start_shell: {self._yamlLiteral(self.default_start_shell)}
    
    # Enable Exegol resources
    enable_exegol_resources: {self.enable_exegol_resources}
    
    # Change the configuration of the shell logging functionality
    shell_logging:
        # Always enable shell logging
        always_enable: {self.always_enable_shell_logging}
    
        #Choice of the method used to record the sessions (script or asciinema)
        logging_method: {self._yamlLiteral(self.shell_logging_method)}
        
        # Enable automatic compression of log files (with gzip)
        enable_log_compression: {self.shell_logging_compress}
    
    # Change the configuration of the shell logging functionality (Enterprise optional add-on)
    sentinel:
        # Enable sentinel logging by default on any new container
        enabled_by_default: {self.sentinel_enabled_by_default}
        
        # If the logs agent (e.g. Splunk Universal Forwarder, Elastic lightweight data shipper, Fluentd data collector etc) belongs to a different group than the user, it is possible to share the log files in read-only mode with another group.
        # Use -1 to refer to the group of the user who is using exegol.
        # Only available for UNIX systems
        log_group_gid: {self.sentinel_gid}
        
        # Sentinel profiles configuration path
        component_path: {self._yamlLiteral(self.sentinel_profile_path)}
        
        # Sentinel default profile
        default_profile: {self._yamlLiteral(self.sentinel_default_profile)}

        # When to refresh sentinel sources. One of: {', '.join(SentinelUpdateStrategy.values())}
        update_strategy: {self._yamlLiteral(self.sentinel_update_strategy)}

        # Log rotation settings for sentinel JSONL logs. Used when a profile does not define its own log_rotation block.
        log_rotation:
            # Enable automatic rotation of the sentinel log file
            enabled: {self.sentinel_log_rotation_enabled}

            # Rotate the log file once it reaches this size (bytes, or a unit suffix like "100MB" / "512KB")
            max_size: {self._yamlLiteral(self.sentinel_log_rotation_max_size)}

            # Maximum number of rotated log files to keep (0 = keep all)
            max_files: {self.sentinel_log_rotation_max_files}

            # Compress rotated log files with gzip
            compress: {self.sentinel_log_rotation_compress}

        # Terminal output capture settings for sentinel audit events. Used when a profile does not define its own log_output block.
        log_output:
            # Record the terminal output of every command in its audit event.
            # When disabled, and unless a profile declares an output_capture action, no session recorder is started at all.
            enabled: {self.sentinel_log_output_enabled}

            # Keep at most this much cleaned output per command (bytes, or a unit suffix like "4KB" / "64KB")
            max_size: {self._yamlLiteral(self.sentinel_log_output_max_size)}

            # Which end of an oversized output to keep: head, tail, or both (half the budget on each end)
            truncation: {self._yamlLiteral(self.sentinel_log_output_truncation)}

        # Additional sentinel profile sources. Each key is a source name that doubles as a
        # directory name under component_path (allowed characters: A-Z a-z 0-9 _ -).
        # The reserved key 'core' cannot be redefined. Git URLs accept https, http and
        # SSH (ssh://… or git@host:org/repo.git the host user's SSH keys are used).
        # The '{ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY}' drop-in source is written here on first setup; your
        # customisations are preserved on config upgrades. Remove an entry to disable it.
        sources:
{sentinel_sources_block}        # Examples (uncomment and adapt):
        #    team-profiles:
        #        git: https://example.com/org/sentinel-profiles.git
        #        ref: v1.0            # optional branch, tag or commit SHA
        #    private-ssh:
        #        git: git@github.com:org/sentinel-profiles.git
        #    onprem:
        #        path: /opt/sentinel-profiles

    # Configure your Exegol container profiles (named sets of container-shape defaults).
    profile:
        # Container profile configuration path. Drop a <name>.yml file in the 'local'
        # sub-directory to define a profile; list them with `exegol info --profile`.
        component_path: {self._yamlLiteral(self.profile_component_path)}

        # Additional container profile sources. Each key is a source name that doubles as a
        # directory name under component_path (allowed characters: A-Z a-z 0-9 _ -).
        # The reserved key 'core' cannot be redefined. Git URLs accept https, http and
        # SSH (ssh://… or git@host:org/repo.git the host user's SSH keys are used).
        # The '{ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY}' drop-in source is written here on first setup; your
        # customisations are preserved on config upgrades. Remove an entry to disable it.
        sources:
{profile_sources_block}        # Examples (uncomment and adapt):
        #    team-profiles:
        #        git: https://example.com/org/container-profiles.git
        #        ref: v1.0            # optional branch, tag or commit SHA
        #    private-ssh:
        #        git: git@github.com:org/container-profiles.git
        #    onprem:
        #        path: /opt/container-profiles

    # Configure your Exegol Desktop
    desktop:
        # Enables or not the desktop mode by default.
        # The CLI --desktop option always ENABLES the feature; set this to False to turn the desktop off.
        enabled_by_default: {self.desktop_default_enable}
        
        # Default desktop protocol,can be "http", or "vnc" (additional protocols to come in the future, check online documentation for updates).
        default_protocol: {self._yamlLiteral(self.desktop_default_proto)}
        
        # Desktop service is exposed on localhost by default. If set to true, services will be exposed on localhost (127.0.0.1) otherwise it will be exposed on 0.0.0.0. This setting can be overwritten with --desktop-config
        localhost_by_default: {self.desktop_default_localhost}
    
    # Configure your Exegol networks
    network:
    
        # Default network mode for any new container
        default_network: {self._yamlLiteral(self.network_default_mode)}
        
        # Fallback bridge network mode
        # If the default network (host) mode cannot be used, a "bridge" network will automatically be selected as a replacement. (This mode can be "nat" or "docker")
        fallback_network: {self._yamlLiteral(self.network_fallback_mode)}
        
        # Network range dedicated for exegol containers
        # Each new container using 'nat' network will have a dedicated smaller sub-network within this range (default to the last private /16 class B available)
        exegol_dedicated_range: {self._yamlLiteral(self.network_dedicated_range)}
        
        # Exegol dedicated sub-network netmask.
        # By default, docker creates huge subnets, but exegol overrides this by using a much smaller subnet mask to optimize the use of network slots. (default to /28 with CIDR format)
        exegol_default_netmask: {self.network_default_netmask}

    # List of custom images from non-official private registry. (Enterprise feature) More info here: https://docs.exegol.com/wrapper/configuration#custom-images
    custom_images:
    #  - docker.io/user/registry
"""
        return config

    @staticmethod
    def __default_resource_location(folder_name: str) -> Path:
        local_src = ConstantConfig.src_root_path_obj / folder_name
        if local_src.is_dir():
            # If exegol is clone from github, exegol submodule is accessible from root src
            return local_src
        else:
            # Default path for pip installation
            return ConstantConfig.exegol_config_path / folder_name

    @staticmethod
    def __load_section(parent: Any, name: str) -> Tuple[Dict[str, Any], bool]:
        """Return ``(mapping, refused)`` for the section ``name`` under ``parent``.

        ``refused`` is True only for a non-mapping. An absent, null or empty section is
        silence ("the operator said nothing, use the defaults"); a scalar is a refusal ("the
        operator said something we could not read"). Conflating the two is what made the
        one-line shorthand ``log_output: false`` resolve to ``enabled: true``: the fallback
        for a refused section is the defaults, and for ``sentinel.log_output`` the default is
        the dangerous direction, so the caller has to tell them apart to point the fallback
        the right way -- see ``_process_data``.

        The `or {}` idiom this replaces rescues `None` and `{}` only. A scalar -- `log_output:
        true`, the obvious shorthand for "just turn it on", or `log_output: "4KB"` from a
        misremembered nesting -- passed straight through to `DataFileUtils.__load_config`,
        whose `data.keys()` raises `AttributeError` inside a `try` that catches `TypeError`
        only. UserConfig() is constructed on essentially every wrapper invocation, so a
        one-character YAML typo killed every `exegol` command with a crash banner, including
        the ones that would have explained it.

        Warn and fall back rather than raise, as the `max_size` and `truncation` cases do:
        `config.yml` is one machine-wide file, and a raise here breaks every container start
        on the host.
        """
        if parent is None:
            return {}, False
        section = parent.get(name) if isinstance(parent, dict) else None
        if section is None:
            return {}, False
        if not isinstance(section, dict):
            logger.warning(f"The configuration is incorrect! '{name}' must be a section "
                           f"(a mapping of keys), not a {type(section).__name__} "
                           f"({section!r}). Ignoring it and using the default values.")
            return {}, True
        return section, False

    def _load_sentinel_bool(self, data: Dict[str, Any], key: str, default: bool,
                             label: str, unreadable: bool) -> bool:
        """Load a sentinel boolean that will be copied verbatim into the container.

        ``_load_config_bool`` is a ``cast``, not a conversion: it hands back whatever YAML
        produced, so the quoted form ``enabled: "true"`` leaves the string ``'true'`` on the
        attribute. From here these values are copied verbatim into
        ``SentinelProfileManager``'s machine default and written into the deployed
        ``sentinel_config.json``, which nothing revalidates -- and the in-container consumers
        read them two different ways, so a YAML string inverts the operator's intent whichever
        key it lands on:

        * by identity (``log_output.enabled``): ``spawn.sh``'s recorder gate and
          ``sentinel_logger``'s inline-output gate both do ``is True``, and ``'true' is True``
          is False, so a quoted *enable* silently switched the whole feature off;
        * by truthiness (``log_rotation.enabled``, ``log_rotation.compress``):
          ``rotation_cfg.get("enabled", True)`` is truthy for the non-empty string
          ``"false"``, so a quoted *disable* is silently ignored -- the worse half, since it
          renames and gzips ``logs.json`` out from under a SIEM tailer on a schedule the
          operator declined.

        Both container-side readings are correct on their own terms and stay; the gap was that
        the host never normalised the value it writes. Normalised here rather than at the write
        site so the regenerated ``config.yml`` template, which echoes these attributes straight
        back, is fixed by the same edit. The accepted spellings are exactly Pydantic's lax-bool
        set, because a profile-supplied block goes through
        ``LogOutputConfig``/``LogRotationConfig`` and has always been rescued by that
        coercion.

        Single underscore, like ``_enforceLogRotationMaxSizePositive``, because
        ``ProfileUserConfigTier`` calls it too: a profile-supplied value must go through the
        same helper, config.yml key name and default as a ``config.yml`` one, and for
        ``log_output.enabled`` that helper is this fail-closed one rather than the bare
        ``_load_config_bool`` cast.

        :param unreadable: what to return for a value matching no recognised spelling. The
            callers differ on purpose, which is the point of this parameter.
            ``log_output.enabled`` falls back to **False** -- from ``config.yml`` and from a
            container profile alike -- because guessing "enabled" for a value nobody could
            read would start shipping terminal output to the SIEM on the strength of a typo.
            It is not the only control over that capture: a Sentinel audit profile's own
            ``log_output`` block replaces this whole family wholesale, so what is set here is
            a default -- and a default nobody could read should not be the permissive one.
            ``log_rotation.*`` falls back to its **default (True)**, because an unreadable
            value must not switch off the only bound on ``logs.json``: the same reasoning,
            pointing the other way.
        """
        raw = self._load_config_bool(data, key, default)
        if isinstance(raw, bool):
            return raw
        spelling = str(raw).strip().lower()
        if spelling in {"true", "yes", "on", "y", "t", "1"}:
            logger.warning(f"{label} must be a boolean ({raw!r} is a "
                           f"{type(raw).__name__}); reading it as true. "
                           f"Write `{key}: true`, unquoted.")
            return True
        if spelling in {"false", "no", "off", "n", "f", "0"}:
            logger.warning(f"{label} must be a boolean ({raw!r} is a "
                           f"{type(raw).__name__}); reading it as false. "
                           f"Write `{key}: false`, unquoted.")
            return False
        logger.warning(f"{label} invalid ({raw!r} is a {type(raw).__name__}); "
                       f"using {unreadable}.")
        return unreadable

    def _process_data(self) -> None:
        # Armed by DataFileUtils._parse_config when the document as a whole could not be
        # read: its root is not a mapping, or it did not parse at all. Both leave
        # `_raw_data` an empty dict, so every section reads as absent, indistinguishable
        # from a config that simply does not set them -- the refusal has to be carried
        # explicitly, or the one key whose default is the unsafe direction silently takes it.
        root_refused = self._config_refused

        # Volume section
        volumes_data, volumes_refused = self.__load_section(self._raw_data, "volumes")
        self.my_resources_path = self._load_config_path(volumes_data, 'my_resources_path', self.my_resources_path)
        self.private_volume_path = self._load_config_path(volumes_data, 'private_workspace_path', self.private_volume_path)
        self.exegol_resources_path = self._load_config_path(volumes_data, 'exegol_resources_path', self.exegol_resources_path)
        self.exegol_images_path = self._load_config_path(volumes_data, 'exegol_images_path', self.exegol_images_path)
        self.sentinel_path = self._load_config_path(volumes_data, 'sentinel_path', self.sentinel_path)

        # Config section
        config_data, config_refused = self.__load_section(self._raw_data, "config")
        # Section presence from one membership test on one object, so both sides are derived
        # identically. A refused root or `config` section yields an empty config_data and False
        # flags, which is harmless: a refusal also suppresses the upgrade rewrite in
        # DataFileUtils.__load_file, so nothing is created for a config that could not be read.
        self.__sentinel_section_present = "sentinel" in config_data
        self.__profile_section_present = "profile" in config_data
        self.auto_check_updates = self._load_config_bool(config_data, 'auto_check_update', self.auto_check_updates)
        self.interactive_update_warning = self._load_config_bool(config_data, 'interactive_update_warning', self.interactive_update_warning)
        self.auto_remove_images = self._load_config_bool(config_data, 'auto_remove_image', self.auto_remove_images)
        self.auto_update_workspace_fs = self._load_config_bool(config_data, 'auto_update_workspace_fs', self.auto_update_workspace_fs)
        user_shell = self._load_config_str(config_data, 'default_start_shell', self.default_start_shell)
        # Manually check shell
        if len(user_shell.split(' ')) > 1:
            logger.warning(f"The configuration is incorrect! "
                           f"The user has configured the 'default_start_shell' parameter with the value '{user_shell}' "
                           f"which cannot be more than one word. The default value will be used instead: '{self.default_start_shell}'.")
        else:
            self.default_start_shell = user_shell

        self.enable_exegol_resources = self._load_config_bool(config_data, 'enable_exegol_resources', self.enable_exegol_resources)

        # Shell_logging section
        shell_logging_data, shell_logging_refused = self.__load_section(config_data, "shell_logging")
        self.shell_logging_method = self._load_config_str(shell_logging_data, 'logging_method', self.shell_logging_method, choices=self.shell_logging_method_options)
        self.shell_logging_compress = self._load_config_bool(shell_logging_data, 'enable_log_compression', self.shell_logging_compress)
        self.always_enable_shell_logging = self._load_config_bool(shell_logging_data, 'always_enable', self.always_enable_shell_logging)

        # Sentinel Shell_logging section
        sentinel_data, sentinel_refused = self.__load_section(config_data, "sentinel")
        self.sentinel_enabled_by_default = self._load_config_bool(sentinel_data, 'enabled_by_default', self.sentinel_enabled_by_default)
        self.sentinel_gid = self._load_config_int(sentinel_data, 'log_group_gid', self.sentinel_gid)
        self.sentinel_profile_path = self._load_config_path(sentinel_data, 'component_path', self.sentinel_profile_path)
        self.sentinel_default_profile = self._load_config_str(sentinel_data, 'default_profile', self.sentinel_default_profile)
        self.sentinel_update_strategy = self._load_config_str(sentinel_data, 'update_strategy', self.sentinel_update_strategy, choices=set(SentinelUpdateStrategy.values()))
        # Sentinel log rotation sub-section
        log_rotation_data, log_rotation_refused = self.__load_section(sentinel_data, "log_rotation")
        self.sentinel_log_rotation_enabled = self._load_sentinel_bool(
            log_rotation_data, 'enabled', self.sentinel_log_rotation_enabled,
            'sentinel.log_rotation.enabled', unreadable=self.sentinel_log_rotation_enabled)
        self.sentinel_log_rotation_max_size = self._load_config_str(log_rotation_data, 'max_size', self.sentinel_log_rotation_max_size)
        # Enforce the same `ge=0` rule as LogRotationConfig.max_size, falling back to the
        # default. 0 is legal and means UNLIMITED (never rotate), matching `max_files`;
        # only a negative or unparseable value falls back.
        self.sentinel_log_rotation_max_size = self._enforceLogRotationMaxSizePositive(
            self.sentinel_log_rotation_max_size, field_label="sentinel.log_rotation.max_size (config.yml)")
        self.sentinel_log_rotation_max_files = self._load_config_int(log_rotation_data, 'max_files', self.sentinel_log_rotation_max_files)
        self.sentinel_log_rotation_compress = self._load_sentinel_bool(
            log_rotation_data, 'compress', self.sentinel_log_rotation_compress,
            'sentinel.log_rotation.compress', unreadable=self.sentinel_log_rotation_compress)
        # Sentinel log output sub-section
        log_output_data, log_output_refused = self.__load_section(sentinel_data, "log_output")
        # Disabled, not the True default, for an unreadable value: log_output.enabled: false
        # is the only complete control against a client's secrets reaching their SIEM, and
        # sentinel_logger already falls back to the disable for the same reason. Deliberately
        # the opposite direction from log_rotation above -- see _load_sentinel_bool.
        #
        # The same direction applies one level up, and this branch is why the node guard
        # reports refusal rather than flattening it into "absent". Falling back to the
        # defaults for a refused section means enabled=True here, so `log_output: false` --
        # the obvious operator shorthand, one YAML typo away from the mapping form -- would
        # resolve to "ship this operator's terminal output to their SIEM". Any refused node on
        # the path to the leaf (config -> sentinel -> log_output) disables capture, because
        # none of them can be read to say otherwise, including the document root, whose
        # refusal makes every section below it read as absent rather than refused. The sibling
        # nodes need no such branch: their defaults are already the safe direction.
        if root_refused or config_refused or sentinel_refused or log_output_refused:
            logger.warning("sentinel.log_output could not be read; output capture is DISABLED "
                           "until it is corrected. Write it as a mapping: `log_output:` on its "
                           "own line, then `  enabled: false` indented under it."
                           if not root_refused else
                           # Cause-agnostic on purpose: this arm now covers a
                           # non-mapping root AND a document that did not parse
                           # at all, and the error naming the file and the reason
                           # has already been logged by _parse_config.
                           "The configuration file could not be read (see the error above); "
                           "output capture is DISABLED until it is corrected.")
            self.sentinel_log_output_enabled = False
        else:
            self.sentinel_log_output_enabled = self._load_sentinel_bool(
                log_output_data, 'enabled', self.sentinel_log_output_enabled,
                'sentinel.log_output.enabled', unreadable=False)
        self.sentinel_log_output_max_size = self._load_config_str(log_output_data, 'max_size', self.sentinel_log_output_max_size)
        # Both halves — the positive-value guard and the Splunk advisory — live in the
        # shared helper, so a profile-supplied value gets the identical treatment.
        self.sentinel_log_output_max_size = self._enforceLogOutputMaxSize(
            self.sentinel_log_output_max_size, field_label="sentinel.log_output.max_size (config.yml)")
        self.sentinel_log_output_truncation = self._load_config_str(log_output_data, 'truncation', self.sentinel_log_output_truncation, choices={"head", "tail", "both"})
        # Sentinel source
        self.__parse_sentinel_sources(sentinel_data)

        # Container profile section
        # `or {}`: an empty `profile:` section parses to None.
        profile_data = config_data.get("profile", {}) or {}
        self.profile_component_path = self._load_config_path(profile_data, 'component_path', self.profile_component_path)
        # Container profile sources; a malformed declaration is fatal, as for `sentinel.sources`.
        self.__parse_profile_sources(profile_data)

        # Desktop section
        desktop_data, desktop_refused = self.__load_section(config_data, "desktop")
        self.desktop_default_enable = self._load_config_bool(desktop_data, 'enabled_by_default', self.desktop_default_enable)
        self.desktop_default_proto = self._load_config_str(desktop_data, 'default_protocol', self.desktop_default_proto, choices=self.desktop_available_proto)
        self.desktop_default_localhost = self._load_config_bool(desktop_data, 'localhost_by_default', self.desktop_default_localhost)

        # Network section
        network_data, network_refused = self.__load_section(config_data, "network")
        self.network_default_mode = self._load_config_str(network_data, 'default_network', self.network_default_mode, choices=NetworkUtils.get_options())
        self.network_dedicated_range = self._load_config_str(network_data, 'exegol_dedicated_range')  # Dynamic default
        self.network_default_netmask = NetworkUtils.parse_netmask(self._load_config_str(network_data, 'exegol_default_netmask', str(self.network_default_netmask)), default=self.network_default_netmask)
        if ConstantConfig.completion_mode:
            # The licensed features are never needed to supply completion options,
            # loading the session here would import the whole license stack and slow down every completion
            self.network_fallback_mode = 'docker'
        else:
            # Imported locally to keep the CLI parser light (see the shell completion fast path)
            from exegol.utils.SessionHandler import SessionHandler
            if SessionHandler().pro_feature_access():
                self.network_fallback_mode = self._load_config_str(network_data, 'fallback_network', self.network_fallback_mode, choices={'nat', 'docker'})
            else:
                self.network_fallback_mode = 'docker'

            # Enterprise features
            if SessionHandler().enterprise_feature_access():
                self.custom_images = self._load_config_list_str(config_data, "custom_images")

        # A refused section leaves every key under it missing, so DataFileUtils raises its
        # upgrade flag for all of them and would rewrite config.yml from the current attribute
        # values -- deleting the operator's own line and replacing it with the defaults we just
        # told them we could not read. That turns the warning above into a one-shot: run 1
        # destroys the intent, run 2 onward is silent with nothing left on disk to correct. So
        # suppress the rewrite while anything was refused; see DataFileUtils.__load_file.
        #
        # OR, never assign. DataFileUtils._parse_config arms this flag before calling us when
        # the document root is not a mapping at all, and an assignment here would disarm it on
        # the very run that also silently re-enables capture.
        self._config_refused = self._config_refused or any(
            (volumes_refused, config_refused, shell_logging_refused,
             sentinel_refused, log_rotation_refused, log_output_refused,
             desktop_refused, network_refused))

    def _parseSourcesSection(self, section_data: dict, section_label: str,
                             reserved_keys: Set[str]) -> Tuple[Dict[str, Dict[str, str]], bool]:
        """Parse a `sources:` sub-section into ``({key: spec}, key_was_present)``.

        Shared by `sentinel.sources` and `profile.sources` so the path-traversal, git-URL and
        ref injection guards exist once. ``section_label`` prefixes every message.
        """
        # String-only validation (no git/filesystem I/O) so every CLI call stays fast and offline-safe.
        # If the `sources` key never existed, the template seeds the default 'local' source.
        sources_present = isinstance(section_data, dict) and "sources" in section_data
        # Fresh accumulator per call, so a reload never merges stale entries.
        parsed: Dict[str, Dict[str, str]] = {}
        # `_load_config_dict` only casts: a YAML list or scalar must be reported, not reach .items().
        raw_sources = self._load_config_dict(section_data, 'sources')
        if not isinstance(raw_sources, dict):
            logger.critical(f"{section_label} must be a mapping of source names to "
                            f"{{git: ..., ref: ...}} or {{path: ...}} entries.")
            raw_sources = {}
        # Every invalid entry `continue`s, in case logger.critical does not exit ("raise" method or mock).
        for source_key, source_spec in raw_sources.items():
            # Type guard first: YAML turns unquoted `1234:`, `on:`, `null:` into int/bool/None,
            # which would pass the str()-based key regex and break `component_path / key`.
            # Rejected rather than coerced, so no directory is named 'True' or 'None'.
            if not isinstance(source_key, str):
                logger.critical(f"{section_label}[{source_key!r}] is invalid: a source name must be a "
                                f"string, not {type(source_key).__name__}. Quote it in config.yml, "
                                f"YAML reads an unquoted 1234, on/off, yes/no and null as a number, a "
                                f"boolean or a null rather than as a name.")
                continue
            # Reserved-key guard: 'core' is provisioned by Exegol and must not be shadowed.
            if source_key in reserved_keys:
                logger.critical(f"{section_label}: the key {source_key!r} is reserved for the official "
                                f"Exegol source and cannot be redefined.")
                continue
            # Path-traversal control: the key is a directory name, so '.', '..' and separators are rejected.
            if not is_valid_sentinel_source_key(source_key):
                logger.critical(f"{section_label}[{source_key!r}] is invalid: source names may only "
                                f"contain letters, digits, '_' or '-' (the key is used as a directory name).")
                continue
            if not isinstance(source_spec, dict):
                logger.critical(f"{section_label}[{source_key!r}] is invalid: each source must be a mapping "
                                f"with a 'git' (plus optional 'ref') or a 'path' entry.")
                continue
            if "git" in source_spec:
                git_url = str(source_spec["git"])
                # Any transport is accepted (https, http, git://, SSH). Rejected: whitespace, a
                # leading '-' (option injection) and 'helper::' remotes (arbitrary command).
                if not is_valid_sentinel_git_url(git_url):
                    logger.critical(f"{section_label}[{source_key!r}].git is not a supported git URL: expected an "
                                    f"http(s)://, ssh://, git:// or user@host:path remote with no whitespace.")
                    continue
                git_entry: Dict[str, str] = {"git": git_url}
                if source_spec.get("ref"):
                    ref_value = str(source_spec["ref"])
                    if not is_valid_sentinel_ref(ref_value):
                        logger.critical(f"{section_label}[{source_key!r}].ref is invalid: a ref may only contain "
                                        f"letters, digits, '.', '_', '/' and '-', and cannot start with '-'.")
                        continue
                    git_entry["ref"] = ref_value
                # Optional mode: 'pinned' (default, shallow clone re-cloned on update) or 'dev'
                # (full clone, updated by a safe pull). 'pinned' is not stored.
                if source_spec.get("mode") is not None:
                    mode_value = str(source_spec["mode"])
                    if mode_value not in ("pinned", "dev"):
                        logger.critical(f"{section_label}[{source_key!r}].mode is invalid: expected "
                                        f"'pinned' or 'dev', got {mode_value!r}.")
                        continue
                    if mode_value == "dev":
                        git_entry["mode"] = "dev"
                parsed[source_key] = git_entry
            elif "path" in source_spec:
                raw_path = str(source_spec["path"])
                # A path: source is globbed recursively on every profile load, so refuse foot-guns early.
                if not raw_path.strip():
                    logger.critical(f"{section_label}[{source_key!r}].path is empty.")
                    continue
                try:
                    expanded_path = EnvInfo.expand_user(raw_path)
                except RuntimeError as e:  # pragma: no cover - unresolvable '~' (no home dir)
                    logger.critical(f"{section_label}[{source_key!r}].path cannot be resolved: {e}")
                    continue
                if not expanded_path.is_absolute():
                    logger.critical(f"{section_label}[{source_key!r}].path must be an absolute path "
                                    f"(or start with '~'), got {raw_path!r}.")
                    continue
                # Refuse a filesystem root: a recursive scan would walk the whole filesystem.
                if expanded_path.parent == expanded_path:
                    logger.critical(f"{section_label}[{source_key!r}].path refuses to use the filesystem "
                                    f"root {raw_path!r}: a recursive profile scan from there would walk the "
                                    f"whole filesystem.")
                    continue
                if expanded_path.exists() and not expanded_path.is_dir():
                    logger.critical(f"{section_label}[{source_key!r}].path must be a directory, "
                                    f"got {raw_path!r}.")
                    continue
                parsed[source_key] = {"path": raw_path}
            else:
                logger.critical(f"{section_label}[{source_key!r}] is invalid: it must define either "
                                f"'git' (with an optional 'ref') or 'path'.")
                continue
        return parsed, sources_present

    def __parse_sentinel_sources(self, sentinel_data: dict) -> None:
        """Parse the Sentinel profile sources sub-section."""
        self.sentinel_sources, self.__sentinel_sources_present = self._parseSourcesSection(
            sentinel_data, "sentinel.sources", {ConstantConfig.SENTINEL_CORE_SOURCE_KEY})

    def __parse_profile_sources(self, profile_data: dict) -> None:
        """Parse the container profile sources sub-section.

        'core' is reserved here too, although no official container-profile source exists yet.
        """
        self.profile_sources, self.__profile_sources_present = self._parseSourcesSection(
            profile_data, "profile.sources", {ConstantConfig.SENTINEL_CORE_SOURCE_KEY})

    @staticmethod
    def _enforceLogRotationMaxSizePositive(value: str, field_label: str = "sentinel.log_rotation.max_size") -> str:
        """Mirror the Pydantic `ge=0` constraint on `LogRotationConfig.max_size`.

        Shared by `_process_data()` and `ProfileUserConfigTier`; single underscore so the
        latter can call it. Warns under `field_label` and falls back to the default.

        Non-negative, not strictly positive: 0 spells unlimited (never rotate), which
        `sentinel_logger` honours explicitly, so only a negative or unparseable value is one
        we could not read.
        """
        try:
            if parse_size_to_bytes(value) < 0:
                raise ValueError("must not be negative")
        except ValueError as e:
            logger.warning(f"{field_label} invalid "
                           f"({value!r}: {e}); falling back to the default.")
            return UserConfig._DEFAULT_LOG_ROTATION_MAX_SIZE
        return value

    @staticmethod
    def _enforceLogOutputMaxSize(value: str, field_label: str = "sentinel.log_output.max_size") -> str:
        """Mirror `LogOutputConfig.max_size`'s `gt=0` rule, then repeat its Splunk advisory.

        Shared by `_process_data()` and `ProfileUserConfigTier` so a profile-supplied value
        gets the same guard, the same fallback and the same warning as a `config.yml` one;
        config.yml never builds the model, so neither path inherits them for free.

        Strictly positive, unlike `log_rotation.max_size`: a zero here would emit an
        always-empty field flagged truncated rather than switching the feature off, which is
        what `sentinel.log_output.enabled` is for.

        The advisory is a warning and never a refusal: an operator who has set
        `TRUNCATE = 0` on their source type is entitled to a large inline field. It is worth
        saying because the failure when they have NOT is silent and total — the indexer cuts
        the event mid-JSON, so the record is destroyed rather than shortened.
        """
        try:
            if parse_size_to_bytes(value) <= 0:
                raise ValueError("must be strictly positive")
        except ValueError as e:
            logger.warning(f"{field_label} invalid "
                           f"({value!r}: {e}); falling back to the default.")
            value = UserConfig._DEFAULT_LOG_OUTPUT_MAX_SIZE
        if parse_size_to_bytes(value) >= SPLUNK_DEFAULT_TRUNCATE:
            logger.warning(
                f"{field_label} ({value}) is at or above Splunk's default TRUNCATE of "
                f"{SPLUNK_DEFAULT_TRUNCATE} bytes: this field is embedded in EVERY audit event, "
                f"and an indexer left on that default cuts the event mid-JSON rather than "
                f"shortening it. Set [green]TRUNCATE = 0[/green] on the source type, or "
                f"lower this value.")
        return value

    def get_configs(self) -> List[str]:
        """User configs getter each options"""
        configs = [
            f"User config file: [magenta]{self._file_path}[/magenta]",
            f"Private workspace: [magenta]{self.private_volume_path}[/magenta]",
            "Exegol resources: " + (f"[magenta]{self.exegol_resources_path}[/magenta]"
                                    if self.enable_exegol_resources else
                                    boolFormatter(self.enable_exegol_resources)),
            f"Exegol images: [magenta]{self.exegol_images_path}[/magenta]",
            f"My resources: [magenta]{self.my_resources_path}[/magenta]",
            f"Auto-check updates: {boolFormatter(self.auto_check_updates)}",
            f"Interactive update message: {boolFormatter(self.interactive_update_warning)}",
            f"Auto-remove images: {boolFormatter(self.auto_remove_images)}",
            f"Auto-update fs: {boolFormatter(self.auto_update_workspace_fs)}",
            f"Default start shell: [blue]{self.default_start_shell}[/blue]",
            f"Always enable Shell logging: [blue]{boolFormatter(self.always_enable_shell_logging)}[/blue]",
            f"Shell logging method: [blue]{self.shell_logging_method}[/blue]",
            f"Shell logging compression: {boolFormatter(self.shell_logging_compress)}",
            f"Sentinel enabled by default: [blue]{boolFormatter(self.sentinel_enabled_by_default)}[/blue]",
            f"Sentinel path: [magenta]{self.sentinel_path}[/magenta]",
            f"Sentinel component path: [magenta]{self.sentinel_profile_path}[/magenta]",
            f"Sentinel GID: [blue]{self.sentinel_gid}[/blue]",
            f"Sentinel default profile: [blue]{self.sentinel_default_profile if self.sentinel_default_profile else '[bright_black]None[/bright_black]'}[/blue]",
            f"Container profile component path: [magenta]{self.profile_component_path}[/magenta]",
            f"Desktop enabled by default: {boolFormatter(self.desktop_default_enable)}",
            f"Desktop default protocol: [blue]{self.desktop_default_proto}[/blue]",
            f"Desktop default host: [blue]{'localhost' if self.desktop_default_localhost else '0.0.0.0'}[/blue]",
            f"Network default mode: [blue]{self.network_default_mode}[/blue]",
            f"Network fallback mode: [blue]{self.network_fallback_mode}[/blue]",
            f"Network range: [blue]{self.network_dedicated_range}[/blue]",
            f"Network exegol netmask: [blue]{self.network_default_netmask}[/blue]",
        ]
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.utils.SessionHandler import SessionHandler
        if SessionHandler().enterprise_feature_access():
            if len(self.custom_images) > 0:
                configs.append(f"Custom images:")
                for custom_image in self.custom_images:
                    configs.append(f"  - {custom_image}")
            else:
                configs.append(f"Custom images: [bright_black]Empty[/bright_black]")
        # TUI can't be called from here to avoid circular importation
        return configs
