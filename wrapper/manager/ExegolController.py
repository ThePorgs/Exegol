from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.console.cli.actions.ExegolParameters import Command
from wrapper.utils.ExeLog import logger
from wrapper.utils.MetaSingleton import MetaSingleton


class ExegolController(metaclass=MetaSingleton):
    __parameters = ParametersManager()
    __action: Command

    def __init__(self):
        self.__parameters.populate()
        self.__action = self.__parameters.parameters

    def call_action(self):
        self.__action() if len(self.__action.check_parameters()) == 0 else logger.error(
            "Call TUI to fix missing parameters")
