import logging
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePath
from typing import Optional, Tuple

from exegol.config.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger


def parseDockerVolumePath(source: str) -> PurePath:
    """Parse docker volume path to find the corresponding host path."""
    # Check if path is from Windows Docker Desktop
    matches = re.match(r"^/run/desktop/mnt/host/([a-z])(/.*)$", source, re.IGNORECASE)
    if matches:
        # Convert Windows Docker-VM style volume path to local OS path
        src_path = Path(f"{matches.group(1).upper()}:{matches.group(2)}")
        logger.debug(f"Windows style detected : {src_path}")
        return src_path
    else:
        # Remove docker mount path if exist
        return PurePath(source.replace('/run/desktop/mnt/host', ''))


def resolvPath(path: Path) -> str:
    """Resolv a filesystem path depending on the environment.
    On WSL, Windows PATH can be resolved using 'wslpath'."""
    if path is None:
        return ''
    # From WSL, Windows Path must be resolved (try to detect a Windows path with '\')
    if EnvInfo.current_platform == "WSL" and '\\' in str(path):
        try:
            # Resolv Windows path on WSL environment
            p = subprocess.Popen(["wslpath", "-a", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, err = p.communicate()
            logger.debug(f"Resolv path input: {path}")
            logger.debug(f"Resolv path output: {output!r}")
            if err != b'':
                # result is returned to STDERR when the translation didn't properly find a match
                logger.debug(f"Error on FS path resolution: {err!r}. Input path is probably a linux path.")
            else:
                return output.decode('utf-8').strip()
        except FileNotFoundError:
            logger.warning("Missing WSL tools: 'wslpath'. Skipping resolution.")
    return str(path)


def resolvStrPath(path: Optional[str]) -> str:
    """Try to resolv a filesystem path from a string."""
    if path is None:
        return ''
    return resolvPath(Path(path))


def setGidPermission(root_folder: Path) -> None:
    """Set the setgid permission bit to every recursive directory"""
    logger.verbose(f"Updating the permissions of {root_folder} (and sub-folders) to allow file sharing between the container and the host user")
    logger.debug(f"Adding setgid permission recursively on directories from {root_folder}")
    perm_alert = False
    # Set permission to root directory
    try:
        root_folder.chmod(root_folder.stat().st_mode | stat.S_IRWXG | stat.S_ISGID)
    except PermissionError:
        # Trigger the error only if the permission is not already set
        if not root_folder.stat().st_mode & stat.S_ISGID:
            logger.warning(f"The permission of this directory ({root_folder}) cannot be automatically changed.")
            perm_alert = True
    for sub_item in root_folder.rglob('*'):
        # Find every subdirectory
        try:
            if not sub_item.is_dir():
                continue
        except PermissionError:
            if not sub_item.is_symlink():
                logger.error(f"Permission denied when trying to resolv {str(sub_item)}")
            continue
        # If the permission is already set, skip
        if sub_item.stat().st_mode & stat.S_ISGID:
            continue
        # Set the permission (g+s) to every child directory
        try:
            sub_item.chmod(sub_item.stat().st_mode | stat.S_IRWXG | stat.S_ISGID)
        except PermissionError:
            logger.warning(f"The permission of this directory ({sub_item}) cannot be automatically changed.")
            perm_alert = True
    if perm_alert:
        logger.warning(f"In order to share files between your host and exegol (without changing the permission), you can run [orange3]manually[/orange3] this command from your [red]host[/red]:")
        logger.empty_line()
        logger.raw(f"sudo chgrp -R $(id -g) {root_folder} && sudo find {root_folder} -type d -exec chmod g+rws {{}} \\;", level=logging.WARNING)
        logger.empty_line()
        logger.empty_line()


def check_sysctl_value(sysctl: str, compare_to: str) -> bool:
    """Function to find a sysctl configured value and compare it to a desired value."""
    sysctl_path = "/proc/sys/" + sysctl.replace('.', '/')
    try:
        with open(sysctl_path, 'r') as conf:
            config = conf.read().strip()
            logger.debug(f"Checking sysctl value {sysctl}={config} (compare to {compare_to})")
            return conf.read().strip() == compare_to
    except FileNotFoundError:
        logger.debug(f"Sysctl file {sysctl} not found!")
    except PermissionError:
        logger.debug(f"Unable to read sysctl {sysctl} permission!")
    return False


def get_user_id() -> Tuple[int, int]:
    """On linux system, retrieve the original user id when using SUDO."""
    if sys.platform == "win32":
        raise SystemError
    user_uid_raw = os.getenv("SUDO_UID")
    if user_uid_raw is None:
        user_uid = os.getuid()
    else:
        user_uid = int(user_uid_raw)
    user_gid_raw = os.getenv("SUDO_GID")
    if user_gid_raw is None:
        user_gid = os.getgid()
    else:
        user_gid = int(user_gid_raw)
    return user_uid, user_gid


def mkdir(path) -> None:
    """Function to recursively create a directory and setting the right user and group id to allow host user access."""
    try:
        path.mkdir(parents=False, exist_ok=False)
        if sys.platform == "linux" and os.getuid() == 0:
            user_uid, user_gid = get_user_id()
            os.chown(path, user_uid, user_gid)
    except FileExistsError:
        # The directory already exist, this setup can be skipped
        pass
    except FileNotFoundError:
        # Create parent directory first
        mkdir(path.parent)
        # Then create the targeted directory
        mkdir(path)
