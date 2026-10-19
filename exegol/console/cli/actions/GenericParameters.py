from typing import List, Optional

from argcomplete.completers import EnvironCompleter, DirectoriesCompleter, FilesCompleter

from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.config.UserConfig import UserConfig
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.console.cli.ExegolCompleter import ContainerCompleter, ImageCompleter, VoidCompleter, DesktopConfigCompleter
from exegol.console.cli.SentinelCompleter import SentinelProfileCompleter
from exegol.console.cli.SyntaxFormat import SyntaxFormat
from exegol.console.cli.actions.Command import Option, GroupArg, _help_literal
from exegol.console.cli.actions.ForceToggleAction import ForceToggleAction
from exegol.utils.NetworkUtils import NetworkUtils


class ContainerSelector:
    """Generic parameter class for container selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create container selector arguments
        self.containertag: Optional[Option] = Option("containertag",
                                                     metavar="CONTAINER",
                                                     nargs='?',
                                                     action="store",
                                                     help="Tag used to target an Exegol container",
                                                     completer=ContainerCompleter)

        # Create group parameter for container selection
        groupArgs.append(GroupArg({"arg": self.containertag, "required": False},
                                  title="[blue]Container selection options[/blue]"))


class ContainerMultiSelector:
    """Generic parameter class for container multi selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create container selector arguments
        self.multicontainertag = Option("multicontainertag",
                                        metavar="CONTAINER",
                                        nargs='*',
                                        action="store",
                                        help="Tag used to target one or more Exegol containers",
                                        completer=ContainerCompleter)
        self.select_all = Option("--all",
                                 dest="select_all",
                                 action="store_true",
                                 default=False,
                                 help="Select every Exegol containers available")

        # Create group parameter for container multi selection
        groupArgs.append(GroupArg({"arg": self.multicontainertag, "required": False},
                                  {"arg": self.select_all, "required": False},
                                  title="[blue]Containers selection options[/blue]"))


class ContainerStart:
    """Generic parameter class for container selection.
    This generic class is used by start, restart and exec actions"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create options on container start
        self.envs = Option("-e", "--env",
                           action="append",
                           default=None,
                           dest="envs",
                           help="Add an environment variable on Exegol (format: --env KEY=value). The variables "
                                "configured during the creation of the container will be persistent in all shells. "
                                "If the container already exists, the variable will be present only in the current shell",
                           completer=EnvironCompleter)

        self.capabilities = Option("--cap",
                                   dest="capabilities",
                                   metavar='CAPABILITY',  # Do not display available choices
                                   action="append",
                                   default=None,
                                   choices=UserConfig.capability_options,
                                   help="[orange3](dangerous)[/orange3] Capabilities allow to add specific privileges to the container "
                                        "(e.g. need to mount volumes, perform low-level operations on the network, etc).")

        # Create group parameter for container options at start
        groupArgs.append(GroupArg({"arg": self.envs, "required": False},
                                  {"arg": self.capabilities, "required": False},
                                  title=f"[blue]Container options[/blue] [bright_blue]at creation or start[/bright_blue]"))


class ContainerSpawnShell(ContainerStart):
    """Generic parameter class to spawn a shell on an exegol container.
    This generic class is used by start and restart"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Spawn container shell arguments
        self.shell = Option("-s", "--shell",
                            dest="shell",
                            action="store",
                            choices=UserConfig.start_shell_options,
                            default=None,
                            help=f"Select a shell environment to launch at startup (Default: [blue]{_help_literal(OptionResolver().defaultFor(OptionKey.SHELL))}[/blue])")

        # Help template for every --[no-]NAME toggle: "<feature> (default: Enabled/Disabled)",
        # with the default read through defaultFor() (see ContainerCreation for why only it).
        # Spellings are written literally: `_REGISTRY`'s `flags` tuples copy them verbatim.
        # A short flag only ever sits on the positive half.
        self.log = Option("-l", "--log", "--no-log",
                          dest="log",
                          action=ForceToggleAction,
                          default=None,
                          help=f"Enable shell logging (commands and outputs) on exegol to /workspace/logs/ (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.LOG) else '[bright_black]Disabled[/bright_black]'})")
        self.log_method = Option("--log-method",
                                 dest="log_method",
                                 action="store",
                                 choices=UserConfig.shell_logging_method_options,
                                 default=None,
                                 help=f"Select a shell logging method used to record the session (default: [blue]{_help_literal(OptionResolver().defaultFor(OptionKey.LOG_METHOD))}[/blue])")
        # `--no-log` is a prefix of `--no-log-compress` and resolves by exact match; the
        # abbreviations `--no-l`/`--no-lo` are now ambiguous (pinned in test_cli_alias_matrix).
        self.log_compress = Option("--log-compress", "--no-log-compress",
                                   dest="log_compress",
                                   action=ForceToggleAction,
                                   default=None,
                                   help=f"Enable the automatic compression of log files at the end of the session (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.LOG_COMPRESS) else '[bright_black]Disabled[/bright_black]'})")

        # Group dedicated to shell logging feature
        groupArgs.append(GroupArg({"arg": self.log, "required": False},
                                  {"arg": self.log_method, "required": False},
                                  {"arg": self.log_compress, "required": False},
                                  title="[bright_blue]Shell logging[/bright_blue][blue] options[/blue]"))

        ContainerStart.__init__(self, groupArgs)

        # Create group parameter for container selection
        groupArgs.append(GroupArg({"arg": self.shell, "required": False},
                                  title="[bright_blue]Start[/bright_blue] [blue]specific options[/blue]"))


