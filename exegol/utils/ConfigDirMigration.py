"""Filesystem engine of the legacy /root/.exegol -> ~user/.exegol migration.

Pure filesystem operations, no prompt: the interactive flow lives in exegol/manager/ConfigDirManager.py.

The migration runs as root while the invoking user controls ~user/.exegol: every user-side path is
reached through directory fds opened component by component without following symlinks, so a path
swapped for a symlink during the migration makes it fail instead of acting on the link target.
"""
import errno
import filecmp
import os
import re
import secrets
import stat
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import SCRATCH_SUFFIX, scratch_prefix


class MigrationAborted(ValueError):
    """The migration was refused before any filesystem change"""


class MigrationSide(Enum):
    """Side of a conflict to keep"""
    ROOT = "root"
    USER = "user"


class MigrationAction(Enum):
    # Move the root entry to the user dir (absent or file-free on the user side)
    MOVE = "move"
    # Drop the root entry: byte-identical file, or a tree holding no file
    DISCARD_ROOT = "discard_root"
    # Back up the user entry, then move the root entry in (wrapper state: the active copy wins)
    REPLACE = "replace"
    # Back up a user entry that must not be paired with the root content (stale SQLite side files)
    BACKUP_USER = "backup_user"
    # Both sides hold different data: the user decides, the other side is backed up
    CONFLICT = "conflict"


@dataclass(frozen=True)
class MigrationStep:
    action: MigrationAction
    relative: Path
    reason: str


@dataclass
class MigrationPlan:
    root_dir: Path
    user_dir: Path
    # True when the user dir does not exist: the whole root dir is moved as is
    fresh: bool
    steps: List[MigrationStep] = field(default_factory=list)

    @property
    def conflicts(self) -> List[MigrationStep]:
        return [step for step in self.steps if step.action == MigrationAction.CONFLICT]


# Directories holding one entry per container, merged per child instead of as a whole: keeping one side
# wholesale would remove another container's bind-mount source.
# workspaces: <private_workspace_path>/<container_name> (ContainerConfig.py, private workspace setup ~line 1281)
# sentinel: <sentinel_path>/<container_name>_<timestamp> (ContainerConfig.py, sentinel setup ~line 795)
CONTAINER_KEYED_DIRS = ("workspaces", "sentinel")

DATASTORE_FILE = ".datastore"
DATASTORE_SIDE_FILES = (".datastore-wal", ".datastore-shm", ".datastore-journal")
SESSION_LOCK_FILE = ".session.lock"
# Root-side files that only exist while a process uses the license database or refreshes the session.
# SQLite removes the side files when the last connection closes and SessionHandler removes the lock:
# they are never planned, and their presence at apply time means another exegol process is active.
VOLATILE_ROOT_FILES = DATASTORE_SIDE_FILES + (SESSION_LOCK_FILE,)
# Same rule as SessionHandler: a session lock older than one hour was left by a crashed process
SESSION_LOCK_MAX_AGE = 3600
# Suffix (+ random hex) of a cross-filesystem source taken out of service once copied, until it is removed
RETIRED_MARKER = ".migrated-"
_RETIRED_NAME = re.compile(re.escape(RETIRED_MARKER) + r"[0-9a-f]{8}$")


# Files written by the wrapper itself at the top level of the config directory.
# Any other top-level '*.key' file (offline license keys, see SessionHandler) is also a wrapper file.
WRAPPER_FILE_NAMES: Tuple[str, ...] = ("config.yml", "config.yml.bak",
                                       DATASTORE_FILE) + DATASTORE_SIDE_FILES + (".datacache", SESSION_LOCK_FILE, "license.key")
WRAPPER_FILE_SUFFIX = ".key"


def isWrapperFileName(name: str) -> bool:
    """Tell whether a top-level entry name of the config directory is a wrapper file"""
    return name in WRAPPER_FILE_NAMES or name.endswith(WRAPPER_FILE_SUFFIX)


def _isRealDir(path: Path) -> bool:
    """Directory that is not a symlink"""
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def _isRegularFile(path: Path) -> bool:
    """Regular file that is not a symlink"""
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


# Linux-only open flags, read through getattr so the module still imports and type-checks on every platform
_O_NOFOLLOW: int = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY: int = getattr(os, "O_DIRECTORY", 0)
_O_CLOEXEC: int = getattr(os, "O_CLOEXEC", 0)
_DIR_FLAGS = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
_COPY_CHUNK = 1024 * 1024


