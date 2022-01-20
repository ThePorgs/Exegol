# Generic singleton class
from typing import Dict


class MetaSingleton(type):
    __instances: Dict[type, object] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in MetaSingleton.__instances:
            MetaSingleton.__instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return MetaSingleton.__instances[cls]