from wrapper.utils.ExeLog import logger


class Option:
    def __init__(self, *args, dest=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        if dest is not None:
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
                             help="Allow insecure server connections for web requests, e.g. when fetching info from DockerHub (default: [red bold not italic]False[/red bold not italic])")
        self.quiet = Option("-q", "--quiet",
                            dest="quiet",
                            action="store_true",
                            default=False,
                            help="Show no information at all")
        self.verbosity = Option("-v", "--verbose",
                                dest="verbosity",
                                action="count",
                                default=0,
                                help="Verbosity level (-v for verbose, -vv for advanced, -vvv for debug)")

        self.groupArg = [
            GroupArgs({"arg": self.verify, "required": False},
                      {"arg": self.quiet, "required": False},
                      {"arg": self.verbosity, "required": False},
                      title="[blue]Optional arguments[/blue]",
                      is_global=True)
        ]

    def __call__(self, *args, **kwargs):
        logger.debug("The called command is : ", self.name)
        logger.debug("the object is", type(self).__name__)

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
