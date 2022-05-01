from exegol.console.cli.actions.Command import Command
from exegol.console.cli.actions.GenericParameters import *
from exegol.manager.ExegolManager import ExegolManager
from exegol.manager.UpdateManager import UpdateManager
from exegol.utils.ExeLog import logger


class Start(Command, ContainerCreation, ContainerStart):
    """Automatically create, start / resume and enter an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerStart.__init__(self, self.groupArgs)

        self._usages = {
            "Start interactively a container": "exegol start",
            "Create a [blue]demo[/blue] container using [bright_blue]full[/bright_blue] image": "exegol start [blue]demo[/blue] [bright_blue]full[/bright_blue]",
            "Spawn a shell from [blue]demo[/blue] container": "exegol start [blue]demo[/blue]",
            "Create a container [blue]test[/blue] with a custom shared workspace": "exegol start [blue]test[/blue] [bright_blue]full[/bright_blue] -w [magenta]./project/pentest/[/magenta]",
            "Create a container [blue]test[/blue] sharing the current working directory": "exegol start [blue]test[/blue] [bright_blue]full[/bright_blue] -cwd",
            "Create a container [blue]htb[/blue] with a VPN": "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] --vpn [magenta]~/vpn/[/magenta][bright_magenta]lab_Dramelac.ovpn[/bright_magenta]",
            "Create a container [blue]app[/blue] with custom volume": "exegol start [blue]app[/blue] [bright_blue]full[/bright_blue] -V [bright_magenta]'/var/app/:/app/'[/bright_magenta]",
            "Get a [blue]tmux[/blue] shell": "exegol start --shell [blue]tmux[/blue]",
            "Use a Proxmark": "exegol start -d /dev/ttyACM0",
            "Use an HackRF One": "exegol start -d /dev/bus/usb/",
        }

        # Create container start / exec arguments
        self.shell = Option("-s", "--shell",
                            dest="shell",
                            action="store",
                            choices={"zsh", "bash", "tmux"},
                            default="zsh",
                            help="Select a shell environment to launch at startup (Default: [blue]zsh[/blue])")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.shell, "required": False},
                                       title="[bold cyan]Start[/bold cyan] [blue]specific options[/blue]"))

    def __call__(self, *args, **kwargs):
        return ExegolManager.start


class Stop(Command, ContainerMultiSelector):
    """Stop an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Stop interactively one or multiple container": "exegol stop",
            "Stop [blue]demo[/blue]": "exegol stop [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running stop module")
        return ExegolManager.stop


class Install(Command, ImageSelector):
    """Install or build Exegol image"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Install or build interactively an exegol image": "exegol install",
            "Install or update the [bright_blue]full[/bright_blue] image": "exegol install [bright_blue]full[/bright_blue]",
            "Build [bright_blue]local[/bright_blue] image": "exegol install [bright_blue]local[/bright_blue]"
        }

        # Create container build arguments
        self.build_profile = Option("build_profile",
                                    metavar="BUILD_PROFILE",
                                    choices=UpdateManager.listBuildProfiles().keys(),
                                    nargs="?",
                                    action="store",
                                    help="Select the build profile used to create a local image.")
        self.build_log = Option("--build-log",
                                dest="build_log",
                                metavar="LOGFILE_PATH",
                                action="store",
                                help="Write image building logs to a file.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.build_profile, "required": False},
                                       {"arg": self.build_log, "required": False},
                                       title="[bold cyan]Build[/bold cyan] [blue]specific options[/blue]"))

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return ExegolManager.install


class Update(Command, ImageSelector):
    """Update an Exegol image"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        self.skip_git = Option("--skip-git",
                               dest="skip_git",
                               action="store_true",
                               help="Skip git updates (wrapper, image sources and exegol resources).")
        self.skip_images = Option("--skip-images",
                                  dest="skip_images",
                                  action="store_true",
                                  help="Skip images updates (exegol docker images).")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.skip_git, "required": False},
                                       {"arg": self.skip_images, "required": False},
                                       title="[bold cyan]Update[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Install or update interactively an exegol image": "exegol update",
            "Install or update the [bright_blue]full[/bright_blue] image": "exegol update [bright_blue]full[/bright_blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return ExegolManager.update


class Uninstall(Command, ImageMultiSelector):
    """Remove Exegol [default not bold]image(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ImageMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove image without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Uninstall[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Uninstall interactively one or many exegol image": "exegol uninstall",
            "Uninstall the [bright_blue]dev[/bright_blue] image": "exegol uninstall [bright_blue]dev[/bright_blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerMultiSelector):
    """Remove Exegol [default not bold]container(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove container without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Remove[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Remove interactively one or many containers": "exegol remove",
            "Remove the [blue]demo[/blue] container": "exegol remove [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return ExegolManager.remove


class Exec(Command, ContainerCreation, ContainerStart):
    """Execute a command on an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerStart.__init__(self, self.groupArgs)

        self._usages = {
            "Execute the command [magenta]bloodhound[/magenta] in the container [blue]demo[/blue]":
                "exegol exec [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]'nmap -h'[/magenta] with console output":
                "exegol exec -v [blue]demo[/blue] [magenta]'nmap -h'[/magenta]",
            "Execute a command in background within the [blue]demo[/blue] container":
                "exegol exec -b [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]bloodhound[/magenta] in a temporary container based on the [bright_blue]full[/bright_blue] image":
                "exegol exec --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Execute a command in background with a temporary container":
                "exegol exec -b --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
        }

        # Overwrite default selectors
        for group in self.groupArgs.copy():
            # Find group containing default selector to remove them
            for parameter in group.options:
                if parameter.get('arg') == self.containertag or parameter.get('arg') == self.imagetag:
                    # Removing default GroupArg selector
                    self.groupArgs.remove(group)
                    break
        # Removing default selector objects
        self.containertag = None
        self.imagetag = None

        self.selector = Option("selector",
                               metavar="CONTAINER or IMAGE",
                               nargs='?',
                               action="store",
                               help="Tag used to target an Exegol container (by default) or an image (if --tmp is set).")

        # Custom parameters
        self.exec = Option("exec",
                           metavar="COMMAND",
                           nargs="+",
                           action="store",
                           help="Execute a single command in the exegol container.")
        self.daemon = Option("-b", "--background",
                             action="store_true",
                             dest="daemon",
                             help="Executes the command in background as a daemon "
                                  "(default: [red not italic]False[/red not italic])")
        self.tmp = Option("--tmp",
                          action="store_true",
                          dest="tmp",
                          help="Created a dedicated and temporary container to execute the command "
                               "(default: [red not italic]False[/red not italic])")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.selector, "required": False},
                                       {"arg": self.exec, "required": False},
                                       {"arg": self.daemon, "required": False},
                                       {"arg": self.tmp, "required": False},
                                       title="[bold cyan]Exec[/bold cyan] [blue]specific options[/blue]"))

    def __call__(self, *args, **kwargs):
        logger.debug("Running exec module")
        return ExegolManager.exec


class Info(Command, ContainerSelector):
    """Show info on containers and images (local & remote)"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Print containers and images essentials information": "exegol info",
            "Print the detailed configuration of the [blue]demo[/blue] container": "exegol info [blue]demo[/blue]",
            "Print verbose information": "exegol info [yellow3]-v[/yellow3]",
            "Print advanced information": "exegol info [yellow3]-vv[/yellow3]",
            "Print debug information": "exegol info [yellow3]-vvv[/yellow3]"
        }

    def __call__(self, *args, **kwargs):
        return ExegolManager.info


class Version(Command):
    """Print current Exegol version"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.print_version
