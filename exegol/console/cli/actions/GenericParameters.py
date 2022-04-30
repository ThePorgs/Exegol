from typing import List

from exegol.console.cli.actions.Command import Option, GroupArg
from exegol.utils.UserConfig import UserConfig


class ContainerSelector:
    """Generic parameter class for container selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create container selector arguments
        self.containertag = Option("containertag",
                                   metavar="CONTAINER",
                                   nargs='?',
                                   action="store",
                                   help="Tag used to target an Exegol container")

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
                                        help="Tag used to target one or multiple Exegol container")

        # Create group parameter for container multi selection
        groupArgs.append(GroupArg({"arg": self.multicontainertag, "required": False},
                                  title="[blue]Containers selection options[/blue]"))


class ContainerStart:
    """Generic parameter class for container selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create options on container start
        self.envs = Option("-e", "--env",
                           action="append",
                           default=[],
                           dest="envs",
                           help="And an environment variable on Exegol (format: --env KEY=value). The variables "
                                "configured during the creation of the container will be persistent in all shells. "
                                "If the container already exists, the variable will be present only in the current shell")

        # Create group parameter for container options at start
        groupArgs.append(GroupArg({"arg": self.envs, "required": False},
                                  title="[blue]Container start options[/blue]"))


class ImageSelector:
    """Generic parameter class for image selection"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Create image selector arguments
        self.imagetag = Option("imagetag",
                               metavar="IMAGE",
                               nargs='?',
                               action="store",
                               help="Tag used to target an Exegol image")

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
                                    help="Tag used to target one or multiple Exegol image")

        # Create group parameter for image multi selection
        groupArgs.append(GroupArg({"arg": self.multiimagetag, "required": False},
                                  title="[blue]Images selection options[/blue]"))


class ContainerCreation(ContainerSelector, ImageSelector):
    """Generic parameter class for container creation"""

    def __init__(self, groupArgs: List[GroupArg]):
        # Init parents : ContainerStart > ContainerSelector
        ContainerSelector.__init__(self, groupArgs)
        ImageSelector.__init__(self, groupArgs)

        self.X11 = Option("--disable-X11",
                          action="store_false",
                          default=True,
                          dest="X11",
                          help="Disable display sharing to run GUI-based applications (default: [green]Enabled[/green])")
        self.shared_resources = Option("--disable-my-resources",
                                       action="store_false",
                                       default=True,
                                       dest="shared_resources",
                                       help=f"Disable the mount of the shared resources (/my-resources) from the host ({UserConfig().shared_resources_path}) (default: [green]Enabled[/green])")
        self.exegol_resources = Option("--disable-exegol-resources",
                                       action="store_false",
                                       default=True,
                                       dest="exegol_resources",
                                       help=f"Disable the mount of the exegol resources (/opt/resources) from the host ({UserConfig().exegol_resources_path}) (default: [green]Enabled[/green])")
        self.host_network = Option("--disable-shared-network",
                                   action="store_false",
                                   default=True,
                                   dest="host_network",
                                   help="Disable the sharing of the host's network interfaces with exegol (default: [green]Enabled[/green])")
        self.share_timezone = Option("--disable-shared-timezones",
                                     action="store_false",
                                     default=True,
                                     dest="share_timezone",
                                     help="Disable the sharing of the host's time and timezone configuration with exegol (default: [green]Enabled[/green])")
        self.mount_current_dir = Option("-cwd", "--cwd-mount",
                                        dest="mount_current_dir",
                                        action="store_true",
                                        default=False,
                                        help="This option is a shortcut to set the /workspace folder to the user's current working directory")
        self.workspace_path = Option("-w", "--workspace",
                                     dest="workspace_path",
                                     action="store",
                                     help="The specified host folder will be linked to the /workspace folder in the container")
        self.volumes = Option("-V", "--volume",
                              action="append",
                              default=[],
                              dest="volumes",
                              help="Share a new volume between host and exegol (format: --volume /host/path/:/exegol/mount/)")
        self.privileged = Option("--privileged",
                                 dest="privileged",
                                 action="store_true",
                                 default=False,
                                 help="[orange3](dangerous)[/orange3] give extended privileges at the container creation (e.g. needed to "
                                      "mount things, to use wifi or bluetooth)")
        self.devices = Option("-d", "--device",
                              dest="devices",
                              default=[],
                              action="append",
                              help="Add host [default not bold]device(s)[/default not bold] at the container creation (example: -d /dev/ttyACM0 -d /dev/bus/usb/)")

        self.vpn = Option("--vpn",
                          dest="vpn",
                          default=None,
                          action="store",
                          help="Setup an OpenVPN connection at the container creation (example: --vpn /home/user/vpn/conf.ovpn)")
        self.vpn_auth = Option("--vpn-auth",
                               dest="vpn_auth",
                               default=None,
                               action="store",
                               help="Enter the credentials with a file (first line: username, second line: password) to establish the VPN connection automatically (example: --vpn-auth /home/user/vpn/auth.txt)")

        groupArgs.append(GroupArg({"arg": self.workspace_path, "required": False},
                                  {"arg": self.mount_current_dir, "required": False},
                                  {"arg": self.volumes, "required": False},
                                  {"arg": self.privileged, "required": False},
                                  {"arg": self.devices, "required": False},
                                  {"arg": self.X11, "required": False},
                                  {"arg": self.shared_resources, "required": False},
                                  {"arg": self.exegol_resources, "required": False},
                                  {"arg": self.host_network, "required": False},
                                  {"arg": self.share_timezone, "required": False},
                                  title="[blue]Container creation options[/blue]"))

        groupArgs.append(GroupArg({"arg": self.vpn, "required": False},
                                  {"arg": self.vpn_auth, "required": False},
                                  title="[blue]Container creation VPN options[/blue]"))
