import argparse
import os
from typing import Optional

from argcomplete.completers import DirectoriesCompleter, FilesCompleter

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.console.cli.ExegolCompleter import HybridContainerImageCompleter, VoidCompleter, BuildProfileCompleter, ImageCompleter, ProfileCompleter
from exegol.console.cli.SentinelCompleter import SentinelProfileCompleter
from exegol.console.cli.actions.Command import Command, Option, GroupArg
from exegol.console.cli.actions.GenericParameters import ContainerCreation, ContainerSpawnShell, ContainerMultiSelector, ContainerSelector, ImageSelector, ImageMultiSelector, ContainerStart
from exegol.utils.ExeLog import logger


class Start(Command, ContainerCreation, ContainerSpawnShell):
    """Automatically create, start, resume and enter an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerCreation.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        # Required value (no `nargs='?'`): an optional value would greedily swallow the
        # container positional. An empty or unknown name falls back to the interactive
        # picker, on a TTY only.
        # Same dest as `Info`'s flag: `RESOLVER_EXCLUDED["profile"]` covers both. `profile`
        # must never be registered in `_REGISTRY` nor made profilable: it selects which
        # profile supplies the profile tier.
        # `-P` and `-p` (`--port`) differ only by case. `-SP` still wins over `-S` + `-P`
        # (argparse matches exact option strings first); `-SPsoc` parses as `-S -P soc`.
        self.profile = Option("-P", "--profile",
                              dest="profile",
                              metavar="CONTAINER_PROFILE",
                              action="store",
                              default=None,
                              completer=ProfileCompleter,
                              help="Apply a named [blue]container[/blue] configuration profile to the container being "
                                   "created. Its declared options are applied at creation only, and anything typed on "
                                   "the command line wins over them. A container profile is a named set of "
                                   "container-shape defaults.")

        self.groupArgs.append(GroupArg({"arg": self.profile, "required": False},
                                       title="[bright_blue]Container profile[/bright_blue][blue] options[/blue]"))

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
            "Create the [blue]htb[/blue] container from the [green]redteam[/green] profile":
                "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] [green]--profile redteam[/green]",
            "Create a container from a profile, overriding its shell":
                "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] [green]-P redteam[/green] --shell [blue]tmux[/blue]",
            "Create the [blue]audit[/blue] container with [green]Sentinel[/green] command logging":
                "exegol start [blue]audit[/blue] [bright_blue]full[/bright_blue] [green]-S[/green]",
            "Create it with a named [green]Sentinel audit profile[/green]":
                "exegol start [blue]audit[/blue] [bright_blue]full[/bright_blue] [green]-SP soc[/green]",
            "Refuse a setting the profile turns on [bright_black](every toggle has a [/bright_black]--no-[bright_black] half)[/bright_black]":
                "exegol start [blue]htb[/blue] [bright_blue]full[/bright_blue] [green]--profile redteam[/green] --no-gui",
        }

    def __call__(self, *args, **kwargs):
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
        return ExegolManager.stop


class Restart(Command, ContainerSelector, ContainerSpawnShell):
    """Restart an Exegol container"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)
        ContainerSpawnShell.__init__(self, self.groupArgs)

        # Not -F/--force: only forces Sentinel config regeneration at restart, even with the 'disabled' strategy.
        self.sentinel_refresh = Option("--sentinel-refresh",
                                       dest="sentinel_refresh",
                                       action="store_true",
                                       help="Force a Sentinel profile config refresh from host sources at restart, "
                                            "even for containers whose update strategy is 'disabled'.")

        self.groupArgs.append(GroupArg({"arg": self.sentinel_refresh, "required": False},
                                       title="[bright_blue]Restart[/bright_blue][blue]-only options[/blue]"))

        self._usages = {
            "Restart a container [bright_black](interactive)[/bright_black]": "exegol restart",
            "Restart the [blue]demo[/blue] container": "exegol restart [blue]demo[/blue]",
            "Restart [blue]demo[/blue] and force-refresh its Sentinel config": "exegol restart [blue]demo[/blue] --sentinel-refresh"
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running restart module")
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
                                help="Write image building logs to a file.",
                                completer=FilesCompleter())
        self.build_path = Option("--build-path",
                                 dest="build_path",
                                 metavar="DOCKERFILES_PATH",
                                 action="store",
                                 help=f"Path to the dockerfiles and sources.",
                                 completer=DirectoriesCompleter())

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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
        return ExegolManager.build


