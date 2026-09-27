import json
import os
import platform
import re
import sys
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, List, Dict, Iterable, Tuple, Union, overload

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


def _read_proc_status(pid: int) -> Tuple[int, int, int]:
    """Return the (parent pid, real uid, effective uid) of a process from /proc/<pid>/status"""
    ppid: Optional[int] = None
    uid: Optional[int] = None
    euid: Optional[int] = None
    with open(f"/proc/{pid}/status", 'r') as status:
        for line in status:
            try:
                if line.startswith("PPid:"):
                    ppid = int(line.split()[1])
                elif line.startswith("Uid:"):
                    fields = line.split()
                    uid = int(fields[1])
                    euid = int(fields[2])
            except IndexError:
                raise ValueError(f"Malformed status of process {pid}")
    if ppid is None or uid is None or euid is None:
        raise ValueError(f"Incomplete status of process {pid}")
    return ppid, uid, euid


def _read_proc_environ(pid: int) -> bytes:
    """Return the raw exec-time environment of a process"""
    with open(f"/proc/{pid}/environ", 'rb') as environ:
        return environ.read()


def _read_proc_exe(pid: int) -> str:
    """Return the executable path of a process"""
    return os.readlink(f"/proc/{pid}/exe")


def _is_dir(path: str) -> bool:
    return os.path.isdir(path)


def _passwd_home(uid: int) -> Optional[str]:
    """Return the home directory of a user from the passwd database"""
    if sys.platform == "win32":
        return None
    import pwd
    try:
        return pwd.getpwuid(uid).pw_dir or None
    except KeyError:
        return None


