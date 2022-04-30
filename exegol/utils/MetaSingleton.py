# Generic singleton class
from typing import Dict


class MetaSingleton(type):
    """Metaclass to create a singleton class"""
    __instances: Dict[type, object] = {}

    def __call__(cls, *args, **kwargs) -> object:
        """Redirects each call to the current class to the corresponding single instance"""
        if cls not in MetaSingleton.__instances:
            # If the instance does not already exist, it is created
            MetaSingleton.__instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        # Return the desired object
        return MetaSingleton.__instances[cls]