def _symlinkFree(path: Path) -> Path:
    """Absolute path of an entry with the symlinks of its parent resolved, the entry itself kept as is"""
    return Path(os.path.realpath(path.parent)) / path.name


def _openStrictDir(path: Path, create: bool = False) -> int:
    """Open a directory by walking an absolute path component by component, never following a symlink
    (ELOOP / ENOTDIR when a component is a symlink or not a directory). Missing components are created when
    create is True. Return a directory fd owned by the caller."""
    if sys.platform == "win32":
        raise OSError(errno.ENOTSUP, "Directory fds are not supported on Windows")
    if not path.is_absolute():
        raise ValueError(f"{path} is not an absolute path")
    fd = os.open("/", os.O_RDONLY | _O_DIRECTORY | _O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            try:
                next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o777, dir_fd=fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
    except BaseException:
        os.close(fd)
        raise
    return fd


def _lexistsAt(dir_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _setOwnerAt(dir_fd: int, name: str, uid: int, gid: int) -> None:
    """Best-effort lchown relative to a directory fd, ignored when not privileged"""
    if sys.platform == "win32":
        return
    try:
        os.chown(name, uid, gid, dir_fd=dir_fd, follow_symlinks=False)
    except PermissionError:
        pass


# Extended attribute errors skipped like shutil.copystat does: unsupported by a filesystem (ENOTSUP is
# EOPNOTSUPP on Linux), attribute gone, namespace not writable (e.g. trusted.* without CAP_SYS_ADMIN)
_XATTR_SKIPPED_ERRORS = (errno.ENOTSUP, errno.ENODATA, errno.EPERM, errno.EINVAL)


def _copyXattrs(src: Union[int, str], dst: Union[int, str]) -> None:
    """Copy the extended attributes (SELinux label, POSIX ACLs, file capabilities) of an fd to an fd, or of a
    path to a path without following its last component. Best effort: what a filesystem cannot hold is skipped."""
    if sys.platform != "linux":
        return
    # An fd cannot be combined with follow_symlinks=False, a path names the entry itself (a symlink included)
    follow = isinstance(src, int)
    try:
        names = os.listxattr(src, follow_symlinks=follow)
        for name in names:
            try:
                os.setxattr(dst, name, os.getxattr(src, name, follow_symlinks=follow), follow_symlinks=follow)
            except OSError as e:
                if e.errno not in _XATTR_SKIPPED_ERRORS:
                    raise
                logger.debug(f"Extended attribute {name} not copied: {e}")
    except OSError as e:
        if e.errno not in _XATTR_SKIPPED_ERRORS:
            raise
        logger.debug(f"Extended attributes not copied: {e}")


def _fdPath(dir_fd: int, name: str) -> str:
    """Path of an entry relative to a directory fd, for the calls without a dir_fd argument"""
    return f"/proc/self/fd/{dir_fd}/{name}"


def _copyEntryAt(src_dir_fd: int, src_name: str, dst_dir_fd: int, dst_name: str) -> None:
    """Copy an entry between two directory fds without following any symlink: symlinks are copied as links,
    special files are re-created, owners, extended attributes, modes and times are kept (owners only when
    privileged). Extended attributes are set after the owner: a chown drops the file capabilities."""
    if sys.platform == "win32":
        raise OSError(errno.ENOTSUP, "Directory fds are not supported on Windows")
    src_stat = os.stat(src_name, dir_fd=src_dir_fd, follow_symlinks=False)
    mode = src_stat.st_mode
    times = (src_stat.st_atime_ns, src_stat.st_mtime_ns)
    if stat.S_ISLNK(mode):
        os.symlink(os.readlink(src_name, dir_fd=src_dir_fd), dst_name, dir_fd=dst_dir_fd)
        _setOwnerAt(dst_dir_fd, dst_name, src_stat.st_uid, src_stat.st_gid)
        _copyXattrs(_fdPath(src_dir_fd, src_name), _fdPath(dst_dir_fd, dst_name))
    elif stat.S_ISDIR(mode):
        os.mkdir(dst_name, 0o700, dir_fd=dst_dir_fd)
        src_fd = os.open(src_name, _DIR_FLAGS, dir_fd=src_dir_fd)
        try:
            dst_fd = os.open(dst_name, _DIR_FLAGS, dir_fd=dst_dir_fd)
            try:
                for child in sorted(os.listdir(src_fd)):
                    _copyEntryAt(src_fd, child, dst_fd, child)
                _setOwnerAt(dst_dir_fd, dst_name, src_stat.st_uid, src_stat.st_gid)
                _copyXattrs(src_fd, dst_fd)
                os.fchmod(dst_fd, stat.S_IMODE(mode))
                os.utime(dst_fd, ns=times)
            finally:
                os.close(dst_fd)
        finally:
            os.close(src_fd)
    elif stat.S_ISREG(mode):
        src_fd = os.open(src_name, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=src_dir_fd)
        try:
            dst_fd = os.open(dst_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC, 0o600,
                             dir_fd=dst_dir_fd)
            try:
                while True:
                    chunk = os.read(src_fd, _COPY_CHUNK)
                    if not chunk:
                        break
                    view = memoryview(chunk)
                    while view:
                        view = view[os.write(dst_fd, view):]
                _setOwnerAt(dst_dir_fd, dst_name, src_stat.st_uid, src_stat.st_gid)
                _copyXattrs(src_fd, dst_fd)
                os.fchmod(dst_fd, stat.S_IMODE(mode))
                os.utime(dst_fd, ns=times)
            finally:
                os.close(dst_fd)
        finally:
            os.close(src_fd)
    else:
        # FIFO, socket or device node (e.g. a tmux socket written by a container)
        os.mknod(dst_name, mode, src_stat.st_rdev, dir_fd=dst_dir_fd)
        _setOwnerAt(dst_dir_fd, dst_name, src_stat.st_uid, src_stat.st_gid)
        _copyXattrs(_fdPath(src_dir_fd, src_name), _fdPath(dst_dir_fd, dst_name))


def _removeEntryAt(dir_fd: int, name: str, only_dirs: bool = False) -> None:
    """Remove an entry (a whole tree for a directory) relative to a directory fd, never following a symlink.
    With only_dirs, any file or symlink raises ENOTEMPTY before its directory is removed."""
    entry_stat = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    if not stat.S_ISDIR(entry_stat.st_mode):
        if only_dirs:
            raise OSError(errno.ENOTEMPTY, f"Refusing to remove {name}: not a directory")
        os.unlink(name, dir_fd=dir_fd)
        return
    child_fd = os.open(name, _DIR_FLAGS, dir_fd=dir_fd)
    try:
        for child in os.listdir(child_fd):
            if only_dirs and not stat.S_ISDIR(os.stat(child, dir_fd=child_fd, follow_symlinks=False).st_mode):
                raise OSError(errno.ENOTEMPTY, f"Refusing to remove {name}: it still holds {child}")
            _removeEntryAt(child_fd, child, only_dirs)
    finally:
        os.close(child_fd)
    os.rmdir(name, dir_fd=dir_fd)


def _sameRegularContent(first: Path, second: Path) -> bool:
    """Tell whether two paths are regular files with the same content, opened without following symlinks"""
    fds: List[int] = []
    try:
        for path in (first, second):
            parent_fd = _openStrictDir(path.parent)
            try:
                fds.append(os.open(path.name, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=parent_fd))
            finally:
                os.close(parent_fd)
        stats = [os.fstat(fd) for fd in fds]
        if not all(stat.S_ISREG(st.st_mode) for st in stats) or stats[0].st_size != stats[1].st_size:
            return False
        while True:
            chunks = [os.read(fd, _COPY_CHUNK) for fd in fds]
            if chunks[0] != chunks[1]:
                return False
            if not chunks[0]:
                return True
    except OSError:
        return False
    finally:
        for fd in fds:
            os.close(fd)


def _describe(path: Path) -> str:
    """Kind of an entry, for the messages listing what must be migrated by hand"""
    mode = os.lstat(path).st_mode
    if stat.S_ISLNK(mode):
        return f"symlink to {os.readlink(path)}"
    if stat.S_ISDIR(mode):
        return "directory"
    return "file" if stat.S_ISREG(mode) else "special file"


def _setOwner(path: Path, uid: int, gid: int) -> None:
    """Best-effort lchown, ignored when not privileged"""
    if sys.platform == "win32":
        return
    try:
        os.lchown(path, uid, gid)
    except PermissionError:
        pass


class ConfigDirMigration:

    @staticmethod
    def isLegacyRootDir(active: Path, root_home: Path, user_home: Path) -> bool:
        """Tell whether the active config dir is a real directory in root's home while the invoking
        user has another home (legacy location created by the old sudo path resolution)"""
        if not _isRealDir(active):
            return False
        try:
            root_real = os.path.realpath(root_home)
            return os.path.realpath(active.parent) == root_real and root_real != os.path.realpath(user_home)
        except OSError:
            return False

    @staticmethod
    def sessionLockAge(lock_file: Path) -> Optional[float]:
        """Age in seconds of a session refresh lock, None when there is no lock.
        The age comes from the timestamp SessionHandler writes in it, else (unreadable, invalid or in the
        future) from the file change time."""
        try:
            lock_stat = os.lstat(lock_file)
        except FileNotFoundError:
            return None
        now = time.time()
        created: Optional[float] = None
        if stat.S_ISREG(lock_stat.st_mode):
            try:
                with open(lock_file, "r") as lock:
                    created = float(lock.read(64).strip())
            except (OSError, ValueError):
                created = None
        if created is None or not 0 < created <= now:
            created = lock_stat.st_ctime
        return max(0.0, now - created)

    @staticmethod
    def isEmptyTree(path: Path) -> bool:
        """Tell whether a directory tree holds no file and no symlink (only empty directories)"""
        if not _isRealDir(path):
            return False
        errors: List[OSError] = []
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False, onerror=errors.append):
            if filenames:
                return False
            for name in dirnames:
                if os.path.islink(os.path.join(dirpath, name)):
                    return False
        # An unreadable sub-directory could hold anything
        return len(errors) == 0

    @staticmethod
    def __checkDirs(root_dir: Path, user_dir: Path) -> None:
        if not _isRealDir(root_dir):
            raise ValueError(f"{root_dir} is not a real directory")
        if os.path.lexists(user_dir) and not _isRealDir(user_dir):
            raise ValueError(f"{user_dir} is a symlink or not a directory")

    @classmethod
    def __classify(cls, root_dir: Path, user_dir: Path, relative: Path, collision_is_conflict: bool,
                   problems: List[str]) -> List[MigrationStep]:
        """Classify a root entry. A root symlink or special file is added to problems, to be migrated by hand (a
        moved relative link changes target). A name present on both sides is only classified when both are regular
        files or both real directories: any other pair (a file facing a directory included) is added to problems."""
        root_entry = root_dir / relative
        user_entry = user_dir / relative
        if _RETIRED_NAME.search(relative.name):
            problems.append(f"{root_entry}: left by an interrupted migration, delete it once "
                            f"{user_dir / relative.parent / _RETIRED_NAME.sub('', relative.name)} is checked complete")
            return []
        if not (_isRegularFile(root_entry) or _isRealDir(root_entry)):
            problems.append(f"{root_entry} ({_describe(root_entry)}): only files and directories are migrated")
            return []
        if not os.path.lexists(user_entry):
            return [MigrationStep(MigrationAction.MOVE, relative, "absent on the user side")]
        if _isRegularFile(root_entry) and _isRegularFile(user_entry):
            if filecmp.cmp(root_entry, user_entry, shallow=False):
                return [MigrationStep(MigrationAction.DISCARD_ROOT, relative, "identical on both sides")]
            # Only the wrapper's own state is replaced without a question, any other file is the user's decision
            if not collision_is_conflict and isWrapperFileName(relative.name):
                return [MigrationStep(MigrationAction.REPLACE, relative, "wrapper file, the active copy wins")]
            return [MigrationStep(MigrationAction.CONFLICT, relative, "different on both sides")]
        if _isRealDir(root_entry) and _isRealDir(user_entry):
            if cls.isEmptyTree(root_entry):
                return [MigrationStep(MigrationAction.DISCARD_ROOT, relative, "no file on the root side")]
            if cls.isEmptyTree(user_entry):
                return [MigrationStep(MigrationAction.MOVE, relative, "no file on the user side")]
            return [MigrationStep(MigrationAction.CONFLICT, relative, "data on both sides")]
        problems.append(f"{root_entry} ({_describe(root_entry)}) and {user_entry} ({_describe(user_entry)}): "
                        f"only two files or two directories can be merged")
        return []

    @classmethod
    def __classifyKeyedDir(cls, root_dir: Path, user_dir: Path, relative: Path,
                           problems: List[str]) -> List[MigrationStep]:
        """Classify a container-keyed dir child by child, even when one side holds no file: an empty
        per-container dir is the bind-mount source of a never-used container. Keeping one side wholesale would
        remove the bind-mount sources of the other side's containers, so only real directories are merged: a
        symlink or a non-directory on either side is added to problems, to be migrated by hand. The root
        per-container entries are always checked, even when the whole dir moves as is."""
        root_entry = root_dir / relative
        user_entry = user_dir / relative
        odd = [entry for entry in (root_entry, user_entry) if os.path.lexists(entry) and not _isRealDir(entry)]
        for entry in odd:
            problems.append(f"{entry} ({_describe(entry)}): a real directory is expected for {relative}")
        if odd:
            return []
        steps: List[MigrationStep] = []
        for child in sorted(os.listdir(root_entry)):
            steps += cls.__classify(root_dir, user_dir, relative / child, True, problems)
        if not os.path.lexists(user_entry):
            return [MigrationStep(MigrationAction.MOVE, relative, "absent on the user side")]
        return steps

    @classmethod
    def planMigration(cls, root_dir: Path, user_dir: Path) -> MigrationPlan:
        """Compute the steps moving root_dir content into user_dir. Nothing is changed on disk.
        Raise ValueError when root_dir is not a real directory, user_dir is a symlink / not a directory, or some
        entries cannot be migrated automatically, a fresh migration included (every one of them is listed, to be
        migrated by hand)."""
        cls.__checkDirs(root_dir, user_dir)
        dir_steps: List[MigrationStep] = []
        file_steps: List[MigrationStep] = []
        problems: List[str] = []
        for name in sorted(os.listdir(root_dir)):
            if name in VOLATILE_ROOT_FILES:
                # Removed by the datastore close / the lock release, must never be moved
                continue
            relative = Path(name)
            if name in CONTAINER_KEYED_DIRS:
                steps = cls.__classifyKeyedDir(root_dir, user_dir, relative, problems)
            else:
                steps = cls.__classify(root_dir, user_dir, relative, False, problems)
            if _isRealDir(root_dir / name):
                dir_steps += steps
            else:
                file_steps += steps
        if problems:
            raise ValueError("these elements cannot be migrated automatically, migrate them manually:\n" +
                             "\n".join(f"  - {problem}" for problem in problems))
        if not os.path.lexists(user_dir):
            return MigrationPlan(root_dir, user_dir, fresh=True)
        backup_steps: List[MigrationStep] = []
        if _isRegularFile(root_dir / DATASTORE_FILE):
            # A foreign WAL / SHM / journal must never be paired with the migrated database
            for name in DATASTORE_SIDE_FILES:
                if os.path.lexists(user_dir / name):
                    backup_steps.append(MigrationStep(MigrationAction.BACKUP_USER, Path(name),
                                                      "stale database side file"))
        # The license database moves last: until then the root dir still holds a working license
        file_steps.sort(key=lambda step: step.relative.name == DATASTORE_FILE)
        # Directories first, top-level wrapper files last (crash ordering)
        return MigrationPlan(root_dir, user_dir, fresh=False, steps=dir_steps + backup_steps + file_steps)

    @classmethod
    def applyMigration(cls, plan: MigrationPlan, decisions: Dict[Path, MigrationSide], backup_dir: Path) -> Optional[Path]:
        """Apply a migration plan, then replace root_dir with a symlink to user_dir.
        Non-empty discarded data is moved to backup_dir/{root,user}/<relative path>, never deleted.
        Return backup_dir when something was backed up, else None.
        Raise MigrationAborted (nothing changed) when a conflict has no decision, the dirs changed type
        or another process still uses the license database / session of root_dir."""
        root_dir, user_dir = plan.root_dir, plan.user_dir
        try:
            cls.__checkDirs(root_dir, user_dir)
        except ValueError as e:
            raise MigrationAborted(str(e)) from e
        if plan.fresh and os.path.lexists(user_dir):
            raise MigrationAborted(f"{user_dir} has been created since the migration was planned")
        missing = [str(step.relative) for step in plan.conflicts if step.relative not in decisions]
        if missing:
            raise MigrationAborted(f"No decision for the conflicts: {', '.join(missing)}")
        in_use = [name for name in VOLATILE_ROOT_FILES if os.path.lexists(root_dir / name)]
        if in_use:
            # The database must be closed by its last user before it moves, or the WAL content would be lost
            raise MigrationAborted(f"{root_dir} still holds {', '.join(in_use)}: another exegol process "
                                   f"(or Exegol Studio) is using the license, close it first")

        # Every move goes through symlink-free paths, walked without following symlinks
        real_plan = MigrationPlan(_symlinkFree(root_dir), _symlinkFree(user_dir), plan.fresh, plan.steps)
        real_backup_dir = _symlinkFree(backup_dir)
        if plan.fresh:
            # Across filesystems, the real root_dir stays complete (license included) until the copy fully
            # succeeded and it is taken out of service in one rename: a missing root_dir already resolves to
            # user_dir, the symlink follows and the old tree is removed last (a failure there leaves garbage only)
            retired = cls.__moveEntry(real_plan.root_dir, real_plan.user_dir, keep_retired=True)
            os.symlink(user_dir, root_dir)
            if retired is not None:
                try:
                    parent_fd = _openStrictDir(retired.parent)
                    try:
                        _removeEntryAt(parent_fd, retired.name)
                    finally:
                        os.close(parent_fd)
                except OSError as e:
                    logger.warning(f"Unable to remove the old copy {retired} ({e}), {user_dir} is complete: "
                                   f"delete it manually.")
            return None

        # The license database moves last, once nothing can stop the cleanup: until then root_dir stays
        # a working configuration folder and a re-run resumes the merge
        datastore_steps = [step for step in plan.steps if step.relative == Path(DATASTORE_FILE)]
        backup_used = False
        for step in plan.steps:
            if step not in datastore_steps:
                backup_used |= cls.__applyStep(real_plan, step, decisions, real_backup_dir, [])
        leftovers = cls.__listLeftovers(root_dir, allowed={DATASTORE_FILE} if datastore_steps else set())
        if leftovers:
            raise OSError(errno.ENOTEMPTY, f"Refusing to remove {root_dir}: it still holds {', '.join(leftovers)} "
                                           f"(created since the migration was planned)")
        # Moves of the license database, undone when the swap fails while root_dir is still a real directory
        moves: List[Tuple[Path, Path]] = []
        dropped: Optional[Tuple[Path, Path, os.stat_result]] = None
        try:
            for step in datastore_steps:
                if step.action == MigrationAction.DISCARD_ROOT:
                    dropped = (real_plan.root_dir / step.relative, real_plan.user_dir / step.relative,
                               os.lstat(real_plan.root_dir / step.relative))
                backup_used |= cls.__applyStep(real_plan, step, decisions, real_backup_dir, moves)
            # Only empty directories can remain: any leftover file raises, nothing non-empty is deleted
            cls.__removeEmptyTree(real_plan.root_dir)
            os.symlink(user_dir, root_dir)
        except BaseException:
            # A Ctrl-C too: the still active root dir must never be left without its license
            if _isRealDir(root_dir):
                cls.__restoreDatastore(moves, dropped)
            raise
        return backup_dir if backup_used else None

    @classmethod
    def __applyStep(cls, plan: MigrationPlan, step: MigrationStep, decisions: Dict[Path, MigrationSide],
                    backup_dir: Path, moves: List[Tuple[Path, Path]]) -> bool:
        """Apply one plan step, recording each (source, destination) move. Return True when backup_dir was used."""
        root_entry = plan.root_dir / step.relative
        user_entry = plan.user_dir / step.relative

        def move(src: Path, dst: Path) -> None:
            try:
                cls.__moveEntry(src, dst)
            finally:
                # Across filesystems, an interruption can land once dst is complete and src set aside: still a move
                if os.path.lexists(dst) and not os.path.lexists(src):
                    moves.append((src, dst))

        if step.action == MigrationAction.MOVE:
            if os.path.lexists(user_entry):
                cls.__removeEmptyTree(user_entry)
            move(root_entry, user_entry)
        elif step.action == MigrationAction.REPLACE or \
                (step.action == MigrationAction.CONFLICT and decisions[step.relative] == MigrationSide.ROOT):
            move(user_entry, backup_dir / MigrationSide.USER.value / step.relative)
            move(root_entry, user_entry)
            return True
        elif step.action == MigrationAction.CONFLICT:
            move(root_entry, backup_dir / MigrationSide.ROOT.value / step.relative)
            return True
        elif step.action == MigrationAction.BACKUP_USER:
            move(user_entry, backup_dir / MigrationSide.USER.value / step.relative)
            return True
        elif step.action == MigrationAction.DISCARD_ROOT:
            if not _isRealDir(root_entry):
                if not _sameRegularContent(root_entry, user_entry):
                    raise ValueError(f"{root_entry} changed since the migration was planned")
                logger.debug(f"Dropping {root_entry}: identical to {user_entry}")
                os.unlink(root_entry)
            # A file-free tree is removed by the final cleanup
        return False

    @classmethod
    def __restoreDatastore(cls, moves: List[Tuple[Path, Path]], dropped: Optional[Tuple[Path, Path, os.stat_result]]) -> None:
        """Put the license database back in the still active root dir after a failed swap"""
        try:
            for src, dst in reversed(moves):
                cls.__moveEntry(dst, src)
            if dropped is not None and not os.path.lexists(dropped[0]):
                root_entry, user_entry, root_stat = dropped
                # The root copy was byte-identical to the user one
                cls.__copyEntry(user_entry, root_entry)
                _setOwner(root_entry, root_stat.st_uid, root_stat.st_gid)
        except OSError as e:
            logger.error(f"Unable to restore the license database in the root configuration folder: {e}")

    @staticmethod
    def __listLeftovers(path: Path, allowed: Set[str]) -> List[str]:
        """List the files and symlinks of a tree (relative paths), the top-level allowed names excepted.
        An unreadable directory is listed as a leftover: it could hold anything."""
        leftovers: List[str] = []

        def on_error(error: OSError) -> None:
            leftovers.append(str(error.filename))

        for dirpath, dirnames, filenames in os.walk(path, followlinks=False, onerror=on_error):
            for name in filenames + [name for name in dirnames if os.path.islink(os.path.join(dirpath, name))]:
                relative = os.path.relpath(os.path.join(dirpath, name), path)
                if relative not in allowed:
                    leftovers.append(relative)
        return sorted(leftovers)

    @staticmethod
    def __removeEmptyTree(path: Path) -> None:
        """Remove a tree made only of directories, bottom-up. Raise OSError on any file or symlink
        (nothing is removed from a directory holding one)."""
        parent_fd = _openStrictDir(path.parent)
        try:
            if not stat.S_ISDIR(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False).st_mode):
                raise OSError(errno.ENOTDIR, f"Refusing to remove {path}: not a directory")
            try:
                _removeEntryAt(parent_fd, path.name, only_dirs=True)
            except OSError as e:
                if e.errno == errno.ENOTEMPTY:
                    raise OSError(errno.ENOTEMPTY, f"Refusing to remove {path}: {e.strerror}") from e
                raise
        finally:
            os.close(parent_fd)

    @staticmethod
    def __copyEntry(src: Path, dst: Path) -> None:
        """Copy an entry to a new path, both reached without following symlinks"""
        src_parent = _openStrictDir(src.parent)
        try:
            dst_parent = _openStrictDir(dst.parent, create=True)
            try:
                _copyEntryAt(src_parent, src.name, dst_parent, dst.name)
            finally:
                os.close(dst_parent)
        finally:
            os.close(src_parent)

    @staticmethod
    def __moveEntry(src: Path, dst: Path, keep_retired: bool = False) -> Optional[Path]:
        """Move a file, directory or symlink (never followed), across filesystems when needed.
        Both parents are walked without following symlinks: a component swapped for a symlink raises.
        Across filesystems, the source is renamed aside in its own directory once the copy fully succeeded (one
        atomic step), then removed: an interruption never leaves a partial source under its own name, only a
        RETIRED_MARKER entry the plan refuses. With keep_retired, that path is returned for the caller to remove."""
        src_parent = _openStrictDir(src.parent)
        try:
            dst_parent = _openStrictDir(dst.parent, create=True)
            try:
                if _lexistsAt(dst_parent, dst.name):
                    raise FileExistsError(errno.EEXIST, f"Refusing to overwrite {dst}")
                logger.debug(f"Moving {src} to {dst}")
                try:
                    os.rename(src.name, dst.name, src_dir_fd=src_parent, dst_dir_fd=dst_parent)
                    return None
                except OSError as e:
                    if e.errno != errno.EXDEV:
                        raise
                # Cross-device: copy (symlinks kept as links, owners restored), then retire and remove the source
                retired = f"{src.name}{RETIRED_MARKER}{secrets.token_hex(4)}"
                try:
                    _copyEntryAt(src_parent, src.name, dst_parent, dst.name)
                except BaseException:
                    # Only drop our own copy, the source is complete and in place
                    if _lexistsAt(dst_parent, dst.name):
                        _removeEntryAt(dst_parent, dst.name)
                    raise
                try:
                    os.rename(src.name, retired, src_dir_fd=src_parent, dst_dir_fd=src_parent)
                except OSError:
                    # The rename did not happen: the source is still complete under its own name. Any other exception
                    # (Ctrl-C) may land once the rename is done: the complete copy is then the only one, it is kept
                    _removeEntryAt(dst_parent, dst.name)
                    raise
                if keep_retired:
                    return src.parent / retired
                _removeEntryAt(src_parent, retired)
                return None
            finally:
                os.close(dst_parent)
        finally:
            os.close(src_parent)

    @staticmethod
    def handBackOwnership(directory: Path, uid: int, gid: int, recursive_children: Tuple[str, ...] = (),
                          recursive: bool = False) -> None:
        """Give a directory and its top-level entries to uid:gid, plus the whole tree of the recursive_children
        directories (of every directory with recursive). Best effort, through no-follow directory fds:
        a symlink is re-owned itself, never followed, and a regular file with several links is skipped."""
        if sys.platform == "win32":
            return
        try:
            dir_fd = _openStrictDir(_symlinkFree(directory))
        except OSError as e:
            logger.debug(f"Skipping the ownership hand-back of {directory}: {e}")
            return

        def hand_back(fd: int, label: Path, recurse_all: bool, recurse_names: Tuple[str, ...]) -> None:
            try:
                os.fchown(fd, uid, gid)
                names = os.listdir(fd)
            except OSError as e:
                logger.debug(f"Could not hand {label} back: {e}")
                return
            for name in names:
                try:
                    entry_stat = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(entry_stat.st_mode) and (recurse_all or name in recurse_names):
                        child_fd = os.open(name, _DIR_FLAGS, dir_fd=fd)
                        try:
                            hand_back(child_fd, label / name, True, ())
                        finally:
                            os.close(child_fd)
                    elif not (stat.S_ISREG(entry_stat.st_mode) and entry_stat.st_nlink > 1):
                        os.chown(name, uid, gid, dir_fd=fd, follow_symlinks=False)
                except OSError as e:
                    logger.debug(f"Could not hand {label / name} back: {e}")

        try:
            hand_back(dir_fd, directory, recursive, recursive_children)
        finally:
            os.close(dir_fd)

    @staticmethod
    def rewriteConfigPaths(config_file: Path, old_dir: Path, new_dir: Path, dry_run: bool = False) -> bool:
        """Replace the old_dir prefix of the absolute paths stored in config_file by new_dir.
        Only whole path prefixes match (not '/x/old_dir' nor 'old_dir-other'). Return True when the file changed
        (would change, with dry_run: nothing is written).
        A config_file that is a symlink or not a regular file is left untouched."""
        if sys.platform == "win32":
            return False
        try:
            parent_fd = _openStrictDir(_symlinkFree(config_file).parent)
        except FileNotFoundError:
            return False
        try:
            try:
                file_fd = os.open(config_file.name, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=parent_fd)
            except OSError as e:
                if e.errno in (errno.ENOENT, errno.ELOOP):
                    return False
                raise
            with os.fdopen(file_fd, "rb") as current:
                file_stat = os.fstat(current.fileno())
                if not stat.S_ISREG(file_stat.st_mode):
                    return False
                content = current.read().decode("utf-8")
            pattern = re.compile(r"(?<![\w./~-])" + re.escape(str(old_dir)) + r"(?=[/'\"\s]|$)", re.MULTILINE)
            new_content = pattern.sub(lambda _: str(new_dir), content)
            if new_content == content or dry_run:
                return new_content != content
            tmp_name = f"{scratch_prefix(config_file.name)}{secrets.token_hex(8)}{SCRATCH_SUFFIX}"
            tmp_fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC, 0o600,
                             dir_fd=parent_fd)
            try:
                with os.fdopen(tmp_fd, "wb") as tmp_file:
                    tmp_file.write(new_content.encode("utf-8"))
                    os.fchmod(tmp_file.fileno(), stat.S_IMODE(file_stat.st_mode))
                    try:
                        os.fchown(tmp_file.fileno(), file_stat.st_uid, file_stat.st_gid)
                    except PermissionError:
                        pass
                os.replace(tmp_name, config_file.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except BaseException:
                if _lexistsAt(parent_fd, tmp_name):
                    os.unlink(tmp_name, dir_fd=parent_fd)
                raise
        finally:
            os.close(parent_fd)
        logger.debug(f"Rewrote {old_dir} paths to {new_dir} in {config_file}")
        return True
