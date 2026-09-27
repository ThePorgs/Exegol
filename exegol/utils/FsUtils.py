import asyncio
import logging
import os
import re
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import List, Optional, Tuple

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
    user_gid_raw = os.getenv("SUDO_GID")
    # A non-numeric SUDO_UID/SUDO_GID (env pollution, an exotic sudo wrapper) raises ValueError
    # through chown_to_user()/mkdir(), which only catch SystemError, aborting a successful clone.
    try:
        user_uid = int(user_uid_raw) if user_uid_raw is not None else os.getuid()
        user_gid = int(user_gid_raw) if user_gid_raw is not None else os.getgid()
    except ValueError:
        logger.debug(f"Invalid SUDO_UID/SUDO_GID ({user_uid_raw!r}/{user_gid_raw!r}), "
                     f"falling back to the current process ids.")
        user_uid, user_gid = os.getuid(), os.getgid()
    return user_uid, user_gid


def mkdir(path: Path) -> None:
    """Function to recursively create a directory and setting the right user and group id to allow host user access."""
    if not path.parent.is_dir():
        mkdir(path.parent)
    try:
        path.mkdir(parents=False, exist_ok=False)
        if sys.platform == "linux" and os.getuid() == 0:
            user_uid, user_gid = get_user_id()
            os.chown(path, user_uid, user_gid)
    except FileExistsError:
        # The directory already exist, this setup can be skipped
        pass
    except (FileNotFoundError, PermissionError):
        logger.error(f"Unable to create directory {path}. Please check your file permissions.")


# Every scratch file this project creates carries this marker in its name, and the sweep below
# keys on the marker rather than on the shape of the random part `tempfile.mkstemp` appends.
# That shape is a CPython private detail that has moved before (6 to 8 characters in 3.6), and
# a guard pinned to it would fail in the worst way: the regex stops matching, the sweep becomes
# a silent no-op, and the leak returns at a site reached on every `exegol` invocation. The
# marker is ours, so it cannot drift under us, and it is what keeps housekeeping from matching
# a file an operator wrote themselves -- `config.yml.backup.tmp` sits in the same directory and
# matches the same glob, but carries no marker.
SCRATCH_MARKER = "exegol-scratch"
SCRATCH_SUFFIX = ".tmp"

# Belt and braces behind the marker: the random part must still LOOK random. Kept
# deliberately wider than any name shape CPython has ever produced, because it is
# no longer the thing standing between "housekeeping" and "delete a file the
# operator named" -- the marker is.
_SCRATCH_RANDOM_RE = re.compile(r"^[A-Za-z0-9_]{4,32}$")


def scratch_prefix(target_name: str) -> str:
    """The ``prefix=`` every ``mkstemp`` scratch beside ``target_name`` is created with.

    Both writers (``DataFileUtils._create_config_file`` and
    ``ContainerConfig.__writeSentinelConfig``) must build their scratch through this helper:
    it is the only thing that makes the residue recognisable to ``sweep_stale_scratch`` after
    the process that created it is gone.
    """
    return f"{target_name}.{SCRATCH_MARKER}."

# A write of a config file is a few kilobytes and completes in milliseconds. A
# scratch older than this cannot be an in-flight write by a concurrent `exegol`;
# it is the residue of one that was killed. Erring long is free -- a leftover
# simply survives one more run -- while erring short would let one invocation
# unlink another's scratch mid-write and turn its `replace` into a
# FileNotFoundError, which is the failure the unique naming exists to prevent.
SCRATCH_STALE_AFTER_SECONDS = 300.0


