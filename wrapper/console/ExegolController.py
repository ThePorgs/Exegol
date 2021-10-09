from wrapper.console.ExegolArgs import ParametersManager
from wrapper.console.ExegolArgs.ExegolParameters import Command


class ExegolController:
    __parameters = ParametersManager().parameters
    __action: Command

    def __init__(self):
        try:
            self.__parameters.action.populate(self.__parameters)
            self.__action = self.__parameters.action
        except AttributeError:
            # TODO Call TUI --> Choose action
            raise NotImplementedError("Functionality not implemented yet")

        self.call_action()

    def call_action(self):
        self.__action() if len(self.__action.check_parameters()) is 0 else print("Call TUI to fix missing parameters")
