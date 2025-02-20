from pathlib import Path

__version__ = "4.3.10b2"


class ConstantConfig:
    """Constant parameters information"""
    # Exegol Version
    version: str = __version__

    # Exegol documentation link
    documentation: str = "https://exegol.rtfd.io/"
    discord: str = "https://discord.gg/cXThyp7D6P"
    # OS Dir full root path of exegol project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # Path of the entrypoint.sh
    entrypoint_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/entrypoint.sh"
    # Path of the spawn.sh
    spawn_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/spawn.sh"
    # Exegol config directory
    exegol_config_path: Path = Path().home() / ".exegol"
    # Docker Desktop for mac config file
    docker_desktop_mac_config_path = Path().home() / "Library/Group Containers/group.com.docker"
    docker_desktop_windows_config_short_path = "AppData/Roaming/Docker"
    docker_desktop_windows_config_path = Path().home() / docker_desktop_windows_config_short_path
    # Install mode, check if Exegol has been git cloned or installed using pip package
    git_source_installation: bool = (src_root_path_obj / '.git').is_dir()
    pip_installed: bool = src_root_path_obj.name == "site-packages"
    pipx_installed: bool = "/pipx/venvs/" in src_root_path_obj.as_posix()
    # Dockerhub Exegol images repository
    DOCKER_HUB: str = "hub.docker.com"  # Don't handle docker login operations
    DOCKER_REGISTRY: str = "registry-1.docker.io"  # Don't handle docker login operations
    IMAGE_NAME: str = "nwodtuhs/exegol"
    GITHUB_REPO: str = "ThePorgs/Exegol"
    # Docker volume names (no docker volume used at this moment)
    # Resources repository
    EXEGOL_IMAGES_REPO: str = "https://github.com/ThePorgs/Exegol-images.git"
    EXEGOL_RESOURCES_REPO: str = "https://github.com/ThePorgs/Exegol-resources.git"