def sweep_stale_scratch(directory: Path, target_name: str) -> None:
    """Remove abandoned ``mkstemp`` scratch files left beside ``target_name``.

    The write-then-rename shape used by ``DataFileUtils._create_config_file`` and
    ``ContainerConfig.__writeSentinelConfig`` cleans up after itself with an
    ``except: unlink``, which covers exceptions only. A SIGKILL, an OOM kill, a power loss or
    a container teardown between ``mkstemp`` and ``replace`` leaves the scratch behind, and
    nothing ever removed it -- the name is random by design, so there was not even a fixed
    path a later run could clean. The ``DataFileUtils`` site is reached on essentially every
    ``exegol`` invocation, so every interrupted run could leave one more file in the
    operator's config directory, forever.

    Swept at the top of the writing method, the only moment a later run is known to be about
    to touch that name anyway. Two guards keep it from being destructive:

    * the name must carry ``SCRATCH_MARKER``, which only ``scratch_prefix()`` puts there, so
      a file the operator named themselves is never a candidate however well it matches the
      glob (see that constant for why the marker and not ``mkstemp``'s random part);
    * it must be older than ``SCRATCH_STALE_AFTER_SECONDS``, so a concurrent invocation's
      in-flight scratch is never unlinked out from under its own ``replace``.

    Best effort throughout: this is housekeeping, and it must never be the reason a config
    write fails. Every filesystem error is swallowed.
    """
    try:
        cutoff = time.time() - SCRATCH_STALE_AFTER_SECONDS
        prefix = scratch_prefix(target_name)
        for candidate in directory.glob(f"{prefix}*{SCRATCH_SUFFIX}"):
            middle = candidate.name[len(prefix):-len(SCRATCH_SUFFIX)]
            if not _SCRATCH_RANDOM_RE.match(middle):
                continue
            try:
                if candidate.stat().st_mtime > cutoff:
                    continue
                candidate.unlink()
                logger.debug(f"Removed an abandoned scratch file: {candidate}")
            except OSError:
                # Raced with another sweeper, or not ours to remove. Either way
                # the next run tries again.
                continue
    except OSError:
        # An unreadable directory is the writer's problem to report, not this
        # helper's; it is about to try the real write and will say so properly.
        pass


def chown_to_user(path: Path, recursive: bool = True) -> None:
    """On Linux running as root (typically via sudo), reassign ownership of ``path`` (and,
    when ``recursive``, everything under it) to the original invoking user.

    Files created by a root subprocess — e.g. the contents of a ``git clone`` — would
    otherwise stay root-owned and become unmanageable for the non-sudo user. No-op off
    Linux or when not running as root (a normal user already owns what they create)."""
    if sys.platform != "linux" or os.getuid() != 0:
        return
    try:
        user_uid, user_gid = get_user_id()
    except SystemError:
        return
    # SUDO_UID unset (real root login, not sudo) -> nothing to hand back.
    if user_uid == 0 and user_gid == 0:
        return
    targets = [path]
    if recursive and path.is_dir():
        targets += list(path.rglob("*"))
    for target in targets:
        try:
            # lchown so a symlink inside the tree is retargeted, never followed.
            os.lchown(target, user_uid, user_gid)
        except OSError as e:
            logger.debug(f"Could not chown {target} to {user_uid}:{user_gid}: {e}")

# Open flags the hardened removal below relies on, read through getattr because they are
# Linux-only: this module must still import and type-check under mypy's --platform darwin /
# --platform win32 runs. The 0 fallback is never used — _assert_fd_removal_supported() refuses
# the hardened path when any of them is missing.
_O_PATH: int = getattr(os, "O_PATH", 0)
_O_NOFOLLOW: int = getattr(os, "O_NOFOLLOW", 0)
_O_CLOEXEC: int = getattr(os, "O_CLOEXEC", 0)
_O_DIRECTORY: int = getattr(os, "O_DIRECTORY", 0)

# The genuine os functions, pinned once. os.supports_dir_fd / os.supports_fd hold function
# OBJECTS, so membership is an identity test: resolving os.open through the module at check time
# would report "unsupported" the moment anything wraps it (a tracing tool, a test delegate) and
# refuse the removal on a perfectly capable host. Only the identities are pinned — the capability
# SETS are still read on every call, which is what makes the gate below fail-closed and testable.
_DIR_FD_FUNCTIONS = (os.open, os.unlink, os.rmdir)
_FD_FUNCTIONS = (os.listdir,)

