from exegol.console.cli.ExegolCompleter import HybridContainerImageCompleter, VoidCompleter, BuildProfileCompleter
from exegol.console.cli.actions.Command import Command, Option, GroupArg
from exegol.console.cli.actions.GenericParameters import ContainerCreation, ContainerSpawnShell, ContainerMultiSelector, ContainerSelector, ImageSelector, ImageMultiSelector, ContainerStart
from exegol.manager.ExegolManager import ExegolManager
from exegol.utils.ExeLog import logger


class Start(Command, ContainerCreation, ContainerSpawnShell):
    """Automatically create, start / resume and enter an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        self._usages = {
            "Start interactively a container": "exegol start",
            "Create a [blue]demo[/blue] container using [bright_blue]full[/bright_blue] image": "exegol start [blue]demo[/blue] [bright_blue]full[/bright_blue]",
            "Spawn a shell from [blue]demo[/blue] container": "exegol start [blue]demo[/blue]",
            "Create a container [blue]test[/blue] with a custom shared workspace": "exegol start [blue]test[/blue] [bright_blue]full[/bright_blue] -w [magenta]./project/pentest/[/magenta]",
            "Create a container [blue]test[/blue] sharing the current working directory": "exegol start [blue]test[/blue] [bright_blue]full[/bright_blue] -cwd",
            "Create a container [blue]htb[/blue] with a VPN": "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] --vpn [magenta]~/vpn/[/magenta][bright_magenta]lab_Dramelac.ovpn[/bright_magenta]",
            "Create a container [blue]app[/blue] with custom volume": "exegol start [blue]app[/blue] [bright_blue]full[/bright_blue] -V [bright_magenta]/var/app/[/bright_magenta]:[bright_magenta]/app/[/bright_magenta]",
            "Create a container [blue]app[/blue] with custom volume in [blue]ReadOnly[/blue]": "exegol start [blue]app[/blue] [bright_blue]full[/bright_blue] -V [bright_magenta]/var/app/[/bright_magenta]:[bright_magenta]/app/[/bright_magenta]:[blue]ro[/blue]",
            "Get a [blue]tmux[/blue] shell": "exegol start --shell [blue]tmux[/blue]",
            "Share a specific [blue]hardware device[/blue] [bright_black](e.g. Proxmark)[/bright_black]": "exegol start -d /dev/ttyACM0",
            "Share every [blue]USB device[/blue] connected to the host": "exegol start -d /dev/bus/usb/",
        }

    def __call__(self, *args, **kwargs):
        return ExegolManager.start


class Stop(Command, ContainerMultiSelector):
    """Stop an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Stop interactively one or more containers": "exegol stop",
            "Stop [blue]demo[/blue]": "exegol stop [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running stop module")
        return ExegolManager.stop


class Restart(Command, ContainerSelector, ContainerSpawnShell):
    """Restart an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        self._usages = {
            "Restart interactively one containers": "exegol restart",
            "Restart [blue]demo[/blue]": "exegol restart [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running restart module")
        return ExegolManager.restart


class Install(Command, ImageSelector):
    """Install or build Exegol image"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        # Create container build arguments
        self.build_profile = Option("build_profile",
                                    metavar="BUILD_PROFILE",
                                    nargs="?",
                                    action="store",
                                    help="Select the build profile used to create a local image.",
                                    completer=BuildProfileCompleter)
        self.build_log = Option("--build-log",
                                dest="build_log",
                                metavar="LOGFILE_PATH",
                                action="store",
                                help="Write image building logs to a file.")
        self.build_path = Option("--build-path",
                                 dest="build_path",
                                 metavar="DOCKERFILES_PATH",
                                 action="store",
                                 help=f"Path to the dockerfiles and sources.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.build_profile, "required": False},
                                       {"arg": self.build_log, "required": False},
                                       {"arg": self.build_path, "required": False},
                                       title="[bold cyan]Build[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Install or build interactively an exegol image": "exegol install",
            "Install or update the [bright_blue]full[/bright_blue] image": "exegol install [bright_blue]full[/bright_blue]",
            "Build interactively a local image named [blue]myimage[/blue]": "exegol install [blue]myimage[/blue]",
            "Build the [blue]myimage[/blue] image based on the [bright_blue]full[/bright_blue] profile and log the operation": "exegol install [blue]myimage[/blue] [bright_blue]full[/bright_blue] --build-log /tmp/build.log",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return ExegolManager.install


class Update(Command, ImageSelector):
    """Update an Exegol image"""

    def __init__(self) -> None:
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

    def __init__(self) -> None:
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
            "Uninstall interactively one or more exegol images": "exegol uninstall",
            "Uninstall the [bright_blue]dev[/bright_blue] image": "exegol uninstall [bright_blue]dev[/bright_blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerMultiSelector):
    """Remove Exegol [default not bold]container(s)[/default not bold]"""

    def __init__(self) -> None:
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
            "Remove interactively one or more containers": "exegol remove",
            "Remove the [blue]demo[/blue] container": "exegol remove [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return ExegolManager.remove


class Exec(Command, ContainerCreation, ContainerStart):
    """Execute a command on an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerStart.__init__(self, self.groupArgs)

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
                               help="Tag used to target an Exegol container (by default) or an image (if --tmp is set).",
                               completer=HybridContainerImageCompleter)

        # Custom parameters
        self.exec = Option("exec",
                           metavar="COMMAND",
                           nargs="+",
                           action="store",
                           help="Execute a single command in the exegol container.",
                           completer=VoidCompleter)
        self.daemon = Option("-b", "--background",
                             action="store_true",
                             dest="daemon",
                             help="Executes the command in background as a daemon "
                                  "(default: [red not italic]False[/red not italic])")
        self.tmp = Option("--tmp",
                          action="store_true",
                          dest="tmp",
                          help="Creates a dedicated and temporary container to execute the command "
                               "(default: [red not italic]False[/red not italic])")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.selector, "required": False},
                                       {"arg": self.exec, "required": False},
                                       {"arg": self.daemon, "required": False},
                                       {"arg": self.tmp, "required": False},
                                       title="[bold cyan]Exec[/bold cyan] [blue]specific options[/blue]"))

        self._usages = {
            "Execute the command [magenta]bloodhound[/magenta] in the container [blue]demo[/blue]":
                "exegol exec [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]'nmap -h'[/magenta] with console output":
                "exegol exec -v [blue]demo[/blue] [magenta]'nmap -h'[/magenta]",
            "Execute a command in [green]background[/green] within the [blue]demo[/blue] container":
                "exegol exec [green]-b[/green] [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]bloodhound[/magenta] in a temporary container based on the [bright_blue]full[/bright_blue] image":
                "exegol exec --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Execute a command in [green]background[/green] with a temporary container":
                "exegol exec [green]-b[/green] --tmp [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Execute the command [magenta]wireshark[/magenta] with [orange3]network admin[/orange3] privileged":
                "exegol exec [green]-b[/green] --tmp --disable-my-resources --cap [orange3]NET_ADMIN[/orange3] [bright_blue]full[/bright_blue] [magenta]wireshark[/magenta]",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running exec module")
        return ExegolManager.exec


class Info(Command, ContainerSelector):
    """Show info on containers and images (local & remote)"""

    def __init__(self) -> None:
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
        return lambda: None