class Update(Command):
    """Update an Exegol image"""

    def __init__(self) -> None:
        Command.__init__(self)

        # One positive selector per update step; selectors combine, and none selected runs all.
        # Short letters follow the wrapper-wide convention: `-P` container profile, `-S`
        # Sentinel (lowercase `-p`/`-s` are rejected here on purpose).
        # Check `exegol update -h` after adding a flag: argParse.py silently drops a
        # duplicate flag while its dest stays declared.
        # `--wrapper` is hidden, not removed, on a package-manager install, so `-w` still
        # reaches the explanation of how to upgrade.
        self.update_wrapper = Option("-w", "--wrapper",
                                     dest="update_wrapper",
                                     action="store_true",
                                     help="Update the [green]Exegol wrapper[/green] itself."
                                          if ConstantConfig.git_source_installation else argparse.SUPPRESS)

        self.update_resources = Option("-r", "--resources",
                                       dest="update_resources",
                                       action="store_true",
                                       help="Update the [green]Exegol resources[/green] shared with every container.")

        # Private dests (`update_profile`, `update_sentinel`): `profile` is resolver-excluded
        # (it names a profile), and `sentinel` is the container-shape toggle, so reusing
        # either would answer the wrong question.
        # `--profile` reaches `--profiles` through argparse prefix matching; declaring both
        # would make every shorter prefix ambiguous. A future `--profile-*` flag here would
        # break the singular spelling.
        self.update_profile = Option("-P", "--profiles",
                                     dest="update_profile",
                                     action="store_true",
                                     help="Update the [blue]container profile[/blue] sources configured on this host.")

        self.update_sentinel = Option("-S", "--sentinel",
                                      dest="update_sentinel",
                                      action="store_true",
                                      help="Update the [green]Sentinel[/green] audit profile sources configured on this host.")

        # Reuses the `imagetag` dest (`OptionKey.IMAGE_TAG`); safe since `update` never shares
        # an invocation with the creation actions.
        # Bare `-i` opens the image picker, `-i full` names one. nargs='?' consumes the next
        # token, so `-i` goes last in examples. `--image` reaches `--images` by prefix.
        # The metavar also names the option in the ignored-parameter warning.
        self.imagetag: Optional[Option] = Option("-i", "--images",
                                                 dest="imagetag",
                                                 metavar="IMAGE",
                                                 action="store",
                                                 nargs='?',
                                                 const=True,
                                                 default=None,
                                                 completer=ImageCompleter,
                                                 help="Update an Exegol [bright_blue]image[/bright_blue]: pick one "
                                                      "interactively, or name it directly.")

        # All update target selectors in one help group.
        self.groupArgs.append(GroupArg({"arg": self.update_wrapper, "required": False},
                                       {"arg": self.update_resources, "required": False},
                                       {"arg": self.update_profile, "required": False},
                                       {"arg": self.update_sentinel, "required": False},
                                       {"arg": self.imagetag, "required": False},
                                       title="[bright_blue]Update target[/bright_blue][blue] options[/blue]"))

        self._usages = {
            "Update [gold3]everything[/gold3] [bright_black](wrapper, resources, Sentinel, profiles, image)[/bright_black]": "exegol update",
            "Update an Exegol image [bright_black](interactive)[/bright_black]": "exegol update -i",
            # `-i` last, and never mid-example: nargs='?' greedily consumes the next token.
            "Update the [bright_blue]full[/bright_blue] image and nothing else": "exegol update --image [bright_blue]full[/bright_blue]",
            "Update the [green]wrapper[/green] only": "exegol update -w",
            "Update the [blue]container profile[/blue] and [green]Sentinel[/green] sources together": "exegol update -P -S",
        }

    def __call__(self, *args, **kwargs):
        logger.debug("Running update module")
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
        return ExegolManager.exec


