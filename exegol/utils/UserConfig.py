import os
from pathlib import Path
from typing import Dict, List, Union

import yaml
import yaml.parser

from exegol.console.ConsoleFormat import boolFormatter
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class UserConfig(metaclass=MetaSingleton):
    """This class allows loading user defined configurations"""

    def __init__(self):
        # Config file options
        self.__config_file_path: Path = ConstantConfig.exegol_config_path / "config.yml"
        self.__config_upgrade: bool = False

        # Defaults User config
        self.private_volume_path: Path = ConstantConfig.exegol_config_path / "workspaces"
        self.shared_resources_path: str = str(ConstantConfig.exegol_config_path / "my-resources")
        self.exegol_resources_path: Path = self.__default_resource_location('exegol-resources')
        self.auto_check_updates: bool = True
        self.auto_remove_images: bool = True
        self.auto_update_workspace_fs: bool = False

        # process
        self.__load_file()

    def __load_file(self):
        if not ConstantConfig.exegol_config_path.is_dir():
            logger.verbose(f"Creating exegol home folder: {ConstantConfig.exegol_config_path}")
            os.mkdir(ConstantConfig.exegol_config_path)
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

config:
    # Automatically check for wrapper update some time to time (only for git based installation)
    auto_check_update: {self.auto_check_updates}
    
    # Automatically remove outdated image when they are no longer used
    auto_remove_image: {self.auto_remove_images}
    
    # Automatically modifies the permissions of folders and sub-folders in your workspace by default to enable file sharing between the container with your host user.
    auto_update_workspace_fs: {self.auto_update_workspace_fs}
"""
        # TODO handle default image selection
        # TODO handle default start container
        # TODO add custom build profiles path
        with open(self.__config_file_path, 'w') as file:
            file.write(config)

    @staticmethod
    def __default_resource_location(folder_name: str) -> Path:
        local_src = ConstantConfig.src_root_path_obj / folder_name
        if local_src.is_dir():
            # If exegol is clone from github, exegol-resources submodule is accessible from root src
            return local_src
        else:
            # Default path for pip installation
            return ConstantConfig.exegol_config_path / folder_name

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

    def __load_config(self, data: dict, config_name: str, default: bool) -> bool:
        try:
            result = data.get(config_name)
            if result is None:
                logger.debug(f"Config {config_name} has not been found in exegol config file. Config file will be upgrade.")
                self.__config_upgrade = True
                return default
            return result
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
        # TODO bug: logger verbosity not set at this time
        logger.debug(data)
        # Volume section
        volumes_data = data.get("volumes", {})
        # Catch existing but empty section
        if volumes_data is None:
            volumes_data = {}
        self.shared_resources_path = str(self.__load_config_path(volumes_data, 'my_resources_path', self.shared_resources_path))
        self.private_volume_path = self.__load_config_path(volumes_data, 'private_workspace_path', self.private_volume_path)
        self.exegol_resources_path = self.__load_config_path(volumes_data, 'exegol_resources_path', self.exegol_resources_path)

        # Config section
        config_data = data.get("config", {})
        # Catch existing but empty section
        if config_data is None:
            config_data = {}
        self.auto_check_updates = self.__load_config(config_data, 'auto_check_update', self.auto_check_updates)
        self.auto_remove_images = self.__load_config(config_data, 'auto_remove_image', self.auto_remove_images)
        self.auto_update_workspace_fs = self.__load_config(config_data, 'auto_update_workspace_fs', self.auto_update_workspace_fs)

    def get_configs(self) -> List[str]:
        """User configs getter each options"""
        configs = [
            f"Private workspace: [magenta]{self.private_volume_path}[/magenta]",
            f"Exegol resources: [magenta]{self.exegol_resources_path}[/magenta]",
            f"My resources: [magenta]{self.shared_resources_path}[/magenta]",
            f"Auto-check updates: {boolFormatter(self.auto_check_updates)}",
            f"Auto-remove images: {boolFormatter(self.auto_remove_images)}",
            f"Auto-update fs: {boolFormatter(self.auto_update_workspace_fs)}",
        ]
        # TUI can't be called from here to avoid circular importation
        return configs
