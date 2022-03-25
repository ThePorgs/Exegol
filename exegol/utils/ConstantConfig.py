from pathlib import Path


# Constant parameter list
class ConstantConfig:
    # Exegol Version
    version: str = "4.0-dev"
    # OS Dir full root path of exegol project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # OS root path str of the exegol project source
    src_root_path: str = str(src_root_path_obj)
    # Path of the Dockerfile
    build_context_path_obj: Path = src_root_path_obj / "dockerbuild"
    build_context_path: str = str(build_context_path_obj)
    # Dockerhub Exegol images repository
    DOCKER_REGISTRY: str = "hub.docker.com"  # Don't handle docker login operations
    IMAGE_NAME: str = "nwodtuhs/exegol"
    # Docker common share volume name
    COMMON_SHARE_NAME: str = "exegol-shared-resources"
