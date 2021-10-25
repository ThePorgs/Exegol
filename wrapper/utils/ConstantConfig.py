import pathlib


class ConstantConfig:
    # OS Dir full root path of exegol project
    __root_path_obj = pathlib.Path(__file__).parent.parent.parent.resolve()
    # OS root path str of the exegol project source
    root_path = str(__root_path_obj)
    # Path of the Dockerfile
    build_context_path = str(__root_path_obj.joinpath("dockerbuild"))
    # Path of the private workspace volumes
    private_volume_path = __root_path_obj.joinpath("shared-data-volumes")
    # Dockerhub Exegol images repository
    IMAGE_NAME = "nwodtuhs/exegol"
    # Docker common share volume name
    COMMON_SHARE_NAME = "exegol-shared-resources"
    COMMON_SHARE_PATH = str(__root_path_obj.joinpath("shared-resources"))
