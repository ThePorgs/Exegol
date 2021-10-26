import pathlib
import platform


class ConstantConfig:
    # OS Dir full root path of exegol project
    __root_path_obj = pathlib.Path(__file__).parent.parent.parent.resolve()
    # OS root path str of the exegol project source
    root_path = str(__root_path_obj)
    # Path of the Dockerfile
    build_context_path_obj = __root_path_obj.joinpath("dockerbuild")
    build_context_path = str(build_context_path_obj)
    # Path of the private workspace volumes
    private_volume_path = __root_path_obj.joinpath("shared-data-volumes")
    # Dockerhub Exegol images repository
    IMAGE_NAME = "nwodtuhs/exegol"
    # Docker common share volume name
    COMMON_SHARE_NAME = "exegol-shared-resources"
    common_share_path = str(__root_path_obj.joinpath("shared-resources"))
    # Current plateforme
    windows_host = platform.system() == "Windows" or "microsoft" in platform.release()