# Hard ceiling on how deep the removal walk will descend. The Sentinel instance directory is the
# host side of a bind mount a container writes to as root, so the CONTAINER picks the depth of the
# tree found there. 128 is far beyond any layout the agent produces — instance/artifacts/<hash>/
# bottoms out around four levels — while keeping the refusal well clear of the descriptor limit.
_MAX_REMOVAL_DEPTH = 128


async def secure_remove(file_path: Path, passes: int = 3) -> None:
    """Overwrite a regular file with random data and remove it.
    If file_path is a directory, recursively remove its content.
    Attention: does NOT guarantee physical secure erase on SSD / COW / journaled FS.

    The only caller is ExegolContainer.__removeVolume, pointing this at a container's Sentinel
    instance directory — the host side of a bind mount the container writes to as root — and
    remove() calls it before stop(), so the container can mutate every entry name, type and
    symlink target while the shred runs. Classifying an entry then acting on it through a second
    path lookup is unsafe at any ordering: it can become a symlink out of the tree in between.
    Each entry is instead classified from a descriptor already open on it, and every later
    operation goes through that descriptor or an open parent directory descriptor, so a name is
    never re-resolved from the filesystem root."""
    # Platform gate, deliberately the first statement. The hardened path needs os.O_PATH,
    # /proc/self/fd and the dir_fd / fd variants of the os functions, all Linux-only, while the
    # instance directory is a real host bind mount on macOS and Windows too — failing closed
    # there would delete a working feature rather than protect anyone. Those hosts keep the
    # path-based algorithm below and, with it, the racing-rename risk it cannot close.
    # The comparison also keeps mypy green across the CI compatibility matrix: sys.platform is
    # narrowed statically, so under --platform win32 / --platform darwin everything after this
    # early return is unreachable and is not type-checked.
    if sys.platform != "linux":
        await _secure_remove_portable(file_path, passes)
        return

    # Evaluated on every call, never cached: a missing capability must abort the removal.
    _assert_fd_removal_supported()

    # The root is opened by path, unlike its children, on an assumption enforced nowhere: that
    # the path is operator-supplied with its parent outside the bind mount, so no container can
    # swap a component of it. That holds for a container being created, where ContainerConfig
    # builds it under UserConfig().sentinel_path; it is unverified for an existing one — the only
    # case `exegol remove` reaches — because getSentinelPath() returns whatever host path the
    # Docker mount table reports, unvalidated, so an attacker-chosen bind mount source aims this
    # function wherever it likes. Constraining the root belongs in ContainerConfig.__parseMounts,
    # not here; until then the EXDEV argument in _remove_child rests on the same premise.

    # The parent is deliberately NOT opened: the instance directory is created root:sentinel_gid
    # mode 0750, and requiring read access to its parent would add a failure mode for no gain.
    root_fd = os.open(file_path, _O_PATH | _O_NOFOLLOW | _O_CLOEXEC)
    try:
        root_stat = os.fstat(root_fd)
        mode = root_stat.st_mode
        if stat.S_ISLNK(mode):
            os.unlink(file_path)
            return
        if stat.S_ISDIR(mode):
            _purge_directory(root_fd, passes)
            os.rmdir(file_path)
            return
        if not stat.S_ISREG(mode):
            raise NotImplementedError(f"Can only securely remove regular files and directories: {file_path}")
        if root_stat.st_size > 0:
            _shred_regular(root_fd, root_stat.st_size, passes)
        os.unlink(file_path)
    finally:
        os.close(root_fd)


