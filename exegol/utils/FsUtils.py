import logging
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath, PurePath
from typing import Optional

from exegol.utils.EnvInfo import EnvInfo
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
        return PurePosixPath(source.replace('/run/desktop/mnt/host', ''))


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


def setGidPermission(root_folder: Path):
    """Set the setgid permission bit to every recursive directory"""
    logger.verbose(f"Updating the permissions of {root_folder} (and sub-folders) to allow file sharing between the container and the host user")
    logger.debug(f"Adding setgid permission recursively on directories from {root_folder}")
    perm_alert = False
    # Set permission to root directory
    try:
        root_folder.chmod(root_folder.stat().st_mode | stat.S_ISGID)
    except PermissionError:
        # Trigger the error only if the permission is not already set
        if not root_folder.stat().st_mode & stat.S_ISGID:
            logger.warning(f"The permission of this directory ({root_folder}) cannot be automatically changed.")
            perm_alert = True
    for sub_item in root_folder.rglob('*'):
        # Find every subdirectory
        if not sub_item.is_dir():
            continue
        # If the permission is already set, skip
        if sub_item.stat().st_mode & stat.S_ISGID:
            continue
        # Set the permission (g+s) to every child directory
        try:
            sub_item.chmod(sub_item.stat().st_mode | stat.S_ISGID)
        except PermissionError:
            logger.warning(f"The permission of this directory ({sub_item}) cannot be automatically changed.")
            perm_alert = True
    if perm_alert:
        logger.warning(f"In order to share files between your host and exegol (without changing the permission), you can run [orange3]manually[/orange3] this command from your [red]host[/red]:")
        logger.empty_line()
        logger.raw(f"sudo chgrp -R $(id -g) {root_folder} && sudo find {root_folder} -type d -exec chmod g+rws {{}} \;", level=logging.WARNING)
        logger.empty_line()
        logger.empty_line()
