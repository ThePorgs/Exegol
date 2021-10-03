import pathlib


class ConstantConfig:
    # OS Dir full root path of exegol project
    __root_path_obj = pathlib.Path(__file__).parent.parent.parent.resolve()
    root_path = str(__root_path_obj)
    dockerfile_path = root_path  # TODO change Dockerfile location (opti build context copy)