def _assert_fd_removal_supported() -> None:
    """Refuse the removal — loudly — when the descriptor-based primitives are unavailable.

    The path-based algorithm is NEVER used as a silent fallback on Linux: downgrading would
    quietly reopen exactly the window this implementation exists to close. NotImplementedError
    is the right type because __removeVolume already handles it (report and continue), and
    because nothing has been touched on disk when it is raised.

    Read on every call rather than resolved once at import: the fail-closed behaviour is pinned
    by a test that monkeypatches os.supports_dir_fd.
    """
    missing = []
    for flag in ("O_PATH", "O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY"):
        if not hasattr(os, flag):
            missing.append(f"os.{flag}")
    for dir_fd_func in _DIR_FD_FUNCTIONS:
        if dir_fd_func not in os.supports_dir_fd:
            missing.append(f"dir_fd support for os.{dir_fd_func.__name__}()")
    # A SEPARATE binding, deliberately: os.listdir is an overloaded function, and rebinding the
    # loop variable of the previous loop to it is an incompatible assignment that fails
    # `mypy ./exegol/` — the exact command the CI code-analysis step and the pre-push hook run.
    for fd_func in _FD_FUNCTIONS:
        if fd_func not in os.supports_fd:
            missing.append(f"file-descriptor support for os.{fd_func.__name__}()")
    if not os.path.isdir("/proc/self/fd"):
        missing.append("/proc/self/fd")
    if missing:
        raise NotImplementedError(f"Secure removal refused (not downgraded to the unsafe path-based algorithm): "
                                  f"this host is missing {', '.join(missing)}.")


def _open_readable_dir(path_fd: int) -> int:
    """Reopen an O_PATH descriptor as a readable directory descriptor, without naming anything.

    /proc/self/fd/N is a kernel magic link: opening it resolves to the inode N already refers to
    rather than re-walking a path from the filesystem root, so a rename landing in between cannot
    redirect it. Every directory descriptor the walk below works from is obtained this way, which
    is what keeps the traversal inside the tree it started in.
    """
    return os.open(f"/proc/self/fd/{path_fd}", os.O_RDONLY | _O_DIRECTORY | _O_CLOEXEC)


@dataclass
class _PendingDir:
    """A directory the removal walk has descended into and has not finished draining.

    ``dir_fd`` is a readable descriptor on it (see _open_readable_dir). ``name`` and
    ``parent_dir_fd`` are how it gets removed once drained; both are None for the removal root,
    which secure_remove() rmdirs itself. ``rel`` is its path relative to the removal root, carried
    only so errors can name where in the tree they happened. ``pending`` is None until the
    directory is listed, which happens the first time the walk visits the frame.
    """
    dir_fd: int
    rel: str
    name: Optional[str]
    parent_dir_fd: Optional[int]
    pending: Optional[List[str]] = None


