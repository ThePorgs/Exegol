import os
import sys
from pathlib import Path
from typing import Optional, Union


class SudoInfo:
    """Resolve the identity of the user who invoked exegol through sudo.
    Standard library only: ConstantConfig resolves the config dir with it at import time,
    so it must not import any exegol module (EnvInfo imports ConstantConfig)."""

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
