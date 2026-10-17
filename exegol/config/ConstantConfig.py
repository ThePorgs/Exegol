import os
import sys
from pathlib import Path
from typing import Optional

from exegol.config.SudoInfo import SudoInfo

__version__ = "6.0.2"

# Environment variable forcing the exegol config directory
EXEGOL_HOME_ENV: str = "EXEGOL_HOME"


def resolve_exegol_config_path(home: Path, invoker_home: Optional[Path], sudo_home: Optional[str]) -> Path:
    """Resolve the exegol config directory.

    :param home: home of the current process (/root under sudo).
    :param invoker_home: home of the sudo invoking user, None outside a sudo context.
    :param sudo_home: the SUDO_HOME environment variable.
    """
    config = home / ".exegol"
    # A /root/.exegol migrated by 'sudo exegol activate' is a symlink to the invoking user's directory:
    # use the user's real path. A real /root/.exegol directory is never redirected (legacy location kept
    # active on purpose): that is the state the activate migration detects and proposes to fix.
    if invoker_home is not None and config.is_symlink() and \
            os.path.realpath(config) == os.path.realpath(invoker_home / ".exegol"):
        return invoker_home / ".exegol"
    if not config.is_dir():
        # Use legacy path or use sudo home env by default for new config
        if sudo_home:
            return Path(sudo_home) / ".exegol"
        # sudo < 1.9.16 does not export SUDO_HOME: fall back on the invoking user's passwd home
        if invoker_home is not None:
            return invoker_home / ".exegol"
    return config


def resolve_exegol_home(raw: Optional[str]) -> Optional[Path]:
    """Validate the value of EXEGOL_HOME, the exegol config directory forced by the operator.

    The path is used as given (no realpath, no creation): a missing directory is created later by the
    normal config creation path. The path must not be a symbolic link. The directory, or its parent when it
    is missing, must already belong to the user running exegol (the sudo invoking user under sudo), and the
    parent of an existing directory must belong to that user or to root. A parent that is a symbolic link must
    itself belong to that user or to root. These owner checks are POSIX only:
    Windows has no uid, so they are skipped there.

    :param raw: the EXEGOL_HOME value, None when unset.
    :return: the forced config directory, None when unset or empty (automatic resolution applies).
    :raises ValueError: the value cannot be used, with an operator-facing message.
    """
    if not raw:
        return None
    # The owner check needs the invoking user's uid, which is only resolved on Linux (macOS: sudo -E or
    # 'sudo EXEGOL_HOME=...'), and exegol only chowns what it creates under sudo on Linux
    if SudoInfo.isUnresolvedSudo():
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used under sudo on this platform: the sudo invoking "
                         f"user cannot be resolved. Run exegol without sudo, or unset {EXEGOL_HOME_ENV}.")
    fix = f"Set {EXEGOL_HOME_ENV} to an absolute directory path owned by you, or unset it."
    # Usually a copy-paste or '$(cat file)' mistake that would silently create a new, empty config dir
    if raw != raw.strip():
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the value starts or ends with whitespace. {fix}")
    try:
        path = SudoInfo.expandUser(raw)
    except RuntimeError:
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the '~' home directory cannot be resolved. {fix}")
    if not path.is_absolute():
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the path must be absolute, a relative path would "
                         f"depend on the directory exegol is launched from. {fix}")
    # pathlib keeps '..' as given: '/tmp/..' would name the filesystem root past the check below
    if ".." in path.parts:
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: '..' components are not allowed. {fix}")
    # The second check catches an existing path naming the root, e.g. a symlink to it ('/proc/self/root')
    if path.parent == path or (os.path.isdir(path) and os.path.samefile(path, os.sep)):
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the filesystem root cannot hold the exegol "
                         f"config directory. {fix}")
    # '/proc/self/cwd' is absolute but names the directory of whichever process resolves it (dockerd included),
    # and so does '/dev/fd/N' (a link to '/proc/self/fd', the directory fd N of the resolving process)
    if sys.platform != "win32" and (path.parts[1:2] == ("proc",) or path.parts[1:3] == ("dev", "fd")):
        raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: a /proc or /dev/fd path names a per-process "
                         f"location. {fix}")
    if os.path.lexists(path):
        if not os.path.isdir(path):
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the path exists but is not a directory. {fix}")
        # The path is re-resolved on every access: whoever owns the link could repoint it after the owner check
        if os.path.islink(path):
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the path is a symbolic link, set the real "
                             f"directory path instead. {fix}")
        owned, owned_name = path, "the directory"
    else:
        # Only the last directory is created: a missing parent is never created (nor re-owned under sudo)
        if not os.path.isdir(path.parent):
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the parent directory '{path.parent}' does not "
                             f"exist, exegol only creates the last directory of the path. {fix}")
        owned, owned_name = path.parent, "the parent directory"
    # Same trust boundary as the default ~/.exegol: the directory (or the parent that will hold it) must already
    # belong to the user running exegol, the sudo invoking user under sudo (a root-owned directory is refused)
    user_uid = SudoInfo.getUserUid()
    if user_uid is not None:
        sudo_note = ", the sudo invoking user" if SudoInfo.isSudoContext() else ""
        user = f"the user running exegol (uid {user_uid}{sudo_note})"
        owner_uid = os.stat(owned).st_uid
        if owner_uid != user_uid:
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: {owned_name} '{owned}' belongs to uid "
                             f"{owner_uid}, it must already belong to {user}. {fix}")
        # The owner of the parent could rename the directory away and put its own in place after this check
        parent_uid = os.stat(path.parent).st_uid
        if parent_uid not in (user_uid, 0):
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the parent directory '{path.parent}' belongs to "
                             f"uid {parent_uid}, it must belong to {user} or to root. {fix}")
        # The checks above follow a symlinked parent: the link itself must not belong to another user either,
        # or its owner could repoint it after this check (same reason as the symlink refusal of the path)
        parent_link_uid = os.lstat(path.parent).st_uid
        if parent_link_uid not in (user_uid, 0):
            raise ValueError(f"{EXEGOL_HOME_ENV}='{raw}' cannot be used: the parent directory is a symbolic link and the "
                             f"link '{path.parent}' belongs to uid {parent_link_uid}, it must belong to {user} or to "
                             f"root. {fix}")
    return path


