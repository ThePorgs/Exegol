import argparse
from logging import CRITICAL
from typing import IO, Optional, List, Union, Dict, cast

from exegol.console.cli.actions.Command import Command, Option
from exegol.utils.ExeLog import logger


class ExegolArgParse(argparse.ArgumentParser):
    """Overloading of the main parsing (argparse.ArgumentParser) class"""

    # Using Exelog to print built-in parser message
    def _print_message(self, message: str, file: Optional[IO[str]] = None) -> None:
        if message:
            logger.raw(message, level=CRITICAL, rich_parsing=True)


class Parser:
    """Custom Exegol CLI Parser. Main controller of argument building and parsing."""

    __description = "This Python script is a wrapper for Exegol. It can be used to easily manage Exegol on " \
                    "your machine."
    __formatter_class: type = argparse.RawTextHelpFormatter

    def __init__(self, actions: List[Command]):
        """Custom parser creation"""
        # Defines every actions available
        self.__actions: List[Command] = actions
        # Create & init root parser
        self.__root_parser: ExegolArgParse
        self.__init_parser()
        # Configure root options
        # (WARNING: these parameters are duplicate with every sub-parse, cannot use positional args here)
        self.__set_options(self.__root_parser, Command())  # Add global arguments from Command to the root parser
        # Create & fill sub-parser
        self.subParser = self.__root_parser.add_subparsers(help="Description of the actions")
        self.__set_action_parser()

    def __init_parser(self) -> None:
        """Root parser creation"""

        self.__root_parser = ExegolArgParse(
            description=self.__description,
            epilog=Command().formatEpilog(),
            formatter_class=self.__formatter_class,
        )

    def __set_action_parser(self) -> None:
        """Create sub-parser for each action and configure it"""
        self.__root_parser._positionals.title = "[green]Required arguments[/green]"
        for action in self.__actions:
            # Each action has a dedicated sub-parser with different options
            # the 'help' description of the current action is retrieved
            # from the comment of the corresponding action class
            sub_parser = self.subParser.add_parser(action.name, help=action.__doc__,
                                                   description=action.__doc__,
                                                   epilog=action.formatEpilog(),
                                                   formatter_class=self.__formatter_class)
            sub_parser.set_defaults(action=action)
            self.__set_options(sub_parser, target=action)

    def __set_options(self, sub_parser: argparse.ArgumentParser, target: Optional[Command] = None) -> None:
        """Add different groups and parameters/options in the current sub_parser"""
        global_set = False  # Only one group can be global at the time
        # Load actions to be processed (default: every action from cls)
        actions_list = [target] if target else self.__actions
        for action in actions_list:
            # On each action, fetch every group to be processed
            for argument_group in action.groupArgs:
                group_parser: argparse._ActionsContainer
                if argument_group.is_global and not global_set:
                    # If the current group is global (ex: 'Optional arguments'),
                    # overwriting parser main group before adding custom parameters
                    global_set = True  # The setup application should be run only once
                    sub_parser._optionals.title = argument_group.title  # Overwriting default argparse title
                    group_parser = sub_parser  # Subparser is directly used to add arguments
                else:
                    # In every other case, a dedicated group is created in the parser
                    group_parser = sub_parser.add_argument_group(argument_group.title,
                                                                 description=argument_group.description)
                # once the group is created in the parser, the arguments can be added to it
                option: Dict[str, Union[Option, bool]]
                for option in argument_group.options:
                    try:
                        # Retrieve Option object from the Dict
                        assert type(option["arg"]) is Option
                        argument = cast(Option, option["arg"])
                        # Add argument with its config to the parser
                        group_parser.add_argument(*argument.args, **argument.kwargs)
                    except argparse.ArgumentError:
                        continue

    def run_parser(self) -> argparse.Namespace:
        """Execute argparse to retrieve user options from argv"""
        return self.__root_parser.parse_args()

    def print_help(self):
        """Force argparse to display the help message"""
        self.__root_parser.print_help()