class ImageSelector:
    """Generic parameter class for image selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create image selector arguments
        self.imagetag: Optional[Option] = Option("imagetag",
                                                 metavar="IMAGE",
                                                 nargs='?',
                                                 action="store",
                                                 help="Tag used to target an Exegol image",
                                                 completer=ImageCompleter)

        # Create group parameter for image selection
        groupArgs.append(GroupArg({"arg": self.imagetag, "required": False},
                                  title="[blue]Image selection options[/blue]"))


class ImageMultiSelector:
    """Generic parameter class for image multi selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create image multi selector arguments
        self.multiimagetag = Option("multiimagetag",
                                    metavar="IMAGE",
                                    nargs='*',
                                    action="store",
                                    help="Tag used to target one or more Exegol images",
                                    completer=ImageCompleter)
        self.select_all = Option("--all",
                                 dest="select_all",
                                 action="store_true",
                                 default=False,
                                 help="Select every Exegol images available")

        # Create group parameter for image multi selection
        groupArgs.append(GroupArg({"arg": self.multiimagetag, "required": False},
                                  {"arg": self.select_all, "required": False},
                                  title="[blue]Images selection options[/blue]"))


class ContainerCreation(ContainerSelector, ImageSelector):
    """Generic parameter class for container creation"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Init parents : ContainerStart > ContainerSelector
        ContainerSelector.__init__(self, groupArgs)
        ImageSelector.__init__(self, groupArgs)

        # Covers X11 and Wayland. The profile field keeps its `display.share_x11` name so
        # existing profiles stay valid (see ProfileFieldMap.py).
        self.gui = Option("--gui", "--no-gui",
                          dest="gui",
                          action=ForceToggleAction,
                          default=None,
                          help=f"Share the host GUI (X11 or Wayland) so graphical applications can display (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.GUI) else '[bright_black]Disabled[/bright_black]'})")
        # Help defaults use defaultFor(), never get()/resolve()/isExplicit(): these f-strings
        # are built while ParametersManager is mid-construction, and reaching the CLI tier
        # would trip MetaSingleton's recursion guard on every invocation.
        self.my_resources = Option("--my-resources", "--no-my-resources",
                                   dest="my_resources",
                                   action=ForceToggleAction,
                                   default=None,
                                   help=f"Mount the my-resources volume (/opt/my-resources) from the host ({_help_literal(OptionResolver().defaultFor(OptionKey.MY_RESOURCES_PATH))}) (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.MY_RESOURCES) else '[bright_black]Disabled[/bright_black]'})")
        self.exegol_resources = Option("--exegol-resources", "--no-exegol-resources",
                                       dest="exegol_resources",
                                       action=ForceToggleAction,
                                       default=None,
                                       help=f"Mount the exegol resources volume (/opt/resources) from the host ({_help_literal(OptionResolver().defaultFor(OptionKey.EXEGOL_RESOURCES_PATH))}) (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.EXEGOL_RESOURCES) else '[bright_black]Disabled[/bright_black]'})")
        self.network = Option("--network",
                              dest="network",
                              action="store",
                              default=None,
                              choices=NetworkUtils.get_options(),
                              help=f"Select the type of network to which the container will be attached (default: [blue]{_help_literal(OptionResolver().defaultFor(OptionKey.NETWORK))}[/blue])")
        # Singular, like the dest and the `system.share_timezone` profile field. Makes the
        # abbreviations `--sh` and `--no-s` ambiguous (pinned in test_cli_alias_matrix).
        self.share_timezone = Option("--share-timezone", "--no-share-timezone",
                                     dest="share_timezone",
                                     action=ForceToggleAction,
                                     default=None,
                                     help=f"Share the host's time and timezone configuration with exegol (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.SHARE_TIMEZONE) else '[bright_black]Disabled[/bright_black]'})")
        self.mount_current_dir = Option("-cwd", "--cwd-mount",
                                        dest="mount_current_dir",
                                        action="store_true",
                                        default=None,
                                        help="This option is a shortcut to set the /workspace folder to the user's current working directory")
        self.workspace_path = Option("-w", "--workspace",
                                     dest="workspace_path",
                                     action="store",
                                     help="The specified host folder will be linked to the /workspace folder in the container",
                                     completer=DirectoriesCompleter())
        # `-fs` enables only, like every short flag.
        self.update_fs_perms = Option("-fs", "--update-fs", "--no-update-fs",
                                      action=ForceToggleAction,
                                      default=None,
                                      dest="update_fs_perms",
                                      help=f"Modifies the permissions of folders and sub-folders shared in your workspace to access the files created within the container using your host user account. "
                                           f"(default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.UPDATE_FS_PERMS) else '[bright_black]Disabled[/bright_black]'})")
        self.volumes = Option("-V", "--volume",
                              action="append",
                              default=None,
                              dest="volumes",
                              help=f"Share a new volume between host and exegol (format: --volume {SyntaxFormat.volume})",
                              completer=DirectoriesCompleter())
        self.ports = Option("-p", "--port",
                            action="append",
                            default=None,
                            dest="ports",
                            help=f"Share a network port between host and exegol (format: --port {SyntaxFormat.port_sharing}). This configuration will disable the default host network.",
                            completer=VoidCompleter)
        self.hostname = Option("--hostname",
                               dest="hostname",
                               default=None,
                               action="store",
                               help="Set a custom hostname to the exegol container (default: exegol-<name>)",
                               completer=VoidCompleter)
        # `--no-privileged` lets the operator refuse a profile's `system.privileged: true`.
        # Passing both halves exits 2 (ForceToggleAction) instead of last-wins, which is why
        # argparse.BooleanOptionalAction is not used.
        self.privileged = Option("--privileged", "--no-privileged",
                                 dest="privileged",
                                 action=ForceToggleAction,
                                 default=None,
                                 help=f"[red](dangerous)[/red] Give ALL admin privileges to the container when it is created "
                                      f"(if the need is specifically identified, consider adding capabilities instead) "
                                      f"(default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.PRIVILEGED) else '[bright_black]Disabled[/bright_black]'})")
        self.devices = Option("-d", "--device",
                              dest="devices",
                              default=None,
                              action="append",
                              help="Add host [default not bold]device(s)[/default not bold] at the container creation (example: -d /dev/ttyACM0 -d /dev/bus/usb/)",
                              completer=FilesCompleter(directories=True))

        self.hosts_file = Option("--hosts-file",
                        dest="hosts_file",
                        metavar="HOSTS_FILE",
                        action="store",
                        help="Import custom host entries from a file (format: IP HOSTNAME)",
                        completer=FilesCompleter())

        self.comment = Option("--comment",
                              dest="comment",
                              action="store",
                              help="The specified comment will be added to the container info",
                              completer=VoidCompleter)

        # `-S` is a pure toggle (consumes no token) and `-SP` carries the profile name, so
        # `exegol start -S mycontainer` never binds the container name to the profile.
        self.sentinel = Option("-S", "--sentinel", "--no-sentinel",
                               dest="sentinel",
                               action=ForceToggleAction,
                               default=None,
                               help=f"Enable Sentinel audit logging on the exegol container (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.SENTINEL) else '[bright_black]Disabled[/bright_black]'})")

        # Required value: `nargs='?'` would greedily consume the next token.
        self.sentinel_profile = Option("-SP", "--sentinel-profile",
                                       dest="sentinel_profile",
                                       metavar="SENTINEL_PROFILE",
                                       action="store",
                                       default=None,
                                       # The default is unvalidated config.yml text: `_help_literal` escapes both argparse `%`
                                       # expansion and rich markup, which would otherwise crash or corrupt the help. The
                                       # condition tests the unescaped value.
                                       help=f"Name the [green]Sentinel[/green] audit profile to deploy in the container; supplying it enables Sentinel "
                                            f"(default: {f'[blue]{_help_literal(OptionResolver().defaultFor(OptionKey.SENTINEL_PROFILE))}[/blue]' if OptionResolver().defaultFor(OptionKey.SENTINEL_PROFILE) else '[bright_black]none[/bright_black]'})",
                                       completer=SentinelProfileCompleter)

        self.sentinel_strategy = Option("--sentinel-strategy",
                                        dest="sentinel_strategy",
                                        metavar="STRATEGY",
                                        action="store",
                                        choices=SentinelUpdateStrategy.values(),
                                        default=None,
                                        help=f"Set the Sentinel profile update strategy for this container (default: [blue]{_help_literal(OptionResolver().defaultFor(OptionKey.SENTINEL_STRATEGY))}[/blue]). "
                                             f"'on_restart' regenerates the config from host sources at every restart; 'disabled' freezes it until forced.")

        groupArgs.append(GroupArg({"arg": self.workspace_path, "required": False},
                                  {"arg": self.mount_current_dir, "required": False},
                                  {"arg": self.update_fs_perms, "required": False},
                                  {"arg": self.volumes, "required": False},
                                  {"arg": self.ports, "required": False},
                                  {"arg": self.hostname, "required": False},
                                  {"arg": self.privileged, "required": False},
                                  {"arg": self.devices, "required": False},
                                  {"arg": self.sentinel, "required": False},
                                  {"arg": self.sentinel_profile, "required": False},
                                  {"arg": self.sentinel_strategy, "required": False},
                                  {"arg": self.gui, "required": False},
                                  {"arg": self.my_resources, "required": False},
                                  {"arg": self.exegol_resources, "required": False},
                                  {"arg": self.network, "required": False},
                                  {"arg": self.share_timezone, "required": False},
                                  {"arg": self.comment, "required": False},
                                  {"arg": self.hosts_file, "required": False},
                                  title="[blue]Container options[/blue] [bright_blue]at creation only[/bright_blue]"))

        self.vpn = Option("--vpn",
                          dest="vpn",
                          default=None,
                          action="store",
                          help="Setup an OpenVPN (.ovpn) or WireGuard (.conf) connection at the container creation (example: --vpn /home/user/vpn/client.ovpn)",
                          completer=FilesCompleter(["ovpn", "conf"], directories=True))
        self.vpn_auth = Option("--vpn-auth",
                               dest="vpn_auth",
                               default=None,
                               action="store",
                               help="Enter the credentials with a file (line 1: username, line 2: password, optional line 3: private key decryption password) to establish the OpenVPN connection automatically (example: --vpn-auth /home/user/vpn/auth.txt)",
                               completer=FilesCompleter())

        groupArgs.append(GroupArg({"arg": self.vpn, "required": False},
                                  {"arg": self.vpn_auth, "required": False},
                                  title="[bright_blue]VPN[/bright_blue][blue] options (at creation only)[/blue]"))

        # `--desktop-config` has no `--no-` half: a value option is overridden by passing another value.
        self.desktop = Option("--desktop", "--no-desktop",
                              dest="desktop",
                              action=ForceToggleAction,
                              default=None,
                              help=f"Enable the Exegol desktop feature (default: {'[green]Enabled[/green]' if OptionResolver().defaultFor(OptionKey.DESKTOP) else '[bright_black]Disabled[/bright_black]'})")
        # The default shown is composed from its two resolved component settings (via defaultFor(),
        # see --my-resources); `desktop_available_proto` is a class constant, not a setting.
        self.desktop_config = Option("--desktop-config",
                                     dest="desktop_config",
                                     default=None,
                                     action="store",
                                     help=f"Configure your exegol desktop ([blue]{'[/blue] or [blue]'.join(UserConfig.desktop_available_proto)}[/blue]) and its exposure "
                                          f"(format: {SyntaxFormat.desktop_config}) "
                                          f"(default: [blue]{_help_literal(OptionResolver().defaultFor(OptionKey.DESKTOP_DEFAULT_PROTO))}[/blue]:[blue]{'127.0.0.1' if OptionResolver().defaultFor(OptionKey.DESKTOP_DEFAULT_LOCALHOST) else '0.0.0.0'}[/blue]:[blue]<random>[/blue])",
                                     completer=DesktopConfigCompleter)
        groupArgs.append(GroupArg({"arg": self.desktop, "required": False},
                                  {"arg": self.desktop_config, "required": False},
                                  title="[bright_blue]Desktop[/bright_blue][blue] options (at creation only)[/blue]"))
