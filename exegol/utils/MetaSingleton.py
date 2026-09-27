from typing import Dict, Set


# Generic singleton class
class MetaSingleton(type):
    """Metaclass to create a singleton class"""
    __instances: Dict[type, object] = {}
    __spawning: Set[type] = set()

    def __call__(cls, *args, **kwargs) -> object:
        """Redirects each call to the current class to the corresponding single instance"""
        if cls not in MetaSingleton.__instances:
            if cls in MetaSingleton.__spawning:
                raise RuntimeError(f"Singleton {cls.__name__} is already being spawned. Recursive error detected.")
            # Spawning new singleton
            MetaSingleton.__spawning.add(cls)
            try:
                # If the instance does not already exist, it is created
                MetaSingleton.__instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
            finally:
                # Always clear the spawning guard, even if construction raised, so a failed
                # instantiation does not poison later attempts with a false recursion error.
                MetaSingleton.__spawning.discard(cls)
        # Return the desired object
        return MetaSingleton.__instances[cls]

    @classmethod
    def mock(cls, obj_type: type, mocked_obj: object) -> None:
        """Mock a singleton object"""
        MetaSingleton.__instances[obj_type] = mocked_obj
