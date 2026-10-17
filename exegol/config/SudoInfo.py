import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, overload


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


class SudoInfo:
    """Resolve the identity of the user who invoked exegol through sudo, and the environment of that user.
    Standard library only: ConstantConfig resolves the config dir with it at import time,
    so it must not import any exegol module (EnvInfo imports ConstantConfig)."""

    # Environment of the process launched by the sudo user's shell (cached, including a failed load)
    __parent_env: Optional[Dict[str, str]] = None
    __parent_env_loaded: bool = False
    # True when sudo started exegol directly
    __parent_env_direct: bool = True
    # Outcome of the parent env load, recorded for the debug banner because this module cannot log
    __parent_env_report: Optional[str] = None
    __PARENT_ENV_MAX_DEPTH: int = 32
    # Set by pam_systemd for root's own session under sudo
    __PAM_SESSION_NAMES = frozenset({"XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_SESSION_ID", "XDG_SESSION_CLASS",
                                     "XDG_SESSION_DESKTOP", "XDG_SEAT", "XDG_VTNR"})
    # Controlled by sudo on purpose (secure_path, identity, loader and interpreter injection)
    __PROTECTED_NAMES = frozenset({"PATH", "HOME", "SHELL", "USER", "LOGNAME", "MAIL", "IFS", "ENV", "BASH_ENV"})
    __PROTECTED_PREFIXES: Tuple[str, ...] = ("SUDO_", "LD_", "DYLD_", "PYTHON")

    @staticmethod
    def getSudoUserUid() -> Optional[int]:
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
    def isSudoContext(cls) -> bool:
        """Tell whether exegol runs as root through sudo on Linux"""
        return cls.getSudoUserUid() is not None

    @staticmethod
    def isUnresolvedSudo() -> bool:
        """Tell whether exegol runs as root through sudo on a platform where the invoking user is not resolved
        (macOS): only Linux resolves it, see getSudoUserUid"""
        # Two separate checks: mypy's --platform narrowing keeps os.geteuid unreachable on win32
        if sys.platform == "win32":
            return False
        if sys.platform == "linux":
            return False
        return os.geteuid() == 0 and bool(os.environ.get("SUDO_UID"))

    @staticmethod
    def getPasswdHome(uid: int) -> Optional[str]:
        """Return the home directory of a user from the passwd database"""
        if sys.platform == "win32":
            return None
        import pwd
        try:
            return pwd.getpwuid(uid).pw_dir or None
        except KeyError:
            return None

    @classmethod
    def getInvokerHome(cls) -> Optional[Path]:
        """Return the home directory of the user who invoked sudo, None outside a sudo context or when unresolvable"""
        sudo_uid = cls.getSudoUserUid()
        if sudo_uid is None:
            return None
        sudo_home = os.environ.get("SUDO_HOME")
        if sudo_home:
            return Path(sudo_home)
        # sudo < 1.9.16 does not export SUDO_HOME
        passwd_home = cls.getPasswdHome(sudo_uid)
        return Path(passwd_home) if passwd_home else None

    @classmethod
    def getUserUid(cls) -> Optional[int]:
        """Return the uid of the user running exegol, the invoking user's one under sudo, None on Windows (no uid)"""
        if sys.platform == "win32":
            return None
        sudo_uid = cls.getSudoUserUid()
        return sudo_uid if sudo_uid is not None else os.geteuid()

    @classmethod
    def getUserHome(cls) -> Path:
        """Return the home directory of the user running exegol, the invoking user's one under sudo"""
        return cls.getInvokerHome() or Path.home()

    @classmethod
    def expandUser(cls, path: Union[str, "os.PathLike[str]"]) -> Path:
        """Expand a leading '~' like Path.expanduser, to the invoking user's home under sudo"""
        text = os.fspath(path)
        # sudo keeps HOME=/root, so a plain expansion would name root's home
        if cls.isSudoContext() and (text == "~" or text.startswith("~" + os.sep)):
            home = str(cls.getUserHome()).rstrip(os.sep)
            return Path((home + text[1:]) or os.sep)
        return Path(path).expanduser()

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
                    cls.__parent_env_report = f"Host environment loaded from parent process {source} ({len(cls.__parent_env)} variables)"
                    return cls.__parent_env
                chain.append(pid)
                pid = ppid
        except (OSError, ValueError):
            pass
        cls.__parent_env_report = "Unable to load the host environment from a parent process of the sudo user"
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
    def getEnv(cls, name: str) -> Optional[str]:
        ...

    @overload
    @classmethod
    def getEnv(cls, name: str, default: str) -> str:
        ...

    @overload
    @classmethod
    def getEnv(cls, name: str, default: None) -> Optional[str]:
        ...

    @classmethod
    def getEnv(cls, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return a host environment variable.
        Under sudo, the env of the process the user's shell launched is used, taking precedence over os.environ only
        when sudo started exegol directly (not through a root shell). PAM session names never come from root's own
        session, and names sudo controls always come from os.environ."""
        if cls.__isProtected(name):
            return os.environ.get(name, default)
        return cls.__resolveEnv(name, default)

    @classmethod
    def getUserShell(cls) -> Optional[str]:
        """Return the SHELL of the user running exegol, the invoking user's one under sudo.
        SHELL is kept out of getEnv because sudo sets it for the target user: only name a shell
        with this value, never run one."""
        return cls.__resolveEnv("SHELL", None)

    @classmethod
    def getParentEnvReport(cls) -> Optional[str]:
        """Return the outcome of the parent env load for the debug banner, None until a load was attempted.
        Recorded because this module cannot log (standard library only)."""
        return cls.__parent_env_report

    @classmethod
    def __resolveEnv(cls, name: str, default: Optional[str]) -> Optional[str]:
        """Resolve an environment variable through the sudo user env, without the protected name check"""
        sudo_uid = cls.getSudoUserUid()
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