def _purge_directory(path_fd: int, passes: int) -> None:
    """Empty the directory referred to by ``path_fd``, leaving the directory itself in place.

    The walk is ITERATIVE, over an explicit stack of open directory descriptors: a container
    picks the depth of the tree in its own bind mount, and a recursive walk dies with
    RecursionError — neither OSError nor NotImplementedError, so it escapes BOTH of
    __removeVolume's handlers and aborts remove() before the container is stopped and its
    networks released. On a descriptor stack, exhaustion surfaces as EMFILE (an OSError the
    caller handles) and _MAX_REMOVAL_DEPTH raises ahead of it, one descriptor per level.

    ``path_fd`` is O_PATH and cannot be enumerated, so it is reopened through /proc/self/fd,
    which resolves to the inode it already pins instead of re-walking the name — the listing is
    provably of the directory that was classified."""
    stack: List[_PendingDir] = [_PendingDir(dir_fd=_open_readable_dir(path_fd), rel="",
                                            name=None, parent_dir_fd=None)]
    try:
        while stack:
            frame = stack[-1]
            if frame.pending is None:
                # Enumerate once, then work from the names: os.unlink/os.rmdir with dir_fd=
                # neither follow a final-component symlink nor open anything, so a name that
                # turns into a symlink after this listing still cannot reach outside the
                # directory.
                frame.pending = os.listdir(frame.dir_fd)
            if not frame.pending:
                # Drained. Popped before its descriptor is closed so the unwind handler below can
                # never double-close it, and rmdir'd through its parent's still-open descriptor —
                # a parent is only ever popped after all of its children.
                stack.pop()
                os.close(frame.dir_fd)
                if frame.name is not None and frame.parent_dir_fd is not None:
                    os.rmdir(frame.name, dir_fd=frame.parent_dir_fd)
                continue
            name = frame.pending.pop()
            child_rel = frame.rel + name
            child_dir_fd = _remove_child(frame.dir_fd, name, passes, child_rel)
            if child_dir_fd is None:
                continue
            # A directory: descend into it. Pushed before the depth check so the unwind handler
            # owns the descriptor whichever of the two raises.
            stack.append(_PendingDir(dir_fd=child_dir_fd, rel=child_rel + os.sep,
                                     name=name, parent_dir_fd=frame.dir_fd))
            if len(stack) > _MAX_REMOVAL_DEPTH:
                raise NotImplementedError(f"Refusing to descend more than {_MAX_REMOVAL_DEPTH} levels "
                                          f"while securely removing: {child_rel}")
    finally:
        # Any error unwinds with the whole ancestor chain still open; close it here rather than
        # leaking one descriptor per level. Nothing is removed on this path: a partially drained
        # directory is left on disk for the operator, which is what __removeVolume reports.
        while stack:
            frame = stack.pop()
            try:
                os.close(frame.dir_fd)
            except OSError:
                pass


def _remove_child(dir_fd: int, name: str, passes: int, rel: str) -> Optional[int]:
    """Deal with one entry, identified by its bare name relative to the open directory ``dir_fd``.

    Returns None once the entry is gone. A DIRECTORY is not removed here — it may still hold
    content — so a readable descriptor on it is returned for the caller's walk to drain and then
    rmdir; **the caller owns it** and must close it. ``rel`` keeps a refusal locatable.

    The single O_PATH | O_NOFOLLOW open classifies the entry atomically: that flag pair does not
    fail on a symlink, the kernel hands back a descriptor on the LINK ITSELF and os.fstat()
    reports S_ISLNK, so a symlink can never be mistaken for its target. O_PATH also means the
    entry is never opened for I/O, which is what makes refusing a FIFO, socket or device node
    safe: opening a planted FIFO blocks until a writer appears, and a planted device node can
    carry an open-time side effect."""
    child_fd = os.open(name, _O_PATH | _O_NOFOLLOW | _O_CLOEXEC, dir_fd=dir_fd)
    try:
        child_stat = os.fstat(child_fd)
        mode = child_stat.st_mode
        if stat.S_ISLNK(mode):
            os.unlink(name, dir_fd=dir_fd)
            return None
        if stat.S_ISDIR(mode):
            # Reopened while child_fd is still open, so the descriptor handed back refers to the
            # inode just classified. It stays valid after child_fd is closed below: it is an
            # independent descriptor on that inode, not a view of child_fd.
            return _open_readable_dir(child_fd)
        if not stat.S_ISREG(mode):
            # `rel`, not `name`: a Sentinel tree nests one artifacts/<hash>/ directory per
            # captured command, so the same entry name occurs at many depths and a bare
            # os.listdir name does not say WHERE the refused entry is.
            raise NotImplementedError(f"Can only securely remove regular files and directories: {rel}")
        # Zero-length shortcut: there is nothing to overwrite.
        if child_stat.st_size > 0:
            _shred_regular(child_fd, child_stat.st_size, passes)
        # The name only ever reaches unlink/rmdir with dir_fd=, neither of which follows a
        # final-component symlink or opens anything — that is what keeps the walk inside the
        # tree. Residual: a swap landing between the shred and this unlink can remove a DIFFERENT
        # entry, but rename() returns EXDEV across mount points, so it is necessarily another
        # entry of the same bind mount, which was going to be removed anyway.
        os.unlink(name, dir_fd=dir_fd)
        return None
    finally:
        os.close(child_fd)


