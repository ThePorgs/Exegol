from wrapper.console.ExegolArgs import ParametersManager
from wrapper.console.ExegolArgs.ExegolParameters import Command
from wrapper.utils.MetaSingleton import MetaSingleton


class ExegolController(metaclass=MetaSingleton):
    __parameters = ParametersManager()
    __action: Command

    def __init__(self):
        self.__parameters.populate()
        self.__action = self.__parameters.parameters

        self.call_action()

    def call_action(self):
        self.__action() if len(self.__action.check_parameters()) is 0 else print("Call TUI to fix missing parameters")