class Info(Command, ContainerSelector):
    """Show info on containers, images and user config"""

    def __init__(self) -> None:
        Command.__init__(self)
        ContainerSelector.__init__(self, self.groupArgs)

        # Explicit section selectors (`-v` only controls verbosity). Private `info_*` dests:
        # they govern this invocation, not the container shape.
        # One letter per concept across actions: `-P` container profile, `-S` Sentinel.
        # `-s` (sources) and `-S` (sentinel) differ only by case; both are covered by the
        # alias matrix test.
        self.info_config = Option("-c", "--config",
                                  dest="info_config",
                                  action="store_true",
                                  help="Show the [gold3]user configuration[/gold3] table: the wrapper settings currently "
                                       "in effect, and where they come from.")

        # Git status of the wrapper, image and resource sources.
        self.info_sources = Option("-s", "--sources",
                                   dest="info_sources",
                                   action="store_true",
                                   help="Show the [gold3]project sources[/gold3] table: the git status of the wrapper, "
                                        "image and resource sources currently installed.")

        # Bare `--profiles` lists, `--profiles NAME` shows one. nargs='?' consumes the next
        # token, so name the container before this flag. `--profile` reaches it by prefix.
        self.profile = Option("-P", "--profiles",
                              dest="profile",
                              metavar="CONTAINER_PROFILE",
                              action="store",
                              nargs='?',
                              const=True,
                              default=None,
                              completer=ProfileCompleter,
                              help="List the available [blue]container[/blue] configuration profiles, or show one by name. "
                                   "A container profile is a named set of container-shape defaults.")

        # Sentinel counterpart of `--profiles`, same shape. Reuses the creation-time
        # `sentinel` dest; safe since `info` never builds a container. Unlike the creation
        # toggle, it takes an optional name and has no `--no-` half.
        self.sentinel = Option("-S", "--sentinel",
                               dest="sentinel",
                               metavar="SENTINEL_PROFILE",
                               action="store",
                               nargs='?',
                               const=True,
                               default=None,
                               completer=SentinelProfileCompleter,
                               help="List the available [green]Sentinel[/green] audit profiles, or show one by name. "
                                    "A Sentinel profile is a named set of audit triggers and actions.")

        # Every section, in a fixed order; wins over named sections (no mutual-exclusion group).
        # Same string as `MultiSelector`'s `--all` but a distinct dest, and `Info` never
        # inherits `MultiSelector`, so they cannot conflict.
        self.info_all = Option("-a", "--all",
                               dest="info_all",
                               action="store_true",
                               # With a named container, its recap replaces the container table.
                               help="Show [gold3]every[/gold3] section: user configuration, project sources, container "
                                    "profiles, Sentinel profiles, images, and every container (or the recap of the "
                                    "one you named).")

        # Section selectors in one group; the container positional keeps its own (target, not section).
        self.groupArgs.append(GroupArg({"arg": self.info_config, "required": False},
                                       {"arg": self.info_sources, "required": False},
                                       {"arg": self.profile, "required": False},
                                       {"arg": self.sentinel, "required": False},
                                       {"arg": self.info_all, "required": False},
                                       title="[bright_blue]Info section[/bright_blue][blue] options[/blue]"))

        self._usages = {
            "Show the essentials (images, containers)": "exegol info",
            "Show your [gold3]user configuration[/gold3]": "exegol info --config",
            "Show the [gold3]project sources[/gold3] git status": "exegol info --sources",
            "Show the configuration and the sources together": "exegol info --config --sources",
            "Show [gold3]every[/gold3] section": "exegol info --all",
            "Config of the [blue]demo[/blue] container": "exegol info [blue]demo[/blue]",
            "List available container profiles": "exegol info --profile",
            "Show the [blue]redteam[/blue] container profile": "exegol info --profile [blue]redteam[/blue]",
            "List available Sentinel profiles": "exegol info --sentinel",
            "Show the [green]demo[/green] Sentinel profile": "exegol info --sentinel [green]demo[/green]",
        }

    def __call__(self, *args, **kwargs):
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
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
                              default=EnvInfo.get_env("EXEGOL_API_KEY"),
                              help="Use an API Key to activate Exegol")

        self.license_id = Option("--license-id",
                                 action="store",
                                 dest="license_id",
                                 default=EnvInfo.get_env("EXEGOL_LICENSE_ID"),
                                 help="License ID to activate Exegol")

        # Create group parameter for container selection
        self.groupArgs.append(GroupArg({"arg": self.revoke, "required": False},
                                       {"arg": self.api_key, "required": False},
                                       {"arg": self.license_id, "required": False},
                                       title="[bright_blue]Activate[/bright_blue][blue]-only options[/blue]"))

    def __call__(self, *args, **kwargs):
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
        return ExegolManager.activate


