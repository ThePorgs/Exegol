from argparse import Namespace
from typing import List, Any

from exegol.console.cli.actions.Command import Command
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.argParse import Parser


class ParametersManager(metaclass=MetaSingleton):
    """This class is a singleton allowing to access from anywhere to any parameter
    filled by the user from the CLI arguments"""

    def __init__(self):
        # List every action available on the project (from the root Class)
        actions: List[Command] = [cls() for cls in Command.__subclasses__()]
        # Load & execute argparse
        parser: Parser = Parser(actions)
        parsing_results = parser.run_parser()
        # The user arguments resulting from the parsing will be stored in parameters
        self.parameters: Command = self.__loadResults(parser, parsing_results)

    @staticmethod
    def __loadResults(parser: Parser, parsing_results: Namespace) -> Command:
        """The result of argparse is sent to the action object to replace the parser with the parsed values"""
        try:
            action: Command = parsing_results.action
            action.populate(parsing_results)
            return action
        except AttributeError:
            # Catch missing "action" parameter en CLI
            parser.print_help()
            exit(0)

    def getCurrentAction(self) -> Command:
        """Return the object corresponding to the action selected by the user"""
        return self.parameters

    def __getattr__(self, item: str) -> Any:
        """The getattr function is overloaded to transparently pass the parameter search
        in the child object of Command stored in the 'parameters' attribute"""
        try:
            # The priority is to first return the attributes of the current object
            # Using the object generic method to avoid infinite loop to itself
            return object.__getattribute__(self, item)
        except AttributeError:
            # If parameters is called before initialisation (from the next statement), this can create an infinite loop
            if item == "parameters":
                return None
        try:
            # If item was not found in self, the search is initiated among the parameters
            return getattr(self.parameters, item)
        except AttributeError:
            # The logger may not work if the call is made before its initialization
            logger.debug(f"Attribute not found in parameters: {item}")
