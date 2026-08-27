import os
from typing import Optional

from exegol.console.cli.ExegolCompleter import HybridContainerImageCompleter, VoidCompleter, BuildProfileCompleter, ImageCompleter
from exegol.console.cli.actions.Command import Command, Option, GroupArg
from exegol.console.cli.actions.GenericParameters import ContainerCreation, ContainerSpawnShell, ContainerMultiSelector, ContainerSelector, ImageSelector, ImageMultiSelector, ContainerStart
from exegol.manager.ExegolManager import ExegolManager
from exegol.utils.ExeLog import logger


class Start(Command, ContainerCreation, ContainerSpawnShell):
    """Automatically create, start, resume and enter an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        self._usages = {
            "Get started with Exegol [bright_black](interactive)[/bright_black]": "exegol start",
            "Create the [blue]demo[/blue] container using the [bright_blue]full[/bright_blue] image": "exegol start [blue]demo[/blue] [bright_blue]full[/bright_blue]",
            "Spawn a shell from the [blue]demo[/blue] container": "exegol start [blue]demo[/blue]",
            "Create the [blue]app[/blue] container with the [green]full graphical desktop[/green]": "exegol start [blue]app[/blue] [bright_blue]full[/bright_blue] [green]--desktop[/green]",
            "Create the [blue]test[/blue] container with a custom shared workspace": "exegol start [blue]test[/blue] [bright_blue]full[/bright_blue] -w [magenta]./project/pentest/[/magenta]",
            "Create the [blue]htb[/blue] container with a VPN": "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] --vpn [magenta]~/vpn/[/magenta][bright_magenta]lab_Dramelac.ovpn[/bright_magenta]",
            "Get a [blue]tmux[/blue] shell": "exegol start --shell [blue]tmux[/blue]",
            "Share a specific [blue]hardware device[/blue] [bright_black](e.g. Proxmark)[/bright_black]": "exegol start -d [bright_magenta]/dev/ttyACM0[/bright_magenta]",
            "Share every [blue]USB device[/blue] connected to the host": "exegol start -d [magenta]/dev/bus/usb/[/magenta]",
        }

    def __call__(self, *args, **kwargs):
        return ExegolManager.start


class Stop(Command, ContainerMultiSelector):
    """Stop an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Stop container(s) [bright_black](interactive)[/bright_black]": "exegol stop",
            "Stop the [blue]demo[/blue] container": "exegol stop [blue]demo[/blue]"
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
            "Restart a container [bright_black](interactive)[/bright_black]": "exegol restart",
            "Restart the [blue]demo[/blue] container": "exegol restart [blue]demo[/blue]"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running restart module")
        return ExegolManager.restart


class Install(Command, ImageSelector):
    """Install an Exegol image"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Install an image and exegol-resources without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bright_blue]Install[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Install an Exegol image [bright_black](interactive)[/bright_black]": "exegol install",
            "Install the [bright_blue]full[/bright_blue] image [bright_black](unattended)[/bright_black]": "exegol install [bright_blue]full[/bright_blue] -F"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running install module")
        return ExegolManager.install


class Build(Command, ImageSelector):
    """Build a local Exegol image"""

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
                                       title="[bright_blue]Build[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Build an Exegol image [bright_black](interactive)[/bright_black]": "exegol build",
            "Build the [blue]myimage[/blue] image based on the [bright_blue]full[/bright_blue] profile, with logs": "exegol build [blue]myimage[/blue] [bright_blue]full[/bright_blue] --build-log /tmp/build.log",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running build module")
        return ExegolManager.build


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
                                       title="[bright_blue]Update[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Update an Exegol image [bright_black](interactive)[/bright_black]": "exegol update",
            "Update the [bright_blue]full[/bright_blue] image": "exegol update [bright_blue]full[/bright_blue]",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        return ExegolManager.update


class Upgrade(Command, ContainerMultiSelector):
    """Upgrade Exegol container(s)"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Upgrade container without interactive user confirmation.")

        self.no_backup = Option("--no-backup",
                                dest="no_backup",
                                action="store_true",
                                help="Remove the outdated container after the upgrade instead of renaming it.")

        self.image_tag: Optional[Option] = Option("--image",
                                                  dest="image_tag",
                                                  action="store",
                                                  help="Upgrade the container to another Exegol image using its tag",
                                                  completer=ImageCompleter)

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.image_tag, "required": False},
                                       {"arg": self.no_backup, "required": False},
                                       {"arg": self.force_mode, "required": False},
                                       title="[bright_blue]Upgrade[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Upgrade an Exegol container [bright_black](interactive)[/bright_black]": "exegol upgrade",
            "Upgrade the [blue]ctf[/blue] container": "exegol upgrade [blue]ctf[/blue]",
            "Upgrade the [blue]test[/blue] container to the [bright_blue]full[/bright_blue] image": "exegol upgrade --image [bright_blue]full[/bright_blue] [blue]test[/blue]",
            "Upgrade [blue]lab[/blue] and [blue]test[/blue] containers [bright_black](unattended)[/bright_black]": "exegol upgrade -F [blue]lab[/blue] [blue]test[/blue]",
            "Upgrade all outdated containers": "exegol upgrade --all",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running upgrade module")
        return ExegolManager.upgrade


