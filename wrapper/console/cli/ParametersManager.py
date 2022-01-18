from wrapper.console.cli.actions.Command import Command
from wrapper.utils.argParse import Parser
from wrapper.utils.ExeLog import logger
from wrapper.utils.MetaSingleton import MetaSingleton


class ParametersManager(metaclass=MetaSingleton):
    def __init__(self):
        self.__actions = [cls() for cls in Command.__subclasses__()]
        self.__parser = Parser(self.__actions)
        self.parameters = self.__parser.get_parameters()

    def populate(self):
        try:
            self.parameters.action.populate(self.parameters)
            self.parameters = self.parameters.action
        except AttributeError:
            # Catch missing "action" parameter en CLI
            self.__parser.parser.print_help()
            exit(0)

    def __getattr__(self, item):
        try:
            return getattr(self.parameters, item)
        except AttributeError as r:
            logger.debug(r)