class Completion(Command):
    """Generate the shell completion script of the Exegol wrapper"""

    # Printing a static shell script must not require a running docker daemon
    require_docker = False
    # The generated script is meant to be redirected to a file, it must be the only thing on stdout
    stdout_is_data = True

    def __init__(self) -> None:
        Command.__init__(self)

        self.shell_type = Option("shell_type",
                                 metavar="SHELL",
                                 nargs="?",
                                 action="store",
                                 choices={"bash", "zsh", "fish", "tcsh", "powershell"},
                                 default=None,
                                 help="Shell to generate the completion script for "
                                      "(default: [blue]auto-detected[/blue])")

        self.groupArgs.append(GroupArg({"arg": self.shell_type, "required": False},
                                       title="[bright_blue]Completion[/bright_blue][blue]-only options[/blue]"))

        self._pre_usages = ("Once installed, restart your shell to complete container and image names "
                            "with [blue]<TAB>[/blue]." + os.linesep)
        self._usages = {
            "Show the script of the [bright_black](auto-detected)[/bright_black] current shell": "exegol completion",
            "Show the script of a specific shell": "exegol completion [blue]zsh[/blue]",
        }
        self._post_usages = (os.linesep +
                             "[blue]Installation:[/blue]" + os.linesep +
                             "  [bright_blue]bash[/bright_blue]" + os.linesep +
                             "    [i]mkdir -p ~/.local/share/bash-completion/completions[/i]" + os.linesep +
                             "    [i]exegol completion bash > ~/.local/share/bash-completion/completions/exegol[/i]" + os.linesep +
                             "  [bright_blue]zsh[/bright_blue] [bright_black](the completion directory must be in your fpath before compinit)[/bright_black]" + os.linesep +
                             "    [i]mkdir -p ~/.zsh/completions[/i]" + os.linesep +
                             "    [i]exegol completion zsh > ~/.zsh/completions/_exegol[/i]" + os.linesep +
                             "    [bright_black]# in ~/.zshrc, before compinit:[/bright_black] [i]fpath=(~/.zsh/completions $fpath)[/i]" + os.linesep +
                             "  [bright_blue]fish[/bright_blue]" + os.linesep +
                             "    [i]exegol completion fish > ~/.config/fish/completions/exegol.fish[/i]")

    def __call__(self, *args, **kwargs):
        logger.debug("Running completion module")
        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.ExegolManager import ExegolManager
        return ExegolManager.completion


class Version(Command):
    """Show the current Exegol Wrapper version"""

    def __call__(self, *args, **kwargs):
        return None
