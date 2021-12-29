from wrapper.console.cli.actions.Command import Option, GroupArgs
from wrapper.utils.ConstantConfig import ConstantConfig


# Generic parameter class for container selection
class ContainerSelector:

    def __init__(self, groupArg):
        # Create container selector arguments
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
        self.imagetag = Option("-i", "--image-tag",
                               dest="imagetag",
                               action="store",
                               help="Tag used to target an Exegol image")

        # Create group parameter for container selection
        groupArg.append(GroupArgs({"arg": self.imagetag, "required": False},
                                  title="[blue]Image selection options[/blue]"))


# Generic parameter class for container start
class ContainerStart(ContainerSelector, ImageSelector):

    def __init__(self, groupArg):
        # Init parents : ContainerSelector
        ContainerSelector.__init__(self, groupArg)
        ImageSelector.__init__(self, groupArg)

        # Create container start / exec arguments
        self.shell = Option("-s", "--shell",
                            dest="shell",
                            action="store",
                            choices={"zsh", "bash", "tmux"},
                            default="zsh",
                            help="Select an environment to spawn at shell startup (Default: zsh)")

        # Create group parameter for container selection
        groupArg.append(GroupArgs({"arg": self.shell, "required": False},
                                  title="[blue]Advanced start options[/blue]",
                                  description='These options are available to customize the startup options '
                                              'of the container'))


# Generic parameter class for container creation
class ContainerCreation(ContainerStart, ImageSelector):

    def __init__(self, groupArg):
        # Init parents : ContainerStart > ContainerSelector
        super().__init__(groupArg)

        # Standard Args
        self.mount_current_dir = Option("-cwd", "--cwd-mount",
                                        dest="mount_current_dir",
                                        action="store_true",
                                        help="Share the current working directory to container's /workspace")
        self.X11 = Option("-x", "--disable-x11",
                          action="store_false",
                          dest="X11",
                          help="Disable display sharing to run GUI-based applications (default: enable)")
        self.common_resources = Option("--disable-common-resources",
                                       action="store_false",
                                       dest="common_resources",
                                       help=f"Mount the common exegol resources (/opt/resources) from the host ({ConstantConfig.root_path_obj.joinpath('shared-resources')}) (default: enable)")
        self.volumes = Option("--volume",
                              action="append",
                              default=[],
                              dest="volumes",
                              help="Share a new volume between host and exegol (format: /host/path/:/exegol/mount/)")

        # Advanced args
        self.privileged = Option("--privileged",
                                 dest="privileged",
                                 action="store_true",
                                 default=False,
                                 help="(dangerous) give extended privileges at the container creation (e.g. needed to "
                                      "mount things, to use wifi or bluetooth)")
        self.devices = Option("-d", "--device",
                              dest="devices",
                              default=[],
                              action="append",
                              help="Add a host device at the container creation")
        self.share_timezone = Option("--disable-shared-timezones",
                                     action="store_false",
                                     default=True,
                                     dest="share_timezone",
                                     help="Share the time and timezone configuration of the host with exegol. (default: enable)")
        self.host_network = Option("--disable-shared-network",
                                   action="store_false",
                                   dest="host_network",
                                   help="Share the host's network interfaces with exegol. (default: enable)")

        groupArg.append(GroupArgs({"arg": self.common_resources, "required": False},
                                  {"arg": self.X11, "required": False},
                                  {"arg": self.mount_current_dir, "required": False},
                                  {"arg": self.volumes, "required": False},
                                  title="[blue]Default container options[/blue]"))

        groupArg.append(GroupArgs({"arg": self.privileged, "required": False},
                                  {"arg": self.devices, "required": False},
                                  {"arg": self.host_network, "required": False},
                                  {"arg": self.share_timezone, "required": False},
                                  title="[blue]Advanced container options[/blue]"))
