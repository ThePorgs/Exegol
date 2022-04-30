import os
from pathlib import Path
from typing import Dict, List, Union

import yaml
import yaml.parser

from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class UserConfig(metaclass=MetaSingleton):
    """This class allows loading user defined configurations"""

    def __init__(self):
        # Config file options
        self.__exegol_path: Path = Path().home() / ".exegol"
        self.__config_file_path: Path = self.__exegol_path / "config.yml"
        self.__config_upgrade: bool = False

        # Defaults User config
        self.private_volume_path: Path = self.__exegol_path / "workspaces"
        self.shared_resources_path: str = str(self.__exegol_path / "my-resources")
        self.exegol_resources_path: Path = self.__default_resource_location('exegol-resources')

        # process
        self.__load_file()

    def __load_file(self):
        if not self.__exegol_path.is_dir():
            logger.verbose(f"Creating exegol home folder: {self.__exegol_path}")
            os.mkdir(self.__exegol_path)
        if not self.__config_file_path.is_file():
            logger.verbose(f"Creating default exegol config: {self.__config_file_path}")
            self.__create_config_file()
        else:
            self.__parse_config()
            if self.__config_upgrade:
                logger.verbose("Upgrading config file")
                self.__create_config_file()

    def __create_config_file(self):
        config = f"""# Exegol configuration

# Volume path can be changed at any time but existing containers will not be affected by the update
volumes:
    # The shared resources volume is a storage space dedicated to the user to customize his environment and tools. This volume can be shared across all exegol containers.
    my_resources_path: {self.shared_resources_path}
    
    # Exegol resources are data and static tools downloaded in addition to docker images. These tools are complementary and are accessible directly from the host.
    exegol_resources_path: {self.exegol_resources_path}
    
    # When containers do not have an explicitly declared workspace, a dedicated folder will be created at this location to share the workspace with the host but also to save the data after deleting the container
    private_workspace_path: {self.private_volume_path}
"""
        # TODO handle default image selection
        # TODO handle default start container
        # TODO add custom build profiles path
        # TODO add auto_remove flag True/False to remove outdated images
        with open(self.__config_file_path, 'w') as file:
            file.write(config)

    def __default_resource_location(self, folder_name: str) -> Path:
        local_src = ConstantConfig.src_root_path_obj / folder_name
        if local_src.is_dir():
            # If exegol is clone from github, exegol-resources submodule is accessible from root src
            return local_src
        else:
            # Default path for pip installation
            return self.__exegol_path / folder_name

    def __load_config_path(self, data: dict, config_name: str, default: Union[Path, str]) -> Union[Path, str]:
        try:
            result = data.get(config_name)
            if result is None:
                logger.debug(f"Config {config_name} has not been found in exegol config file. Config file will be upgrade.")
                self.__config_upgrade = True
                return default
            return Path(result).expanduser()
        except TypeError:
            logger.error(f"Error while loading {config_name}! Using default config.")
        return default

    def __parse_config(self):
        with open(self.__config_file_path, 'r') as file:
            try:
                data: Dict = yaml.safe_load(file)
            except yaml.parser.ParserError:
                data = {}
                logger.error("Error while parsing exegol config file ! Check for syntax error.")
        # bug: logger verbosity not set at this time
        logger.debug(data)
        volumes_data = data.get("volumes", {})
        # Catch existing but empty section
        if volumes_data is None:
            volumes_data = {}
        self.shared_resources_path = str(self.__load_config_path(volumes_data, 'my_resources_path', self.shared_resources_path))
        self.private_volume_path = self.__load_config_path(volumes_data, 'private_workspace_path', self.private_volume_path)
        self.exegol_resources_path = self.__load_config_path(volumes_data, 'exegol_resources_path', self.exegol_resources_path)

    def get_configs(self) -> List[str]:
        """User configs getter each options"""
        configs = [
            f"Private workspace: [magenta]{self.private_volume_path}[/magenta]",
            f"Exegol resources: [magenta]{self.exegol_resources_path}[/magenta]",
            f"My resources: [magenta]{self.shared_resources_path}[/magenta]"
        ]
        # TUI can't be called from here to avoid circular importation
        return configs
