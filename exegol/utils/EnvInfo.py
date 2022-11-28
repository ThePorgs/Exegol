import json
import platform
import re
import shutil
import subprocess
from typing import Optional, Any, List

from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


class EnvInfo:
    """Class to identify the environment in which exegol runs to adapt
    the configurations, processes and messages for the user"""

    class HostOs:
        """Dictionary class for static OS Name"""
        WINDOWS = "Windows"
        LINUX = "Linux"
        MAC = "Mac"

    class DockerEngine:
        """Dictionary class for static Docker engine name"""
        WLS2 = "wsl2"
        HYPERV = "hyper-v"
        MAC = "mac"
        LINUX = "kernel"

    """Contain information about the environment (host, OS, platform, etc)"""
    # Shell env
    current_platform: str = "WSL" if "microsoft" in platform.release() else platform.system()  # Can be 'Windows', 'Linux' or 'WSL'
    is_linux_shell: bool = current_platform in ["WSL", "Linux"]
    is_windows_shell: bool = current_platform == "Windows"
    is_mac_shell = not is_windows_shell and not is_linux_shell  # If not Linux nor Windows, its (probably) a mac
    __is_docker_desktop: bool = False
    __windows_release: Optional[str] = None
    # Host OS
    __docker_host_os: Optional[str] = None
    __docker_engine: Optional[str] = None
    # Docker desktop cache config
    __docker_desktop_resource_config = None
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
    def initData(cls, docker_info):
        """Initialize information from Docker daemon data"""
        # Fetch data from Docker daemon
        docker_os = docker_info.get("OperatingSystem", "unknown").lower()
        docker_kernel = docker_info.get("KernelVersion", "unknown").lower()
        # Deduct a Windows Host from data
        cls.__is_docker_desktop = docker_os == "docker desktop"
        is_host_windows = cls.__is_docker_desktop and "microsoft" in docker_kernel
        if is_host_windows:
            # Check docker engine with Windows host
            if "wsl2" in docker_kernel:
                cls.__docker_engine = cls.DockerEngine.WLS2
            else:
                cls.__docker_engine = cls.DockerEngine.HYPERV
            cls.__docker_host_os = cls.HostOs.WINDOWS
        elif cls.__is_docker_desktop:
            # If docker desktop is detected but not a Windows engine/kernel, it's (probably) a mac
            cls.__docker_engine = cls.DockerEngine.MAC
            cls.__docker_host_os = cls.HostOs.MAC
        else:
            # Every other case it's a linux distro and docker is powered from the kernel
            cls.__docker_engine = cls.DockerEngine.LINUX
            cls.__docker_host_os = cls.HostOs.LINUX

    @classmethod
    def getHostOs(cls) -> str:
        """Return Host OS
        Can be 'Windows', 'Mac' or 'Linux'"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_host_os is not None
        return cls.__docker_host_os

    @classmethod
    def getWindowsRelease(cls) -> str:
        # Cache check
        if cls.__windows_release is None:
            if cls.is_windows_shell:
                # From a Windows shell, python supply an approximate (close enough) version of windows
                cls.__windows_release = platform.win32_ver()[1]
            elif cls.current_platform == "WSL":
                # From a WSL shell, we must create a process to retrieve the host's version
                # Find version using MS-DOS command 'ver'
                if not shutil.which("cmd.exe"):
                    logger.critical("cmd.exe is not accessible from your WSL environment!")
                proc = subprocess.Popen(["cmd.exe", "/c", "ver"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                proc.wait()
                assert proc.stdout is not None
                # Try to match Windows version
                matches = re.search(r"version (\d+\.\d+\.\d+)(\.\d*)?", proc.stdout.read().decode('utf-8'))
                if matches:
                    # Select match 1 and apply to the attribute
                    cls.__windows_release = matches.group(1)
                else:
                    # If there is any match, fallback to empty
                    cls.__windows_release = ""
            else:
                cls.__windows_release = ""
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
    def isDockerDesktop(cls) -> bool:
        """Return true if docker desktop is used on the host"""
        return cls.__is_docker_desktop

    @classmethod
    def getDockerEngine(cls) -> str:
        """Return Docker engine type.
        Can be 'kernel', 'mac', 'wsl2' or 'hyper-v'"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_engine is not None
        return cls.__docker_engine

    @classmethod
    def getShellType(cls):
        """Return the type of shell exegol is executed from"""
        if cls.is_linux_shell:
            return cls.HostOs.LINUX
        elif cls.is_windows_shell:
            return cls.HostOs.WINDOWS
        elif cls.is_mac_shell:
            return cls.HostOs.MAC
        else:
            return "Unknown"

    @classmethod
    def getDockerDesktopSettings(cls) -> Optional[Any]:
        """Applicable only for docker desktop on macos"""
        if cls.isDockerDesktop():
            if cls.__docker_desktop_resource_config is None:
                if cls.is_mac_shell:
                    path = ConstantConfig.docker_desktop_mac_config_path
                elif cls.is_windows_shell:
                    path = ConstantConfig.docker_desktop_windows_config_path
                else:
                    return None
                    # TODO support from WSL shell
                try:
                    with open(path, 'r') as docker_desktop_config:
                        cls.__docker_desktop_resource_config = json.load(docker_desktop_config)
                except FileNotFoundError:
                    logger.warning(f"Docker Desktop configuration file not found: '{path}'")
                    return None
            return cls.__docker_desktop_resource_config
        return None

    @classmethod
    def getDockerDesktopResources(cls) -> List[str]:
        config = cls.getDockerDesktopSettings()
        if config:
            return config.get('filesharingDirectories', [])
        return []
