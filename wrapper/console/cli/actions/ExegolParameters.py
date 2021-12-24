from wrapper.console.cli.actions.Command import Command
from wrapper.console.cli.actions.GenericParameters import *
from wrapper.manager.ExegolManager import ExegolManager
from wrapper.manager.UpdateManager import UpdateManager
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


class Start(Command, ContainerCreation):
    """Automatically create, start / resume and enter an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArg)

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
    """Install Exegol image (build or pull depending on the chosen install --mode)"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArg)

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

        self.groupArg.append(GroupArgs({"arg": self.mode, "required": False},
                                       title="[blue]Install/update options[/blue]"))

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return UpdateManager.updateImage


class Update(Command):
    """Update Exegol image (build or pull depending on the chosen update --mode)"""

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return UpdateManager.updateImage


class Uninstall(Command):
    """Remove Exegol image(s)"""

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerSelector):
    """Remove Exegol container(s)"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArg)

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return ExegolManager.remove


class Exec(Command, ContainerStart):
    """Execute a command on an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerStart.__init__(self, self.groupArg)

        self.exec = Option("-e", "--exec",
                           dest="exec",
                           action="store",
                           help="Execute a single command in the exegol container")
        self.daemon = Option("-d", "--daemon",
                             action="store_true",
                             dest="daemon",
                             default=False,
                             help="Executes the command as a daemon (default: False)")

        # Create group parameter for container selection
        self.groupArg.append(GroupArgs({"arg": self.shell, "required": False},
                                       {"arg": self.daemon, "required": False},
                                       title="[blue]Exec options[/blue]",
                                       description='Command execution options in Exegol'))

    def __call__(self, *args, **kwargs):
        raise NotImplementedError


class Info(Command):
    """Print info on containers and local & remote images (name, size, state, ...)"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.info


class Version(Command):
    """Print current Exegol banner & version"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.banner
