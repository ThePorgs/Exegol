from wrapper.console.cli.actions.Command import Option, GroupArgs
from wrapper.utils.ConstantConfig import ConstantConfig


# Generic parameter class for container selection
class ContainerSelector:

    def __init__(self, groupArg):
        # Create container selector arguments
        # TODO : switch to a positional argument
        self.containertag = Option("-c", "--container-tag",
                                   dest="containertag",
                                   action="store",
                                   help="Tag used to target an Exegol container")

        # Create group parameter for container selection
        groupArg.append(GroupArgs({"arg": self.containertag, "required": False},
                                  title="[blue]Container selection options[/blue]"))


# Generic parameter class for container selection
class ImageSelector:

    def __init__(self, groupArg):
        # Create image selector arguments
        # TODO : switch to a positional argument
        self.imagetag = Option("-i", "--image-tag",
                               dest="imagetag",
                               action="store",
                               help="Tag used to target an Exegol image")

        # Create group parameter for container selection
        groupArg.append(GroupArgs({"arg": self.imagetag, "required": False},
                                  title="[blue]Image selection options[/blue]"))


# Generic parameter class for container creation
class ContainerCreation(ContainerSelector, ImageSelector):

    def __init__(self, groupArg):
        # Init parents : ContainerStart > ContainerSelector
        ContainerSelector.__init__(self, groupArg)
        ImageSelector.__init__(self, groupArg)

        self.X11 = Option("--disable-X11",
                          action="store_false",
                          dest="X11",
                          help="Disable display sharing to run GUI-based applications (default: [green]Enabled[/green])")
        self.common_resources = Option("--disable-common-resources",
                                       action="store_false",
                                       dest="common_resources",
                                       help=f"Disable the mount of the common exegol resources (/opt/resources) from the host ({ConstantConfig.root_path_obj.joinpath('shared-resources')}) (default: [green]Enabled[/green])")
        self.host_network = Option("--disable-shared-network",
                                   action="store_false",
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
                                        help="Share the current working directory to container's /workspace")
        self.volumes = Option("--volume",
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

        groupArg.append(GroupArgs({"arg": self.X11, "required": False},
                                  {"arg": self.common_resources, "required": False},
                                  {"arg": self.vpn, "required": False},
                                  {"arg": self.host_network, "required": False},
                                  {"arg": self.share_timezone, "required": False},
                                  {"arg": self.mount_current_dir, "required": False},
                                  {"arg": self.volumes, "required": False},
                                  {"arg": self.privileged, "required": False},
                                  {"arg": self.devices, "required": False},
                                  title="[blue]Container creation options[/blue]"))
