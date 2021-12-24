from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.console.cli.actions.ExegolParameters import Command
from wrapper.utils.ExeLog import logger
from wrapper.utils.MetaSingleton import MetaSingleton


# Main controller of exegol
class ExegolController(metaclass=MetaSingleton):
    __parameters = ParametersManager()
    __action: Command

    def __init__(self):
        self.__parameters.populate()
        self.__action = self.__parameters.parameters

    def call_action(self):
        if len(self.__action.check_parameters()) == 0:
            # Fetch operation function
            main_action = self.__action()
            # Execute selected function
            main_action()
        else:
            logger.error("Call TUI to fix missing parameters")