def read_exegol_home(completion_mode: bool) -> Optional[Path]:
    """Return the exegol config directory forced by EXEGOL_HOME, read through the sudo user env, None when unset.
    A refused value stops exegol (SystemExit(1)), silently in shell completion mode."""
    try:
        return resolve_exegol_home(SudoInfo.getEnv(EXEGOL_HOME_ENV))
    except ValueError as error:
        if completion_mode:
            # A completer prints nothing: no candidate is offered
            raise SystemExit(1)
        # ExeLog imports no exegol module, so there is no import cycle. Reported here because every entry point
        # imports this module first, and ExegolController's module-level imports create the config dir before main() runs
        from rich.markup import escape
        from exegol.utils.ExeLog import logger, ExeLog
        # 'exegol completion > file' must not hide the error inside the file
        ExeLog.console.file = sys.stderr
        logger.critical(escape(str(error)))
        # Unreachable: logger.critical exits or raises (and raise mode cannot be set before this import).
        # Kept because critical is not typed NoReturn: mypy and callers stay fail-closed
        raise SystemExit(1)


class ConstantConfig:
    """Constant parameters information"""
    # Exegol Version
    version: str = __version__

    # Exegol documentation link
    landing: str = "https://exegol.com"
    documentation: str = "https://docs.exegol.com"
    # OS Dir full root path of exegol project
    src_root_path_obj: Path = Path(__file__).parent.parent.parent.resolve()
    # Path of the entrypoint.sh
    entrypoint_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/entrypoint.sh"
    # Path of the spawn.sh
    spawn_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/spawn.sh"
    # Path of sentinel logging scripts
    sentinel_zsh_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/shell_script/zsh_hooks.sh"
    sentinel_bash_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/shell_script/bash_hooks.sh"
    sentinel_context_path_obj: Path = src_root_path_obj / "exegol/utils/imgsync/sentinel"
    # Path to the EULA docs
    eula_path: Path = src_root_path_obj / "exegol/utils/docs/eula.md"
    # True when the current process has been spawned by the shell completion system (argcomplete).
    # In this mode, everything not strictly required to supply completion options must be skipped.
    completion_mode: bool = bool(os.getenv("_ARGCOMPLETE"))
    # Exegol config directory: forced by EXEGOL_HOME, with no automatic resolution and no migration; resolved otherwise
    __sudo_home = os.getenv("SUDO_HOME")
    __forced_config_path = read_exegol_home(completion_mode)
    exegol_config_forced: bool = __forced_config_path is not None
    exegol_config_path: Path = __forced_config_path if __forced_config_path is not None else \
        resolve_exegol_config_path(Path.home(), SudoInfo.getInvokerHome(), __sudo_home)
    # Docker Desktop for mac config file
    docker_desktop_mac_config_path = (Path(__sudo_home) if __sudo_home else Path().home()) / "Library/Group Containers/group.com.docker"
    docker_desktop_windows_config_short_path = "AppData/Roaming/Docker"
    docker_desktop_windows_config_path = Path().home() / docker_desktop_windows_config_short_path
    # Install mode, check if Exegol has been git cloned or installed using pip package
    git_source_installation: bool = (src_root_path_obj / '.git').is_dir()
    pip_installed: bool = src_root_path_obj.name == "site-packages"
    pipx_installed: bool = "/pipx/venvs/" in src_root_path_obj.as_posix()
    uv_installed: bool = "/uv/tools/" in src_root_path_obj.as_posix()
    # Dockerhub Exegol images repository
    DOCKER_HUB: str = "hub.docker.com"  # Don't handle docker login operations
    DOCKER_REGISTRY: str = "registry-1.docker.io"  # Don't handle docker login operations
    IMAGE_NAME: str = "registry.exegol.com/exegol"
    COMMUNITY_IMAGE_NAME: str = "nwodtuhs/exegol"
    OFFICIAL_REPOSITORIES = [IMAGE_NAME, COMMUNITY_IMAGE_NAME]
    GITHUB_REPO: str = "ThePorgs/Exegol"
    # Docker volume names (no docker volume used at this moment)
    # Resources repository
    EXEGOL_IMAGES_REPO: str = "https://github.com/ThePorgs/Exegol-images.git"
    EXEGOL_RESOURCES_REPO: str = "https://github.com/ThePorgs/Exegol-resources.git"
    # Official Sentinel 'core' profile source.
    EXEGOL_SENTINEL_CORE_REPO: str = "https://github.com/ThePorgs/sentinel-core-library.git"
    # Supabase
    SUPABASE_URL: str = "https://piysvuvahfkfxnlxqpdd.supabase.co"
    SUPABASE_KEY: str = "sb_publishable_pvQaN5IZryBn5a2kdkQxVw_TbxfM6Wq"

    # Zero-configuration source: the 'local' directory under a component_path.
    DEFAULT_LOCAL_SOURCE_KEY = "local"
    # Reserved key of the official Sentinel source: fallback namespace for bare references,
    # cannot be redefined by a user source.
    SENTINEL_CORE_SOURCE_KEY = "core"
