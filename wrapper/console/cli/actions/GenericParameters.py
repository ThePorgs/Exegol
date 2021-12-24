from wrapper.console.cli.actions.Command import Option, GroupArgs
from wrapper.utils.ConstantConfig import ConstantConfig


# Generic parameter class for container selection
class ContainerSelector:

    def __init__(self, groupArg):
        # Create container selector arguments
        self.containertag = Option("-t", "--container-tag",
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
class ContainerStart(ContainerSelector):

    def __init__(self, groupArg):
        # Init parents : ContainerSelector
        super().__init__(groupArg)

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
        self.X11 = Option("-x", "-x11",
                          action="store_true",
                          dest="X11",
                          help="enable display sharing to run GUI-based applications")
        self.host_timezones = Option("--host-timezones",
                                     action="store_true",
                                     dest="host_timezones",
                                     help="let the container share the host's timezones configuration")
        self.host_network = Option("--host-network",
                                   action="store_true",
                                   dest="host_network",
                                   help="let the container share the host's timezones configuration")
        self.bind_resources = Option("--bind-resources",
                                     action="store_true",
                                     dest="bind_resources",
                                     help=f"mount the /opt/resources of the container in a subdirectory of host\'s {ConstantConfig.root_path + '/shared-resources'}", )

        # Advanced args
        self.no_default = Option("--no-default",
                                 dest="no_default",
                                 action="store_true",
                                 default=False,
                                 help="disable the default start options (e.g. --X11, --host-network)")
        self.privileged = Option("--privileged",
                                 dest="privileged",
                                 action="store_true",
                                 default=False,
                                 help="(dangerous) give extended privileges at the container creation (e.g. needed to "
                                      "mount things, to use wifi or bluetooth)")
        self.device = Option("-d", "--device",
                             dest="device",
                             action="store",
                             help="add a host device at the container creation")
        self.custom_options = Option("-c", "--custom-options",
                                     dest="custom_options",
                                     action="store",
                                     default="",
                                     help="specify custom options for the container creation")
        self.mount_current_dir = Option("-cwd", "--cwd-mount",
                                        dest="mount_current_dir",
                                        action="store_true",
                                        help="mount current dir to container's /workspace")

        groupArg.append(GroupArgs({"arg": self.X11, "required": False},
                                  {"arg": self.host_network, "required": False},
                                  {"arg": self.host_timezones, "required": False},
                                  {"arg": self.bind_resources, "required": False},
                                  title="[blue]Default container options[/blue]",
                                  description='The following options are enabled by default. They can all be '
                                              'disabled with the advanced option "--no-default". They can then '
                                              'be enabled back separately, for example "exegol --no-default '
                                              '--X11 start"'))
        groupArg.append(GroupArgs({"arg": self.no_default, "required": False},
                                  {"arg": self.privileged, "required": False},
                                  {"arg": self.device, "required": False},
                                  {"arg": self.custom_options, "required": False},
                                  {"arg": self.mount_current_dir, "required": False},
                                  title="[blue]Advanced container options[/blue]"))
