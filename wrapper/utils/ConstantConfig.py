import platform
from pathlib import Path


# Constant parameter list
class ConstantConfig:
    # Exegol Version
    version: str = "4.0-dev"
    # OS Dir full root path of exegol project
    root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # OS root path str of the exegol project source
    root_path: str = str(root_path_obj)
    # Path of the Dockerfile
    build_context_path_obj: Path = root_path_obj.joinpath("dockerbuild")
    build_context_path: str = str(build_context_path_obj)
    # Path of the private workspace volumes
    private_volume_path: Path = root_path_obj.joinpath("shared-data-volumes")
    # Dockerhub Exegol images repository
    IMAGE_NAME: str = "nwodtuhs/exegol"
    # Docker common share volume name
    COMMON_SHARE_NAME: str = "exegol-shared-resources"
    common_share_path: str = str(root_path_obj.joinpath("shared-resources"))
    # Current plateforme
    windows_host: bool = platform.system() == "Windows" or "microsoft" in platform.release()
    windows_release: str = platform.win32_ver()[1]
