import os
from pathlib import Path
from typing import Dict, List

import yaml
import yaml.parser

from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class UserConfig(metaclass=MetaSingleton):
    """This class allows loading user defined configurations"""

    def __init__(self):
        # Config file options
        self.__exegol_path = Path().home() / ".exegol"
        self.__config_file_path = self.__exegol_path / "config.yml"

        # Defaults User config
        self.private_volume_path = self.__exegol_path / "workspaces"
        self.shared_resources_path = str(self.__exegol_path / "shared-resources")

        # process
        self.__load_file()

    def __load_file(self):
        if not self.__exegol_path.is_dir():
            logger.verbose(f"Creating exegol home folder: {self.__exegol_path}")
            os.mkdir(self.__exegol_path)
        if not self.__config_file_path.is_file():
            logger.verbose(f"Creating default exegol config: {self.__config_file_path}")
            self.__create_default_config()
        else:
            self.__parse_config()

    def __create_default_config(self):
        config = f"""# Exegol configuration
        
volumes:
    # Changing the shared resources path must be set before creating any exegol container (and remove the docker volume {ConstantConfig.COMMON_SHARE_NAME} if exists)
    shared_resources_path: {self.shared_resources_path}
    
    # Changing the location of the private workspace parent directory can be done at any moment but the change will not affect already created containers
    private_workspace_path: {self.private_volume_path}
"""
        # TODO handle default image selection
        # TODO handle default start container
        # TODO add custom build profiles path
        with open(self.__config_file_path, 'w') as file:
            file.write(config)

    def __parse_config(self):
        with open(self.__config_file_path, 'r') as file:
            try:
                data: Dict = yaml.safe_load(file)
            except yaml.parser.ParserError:
                data = {}
                logger.error("Error while parsing exegol config file ! Check for syntax error.")
        logger.debug(data)
        volumes_data = data.get("volumes", {})
        if volumes_data is None:
            volumes_data = {}
        try:
            self.shared_resources_path = str(Path(volumes_data.get('shared_resources_path',
                                                                   self.shared_resources_path)).expanduser())
        except TypeError:
            logger.error("Error while loading shared_resources path! Using default config.")
        try:
            self.private_volume_path = Path(volumes_data.get('private_workspace_path',
                                                             self.private_volume_path)).expanduser()
        except TypeError:
            logger.error("Error while loading private_workspace path! Using default config.")

    def get_configs(self) -> List[str]:
        configs = [
            f"Shared resources = {self.shared_resources_path}",
            f"Private workspace = {self.private_volume_path}"
        ]
        # TUI can't be called from here to avoid circular importation
        return configs
