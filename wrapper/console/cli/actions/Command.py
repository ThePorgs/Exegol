from argparse import Namespace
from typing import List, Optional, Tuple, Union, Dict, cast

from wrapper.utils.ExeLog import logger


class Option:
    """This object allows to define and configure an argparse parameter"""

    def __init__(self, *args, dest: Optional[str] = None, **kwargs):
        """Generic class to handle Key:Value object directly from the constructor"""
        # Set arguments to the object to save every setting, these values will be sent to argparser
        self.args = args
        self.kwargs = kwargs
        if dest is not None:
            self.kwargs["dest"] = dest
        self.dest = dest


class GroupArg:
    """This object allows you to group a set of options within the same group"""

    def __init__(self, *options, title: Optional[str] = None, description: Optional[str] = None,
                 is_global: bool = False):
        self.title = title
        self.description = description
        self.options: Tuple[Dict[str, Union[Option, bool]]] = cast(Tuple[Dict[str, Union[Option, bool]]], options)
        self.is_global = is_global


class Command:
    """The Command class is the root of all CLI actions"""

    def __init__(self):
        # Name of the object
        self.name = type(self).__name__.lower()
        # Global parameters
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

        # Main global group of argparse
        self.groupArgs = [
            GroupArg({"arg": self.verify, "required": False},
                     {"arg": self.quiet, "required": False},
                     {"arg": self.verbosity, "required": False},
                     title="[blue]Optional arguments[/blue]",
                     is_global=True)
        ]

    def __call__(self, *args, **kwargs):
        """This method is called by the main controller (ExegolController)
        to get the function to execute to launch the action.
        This method must be overloaded in all child classes to ensure the correct execution of the thread"""
        logger.debug("The called command is : ", self.name)
        logger.debug("the object is", type(self).__name__)
        raise NotImplementedError

    def __repr__(self):
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
