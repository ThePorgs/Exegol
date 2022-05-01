import os
from argparse import Namespace
from typing import List, Optional, Tuple, Union, Dict, cast

from exegol.console.ConsoleFormat import richLen
from exegol.utils.ExeLog import logger


class Option:
    """This object allows to define and configure an argparse parameter"""

    def __init__(self, *args, dest: Optional[str] = None, **kwargs):
        """Generic class to handle Key:Value object directly from the constructor"""
        # Set arguments to the object to save every setting, these values will be sent to the argparser
        self.args = args
        self.kwargs = kwargs
        if dest is not None:
            self.kwargs["dest"] = dest
        self.dest = dest

    def __repr__(self) -> str:
        """This overload allows to format the name of the object.
        Mainly used by developers to easily identify objects"""
        return f"Option: {str(self.dest) if self.dest is not None else self.kwargs.get('metavar', 'Option not found')}"


class GroupArg:
    """This object allows you to group a set of options within the same group"""

    def __init__(self, *options, title: Optional[str] = None, description: Optional[str] = None,
                 is_global: bool = False):
        self.title = title
        self.description = description
        self.options: Tuple[Dict[str, Union[Option, bool]]] = cast(Tuple[Dict[str, Union[Option, bool]]], options)
        self.is_global = is_global

    def __repr__(self) -> str:
        """This overload allows to format the name of the object.
        Mainly used by developers to easily identify objects"""
        return f"GroupArg: {self.title}"


class Command:
    """The Command class is the root of all CLI actions"""

    def __init__(self):
        # Root command usages (can be overwritten by subclasses to display different use cases)
        self._pre_usages = "[underline]To see specific examples run:[/underline][italic] exegol [cyan]command[/cyan] -h[/italic]"
        self._usages = {
            "Install (or build) (↓ ~25GB max)": "exegol install",
            "Open an exegol shell": "exegol start",
            "Show exegol images & containers": "exegol info",
            "Update an image": "exegol update",
            "See commands examples to execute": "exegol exec -h",
            "Remove a container": "exegol remove",
            "Uninstall an image": "exegol uninstall",
            "Stop a container": "exegol stop"
        }
        self._post_usages = ""

        # Name of the object
        self.name = type(self).__name__.lower()
        # Global parameters
        self.verify = Option("-k", "--insecure",
                             dest="verify",
                             action="store_false",
                             default=True,
                             required=False,
                             help="Allow insecure server connections for web requests, "
                                  "e.g. when fetching info from DockerHub "
                                  "(default: [red not italic]False[/red not italic])")
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
        # TODO review non-interactive mode
        #self.interactive_mode = Option("--non-interactive",
        #                               dest="interactive_mode",
        #                               action="store_false",
        #                               help="[red](WIP)[/red] Prevents Exegol from interactively requesting information. "
        #                                    "If critical information is missing, an error will be raised.")

        # Main global group of argparse
        self.groupArgs = [
            GroupArg({"arg": self.verify, "required": False},
                     {"arg": self.quiet, "required": False},
                     #{"arg": self.interactive_mode, "required": False},
                     {"arg": self.verbosity, "required": False},
                     title="[blue]Optional arguments[/blue]",
                     is_global=True)
        ]

    def __call__(self, *args, **kwargs):
        """This method is called by the main controller (ExegolController)
        to get the function, execute it and launch the action.
        This method must be overloaded in all child classes to ensure the correct execution of the thread"""
        logger.debug("The called command is : ", self.name)
        logger.debug("the object is", type(self).__name__)
        raise NotImplementedError

    def __repr__(self) -> str:
        """This overload allows to format the name of the object.
        Mainly used by developers to easily identify objects"""
        return self.name

    def populate(self, args: Namespace):
        """This method replaces the parsing objects (Option) with the result of the parsing"""
        for arg in vars(args).keys():
            # Check if the argument exist in the current class
            if arg in self.__dict__:
                # If so, overwrite it with the corresponding value after parsing
                self.__setattr__(arg, vars(args)[arg])

    def check_parameters(self) -> List[str]:
        """This method identifies the missing required parameters"""
        missingOption = []
        for groupArg in self.groupArgs:
            for option in groupArg.options:
                if option["required"]:
                    if self.__dict__[option["arg"].dest] is None:
                        missingOption.append(option["arg"].dest)
        return missingOption

    def formatEpilog(self) -> str:
        epilog = "[blue]Examples:[/blue]" + os.linesep
        epilog += self._pre_usages + os.linesep
        keys_len = {}
        # Replace [.*] rich tag for line length count
        for k in self._usages.keys():
            keys_len[k] = richLen(k)
        max_key = max(keys_len.values())
        for k, v in self._usages.items():
            space = ' ' * (max_key - keys_len.get(k, 0) + 2)
            epilog += f"  {k}:{space}[i]{v}[/i]{os.linesep}"
        epilog += self._post_usages + os.linesep
        return epilog
