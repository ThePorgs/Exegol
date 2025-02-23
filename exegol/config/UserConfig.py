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
    desktop_available_proto = {'http', 'vnc'}

    def __init__(self) -> None:
        # Defaults User config
        self.private_volume_path: Path = ConstantConfig.exegol_config_path / "workspaces"
        self.my_resources_path: Path = ConstantConfig.exegol_config_path / "my-resources"
        self.exegol_resources_path: Path = self.__default_resource_location('exegol-resources')
        self.exegol_images_path: Path = self.__default_resource_location('exegol-images')
        self.auto_check_updates: bool = True
        self.auto_remove_images: bool = True
        self.auto_update_workspace_fs: bool = False
        self.default_start_shell: str = "zsh"
        self.enable_exegol_resources: bool = True
        self.shell_logging_method: str = "asciinema"
        self.shell_logging_compress: bool = True
        self.desktop_default_enable: bool = False
        self.desktop_default_localhost: bool = True
        self.desktop_default_proto: str = "http"

        super().__init__("config.yml", "yml")

    def _build_file_content(self) -> str:
        config = f"""# Exegol configuration
# Full documentation: https://exegol.readthedocs.io/en/latest/exegol-wrapper/advanced-uses.html#id1

# Volume path can be changed at any time but existing containers will not be affected by the update
volumes:
    # The my-resources volume is a storage space dedicated to the user to customize his environment and tools. This volume can be shared across all exegol containers.
    # Attention! The permissions of this folder (and subfolders) will be updated to share read/write rights between the host (user) and the container (root). Do not modify this path to a folder on which the permissions (chmod) should not be modified.
    my_resources_path: {self.my_resources_path}
    
    # Exegol resources are data and static tools downloaded in addition to docker images. These tools are complementary and are accessible directly from the host.
    exegol_resources_path: {self.exegol_resources_path}
    
    # Exegol images are the source of the exegol environments. These sources are needed when locally building an exegol image.
    exegol_images_path: {self.exegol_images_path}
    
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
    
    # Enable Exegol resources
    enable_exegol_resources: {self.enable_exegol_resources}
    
    # Change the configuration of the shell logging functionality
    shell_logging:
        #Choice of the method used to record the sessions (script or asciinema)
        logging_method: {self.shell_logging_method}
        
        # Enable automatic compression of log files (with gzip)
        enable_log_compression: {self.shell_logging_compress}
        
    # Configure your Exegol Desktop
    desktop:
        # Enables or not the desktop mode by default
        # If this attribute is set to True, then using the CLI --desktop option will be inverted and will DISABLE the feature
        enabled_by_default: {self.desktop_default_enable}
        
        # Default desktop protocol,can be "http", or "vnc" (additional protocols to come in the future, check online documentation for updates).
        default_protocol: {self.desktop_default_proto}
        
        # Desktop service is exposed on localhost by default. If set to true, services will be exposed on localhost (127.0.0.1) otherwise it will be exposed on 0.0.0.0. This setting can be overwritten with --desktop-config
        localhost_by_default: {self.desktop_default_localhost}

"""
        return config

    @staticmethod
    def __default_resource_location(folder_name: str) -> Path:
        local_src = ConstantConfig.src_root_path_obj / folder_name
        if local_src.is_dir():
            # If exegol is clone from github, exegol submodule is accessible from root src
            return local_src
        else:
            # Default path for pip installation
            return ConstantConfig.exegol_config_path / folder_name

    def _process_data(self) -> None:
        # Volume section
        volumes_data = self._raw_data.get("volumes", {})
        # Catch existing but empty section
        if volumes_data is None:
            volumes_data = {}
        self.my_resources_path = self._load_config_path(volumes_data, 'my_resources_path', self.my_resources_path)
        self.private_volume_path = self._load_config_path(volumes_data, 'private_workspace_path', self.private_volume_path)
        self.exegol_resources_path = self._load_config_path(volumes_data, 'exegol_resources_path', self.exegol_resources_path)
        self.exegol_images_path = self._load_config_path(volumes_data, 'exegol_images_path', self.exegol_images_path)

        # Config section
        config_data = self._raw_data.get("config", {})
        # Catch existing but empty section
        if config_data is None:
            config_data = {}
        self.auto_check_updates = self._load_config_bool(config_data, 'auto_check_update', self.auto_check_updates)
        self.auto_remove_images = self._load_config_bool(config_data, 'auto_remove_image', self.auto_remove_images)
        self.auto_update_workspace_fs = self._load_config_bool(config_data, 'auto_update_workspace_fs', self.auto_update_workspace_fs)
        self.default_start_shell = self._load_config_str(config_data, 'default_start_shell', self.default_start_shell, choices=self.start_shell_options)
        self.enable_exegol_resources = self._load_config_bool(config_data, 'enable_exegol_resources', self.enable_exegol_resources)

        # Shell_logging section
        shell_logging_data = config_data.get("shell_logging", {})
        self.shell_logging_method = self._load_config_str(shell_logging_data, 'logging_method', self.shell_logging_method, choices=self.shell_logging_method_options)
        self.shell_logging_compress = self._load_config_bool(shell_logging_data, 'enable_log_compression', self.shell_logging_compress)

        # Desktop section
        desktop_data = config_data.get("desktop", {})
        self.desktop_default_enable = self._load_config_bool(desktop_data, 'enabled_by_default', self.desktop_default_enable)
        self.desktop_default_proto = self._load_config_str(desktop_data, 'default_protocol', self.desktop_default_proto, choices=self.desktop_available_proto)
        self.desktop_default_localhost = self._load_config_bool(desktop_data, 'localhost_by_default', self.desktop_default_localhost)

    def get_configs(self) -> List[str]:
        """User configs getter each options"""
        configs = [
            f"User config file: [magenta]{self._file_path}[/magenta]",
            f"Private workspace: [magenta]{self.private_volume_path}[/magenta]",
            "Exegol resources: " + (f"[magenta]{self.exegol_resources_path}[/magenta]"
                                    if self.enable_exegol_resources else
                                    boolFormatter(self.enable_exegol_resources)),
            f"Exegol images: [magenta]{self.exegol_images_path}[/magenta]",
            f"My resources: [magenta]{self.my_resources_path}[/magenta]",
            f"Auto-check updates: {boolFormatter(self.auto_check_updates)}",
            f"Auto-remove images: {boolFormatter(self.auto_remove_images)}",
            f"Auto-update fs: {boolFormatter(self.auto_update_workspace_fs)}",
            f"Default start shell: [blue]{self.default_start_shell}[/blue]",
            f"Shell logging method: [blue]{self.shell_logging_method}[/blue]",
            f"Shell logging compression: {boolFormatter(self.shell_logging_compress)}",
            f"Desktop enabled by default: {boolFormatter(self.desktop_default_enable)}",
            f"Desktop default protocol: [blue]{self.desktop_default_proto}[/blue]",
            f"Desktop default host: [blue]{'localhost' if self.desktop_default_localhost else '0.0.0.0'}[/blue]",
        ]
        # TUI can't be called from here to avoid circular importation
        return configs