class Uninstall(Command, ImageMultiSelector):
    """Uninstall Exegol image(s)"""

    def __init__(self) -> None:
        Command.__init__(self)
        ImageMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove image without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bright_blue]Uninstall[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Uninstall Exegol image(s) [bright_black](interactive)[/bright_black]": "exegol uninstall",
            "Uninstall the [bright_blue]dev[/bright_blue] image [bright_black](unattended)[/bright_black]": "exegol uninstall [bright_blue]dev[/bright_blue] -F"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running uninstall module")
        return ExegolManager.uninstall


class Remove(Command, ContainerMultiSelector):
    """Remove Exegol container(s)"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerMultiSelector.__init__(self, self.groupArgs)

        self.force_mode = Option("-F", "--force",
                                 dest="force_mode",
                                 action="store_true",
                                 help="Remove container without interactive user confirmation.")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.force_mode, "required": False},
                                       title="[bright_blue]Remove[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Remove Exegol container(s) [bright_black](interactive)[/bright_black]": "exegol remove",
            "Remove the [blue]demo[/blue] container": "exegol remove [blue]demo[/blue]",
            "Remove the [blue]demo[/blue] container [bright_black](unattended)[/bright_black]": "exegol remove [blue]demo[/blue] -F"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running remove module")
        return ExegolManager.remove


class Exec(Command, ContainerCreation, ContainerStart):
    """Execute a command in an Exegol container"""

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
                                       title="[bright_blue]Exec[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Execute the [magenta]bloodhound[/magenta] command in the [blue]demo[/blue] container":
                "exegol exec [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute the [magenta]'nmap -h'[/magenta] command, with [green]console output[/green]":
                "exegol exec [green]-v[/green] [blue]demo[/blue] [magenta]'nmap -h'[/magenta]",
            "Execute a command, in the [green]background[/green]":
                "exegol exec [green]-b[/green] [blue]demo[/blue] [magenta]bloodhound[/magenta]",
            "Execute a command in a [green]temporary[/green] container based on the [bright_blue]full[/bright_blue] image":
                "exegol exec [green]--tmp[/green] [bright_blue]full[/bright_blue] [magenta]bloodhound[/magenta]",
            "Launch [magenta]wireshark[/magenta] in a container with [orange3]network admin[/orange3] privileges)":
                "exegol exec -b --tmp --cap [orange3]NET_ADMIN[/orange3] [bright_blue]full[/bright_blue] [magenta]wireshark[/magenta]",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running exec module")
        return ExegolManager.exec


class Info(Command, ContainerSelector):
    """Show info on containers, images and user config"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        self._usages = {
            "Show the essentials (images, containers)": "exegol info",
            "User config file and verbose information": "exegol info -v",
            "Config of the [blue]demo[/blue] container": "exegol info [blue]demo[/blue]",
        }

    def __call__(self, *args, **kwargs):
        return ExegolManager.info


class Activate(Command):
    """Activate an Exegol license"""

    def __init__(self) -> None:
        Command.__init__(self)

        self._usages = {
            "Activate Exegol [bright_black](interactive)[/bright_black]": "exegol activate",
            "Revoke the current license": "exegol activate --revoke",
            "Activate Exegol using an [green]API Key[/green] and a [green]license ID[/green] [bright_black](unattended)[/bright_black]": "exegol activate --accept-eula --api [green]API_KEY[/green] --license-id [green]LICENSE_ID[/green]",
        }

        self.revoke = Option("--revoke",
                             action="store_true",
                             dest="revoke",
                             help="Revoke your local Exegol license "
                                  "(default: [bright_black]False[/bright_black])")

        self.api_key = Option("--api",
                              action="store",
                              dest="api_key",
                              default=os.environ.get("EXEGOL_API_KEY"),
                              help="Use an API Key to activate Exegol")

        self.license_id = Option("--license-id",
                                 action="store",
                                 dest="license_id",
                                 default=os.environ.get("EXEGOL_LICENSE_ID"),
                                 help="License ID to activate Exegol")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.revoke, "required": False},
                                       {"arg": self.api_key, "required": False},
                                       {"arg": self.license_id, "required": False},
                                       title="[bright_blue]Activate[/bright_blue][blue]-only options[/blue]"))

    def __call__(self, *args, **kwargs):
        return ExegolManager.activate


class Version(Command):
    """Show the current Exegol Wrapper version"""

    def __call__(self, *args, **kwargs):
        return None
