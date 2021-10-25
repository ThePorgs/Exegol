import pathlib


class ConstantConfig:
    # OS Dir full root path of exegol project
    __root_path_obj = pathlib.Path(__file__).parent.parent.parent.resolve()
    # OS root path str of the exegol project source
    root_path = str(__root_path_obj)
    # Path of the Dockerfile
    dockerfile_path = root_path  # TODO change Dockerfile location (opti build context copy)
