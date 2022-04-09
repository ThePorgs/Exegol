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
            "Create a [green]demo[/green] container using [orange3]full[/orange3] image": "exegol start [green]demo[/green] [orange3]full[/orange3]",
            "Spawn a shell from [green]demo[/green] container": "exegol start [green]demo[/green]",
            "Create a container [green]test[/green] with a custom shared workspace": "exegol start [green]test[/green] [orange3]full[/orange3] -w ./project/pentest",
            "Create a container [green]test[/green] sharing the current working directory": "exegol start [green]test[/green] [orange3]full[/orange3] -cwd",
            "Create a container [green]htb[/green] with a VPN": "exegol start [green]htb[/green] [orange3]full[/orange3] --vpn ~/vpn/lab_Dramelac.ovpn",
            "Create a container [green]app[/green] with custom volume": "exegol start [green]app[/green] [orange3]full[/orange3] -V '/var/app/:/app/'",
            "Get a tmux shell": "exegol start --shell tmux",
            "Use a Proxmark": "exegol start -d /dev/ttyACM0",  # TODO review usages
            "Use a LOGITacker": "exegol start -d /dev/ttyACM0",
            "Use an ACR122u": "exegol start -d /dev/bus/usb/",
            "Use an HackRF One": "exegol start -d /dev/bus/usb/",
            "Use an Crazyradio PA": "exegol start -d /dev/bus/usb/",
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


class Stop(Command, ContainerSelector):
    """Stop an Exegol container"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Stop interactively one or multiple container": "exegol stop",
            "Stop 'demo'": "exegol stop [green]demo[/green]"
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
            "Install or update the [orange3]full[/orange3] image": "exegol install [orange3]full[/orange3]",
            "Build [orange3]local[/orange3] image": "exegol install [orange3]local[/orange3]"
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

        self._usages = {
            "Install or update interactively an exegol image": "exegol update",
            "Install or update the [orange3]full[/orange3] image": "exegol update [orange3]full[/orange3]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return ExegolManager.update


class Uninstall(Command, ImageSelector):
    """Remove Exegol [default not bold]image(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove image without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Uninstall[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Uninstall interactively one or many exegol image": "exegol uninstall",
            "Uninstall the [orange3]dev[/orange3] image": "exegol uninstall [orange3]dev[/orange3]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerSelector):
    """Remove Exegol [default not bold]container(s)[/default not bold]"""

    def __init__(self):
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove container without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bold cyan]Remove[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Remove interactively one or many containers": "exegol remove",
            "Remove the [green]demo[/green] container": "exegol remove [green]demo[/green]"
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
            "Execute the command [blue]bloodhound[/blue] in the container [green]demo[/green]":
                "exegol exec [green]demo[/green] [blue]bloodhound[/blue]",
            "Execute the command [blue]bloodhound[/blue] in a temporary container based on the [orange3]full[/orange3] image":
                "exegol exec --tmp [orange3]full[/orange3] [blue]bloodhound[/blue]",
            "Execute the command [blue]'nmap -h'[/blue] with console output":
                "exegol exec -v [green]demo[/green] [blue]'nmap -h'[/blue]",
            "Execute a command in background within the [green]demo[/green] container":
                "exegol exec -b [green]demo[/green] [blue]bloodhound[/blue]",
            "Execute a command in background with a temporary container":
                "exegol exec -b --tmp [orange3]full[/orange3] [blue]bloodhound[/blue]",
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
                                  "(default: [red bold not italic]False[/red bold not italic])")
        self.tmp = Option("--tmp",
                          action="store_true",
                          dest="tmp",
                          help="Created a dedicated and temporary container to execute the command "
                               "(default: [red bold not italic]False[/red bold not italic])")

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
            "Print the detailed configuration of the [green]demo[/green] container": "exegol info [green]demo[/green]",
            "Print advanced information": "exegol info [green]-v[/green]",
            "Print full information": "exegol info [green]-vv[/green]"
        }

    def __call__(self, *args, **kwargs):
        return ExegolManager.info


class Version(Command):
    """Print current Exegol version"""

    def __call__(self, *args, **kwargs):
        return ExegolManager.print_version
