import pathlib


class ConstantConfig:
    # OS Dir full root path of exegol project
    root_path = str(pathlib.Path(__file__).parent.parent.parent.resolve())
