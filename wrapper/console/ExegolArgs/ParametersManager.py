from .ExegolParameters import *
from .argParsev2 import Parser
from wrapper.utils.MetaSingleton import MetaSingleton


class ParametersManager(metaclass=MetaSingleton):
    def __init__(self):
        self.__actions = [cls() for cls in Command.__subclasses__()]
        self.__parser = Parser(self.__actions)
        self.parameters = self.__parser.get_parameters()
