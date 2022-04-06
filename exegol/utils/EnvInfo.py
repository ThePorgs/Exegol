import platform
from typing import Optional


class EnvInfo:
    """Contain information about the environment (host, OS, platform, etc)"""
    # Shell env
    current_platform: str = "WSL" if "microsoft" in platform.release() else platform.system()  # Can be 'Windows', 'Linux' or 'WSL'
    is_linux_shell: bool = current_platform in ["WSL", "Linux"]  # TODO test mac platform
    is_windows_shell: bool = current_platform == "Windows"
    windows_release: str = platform.win32_ver()[1]
    # Host OS
    __docker_host_os: Optional[str] = None
    __docker_engine: Optional[str] = None

    @classmethod
    def initData(cls, docker_info):
        """Initialize information from Docker daemon data"""
        # Fetch data from Docker daemon
        docker_os = docker_info.get("OperatingSystem", "unknown").lower()
        docker_kernel = docker_info.get("KernelVersion", "unknown").lower()
        # Deduct a Windows Host from data
        is_host_windows = docker_os == "docker desktop" and "microsoft" in docker_kernel  # TODO handle mac docker-desktop
        cls.__docker_host_os = "Windows" if is_host_windows else "Unix"
        if is_host_windows:
            # Check docker engine with Windows host
            is_wsl2 = "wsl2" in docker_kernel
            cls.__docker_engine = "wsl2" if is_wsl2 else "hyper-v"
        else:
            cls.__docker_engine = "Kernel"
        pass

    @classmethod
    def getHostOs(cls) -> str:
        """Return Host OS
        Can be 'Windows' or 'Unix'"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_host_os is not None
        return cls.__docker_host_os

    @classmethod
    def isWindowsHost(cls) -> bool:
        return cls.getHostOs() == "Windows"

    @classmethod
    def getDockerEngine(cls) -> str:
        """Return Docker engine type.
        Can be 'Kernel', 'wsl2' or 'hyper-v'"""
        # initData must be called from DockerUtils on client initialisation
        assert cls.__docker_engine is not None
        return cls.__docker_engine
