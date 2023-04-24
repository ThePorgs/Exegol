from pathlib import Path
from typing import List

from exegol.config.ConstantConfig import ConstantConfig
from exegol.console.ConsoleFormat import boolFormatter
from exegol.utils.DataFileUtils import DataFileUtils
from exegol.utils.MetaSingleton import MetaSingleton


class UserConfig(DataFileUtils, metaclass=MetaSingleton):
    """This class allows loading user defined configurations"""

    # Static choices
    start_shell_options = {'zsh', 'bash', 'tmux'}
    shell_logging_method_options = {'script', 'asciinema'}

    def __init__(self):
        # Defaults User config
        self.private_volume_path: Path = ConstantConfig.exegol_config_path / "workspaces"
        self.my_resources_path: Path = ConstantConfig.exegol_config_path / "my-resources"
        self.exegol_resources_path: Path = self.__default_resource_location('exegol-resources')
        self.auto_check_updates: bool = True
        self.auto_remove_images: bool = True
        self.auto_update_workspace_fs: bool = False
        self.default_start_shell: str = "zsh"
        self.shell_logging_method: str = "asciinema"
        self.shell_logging_compress: bool = True

        super().__init__("config.yml", "yml")

    def _build_file_content(self):
        config = f"""# Exegol configuration

# Volume path can be changed at any time but existing containers will not be affected by the update
volumes:
    # The my-resources volume is a storage space dedicated to the user to customize his environment and tools. This volume can be shared across all exegol containers.
    # Attention! The permissions of this folder (and subfolders) will be updated to share read/write rights between the host (user) and the container (root). Do not modify this path to a folder on which the permissions (chmod) should not be modified.
    my_resources_path: {self.my_resources_path}
    
    # Exegol resources are data and static tools downloaded in addition to docker images. These tools are complementary and are accessible directly from the host.
    exegol_resources_path: {self.exegol_resources_path}
    
    # When containers do not have an explicitly declared workspace, a dedicated folder will be created at this location to share the workspace with the host but also to save the data after deleting the container
    private_workspace_path: {self.private_volume_path}

config:
    # Enables automatic check for wrapper updates
    auto_check_update: {self.auto_check_updates}
    
    # Automatically remove outdated image when they are no longer used
    auto_remove_image: {self.auto_remove_images}
    
    # Automatically modifies the permissions of folders and sub-folders in your workspace by default to enable file sharing between the container with your host user.
    auto_update_workspace_fs: {self.auto_update_workspace_fs}
    
    # Default shell command to start
    default_start_shell: {self.default_start_shell}
    
    # Change the configuration of the shell logging functionality
    shell_logging: 
        #Choice of the method used to record the sessions (script or asciinema)
        logging_method: {self.shell_logging_method}
        
        # Enable automatic compression of log files (with gzip)
        enable_log_compression: {self.shell_logging_compress}

"""
        # TODO handle default image selection
        # TODO handle default start container
        # TODO add custom build profiles path
        return config

    @staticmethod
    def __default_resource_location(folder_name: str) -> Path:
        local_src = ConstantConfig.src_root_path_obj / folder_name
        if local_src.is_dir():
            # If exegol is clone from github, exegol-resources submodule is accessible from root src
            return local_src
        else:
            # Default path for pip installation
            return ConstantConfig.exegol_config_path / folder_name

    def _process_data(self):
        # Volume section
        volumes_data = self._raw_data.get("volumes", {})
        # Catch existing but empty section
        if volumes_data is None:
            volumes_data = {}
        self.my_resources_path = self._load_config_path(volumes_data, 'my_resources_path', self.my_resources_path)
        self.private_volume_path = self._load_config_path(volumes_data, 'private_workspace_path', self.private_volume_path)
        self.exegol_resources_path = self._load_config_path(volumes_data, 'exegol_resources_path', self.exegol_resources_path)

        # Config section
        config_data = self._raw_data.get("config", {})
        # Catch existing but empty section
        if config_data is None:
            config_data = {}
        self.auto_check_updates = self._load_config_bool(config_data, 'auto_check_update', self.auto_check_updates)
        self.auto_remove_images = self._load_config_bool(config_data, 'auto_remove_image', self.auto_remove_images)
        self.auto_update_workspace_fs = self._load_config_bool(config_data, 'auto_update_workspace_fs', self.auto_update_workspace_fs)
        self.default_start_shell = self._load_config_str(config_data, 'default_start_shell', self.default_start_shell, choices=self.start_shell_options)

        # Shell_logging section
        shell_logging_data = config_data.get("shell_logging", {})
        self.shell_logging_method = self._load_config_str(shell_logging_data, 'logging_method', self.shell_logging_method, choices=self.shell_logging_method_options)
        self.shell_logging_compress = self._load_config_bool(shell_logging_data, 'enable_log_compression', self.shell_logging_compress)

    def get_configs(self) -> List[str]:
        """User configs getter each options"""
        configs = [
            f"User config file: [magenta]{self._file_path}[/magenta]",
            f"Private workspace: [magenta]{self.private_volume_path}[/magenta]",
            f"Exegol resources: [magenta]{self.exegol_resources_path}[/magenta]",
            f"My resources: [magenta]{self.my_resources_path}[/magenta]",
            f"Auto-check updates: {boolFormatter(self.auto_check_updates)}",
            f"Auto-remove images: {boolFormatter(self.auto_remove_images)}",
            f"Auto-update fs: {boolFormatter(self.auto_update_workspace_fs)}",
            f"Default start shell: [blue]{self.default_start_shell}[/blue]",
            f"Shell logging method: [blue]{self.shell_logging_method}[/blue]",
            f"Shell logging compression: {boolFormatter(self.shell_logging_compress)}",
        ]
        # TUI can't be called from here to avoid circular importation
        return configs