def _parse_environ(raw: bytes) -> Dict[str, str]:
    """Parse a NUL-separated environment block, keeping the first occurrence of a duplicated name"""
    env: Dict[str, str] = {}
    for entry in raw.split(b"\x00"):
        if not entry:
            continue
        name, sep, value = entry.decode("utf-8", errors="surrogateescape").partition("=")
        if not sep or not name or name in env:
            continue
        env[name] = value
    return env


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

    class StorageDriver(Enum):
        """Dictionary class for static Docker storage driver name"""
        OVERLAY2 = "overlay2"  # Legacy graphdriver
        OVERLAYFS = "overlayfs"  # containerd snapshotter

    """Contain information about the environment (host, OS, platform, etc)"""
    # Shell env
    current_platform: str = "WSL" if "microsoft" in platform.release() else platform.system()  # Can be 'Windows', 'Linux' or 'WSL'
    is_linux_shell: bool = current_platform in ["WSL", "Linux"]
    is_windows_shell: bool = current_platform == "Windows"
    is_mac_shell: bool = not is_windows_shell and not is_linux_shell  # If not Linux nor Windows, its (probably) a mac
    __is_docker_desktop: bool = False
    # Docker client settings shared by the SDK and the docker CLI
    docker_env_names: Tuple[str, ...] = ("DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
    __windows_release: Optional[str] = None
    # Host OS
    __docker_host_os: Optional[HostOs] = None
    __docker_engine: Optional[DockerEngine] = None
    # Docker storage driver and daemon version
    __docker_storage_driver: Optional[str] = None
    __docker_server_version: Tuple[int, ...] = ()
    # Docker desktop cache config
    __docker_desktop_resource_config: Optional[dict] = None
    # Environment of the process launched by the sudo user's shell (cached, including a failed load)
    __parent_env: Optional[Dict[str, str]] = None
    __parent_env_loaded: bool = False
    # True when sudo started exegol directly
    __parent_env_direct: bool = True
    __PARENT_ENV_MAX_DEPTH: int = 32
    # Set by pam_systemd for root's own session under sudo
    __PAM_SESSION_NAMES = frozenset({"XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_SESSION_ID", "XDG_SESSION_CLASS",
                                     "XDG_SESSION_DESKTOP", "XDG_SEAT", "XDG_VTNR"})
    # Controlled by sudo on purpose (secure_path, identity, loader and interpreter injection)
    __PROTECTED_NAMES = frozenset({"PATH", "HOME", "SHELL", "USER", "LOGNAME", "MAIL", "IFS", "ENV", "BASH_ENV"})
    __PROTECTED_PREFIXES: Tuple[str, ...] = ("SUDO_", "LD_", "DYLD_", "PYTHON")
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

    @staticmethod
    def __sudoUserUid() -> Optional[int]:
        """Return the uid of the user who invoked sudo when running as root through sudo on Linux"""
        if sys.platform != "linux":
            return None
        if os.geteuid() != 0:
            return None
        try:
            uid = int(os.environ.get("SUDO_UID", ""))
        except ValueError:
            return None
        return uid if uid > 0 else None

    @classmethod
    def __loadParentEnv(cls, sudo_uid: int) -> Optional[Dict[str, str]]:
        """Load the environment of the process launched by the invoking user's shell (typically sudo), once per process"""
        if cls.__parent_env_loaded:
            return cls.__parent_env
        cls.__parent_env_loaded = True
        try:
            chain: List[int] = []
            pid = os.getppid()
            for _ in range(cls.__PARENT_ENV_MAX_DEPTH):
                if pid <= 1:
                    break
                ppid, uid, euid = _read_proc_status(pid)
                # A genuine user process has both uids. sudo keeps the user's ruid but not its euid, and a sudo
                # that dropped its ruid to 0 must still win over the shell, whose environ is an exec-time snapshot
                if uid == sudo_uid and euid == sudo_uid:
                    if not chain:
                        break
                    source = chain[-1]
                    cls.__parent_env = _parse_environ(_read_proc_environ(source))
                    cls.__parent_env_direct = cls.__isDirectLaunch(chain)
                    logger.debug(f"Host environment loaded from parent process {source} ({len(cls.__parent_env)} variables)")
                    return cls.__parent_env
                chain.append(pid)
                pid = ppid
        except (OSError, ValueError):
            pass
        logger.debug("Unable to load the host environment from a parent process of the sudo user")
        return None

    @staticmethod
    def __isDirectLaunch(chain: List[int]) -> bool:
        """Tell whether the processes between exegol and the env source are all the same executable as that source"""
        between = chain[:-1]
        if not between:
            return True
        # The use_pty monitor is a fork of sudo, anything else (a root shell, su, a script) set its own env on purpose
        try:
            source_exe = _read_proc_exe(chain[-1])
            return all(_read_proc_exe(pid) == source_exe for pid in between)
        except OSError:
            return True

    @classmethod
    def __isProtected(cls, name: str) -> bool:
        return name in cls.__PROTECTED_NAMES or name.startswith(cls.__PROTECTED_PREFIXES)

    @overload
    @classmethod
    def get_env(cls, name: str) -> Optional[str]:
        ...

    @overload
    @classmethod
    def get_env(cls, name: str, default: str) -> str:
        ...

    @overload
    @classmethod
    def get_env(cls, name: str, default: None) -> Optional[str]:
        ...

    @classmethod
    def get_env(cls, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return a host environment variable.
        Under sudo, the env of the process the user's shell launched is used, taking precedence over os.environ only
        when sudo started exegol directly (not through a root shell). PAM session names never come from root's own
        session, and names sudo controls always come from os.environ."""
        if cls.__isProtected(name):
            return os.environ.get(name, default)
        return cls.__resolveEnv(name, default)

    @classmethod
    def get_user_shell(cls) -> Optional[str]:
        """Return the SHELL of the user running exegol, the invoking user's one under sudo.
        SHELL is kept out of get_env because sudo sets it for the target user: only name a shell
        with this value, never run one."""
        return cls.__resolveEnv("SHELL", None)

    @classmethod
    def __resolveEnv(cls, name: str, default: Optional[str]) -> Optional[str]:
        """Resolve an environment variable through the sudo user env, without the protected name check"""
        sudo_uid = cls.__sudoUserUid()
        if sudo_uid is None:
            return os.environ.get(name, default)
        parent_env = cls.__loadParentEnv(sudo_uid)
        parent_value = parent_env.get(name) if parent_env is not None else None
        child_value = os.environ.get(name)
        if name in cls.__PAM_SESSION_NAMES:
            if parent_value is not None:
                return parent_value
            elif name == "XDG_RUNTIME_DIR":
                # Keep a custom or own runtime dir, never another user's one
                match = re.fullmatch(r"/run/user/(\d+)/?", child_value) if child_value is not None else None
                if child_value is not None and (match is None or int(match.group(1)) == sudo_uid):
                    return child_value
                # systemd convention
                derived = f"/run/user/{sudo_uid}"
                if _is_dir(derived):
                    return derived
            return default
        elif cls.__parent_env_direct:
            # An explicit 'sudo VAR=value' is shadowed when the user's shell also exports VAR
            if parent_value is not None:
                return parent_value
            return child_value if child_value is not None else default
        elif child_value is not None:
            return child_value
        return parent_value if parent_value is not None else default

    @classmethod
    def get_env_overlay(cls, names: Iterable[str]) -> Dict[str, str]:
        """Return an environment for a client or subprocess: os.environ with the given names resolved
        through get_env. os.environ is left untouched."""
        environment = dict(os.environ)
        for name in names:
            value = cls.get_env(name)
            # An empty value is meaningful, e.g. docker-py reads an empty DOCKER_TLS_VERIFY as false
            if value is not None:
                environment[name] = value
        return environment

    @classmethod
    def get_x11_client_env(cls) -> Dict[str, str]:
        """Return the environment for the host X11 clients (xhost, xauth)"""
        env = cls.get_env_overlay(("DISPLAY", "XAUTHORITY"))
        if cls.is_sudo_context() and not env.get("XAUTHORITY"):
            # sudo keeps HOME=/root, so the X clients would miss the user's default cookie file
            try:
                xauthority = cls.get_user_home() / ".Xauthority"
            except RuntimeError:
                return env
            try:
                # Path.is_file raises on an unreadable home (e.g. root-squashed NFS) before Python 3.14
                if xauthority.is_file():
                    env["XAUTHORITY"] = str(xauthority)
            except OSError:
                pass
        return env

    @classmethod
    def is_sudo_context(cls) -> bool:
        """Tell whether exegol runs as root through sudo on Linux"""
        return cls.__sudoUserUid() is not None

    @classmethod
    def get_user_home(cls) -> Path:
        """Return the home directory of the user running exegol, the invoking user's one under sudo"""
        sudo_uid = cls.__sudoUserUid()
        if sudo_uid is not None:
            sudo_home = os.environ.get("SUDO_HOME")
            if sudo_home:
                return Path(sudo_home)
            passwd_home = _passwd_home(sudo_uid)
            if passwd_home:
                return Path(passwd_home)
        return Path.home()

    @classmethod
    def expand_user(cls, path: Union[str, "os.PathLike[str]"]) -> Path:
        """Expand a leading '~' like Path.expanduser, to the invoking user's home under sudo"""
        text = os.fspath(path)
        # sudo keeps HOME=/root, so a plain expansion would name root's home
        if cls.is_sudo_context() and (text == "~" or text.startswith("~" + os.sep)):
            home = str(cls.get_user_home()).rstrip(os.sep)
            return Path((home + text[1:]) or os.sep)
        return Path(path).expanduser()

    @classmethod
    def initData(cls, docker_info: Dict[str, str]) -> None:
        """Initialize information from Docker daemon data"""
        # Fetch data from Docker daemon
        docker_os = docker_info.get("OperatingSystem", "unknown").lower()
        docker_kernel = docker_info.get("KernelVersion", "unknown").lower()
        # Storage driver: 'overlay2' is the legacy graphdriver, 'overlayfs' the containerd snapshotter
        cls.__docker_storage_driver = docker_info.get("Driver")
        cls.__docker_server_version = cls.__parseVersion(docker_info.get("ServerVersion"))
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
        if cls.__docker_host_os is not None:
            return cls.__docker_host_os
        raise RuntimeError("Docker host OS is not initialized. Please call EnvInfo.initData() before using this method.")

    @classmethod
    def getDisplayServer(cls) -> DisplayServer:
        """Returns the display server
        Can be 'X11' or 'Wayland'"""
        session_type = cls.get_env("XDG_SESSION_TYPE", "x11")
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
        return cls.getDisplayServer() == cls.DisplayServer.WAYLAND or bool(cls.get_env("WAYLAND_DISPLAY"))

    @classmethod
    def isDockerDesktop(cls) -> bool:
        """Return true if docker desktop is used on the host"""
        return cls.__is_docker_desktop

    @classmethod
    def isOrbstack(cls) -> bool:
        """Return true if docker desktop is used on the host"""
        return cls.__docker_engine == cls.DockerEngine.ORBSTACK

    # Last Docker version where the image inspect 'Size' attribute reports the
    # compressed size instead of the on-disk usage when the containerd snapshotter is enabled.
    # Up to this version the disk usage must be fetched from /system/df, above it 'Size' can be trusted.
    __DOCKER_LAST_BUGGED_SIZE_VERSION: Tuple[int, ...] = (29, 7, 2)

    @staticmethod
    def __parseVersion(version: Optional[str]) -> Tuple[int, ...]:
        """Parse a docker version string (e.g. '29.7.2', '29.7.2-rc1') to a comparable tuple of int."""
        if not version:
            return ()
        numbers = []
        # Only keep the leading numeric parts, ignoring any pre-release / build suffix
        for part in version.split('.'):
            match = re.match(r"^\d+", part)
            if match is None:
                break
            numbers.append(int(match.group()))
        return tuple(numbers)

    @classmethod
    def getDockerStorageDriver(cls) -> Optional[str]:
        """Return the docker storage driver name (e.g. 'overlay2' or 'overlayfs')"""
        return cls.__docker_storage_driver

    @classmethod
    def isContainerdSnapshotter(cls) -> bool:
        """Return true if docker uses the containerd snapshotter image store.
        In this mode the image inspect 'Size' attributes have inconsistent value."""
        return cls.__docker_storage_driver == cls.StorageDriver.OVERLAYFS.value

    @classmethod
    def hasWrongImageSizeAttr(cls) -> bool:
        """Return true if the docker daemon is known to report the compressed size in the image 'Size' attribute.
        Only relevant when the containerd snapshotter is used."""
        # When the version is unknown, assume the daemon is still affected to keep the /system/df fallback
        if not cls.__docker_server_version:
            return True
        return cls.isContainerdSnapshotter() and cls.__docker_server_version <= cls.__DOCKER_LAST_BUGGED_SIZE_VERSION

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
            res = settings.get('HostNetworkingEnabled', settings.get('hostNetworkingEnabled'))
            if res is None:
                logger.warning("Host network mode for Docker Desktop is not available, you need to upgrade Docker Desktop to enable it!")
            elif not res:
                logger.warning(
                    "Docker desktop now supports host network mode. However, this mode is currently [red]disabled[/red]. You need to manually change the configuration in your Docker Desktop settings to support host network sharing with Exegol.")
            if not res:
                logger.info("To share network ports (without host network) between the host and exegol, use the [bright_blue]--port[/bright_blue] parameter.")
                logger.verbose("Official doc: https://docs.docker.com/network/drivers/host/#docker-desktop")
            return res if res is not None else False
        logger.warning("Unknown or not supported environment for host network mode.")
        return False
