import json
import os
import sys
from json import JSONEncoder, JSONDecodeError
from pathlib import Path
from types import MethodType, FunctionType
from typing import Union, Dict, cast, Optional, Set, Any, List

import yaml
import yaml.parser

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import mkdir, get_user_id


class DataFileUtils:

    class ObjectJSONEncoder(JSONEncoder):
        def default(self, o: object) -> Dict:
            result = {}
            for key, value in o.__dict__.items():
                if key.startswith("_"):
                    continue
                result[key] = value
            return result

    def __init__(self, file_path: Union[Path, str], file_type: str, dynamic_default: Optional[Dict] = None):
        """Generic class for datastorage in config file.
        :param file_path: can be a Path object or a string. If a string is supplied it will be automatically place inside the default exegol directory.
        :param file_type: defined the type of file to create. It can be 'yml' or 'json'.
        :param dynamic_default: An optional dictionnary that can be used to dynamically assign a default value to a config key. The key is the config name and the value is a class method or function.
        """
        if type(file_path) is str:
            file_path = ConstantConfig.exegol_config_path / file_path
        if file_type not in ["yml", "yaml", "json"]:
            raise NotImplementedError(f"The file type '{file_type}' is not implemented")
        # Config file options
        self._file_path: Path = cast(Path, file_path)
        self.__file_type: str = file_type
        self.__config_upgrade: bool = False

        # Dynamic default
        self.__dynamic_default: Dict[str, Union[MethodType, FunctionType]] = dynamic_default if dynamic_default is not None else dict()

        self._raw_data: Any = None

        # Process
        self.__load_file()

    def _get_dynamic_default(self, attr_name: str) -> Union[str, int, bool]:
        if attr_name in self.__dynamic_default.keys():
            return self.__dynamic_default[attr_name]()
        raise NotImplementedError(f"The dynamic default value is not define for attribute '{attr_name}'")

    def __load_file(self) -> None:
        """
        Function to load the file and the corresponding parameters
        :return:
        """
        if not self._file_path.parent.is_dir():
            logger.verbose(f"Creating config folder: {self._file_path.parent}")
            mkdir(self._file_path.parent)
        if not self._file_path.is_file():
            logger.verbose(f"Creating default file: {self._file_path}")
            self._create_config_file()
        else:
            self._parse_config()
            if self.__config_upgrade:
                logger.verbose("Upgrading config file")
                self._create_config_file()

    def _build_file_content(self) -> str:
        """
        This function build the default file content. Called when the file doesn't exist yet or have been upgrade and need to be updated.
        :return:
        """
        raise NotImplementedError(f"The '_build_default_file' method hasn't been implemented in the '{self.__class__}' class.")

    def _create_config_file(self) -> None:
        """
        Create or overwrite the file content to the default / current value depending on the '_build_default_file' that must be redefined in child class.
        :return:
        """
        try:
            with open(self._file_path, 'w') as file:
                file.write(self._build_file_content())
            if sys.platform == "linux" and os.getuid() == 0:
                user_uid, user_gid = get_user_id()
                os.chown(self._file_path, user_uid, user_gid)
        except PermissionError as e:
            logger.critical(f"Unable to open the file '{self._file_path}' ({e}). Please fix your file permissions or run exegol with the correct rights.")
        except OSError as e:
            logger.critical(f"A critical error occurred while interacting with filesystem: [{type(e)}] {e}")

    def _parse_config(self) -> None:
        data: Dict = {}
        with open(self._file_path, 'r') as file:
            try:
                if self.__file_type == "yml":
                    data = yaml.safe_load(file)
                elif self.__file_type == "json":
                    data = json.load(file)
            except yaml.parser.ParserError:
                logger.error("Error while parsing exegol config file ! Check for syntax error.")
            except JSONDecodeError:
                logger.error(f"Error while parsing exegol data file {self._file_path} ! Check for syntax error.")
        if data is None:
            logger.warning(f"Exegol was unable to load the file {self._file_path}. Restoring it to its original state.")
            self._create_config_file()
        else:
            self._raw_data = data
            self._process_data()

    def __load_config(self, data: dict, config_name: str, default: Optional[Union[bool, str, int, List[str]]],
                      choices: Optional[Set[str]] = None) -> Union[bool, str, int, List[str]]:
        """
        Function to automatically load a data from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :param default: Default value is the value hasn't been set yet
        :param choices: (Optional) A limit set of acceptable values
        :return: This function return the value for the corresponding config_name.
        """
        try:
            if config_name not in data.keys():
                logger.debug(f"Config {config_name} has not been found in Exegol '{self._file_path.name}' config file. The file will be upgrade.")
                self.__config_upgrade = True
                return default if default is not None else self._get_dynamic_default(config_name)
            result = data.get(config_name)
            if result is None:
                return default if default is not None else self._get_dynamic_default(config_name)
            elif choices is not None and result not in choices:
                default = default if default is not None else self._get_dynamic_default(config_name)
                logger.warning(f"The configuration is incorrect! "
                               f"The user has configured the '{config_name}' parameter with the value '{result}' "
                               f"which is not one of the allowed options ({', '.join(choices)}). Using default value: {default}.")
                return default
            return result
        except TypeError:
            logger.error(f"Error while loading {config_name}! Using default config.")
        return default if default is not None else self._get_dynamic_default(config_name)

    def _load_config_bool(self, data: dict, config_name: str, default: Optional[bool] = None,
                          choices: Optional[Set[str]] = None) -> bool:
        """
        Function to automatically load a BOOL from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :param default: Default value is the value hasn't been set yet
        :param choices: (Optional) A limit set of acceptable values
        :return: This function return the value for the corresponding config_name
        """
        return cast(bool, self.__load_config(data, config_name, default, choices))

    def _load_config_str(self, data: dict, config_name: str, default: Optional[str] = None, choices: Optional[Set[str]] = None) -> str:
        """
        Function to automatically load a STR from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :param default: Default value is the value hasn't been set yet
        :param choices: (Optional) A limit set of acceptable values
        :return: This function return the value for the corresponding config_name
        """
        return cast(str, self.__load_config(data, config_name, default, choices))

    def _load_config_int(self, data: dict, config_name: str, default: Optional[int] = None, choices: Optional[Set[str]] = None) -> int:
        """
        Function to automatically load a INT from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :param default: Default value is the value hasn't been set yet
        :param choices: (Optional) A limit set of acceptable values
        :return: This function return the value for the corresponding config_name
        """
        config = cast(Union[str, int], self.__load_config(data, config_name, default, choices))
        try:
            return int(config)
        except ValueError:
            logger.critical(f"Invalid value for {config_name}: received '{config}' instead of a number. Please use a correct format.")
            exit(1)

    def _load_config_path(self, data: dict, config_name: str, default: Optional[Path] = None) -> Path:
        """
        Function to automatically load a PATH from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :param default: Default value is the value hasn't been set yet
        :return: This function return the value for the corresponding config_name
        """
        try:
            result = data.get(config_name)
            if result is None:
                logger.debug(f"Config {config_name} has not been found in Exegol '{self._file_path.name}' config file. The file will be upgrade.")
                self.__config_upgrade = True
                return default if default is not None else cast(Path, self._get_dynamic_default(config_name))
            return Path(result).expanduser()
        except TypeError:
            logger.error(f"Error while loading {config_name}! Using default config.")
        return default if default is not None else cast(Path, self._get_dynamic_default(config_name))

    def _load_config_list_str(self, data: dict, config_name: str, default: Optional[List[str]] = None) -> List[str]:
        """
        Function to automatically load a STR from a dict object. This function can handle limited choices and default value.
        If the parameter don't exist,a reset flag will be raised.
        :param data: Dict data to retrieve the value from
        :param config_name: Key name of the config to find
        :return: This function return the value for the corresponding config_name
        """
        return cast(List[str], self.__load_config(data, config_name, default=default if default is not None else list(), choices=None))

    def _process_data(self) -> None:
        raise NotImplementedError(f"The '_process_data' method hasn't been implemented in the '{self.__class__}' class.")