def _shred_regular(path_fd: int, size: int, passes: int) -> None:
    """Overwrite the regular file referred to by ``path_fd`` with random data, then truncate it.

    The writable descriptor is obtained by reopening /proc/self/fd/{path_fd}, never by reopening
    the name: the magic link resolves to the inode the classification descriptor already refers
    to, so the random bytes provably land on the entry that was classified and on nothing else.
    This is what stops a racing rename from redirecting the overwrite onto another file.

    O_NOFOLLOW is deliberately NOT passed here — /proc/self/fd/N is itself a symlink and must be
    followed for the reopen to work at all.
    """
    fd = os.open(f"/proc/self/fd/{path_fd}", os.O_RDWR | _O_CLOEXEC)
    try:
        chunk_size = 1024 * 1024
        for _ in range(max(1, passes)):
            os.lseek(fd, 0, os.SEEK_SET)
            remaining = size
            # Write chunk by chunk to avoid using too much memory
            while remaining > 0:
                to_write = min(chunk_size, remaining)
                chunk = os.urandom(to_write)
                written = 0
                # os.write may write less than requested; looping keeps a short write from
                # leaving an un-overwritten hole in the file.
                while written < to_write:
                    written += os.write(fd, chunk[written:])
                remaining -= to_write
            os.fsync(fd)

        os.ftruncate(fd, 0)
        os.fsync(fd)
    finally:
        os.close(fd)


async def _secure_remove_portable(file_path: Path, passes: int = 3) -> None:
    """The path-based removal, kept for non-Linux hosts.

    See the platform gate in secure_remove() for why macOS and Windows keep this algorithm and
    the racing-rename risk that entails. Do not "improve" this function with another
    point-in-time check: on a host where the tree can be raced only the descriptor-based path is
    sound, and adding checks here would suggest otherwise.

    One DECLARED divergence from the hardened branch: a missing target raises
    NotImplementedError here — it falls through is_symlink() / is_dir() / not is_file() — where
    the hardened branch raises FileNotFoundError from its root os.open. Both are types
    __removeVolume recovers from, so the observable outcome is the same; the type is not. Pinned
    by test_missing_target_type_differs_between_the_two_branches."""
    if file_path.is_symlink():
        # Do not follow symlinks. Must be tested before is_dir(): is_dir() resolves the symlink
        # target, so a symlink to a directory would otherwise be recursed into and the TARGET's
        # content shredded, outside file_path's own tree. A container running as root over the
        # host bind mount can plant exactly that, so this ordering is a security boundary.
        file_path.unlink()
        return

    elif file_path.is_dir():
        # Identify all items in the directory
        tasks = []
        for item in file_path.iterdir():
            tasks.append(_secure_remove_portable(item, passes))

        # Parallel execution of all tasks
        if tasks:
            await asyncio.gather(*tasks)

        # Once all files/sub-folders are deleted, delete the directory itself
        file_path.rmdir()
        return

    elif not file_path.is_file():
        raise NotImplementedError(f"Can only securely remove regular files and directories: {file_path}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        file_path.unlink()
        return

    with open(file_path, 'rb+') as f:
        chunk_size = 1024 * 1024
        for _ in range(max(1, passes)):
            f.seek(0)
            remaining = file_size
            # Write chunk by chunk to avoid using too much memory
            while remaining > 0:
                to_write = min(chunk_size, remaining)
                f.write(os.urandom(to_write))
                remaining -= to_write
            f.flush()
            os.fsync(f.fileno())

        f.truncate(0)
        f.flush()
        os.fsync(f.fileno())
    file_path.unlink()
