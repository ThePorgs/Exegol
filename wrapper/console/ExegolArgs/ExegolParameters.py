from wrapper.utils.ConstantConfig import ConstantConfig


class Option:
    def __init__(self, *args, dest=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.kwargs["dest"] = dest
        self.dest = dest


class GroupArgs:
    def __init__(self, *options, title=None, description=None, is_global=False):
        self.title = title
        self.description = description
        self.options = options
        self.is_global = is_global


class Command:
    def __init__(self):
        self.name = type(self).__name__.lower()
        self.verify = Option("-k", "--insecure",
                             dest="verify",
                             action="store_false",
                             default=True,
                             required=False,
                             help="Allow insecure server connections for web requests (default: False)")
        self.quiet = Option("-q", "--quiet",
                            dest="quiet",
                            action="store_true",
                            default=False,
                            help="show no information at all")
        self.verbosity = Option("-v", "--verbose",
                                dest="verbosity",
                                action="count",
                                default=0,
                                help="verbosity level (-v for verbose, -vv for debug)")

        self.groupArg = [
            GroupArgs({"arg": self.verify, "required": False},
                      {"arg": self.quiet, "required": False},
                      {"arg": self.verbosity, "required": False},
                      title="[blue]Optional arguments[/blue]",
                      is_global=True)
        ]

    def __call__(self, *args, **kwargs):
        print("The called command is : ", self.name)
        print("the object is", type(self).__name__)

    def __repr__(self):
        return self.name

    def populate(self, args):
        for arg in vars(args).keys():
            if arg in self.__dict__:
                self.__setattr__(arg, vars(args)[arg])

    def check_parameters(self) -> [str]:
        missingOption = []
        for groupArg in self.groupArg:
            for option in groupArg.options:
                if option["required"]:
                    if self.__dict__[option["arg"].dest] is None:
                        missingOption.append(option["arg"].dest)
        return missingOption


class Start(Command):
    """automatically start, resume, create or enter an Exegol container"""
    def __init__(self):
        #  Standard Args
        self.X11 = Option("-x", "-x11",
                          action="store_true",
                          dest="X11",
                          help="enable display sharing to run GUI-based applications")
        self.host_timezones = Option("--host-timezones",
                                     action="store_true",
                                     dest="host_timezones",
                                     help="let the container share the host's timezones configuration"
                                     )
        self.host_network = Option("--host-network",
                                   action="store_true",
                                   dest="host_network",
                                   help="let the container share the host's timezones configuration")
        self.bind_resources = Option("--bind-resources",
                                     action="store_true",
                                     dest="bind_resources",
                                     help=f"mount the /opt/resources of the container in a subdirectory of host\'s {ConstantConfig.root_path + '/shared-resources'}", )
        self.shell = Option("-s", "--shell",
                            dest="shell",
                            action="store",
                            choices={"zsh", "bash", "tmux"},
                            default="zsh",
                            help="select shell to start when entering Exegol (Default: zsh)")
        self.exec = Option("-e", "--exec",
                           dest="exec",
                           action="store",
                           help="execute a command on exegol container")

        # Advanced args

        self.containertag = Option("-t", "--container-tag",
                                   dest="containertag",
                                   action="store",
                                   help="tag to use in the container name")
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

        super().__init__()

        self.groupArg.append(GroupArgs({"arg": self.X11, "required": False},
                                       {"arg": self.host_network, "required": False},
                                       {"arg": self.host_timezones, "required": False},
                                       {"arg": self.bind_resources, "required": False},
                                       {"arg": self.shell, "required": False},
                                       {"arg": self.exec, "required": False},
                                       title="[blue]Default start options[/blue]",
                                       description='The following options are enabled by default. They can all be '
                                                   'disabled with the advanced option "--no-default". They can then '
                                                   'be enabled back separately, for example "exegol --no-default '
                                                   '--X11 start"'))
        self.groupArg.append(GroupArgs({"arg": self.containertag, "required": True},
                                       {"arg": self.no_default, "required": False},
                                       {"arg": self.privileged, "required": False},
                                       {"arg": self.device, "required": False},
                                       {"arg": self.custom_options, "required": False},
                                       {"arg": self.mount_current_dir, "required": False},
                                       title="[blue]Advanced start options[/blue]"))

    def __call__(self, *args, **kwargs):
        print("Call direct dans start, exemple avec x11 :", self.X11)


class Stop(Command):
    """stop an Exegol container in a saved state"""


class Install(Command):
    """install Exegol image (build or pull depending on the chosen install --mode)"""

    def __init__(self):
        modes = {
            "release": "(default) downloads a pre-built image (from DockerHub) (faster)",
            "sources": f"builds from the local sources in {ConstantConfig.root_path} (pull from GitHub then docker "
                       f"build, local edits won't be overwritten) "
        }

        modes_help = ""
        for mode in modes.keys():
            modes_help += f"{mode}\t\t{modes[mode]}\n"
        self.mode = Option("-m", "--mode",
                           dest="mode",
                           action="store",
                           choices=modes.keys(),
                           default="release",
                           help=modes_help)

        super().__init__()

        self.groupArg.append(GroupArgs({"arg": self.mode, "required": False},
                                       title="[blue]Install/update options[/blue]"))


class Update(Install):
    """update Exegol image (build or pull depending on the chosen update --mode)"""


class Remove(Command):
    """remove Exegol image(s) and/or container(s)"""


class Exec(Command):
    """execute a command on an Exegol container"""


class Info(Command):
    """print info on containers and local & remote images (name, size, state, ...)"""
    def __call__(self, *args, **kwargs):
        print("i execute info")
        print(self.verbosity)


class Version(Command):
    """print current version"""

