import json
import os
import platform
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, List, Dict

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


class EnvInfo:
    """Class to identify the environment in which exegol runs to adapt
    the configurations, processes and messages for the user"""

    class HostOs(Enum):
        """Dictionary class for static OS Name"""
        WINDOWS = "Windows"
        LINUX = "Linux"
        MAC = "Mac"

    class DisplayServer(Enum):
        """Dictionary class for static Display Server"""
        WAYLAND = "Wayland"
        X11 = "X11"

    class DockerEngine(Enum):
        """Dictionary class for static Docker engine name"""
        WSL2 = "WSL2"
        HYPERV = "Hyper-V"
        DOCKER_DESKTOP = "Docker desktop"
        ORBSTACK = "Orbstack"
        LINUX = "Kernel"

    """Contain information about the environment (host, OS, platform, etc)"""
    # Shell env
    current_platform: str = "WSL" if "microsoft" in platform.release() else platform.system()  # Can be 'Windows', 'Linux' or 'WSL'
    is_linux_shell: bool = current_platform in ["WSL", "Linux"]
    is_windows_shell: bool = current_platform == "Windows"
    is_mac_shell: bool = not is_windows_shell and not is_linux_shell  # If not Linux nor Windows, its (probably) a mac
    __is_docker_desktop: bool = False
    __windows_release: Optional[str] = None
    # Host OS
    __docker_host_os: Optional[HostOs] = None
    __docker_engine: Optional[DockerEngine] = None
    # Docker desktop cache config
    __docker_desktop_resource_config: Optional[dict] = None
    # Architecture
    raw_arch = platform.machine().lower()
    arch = raw_arch
    if arch == "x86_64" or arch == "x86-64" or arch == "amd64":
        arch = "amd64"
    elif arch == "aarch64" or "armv8" in arch:
        arch = "arm64"
    elif "arm" in arch:
        if platform.architecture()[0] == '64bit':
            arch = "arm64"
        else:
            logger.error(f"Host architecture seems to be 32-bit ARM ({arch}), which is not supported yet. "
                         f"If possible, please install a 64-bit operating system (Exegol supports ARM64).")
        """
        if "v5" in arch:
            arch = "arm/v5"
        elif "v6" in arch:
            arch = "arm/v6"
        elif "v7" in arch:
            arch = "arm/v7"
        elif "v8" in arch:
            arch = "arm64"
        """
    else:
        logger.warning(f"Unknown / unsupported architecture: {arch}. Using 'AMD64' as default.")
        # Fallback to default AMD64 arch
        arch = "amd64"

    @classmethod
    def initData(cls, docker_info) -> None:
        """Initialize information from Docker daemon data"""
        # Fetch data from Docker daemon
        docker_os = docker_info.get("OperatingSystem", "unknown").lower()
        docker_kernel = docker_info.get("KernelVersion", "unknown").lower()
        # Deduct a Windows Host from data
        cls.__is_docker_desktop = docker_os == "docker desktop"
        is_host_windows = cls.__is_docker_desktop and "microsoft" in docker_kernel
        is_orbstack = (docker_os == "orbstack" or "(containerized)" in docker_os) and "orbstack" in docker_kernel
        if is_host_windows:
            # Check docker engine with Windows host
            if "wsl2" in docker_kernel:
                cls.__docker_engine = cls.DockerEngine.WSL2
            else:
                cls.__docker_engine = cls.DockerEngine.HYPERV
            cls.__docker_host_os = cls.HostOs.WINDOWS
        elif cls.__is_docker_desktop:
            # If docker desktop is detected but not a Windows engine/kernel, it's (probably) a mac
            cls.__docker_engine = cls.DockerEngine.DOCKER_DESKTOP
            cls.__docker_host_os = cls.HostOs.MAC if cls.is_mac_shell else cls.HostOs.LINUX
        elif is_orbstack:
            # Orbstack is only available on Mac
            cls.__docker_engine = cls.DockerEngine.ORBSTACK
            cls.__docker_host_os = cls.HostOs.MAC
        else:
            # Every other case it's a linux distro and docker is powered from the kernel
            cls.__docker_engine = cls.DockerEngine.LINUX
            cls.__docker_host_os = cls.HostOs.LINUX

        if cls.__docker_engine == cls.DockerEngine.DOCKER_DESKTOP and cls.__docker_host_os == cls.HostOs.LINUX:
            logger.warning(f"Using Docker Desktop on Linux is not officially supported !")

    @classmethod
    def getHostOs(cls) -> HostOs:
        """Return Host OS
        Can be 'Windows', 'Mac' or 'Linux'"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_host_os is not None
        return cls.__docker_host_os

    @classmethod
    def getDisplayServer(cls) -> DisplayServer:
        """Returns the display server
        Can be 'X11' or 'Wayland'"""
        session_type = os.getenv("XDG_SESSION_TYPE", "x11")
        if session_type == "wayland":
            return cls.DisplayServer.WAYLAND
        elif session_type in ["x11", "tty"]:  # When using SSH X11 forwarding, the session type is "tty" instead of the classic "x11"
            return cls.DisplayServer.X11
        else:
            # Should return an error
            logger.warning(f"Unknown session type {session_type}. Using X11 as fallback.")
            return cls.DisplayServer.X11

    @classmethod
    def getWindowsRelease(cls) -> str:
        # Cache check
        if cls.__windows_release is None:
            if cls.is_windows_shell:
                # From a Windows shell, python supply an approximate (close enough) version of windows
                cls.__windows_release = platform.win32_ver()[1]
            else:
                cls.__windows_release = "Unknown"
        return cls.__windows_release

    @classmethod
    def isWindowsHost(cls) -> bool:
        """Return true if Windows is detected on the host"""
        return cls.getHostOs() == cls.HostOs.WINDOWS

    @classmethod
    def isMacHost(cls) -> bool:
        """Return true if macOS is detected on the host"""
        return cls.getHostOs() == cls.HostOs.MAC

    @classmethod
    def isLinuxHost(cls) -> bool:
        """Return true if Linux is detected on the host"""
        return cls.getHostOs() == cls.HostOs.LINUX

    @classmethod
    def isWaylandAvailable(cls) -> bool:
        """Return true if wayland is detected on the host"""
        return cls.getDisplayServer() == cls.DisplayServer.WAYLAND or bool(os.getenv("WAYLAND_DISPLAY"))

    @classmethod
    def isDockerDesktop(cls) -> bool:
        """Return true if docker desktop is used on the host"""
        return cls.__is_docker_desktop

    @classmethod
    def isOrbstack(cls) -> bool:
        """Return true if docker desktop is used on the host"""
        return cls.__docker_engine == cls.DockerEngine.ORBSTACK

    @classmethod
    def getDockerEngine(cls) -> DockerEngine:
        """Return Docker engine type.
        Can be any of EnvInfo.DockerEngine"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_engine is not None
        return cls.__docker_engine

    @classmethod
    def getShellType(cls) -> str:
        """Return the type of shell exegol is executed from"""
        if cls.is_linux_shell:
            return cls.HostOs.LINUX.value
        elif cls.is_windows_shell:
            return cls.HostOs.WINDOWS.value
        elif cls.is_mac_shell:
            return cls.HostOs.MAC.value
        else:
            return "Unknown"

    @classmethod
    def getDockerDesktopSettings(cls) -> Dict:
        """Applicable only for docker desktop on macos"""
        if cls.isDockerDesktop():
            if cls.__docker_desktop_resource_config is None:
                dir_path = None
                file_path = None
                if cls.is_mac_shell:
                    # Mac PATH
                    dir_path = ConstantConfig.docker_desktop_mac_config_path
                elif cls.is_windows_shell:
                    # Windows PATH
                    dir_path = ConstantConfig.docker_desktop_windows_config_path
                else:
                    # Windows PATH from WSL shell
                    # Find docker desktop config
                    config_file = list(Path("/mnt/c/Users").glob(f"*/{ConstantConfig.docker_desktop_windows_config_short_path}/settings-store.json"))
                    if len(config_file) == 0:
                        # Testing with legacy file name
                        config_file = list(Path("/mnt/c/Users").glob(f"*/{ConstantConfig.docker_desktop_windows_config_short_path}/settings.json"))
                        if len(config_file) == 0:
                            logger.warning(f"No docker desktop settings file found.")
                            return {}
                    file_path = config_file[0]
                if file_path is None:
                    assert dir_path is not None
                    # Try to find settings file with new filename or fallback to legacy filename for Docker Desktop older than 4.34
                    file_path = (dir_path / "settings-store.json") if (dir_path / "settings-store.json").is_file() else (dir_path / "settings.json")
                logger.debug(f"Loading Docker Desktop config from {file_path}")
                try:
                    with open(file_path, 'r') as docker_desktop_config:
                        cls.__docker_desktop_resource_config = json.load(docker_desktop_config)
                except FileNotFoundError:
                    logger.warning(f"Docker Desktop configuration file not found: '{file_path}'")
                    return {}
                except JSONDecodeError:
                    logger.critical(f"The Docker Desktop configuration file '{file_path}' is not a valid JSON. Please fix your configuration file first.")
            if cls.__docker_desktop_resource_config is None:
                logger.warning(f"Docker Desktop configuration couldn't be loaded.'")
            else:
                return cls.__docker_desktop_resource_config
        return {}

    @classmethod
    def getDockerDesktopResources(cls) -> List[str]:
        settings = cls.getDockerDesktopSettings()
        # Handle legacy settings key
        docker_desktop_resources = settings.get('FilesharingDirectories', settings.get('filesharingDirectories', []))
        logger.debug(f"Docker Desktop resources whitelist: {docker_desktop_resources}")
        return docker_desktop_resources

    @classmethod
    def isHostNetworkAvailable(cls) -> bool:
        if cls.isLinuxHost():
            return True
        elif cls.isOrbstack():
            return True
        elif cls.isDockerDesktop():
            settings = cls.getDockerDesktopSettings()
            # Handle legacy settings key
            res = settings.get('HostNetworkingEnabled', settings.get('hostNetworkingEnabled', False))
            return res if res is not None else False
        logger.warning("Unknown or not supported environment for host network mode.")
        return False
