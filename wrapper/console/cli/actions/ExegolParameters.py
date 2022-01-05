from wrapper.console.cli.actions.Command import Command
from wrapper.console.cli.actions.GenericParameters import *
from wrapper.manager.ExegolManager import ExegolManager
from wrapper.utils.ExeLog import logger


class Start(Command, ContainerCreation):
    """Automatically create, start / resume and enter an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArg)

        # Create container start / exec arguments
        self.shell = Option("-s", "--shell",
                            dest="shell",
                            action="store",
                            choices={"zsh", "bash", "tmux"},
                            default="zsh",
                            help="Select a shell environment to launch at startup (Default: zsh)")

        # Create group parameter for container selection
        self.groupArg.append(GroupArgs({"arg": self.shell, "required": False},
                                       title="[blue]Start options[/blue]"))

    def __call__(self, *args, **kwargs):
        return ExegolManager.start


class Stop(Command, ContainerSelector):
    """Stop an Exegol container in a saved state"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running stop module")
        return ExegolManager.stop


class Install(Command, ImageSelector):
    """Install or build Exegol image (build or pull depending on the chosen install --mode)"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return ExegolManager.install


class Update(Command, ImageSelector):
    """Update or install an Exegol image (build or pull depending on the chosen update --mode)"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return ExegolManager.update


class Uninstall(Command, ImageSelector):
    """Remove Exegol [default not bold]image(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerSelector):
    """Remove Exegol [default not bold]container(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return ExegolManager.remove


class Exec(Command, ContainerCreation):
    """Execute a command on an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArg)

        self.exec = Option("-e", "--exec",
                           dest="exec",
                           action="store",
                           help="Execute a single command in the exegol container. If --tmp is set, this command will be executed via the container entrypoint command.")
        self.daemon = Option("-b", "--background",
                             action="store_true",
                             dest="daemon",
                             help="Executes the command in background as a daemon (default: False)")
        self.tmp = Option("--tmp",
                          action="store_true",
                          dest="tmp",
                          help="Created a dedicated and temporary container to execute the command (default: False)")

        # Create group parameter for container selection
        self.groupArg.append(GroupArgs({"arg": self.exec, "required": True},
                                       {"arg": self.daemon, "required": False},
                                       {"arg": self.tmp, "required": False},
                                       title="[blue]Exec options[/blue]",
                                       description='Command execution options in Exegol'))

    def __call__(self, *args, **kwargs):
        logger.debug("Running exec module")
        return ExegolManager.exec


class Info(Command):
    """Print info on containers and local & remote images (name, size, state, ...)"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.info


class Version(Command):
    """Print current Exegol banner & version"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.banner
