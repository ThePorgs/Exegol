import asyncio
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.SudoInfo import SudoInfo
from exegol.console.ExegolPrompt import ExegolRich, stdinCanAnswer
from exegol.manager.TaskManager import TaskManager
from exegol.utils.ConfigDirMigration import ConfigDirMigration, DATASTORE_FILE, MigrationAborted, MigrationSide, \
    RETIRED_MARKER, SESSION_LOCK_FILE, SESSION_LOCK_MAX_AGE, isWrapperFileName
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import get_user_id
from exegol.utils.LocalDatastore import LocalDatastore
from exegol.utils.SignalHandler import SignalHandler


class ConfigDirManager:
    """Check the location and the ownership of the exegol config directory"""

    @staticmethod
    def fixWrapperOwnership(config_dir: Path) -> List[Path]:
        """Give back to the invoking user the root-owned wrapper files of the config directory.
        Only regular, single-link files of the allowlist are touched, through a no-follow directory fd.
        Return the list of re-owned paths."""
        if sys.platform != "linux":
            return []
        if os.geteuid() != 0:
            return []
        try:
            user_uid, user_gid = get_user_id()
        except SystemError:
            return []
        if user_uid == 0:
            # Real root login, nothing to hand back
            return []
        fixed: List[Path] = []
        try:
            dir_fd = os.open(config_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as e:
            logger.debug(f"Skipping the ownership check of {config_dir}: {e}")
            return []
        try:
            try:
                dir_stat = os.fstat(dir_fd)
                if dir_stat.st_uid == 0:
                    os.fchown(dir_fd, user_uid, user_gid)
                    fixed.append(config_dir)
                    logger.debug(f"Changed owner of {config_dir} to {user_uid}:{user_gid}")
            except OSError as e:
                logger.debug(f"Could not change the owner of {config_dir}: {e}")
            try:
                names = os.listdir(dir_fd)
            except OSError as e:
                logger.debug(f"Could not list {config_dir}: {e}")
                return fixed
            for name in sorted(names):
                if not isWrapperFileName(name):
                    continue
                try:
                    entry_stat = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    # A symlink or a hardlink could alias a system file: only plain single-link files are re-owned
                    if not stat.S_ISREG(entry_stat.st_mode) or entry_stat.st_uid != 0 or entry_stat.st_nlink != 1:
                        continue
                    os.chown(name, user_uid, user_gid, dir_fd=dir_fd, follow_symlinks=False)
                    fixed.append(config_dir / name)
                    logger.debug(f"Changed owner of {config_dir / name} to {user_uid}:{user_gid}")
                except OSError as e:
                    logger.debug(f"Could not change the owner of {config_dir / name}: {e}")
        finally:
            os.close(dir_fd)
        return fixed

    @classmethod
    async def checkConfigLocation(cls) -> None:
        """Check the exegol config directory once the license is known to be active"""
        if not SudoInfo.isSudoContext():
            return
        active = ConstantConfig.exegol_config_path
        user_home = SudoInfo.getUserHome()
        root_home = Path(os.path.expanduser("~root"))
        if os.path.realpath(user_home) == os.path.realpath(root_home):
            # The invoking user's home is unknown (no SUDO_HOME, no passwd entry): root's files are never handed over
            logger.debug(f"The home of the sudo user resolves to {root_home}, skipping the config folder check.")
            return
        user_dir = user_home / ".exegol"
        if ConfigDirMigration.isLegacyRootDir(active, root_home, user_home):
            # Legacy real /root/.exegol: never re-owned to the user, a migration is proposed instead
            await cls.__proposeMigration(active, user_dir)
        elif os.path.realpath(active) == os.path.realpath(user_dir):
            root_link = root_home / ".exegol"
            if os.path.islink(root_link) and os.path.realpath(root_link) == os.path.realpath(user_dir):
                # Migrated (or linked by hand): finish the post-swap work an interrupted migration may have skipped
                cls.__reportOldCopies(root_link, user_dir)
                TaskManager.add_task(asyncio.to_thread(cls.__completeMigratedDir, root_link, user_dir))
            elif os.path.lexists(root_link) or not cls.__reportMissingRootLink(root_link, user_dir, interrupted=False):
                # The config lives in the user's home: silently give back root-owned wrapper files in background.
                TaskManager.add_task(asyncio.to_thread(cls.fixWrapperOwnership, active))

    @classmethod
    def checkLicenseLocation(cls, licensed: bool) -> bool:
        """Before any activation: report a legacy root config dir holding no license while a license database exists
        in the user dir or set aside next to it (a migration stopped while moving it). Activating again would bury that
        license under a new activation. Never repaired automatically. Return True when reported."""
        if licensed or not SudoInfo.isSudoContext():
            return False
        active = ConstantConfig.exegol_config_path
        user_home = SudoInfo.getUserHome()
        if not ConfigDirMigration.isLegacyRootDir(active, Path(os.path.expanduser("~root")), user_home):
            return False
        return cls.__reportMovedLicense(active, user_home / ".exegol")

    @staticmethod
    def __reportMovedLicense(root_dir: Path, user_dir: Path) -> bool:
        """Report the license databases found outside root_dir (which holds no license). Return True when reported."""
        user_db = user_dir / DATASTORE_FILE
        found = ([user_db] if os.path.isfile(user_db) else []) + sorted(root_dir.glob(f"{DATASTORE_FILE}{RETIRED_MARKER}*"))
        if not found:
            return False
        logger.error(f"{root_dir} is still the active configuration folder but holds no license, while a license database "
                     f"exists at {', '.join(map(str, found))}. Nothing changed, no new activation is proposed.")
        logger.info(f"With no exegol process running, move {found[0]} to {root_dir / DATASTORE_FILE} (replacing the "
                    f"license-free one, if any), then run [green]sudo exegol activate[/green] again to resume the migration.")
        if len(found) > 1:
            logger.info(f"{', '.join(map(str, found[1:]))}: copies set aside by the migration, delete them once the license works.")
        return True

    @staticmethod
    def __reportOldCopies(root_link: Path, user_dir: Path) -> None:
        """Report the old root dir copies a cross-filesystem migration set aside and did not remove (never removed
        automatically: an interrupted removal leaves a partial copy)"""
        for leftover in sorted(root_link.parent.glob(f"{root_link.name}{RETIRED_MARKER}*")):
            logger.warning(f"A previous migration left {leftover} behind: delete it once {user_dir} is checked complete.")

    @staticmethod
    def __reportMissingRootLink(root_link: Path, user_dir: Path, interrupted: bool) -> bool:
        """Report a migration stopped before the root_link symlink (unless interrupted, only when an old copy was
        left aside or config.yml still holds root_link paths): without the link, existing containers lose their
        mounts and the next container creation re-creates an empty root_link, which wins over user_dir.
        Never repaired automatically. Return True when reported."""
        leftovers = sorted(root_link.parent.glob(f"{root_link.name}{RETIRED_MARKER}*"))
        if not (interrupted or leftovers):
            try:
                if not ConfigDirMigration.rewriteConfigPaths(user_dir / "config.yml", root_link, user_dir, dry_run=True):
                    return False
            except (OSError, ValueError) as e:
                logger.debug(f"Could not read {user_dir / 'config.yml'}: {e}")
                return False
        logger.error(f"Your configuration lives in {user_dir} but the migration stopped before linking {root_link} to it: "
                     f"run [green]sudo ln -s {user_dir} {root_link}[/green] so existing containers keep their mounts, "
                     f"then [green]sudo exegol activate[/green] to finish.")
        if leftovers:
            logger.error(f"Once {user_dir} is checked complete, delete the old copy: {', '.join(map(str, leftovers))}")
        return True

    @staticmethod
    def __isUnder(source: str, directory: Path) -> bool:
        """Tell whether a mount source is the directory or inside it"""
        for candidate in {str(directory), os.path.realpath(directory)}:
            candidate = candidate.rstrip("/")
            if source == candidate or source.startswith(candidate + "/"):
                return True
        return False

    @classmethod
    async def __listContainerMounts(cls, refresh: bool = False) -> List[Tuple[str, bool, List[str]]]:
        """List (name, is running, bind mount sources) of every exegol container.
        With refresh, the cached container list is dropped to catch the containers created since."""
        from exegol.utils.DockerUtils import DockerUtils
        if refresh:
            DockerUtils().clearCache()
        result: List[Tuple[str, bool, List[str]]] = []
        for container in await DockerUtils().listContainers():
            # isRunning() reloads the container state from docker
            sources = [str(mount.get("Source")) for mount in container.config.getVolumes() if mount.get("Source")]
            result.append((container.name, container.isRunning(), sources))
        return result

    @classmethod
    def __containersUsing(cls, containers: List[Tuple[str, bool, List[str]]], directory: Path) -> List[str]:
        return [name for name, _, sources in containers if any(cls.__isUnder(source, directory) for source in sources)]

    @classmethod
    def __runningUsers(cls, containers: List[Tuple[str, bool, List[str]]], directories: List[Path]) -> List[str]:
        """Names of the running containers mounting one of the directories"""
        users = {name for directory in directories for name in cls.__containersUsing(containers, directory)}
        return sorted({name for name, is_running, _ in containers if is_running and name in users})

    @classmethod
    def __completeMigratedDir(cls, root_link: Path, user_dir: Path) -> None:
        """Idempotent post-swap work of the migration: config.yml paths and ownership hand-back"""
        try:
            if ConfigDirMigration.rewriteConfigPaths(user_dir / "config.yml", root_link, user_dir):
                logger.verbose(f"Updated the {root_link} paths of {user_dir / 'config.yml'}")
        except (OSError, ValueError) as e:
            logger.warning(f"Unable to update the {root_link} paths of {user_dir / 'config.yml'}: {e}")
        cls.__handBackMigration(user_dir, None)

    @staticmethod
    def __handBackMigration(user_dir: Path, backup_dir: Optional[Path]) -> None:
        """Give the migrated config dir back to the invoking user: the dir itself, every top-level entry and
        components/ recursively, plus the whole backup dir. Container-written trees keep their inner ownership.
        Everything is reached through no-follow directory fds (the user controls these paths)."""
        if sys.platform != "linux" or os.geteuid() != 0:
            return
        try:
            user_uid, user_gid = get_user_id()
        except SystemError:
            return
        if user_uid == 0:
            return
        ConfigDirMigration.handBackOwnership(user_dir, user_uid, user_gid, recursive_children=("components",))
        if backup_dir is not None and os.path.lexists(backup_dir):
            ConfigDirMigration.handBackOwnership(backup_dir, user_uid, user_gid, recursive=True)

    @classmethod
    async def __proposeMigration(cls, root_dir: Path, user_dir: Path) -> None:
        """Interactively migrate a legacy real /root/.exegol to the invoking user's ~/.exegol,
        leaving /root/.exegol as a symlink so existing containers keep their mounts"""
        logger.warning(f"Your Exegol configuration and license are stored in [magenta]{root_dir}[/magenta] (root's home) "
                       f"instead of [magenta]{user_dir}[/magenta], which Exegol Studio and non-root tools need.")
        if not stdinCanAnswer():
            logger.info("Run [green]sudo exegol activate[/green] from an interactive terminal to migrate it.")
            return
        try:
            # Preview used for the questions only: the plan applied is computed again once nothing else writes
            # to the folders (the license database closed, the container listing done)
            preview = ConfigDirMigration.planMigration(root_dir, user_dir)
        except ValueError as e:
            logger.error(f"Cannot migrate {root_dir} to {user_dir} automatically, nothing changed: {e}")
            logger.info("Migrate the listed elements manually, then run [green]sudo exegol activate[/green] again.")
            return

        # Every check and prompt happens before the first filesystem change
        try:
            containers = await cls.__listContainerMounts()
        except Exception as e:
            logger.error(f"Unable to list the containers using the configuration folders ({e}), migration aborted.")
            return
        root_users = cls.__containersUsing(containers, root_dir)
        user_users = cls.__containersUsing(containers, user_dir)
        logger.info(f"Containers using {root_dir}: {', '.join(root_users) if root_users else 'none'}")
        logger.info(f"Containers using {user_dir}: {', '.join(user_users) if user_users else 'none'}")
        used_dirs = [root_dir, user_dir]
        running = cls.__runningUsers(containers, used_dirs)
        if running:
            logger.error(f"These containers are running and use a configuration folder: {', '.join(running)}. "
                         f"Stop them ([green]exegol stop --all[/green]) then run [green]sudo exegol activate[/green] again.")
            return

        if not await ExegolRich.Confirm(f"Migrate [magenta]{root_dir}[/magenta] to [magenta]{user_dir}[/magenta] ? Close any other exegol "
                                        f"session first (discarded copies are kept in a backup folder)", default=True):
            logger.info("Migration skipped, it will be proposed again on the next [green]sudo exegol activate[/green].")
            return

        decisions: Dict[Path, MigrationSide] = {}
        for step in preview.conflicts:
            root_path = root_dir / step.relative
            user_path = user_dir / step.relative
            root_mounts = cls.__containersUsing(containers, root_path)
            user_mounts = cls.__containersUsing(containers, user_path)
            logger.empty_line()
            logger.warning(f"[magenta]{step.relative}[/magenta] holds different data on both sides:")
            logger.info(f"root: {root_path} (used by: {', '.join(root_mounts) if root_mounts else 'no container'})")
            logger.info(f"user: {user_path} (used by: {', '.join(user_mounts) if user_mounts else 'no container'})")
            choice = await ExegolRich.Ask("Which version do you want to keep?",
                                          choices=[MigrationSide.ROOT.value, MigrationSide.USER.value],
                                          default=MigrationSide.ROOT.value)
            decisions[step.relative] = MigrationSide(choice)

        # The license tasks must not use the database while it moves
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        await TaskManager.wait_for(TaskManager.TaskId.RefreshSession, clean_task=False)
        lock_file = root_dir / SESSION_LOCK_FILE
        lock_age = ConfigDirMigration.sessionLockAge(lock_file)
        if lock_age is not None and lock_age >= SESSION_LOCK_MAX_AGE:
            # Left by a crashed exegol process: removed like SessionHandler does
            logger.verbose(f"Removing the stale session lock {lock_file}")
            try:
                lock_file.unlink(missing_ok=True)
            except OSError as e:
                logger.error(f"Unable to remove the stale session lock {lock_file} ({e}), delete it then run "
                             f"[green]sudo exegol activate[/green] again.")
                return
        elif lock_age is not None:
            logger.error(f"Another exegol process is refreshing the license ({lock_file} exists), close it then run "
                         f"[green]sudo exegol activate[/green] again. If no exegol process is running, delete {lock_file}.")
            return
        # A container may have been created or started during the questions: query docker again, right before the
        # move (this also rewrites .datacache before the final plan, never after)
        try:
            running = cls.__runningUsers(await cls.__listContainerMounts(refresh=True), used_dirs)
        except Exception as e:
            logger.error(f"Unable to list the containers using the configuration folders ({e}), migration aborted.")
            return
        if running:
            logger.error(f"These containers have been started and use a configuration folder: {', '.join(running)}. "
                         f"Stop them ([green]exegol stop --all[/green]) then run [green]sudo exegol activate[/green] again.")
            return

        backup_dir = SudoInfo.getUserHome() / f".exegol-migration-backup-{datetime.now():%Y%m%d-%H%M%S}"
        logger.info(f"Migrating {root_dir} to {user_dir}, this can take a while for large folders...")
        backup: Optional[Path] = None
        # True once entries may have moved: from then on, the ownership hand-back runs whatever the outcome
        moved = False
        # From the license database close to the final message, a single Ctrl+C is held back until the migration is over
        with SignalHandler.protect("Waiting for the configuration folder migration to complete, forcing the exit "
                                   "could leave it half done."):
            # SQLite checkpoints and removes the -wal/-shm files when its last connection closes
            LocalDatastore().close()
            try:
                # Plan against the state the move will see
                try:
                    plan = ConfigDirMigration.planMigration(root_dir, user_dir)
                except ValueError as e:
                    logger.error(f"Migration aborted, nothing changed: {e}")
                    logger.info("Migrate the listed elements manually, then run [green]sudo exegol activate[/green] again.")
                    return
                if {step.relative for step in plan.conflicts} != set(decisions.keys()):
                    logger.error("The configuration folders changed during the questions, nothing changed. "
                                 "Run [green]sudo exegol activate[/green] again.")
                    return
                try:
                    moved = True
                    backup = ConfigDirMigration.applyMigration(plan, decisions, backup_dir)
                except MigrationAborted as e:
                    moved = False
                    logger.error(f"Migration aborted, nothing changed: {e}")
                    return
                except (OSError, ValueError, KeyboardInterrupt) as e:
                    logger.error(f"Migration failed: {str(e) or type(e).__name__}")
                    if os.path.islink(root_dir) and os.path.realpath(root_dir) == os.path.realpath(user_dir):
                        logger.error(f"{root_dir} already links to {user_dir}, only the removal of the old copy stopped. "
                                     f"Run [green]sudo exegol activate[/green] again to finish.")
                        cls.__reportOldCopies(root_dir, user_dir)
                    elif not os.path.lexists(root_dir):
                        cls.__reportMissingRootLink(root_dir, user_dir, interrupted=True)
                    elif (root_dir / DATASTORE_FILE).is_file() or not cls.__reportMovedLicense(root_dir, user_dir):
                        logger.error(f"{root_dir} is still the active configuration folder, {user_dir} may hold part of the data "
                                     f"and {backup_dir} the discarded copies. Run [green]sudo exegol activate[/green] again to resume the merge.")
                    if isinstance(e, KeyboardInterrupt):
                        raise
                    return
            finally:
                if LocalDatastore.getDbPath().is_file():
                    LocalDatastore().reopen()
                else:
                    logger.error(f"The license database is no longer at {LocalDatastore.getDbPath()}, check {user_dir / '.datastore'}.")
                if moved:
                    # Even after a failure: the user must be able to review the backup and the entries moved so far
                    cls.__handBackMigration(user_dir, backup_dir)

            # The swap is done: from here on, the user dir is the active configuration folder
            try:
                ConfigDirMigration.rewriteConfigPaths(user_dir / "config.yml", root_dir, user_dir)
            except (OSError, ValueError) as e:
                logger.warning(f"The paths of {user_dir / 'config.yml'} still point to {root_dir} ({e}). "
                               f"Run [green]sudo exegol activate[/green] again to update them.")

            logger.success(f"Your configuration now lives in {user_dir}, {root_dir} links to it so existing containers keep their mounts.")
            if backup is not None:
                logger.info(f"Discarded copies are kept in {backup}: review them, then delete this folder.")
