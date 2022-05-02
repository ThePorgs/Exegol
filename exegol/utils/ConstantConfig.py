import site
from pathlib import Path


class ConstantConfig:
    """Constant parameters information"""
    # Exegol Version
    version: str = "4.0.1"

    # OS Dir full root path of exegol project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # Path of the Dockerfile
    build_context_path_obj: Path
    build_context_path: str
    # Install mode, check if Exegol has been git cloned or installed using pip package
    git_source_installation: bool = (src_root_path_obj / '.git').is_dir()
    pip_installed: bool = src_root_path_obj.parent.name == "site-packages"
    # Dockerhub Exegol images repository
    DOCKER_REGISTRY: str = "hub.docker.com"  # Don't handle docker login operations
    IMAGE_NAME: str = "nwodtuhs/exegol"
    # Docker volume names (no docker volume used at this moment)
    # Resources repository
    EXEGOL_RESOURCES_REPO: str = "https://github.com/ShutdownRepo/Exegol-resources.git"

    @classmethod
    def findBuildContextPath(cls) -> Path:
        """Find the right path to the build context from Exegol docker images.
        Support source clone installation and pip package (venv / user / global context)"""
        dockerbuild_folder_name = "exegol-docker-build"
        local_src = cls.src_root_path_obj / dockerbuild_folder_name
        if local_src.is_dir():
            # If exegol is clone from github, build context is accessible from root src
            return local_src
        else:
            # If install from pip
            if site.ENABLE_USER_SITE:
                # Detect a user based python env
                possible_locations = [Path(site.getuserbase())]
                # Detect a global installed package
                for loc in site.getsitepackages():
                    possible_locations.append(Path(loc).parent.parent.parent)
                # Find a good match
                for test in possible_locations:
                    context_path = test / dockerbuild_folder_name
                    if context_path.is_dir():
                        return context_path
            # Detect a venv context
            return Path(site.PREFIXES[0]) / dockerbuild_folder_name


# Dynamically built attribute must be set after class initialization
ConstantConfig.build_context_path_obj = ConstantConfig.findBuildContextPath()
ConstantConfig.build_context_path = str(ConstantConfig.build_context_path_obj)
