import os
import re
import shutil
from pathlib import Path
from typing import Awaitable, Callable, Optional, Dict, cast, Tuple, Sequence, List, Set

from rich.markup import escape

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.DataCache import DataCache
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.console.ExegolPrompt import ExegolRich, stdinCanAnswer
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.model.LicensesTypes import LicenseFeature
from exegol.utils import FsUtils
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.GitUtils import GitUtils
from exegol.utils.SessionHandler import SessionHandler
from exegol.utils.WebRegistryUtils import WebRegistryUtils


class UpdateManager:
    """Procedure class for updating the exegol tool and docker images"""

    @classmethod
    async def updateImage(cls, tag: Optional[str] = None, install_mode: bool = False) -> Optional[ExegolImage]:
        """User procedure to build/pull docker image"""
        # List Images
        # Not a creation path, so the profile tier is never installed here. `update -i` shares
        # the `imagetag` dest with the positional of start/install/build.
        image_args = OptionResolver().get(OptionKey.IMAGE_TAG)
        # Select image
        # `-i` is nargs='?' const=True: None (absent), True (bare `-i`: use the picker) or a tag.
        # True is excluded by identity, since an inequality would also exclude every tag string.
        # A blank `--image ""` is refused rather than sent to Docker as an empty image name.
        if isinstance(image_args, str) and not image_args.strip():
            logger.error("An image tag is required: `exegol update --image <tag>` names one, "
                         "and `exegol update -i` with no value picks one interactively.")
            return None
        if image_args is not None and image_args is not True and tag is None:
            tag = image_args
        if tag is None:
            all_images: List[ExegolImage] = await DockerUtils().listImages()
            # Filter for updatable images
            if install_mode:
                available_images = [i for i in all_images if not i.isLocked() and not i.isLocal()]
            else:
                available_images = [i for i in all_images if i.isInstall() and not i.isLocal() and not i.isUpToDate() and not i.isLocked()]
                if len(available_images) == 0:
                    logger.success("All images already installed are up to date!")
                    return None
            try:
                # Interactive selection
                selected_image = await ExegolTUI.selectFromTable(available_images,
                                                                 object_type=ExegolImage,
                                                                 allow_none=False)
            except IndexError:
                # No images are available
                if install_mode:
                    # If no image are available in install mode,
                    # either the user does not have internet,
                    # or the image repository has been changed and no docker image is available
                    logger.critical("Exegol can't be installed offline")
                return None
        else:
            try:
                # Find image by name
                selected_image = await DockerUtils().getOfficialImageFromList(tag)
            except ObjectNotFound:
                logger.error(f"Image '{tag}' was not found. If you wanted to build a local image, you can use the 'build' action instead.")
                return None

        if selected_image is not None and type(selected_image) is ExegolImage:
            # Update existing ExegolImage
            if await DockerUtils().downloadImage(selected_image, install_mode):
                sync_result = None
                # Name comparison allow detecting images without version tag
                if selected_image.isVersionSpecific():
                    # Install latest tag if not already installed
                    try:
                        result = await DockerUtils().getOfficialImageFromList(selected_image.getName().split('-')[0])
                        if result is None or not result.isInstall():
                            raise ObjectNotFound
                    except ObjectNotFound:
                        DockerUtils().createLocalLastestImageTag(selected_image)
                elif selected_image.hasVersionTag():
                    async with ExegolStatus(f"Synchronizing version tag information. Please wait.", spinner_style="blue"):
                        # Download associated version tag.
                        sync_result = await DockerUtils().downloadVersionTag(selected_image)
                    # Detect if an error have been triggered during the download
                    if type(sync_result) is str:
                        logger.error(f"Error while downloading version tag, {sync_result}")
                        sync_result = None
                # if version tag have been successfully download, returning ExegolImage from docker response
                if sync_result is not None and type(sync_result) is ExegolImage:
                    return sync_result
                # Version-specific images must skip cache to avoid loading latest image
                return await DockerUtils().getInstalledImage(selected_image.getName(), selected_image.getRepository(), skip_cache=selected_image.isVersionSpecific())
        else:
            # Unknown use case
            logger.critical(f"Unknown selected image '{selected_image}'. Exiting.")
        return cast(Optional[ExegolImage], selected_image)

    @classmethod
    async def updateWrapper(cls) -> bool:
        """Update wrapper source code from git"""
        result = await cls.__updateGit(await ExegolModules().getWrapperGit())
        if result:
            await cls.__untagUpdateAvailable()
            logger.empty_line()
            logger.warning("After this wrapper update, remember to update Exegol [bold]requirements[bold]! ([magenta]python3 -m pip install --upgrade -r requirements.txt[/magenta])")
            logger.empty_line()
        return result

    @classmethod
    async def updateImageSource(cls) -> bool:
        """Update image source code from git submodule"""
        return await cls.__updateGit(await ExegolModules().getSourceGit())

    @classmethod
    async def updateResources(cls) -> bool:
        """Update Exegol-resources from git (submodule)"""
        if not OptionResolver().get(OptionKey.ENABLE_EXEGOL_RESOURCES):
            logger.info("Skipping disabled Exegol resources.")
            return False
        try:
            if not await ExegolModules().isExegolResourcesReady() and not await ExegolRich.Confirm('Do you want to update exegol resources.', default=True):
                return False
            return await cls.__updateGit(await ExegolModules().getResourcesGit())
        except CancelOperation:
            # Error during installation, skipping operation
            return False

    @classmethod
    async def fetchSentinelSources(cls) -> bool:
        """Fetch declared Sentinel sources without pruning (see :meth:`fetchProfileSources`)."""
        return await cls.updateSentinelSources(prune=False)

    @classmethod
    async def updateSentinelSources(cls, prune: bool = True, explain_refusal: bool = False) -> bool:
        """License-gated fetch of Sentinel profile sources.

        Provisions the official 'core' source, then clones/pulls each declared git source
        into component_path/<key> and prunes stale ones. Local 'path:' sources are never
        fetched or pruned. Returns False when unlicensed or offline."""
        # A profile can never set these discovery settings (see ProfileFieldMap.PROFILE_TIER_DEAD).
        component_path = OptionResolver().get(OptionKey.SENTINEL_PROFILE_PATH)
        sources = OptionResolver().get(OptionKey.SENTINEL_SOURCES)

        async def provision_core() -> bool:
            """Clone or update the official core source."""
            return await cls.__updateGit(await ExegolModules().getSentinelCoreGit())

        return await cls.__syncComponentSources(
            component_path=component_path,
            sources=sources,
            # Sentinel is gated by an a-la-carte feature flag, not by the licence tier.
            licence_check=lambda: SessionHandler().has_feature(LicenseFeature.Sentinel),
            log_label="Sentinel",
            git_name_prefix="sentinel",
            git_subject="sentinel library",
            extra_keep_keys={ConstantConfig.SENTINEL_CORE_SOURCE_KEY},
            pre_fetch=provision_core,
            prune=prune,
            # Feature-flag wording, matching the gate above.
            refusal_message=SessionHandler.feature_access_message("Sentinel source fetching") if explain_refusal else None,
        )

    @classmethod
    async def fetchProfileSources(cls) -> bool:
        """Fetch declared container profile sources without pruning.

        Used by the fetch prompt on ``exegol start`` / ``exegol info``: agreeing to fetch is
        not consent to delete, so pruning only happens on ``exegol update``.
        """
        return await cls.updateProfileSources(prune=False)

    @classmethod
    async def updateProfileSources(cls, prune: bool = True, explain_refusal: bool = False) -> bool:
        """License-gated (Enterprise) fetch of container profile sources.

        Clones/pulls each declared git source into component_path/<key> and prunes
        undeclared ones, through the same body as the Sentinel entrypoint. Only
        `exegol update` calls it. Without the licence it neither fetches nor prunes, so
        existing clones (which may hold uncommitted work) are kept. Local 'path:' sources
        are never cloned or pruned.
        """
        # A profile can never set these discovery settings (see ProfileFieldMap.PROFILE_TIER_DEAD).
        component_path = OptionResolver().get(OptionKey.PROFILE_COMPONENT_PATH)
        sources = OptionResolver().get(OptionKey.PROFILE_SOURCES)
        return await cls.__syncComponentSources(
            component_path=component_path,
            sources=sources,
            # The bound method itself, not a wrapper: ContainerProfileManager's load gate uses
            # the same function, so fetch and load gates cannot drift apart.
            licence_check=SessionHandler().enterprise_feature_access,
            log_label="container profile",
            git_name_prefix="profile",
            git_subject="container profile library",
            # 'local' is always kept, even when undeclared: it is the operator's own drop-in
            # directory, possibly their only copy of their profiles, not a re-clonable checkout.
            extra_keep_keys={ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY},
            pre_fetch=None,
            prune=prune,
            # Enterprise-tier wording, matching `enterprise_feature_access` above.
            refusal_message=SessionHandler.enterprise_access_message("container profile source fetching") if explain_refusal else None,
        )

    @classmethod
    async def promptFetchMissingSources(cls,
                                        missing_keys: List[str],
                                        log_label: str,
                                        fetch: Callable[[], Awaitable[bool]]) -> bool:
        """Offer to fetch declared-but-unfetched git sources; return True when ``fetch()`` ran.

        True tells the caller to reload and resume the interrupted action. Nothing missing is
        a silent no-op; offline mode only warns; a closed stdin (EOFError) warns with an
        ``exegol update`` hint and never fetches; a decline logs the hint. Source keys are
        markup-escaped. ``ExegolRich`` and ``stdinCanAnswer`` are both read from the module
        globals so tests can patch them.
        """
        if not missing_keys:
            return False
        named = ", ".join(f"'{escape(key)}'" for key in missing_keys)
        headline = (f"{len(missing_keys)} declared {log_label} git source(s) have not been fetched yet: "
                    f"{named}.")
        hint = f"Run `exegol update` to fetch {'it' if len(missing_keys) == 1 else 'them'}."
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.warning(f"{headline} They cannot be fetched in offline mode.")
            return False
        logger.info(headline)
        try:
            # Default Yes at a terminal, No on piped stdin: an empty line is not consent to fetch.
            confirmed = await ExegolRich.Confirm(f"Do you want to update the {log_label} sources now?",
                                                 default=stdinCanAnswer())
        except EOFError:
            # No answerable stdin: warn and let the interrupted action continue without fetching.
            logger.empty_line()
            logger.warning(f"{headline} {hint}")
            return False
        if not confirmed:
            logger.info(hint)
            return False
        await fetch()
        return True

    @classmethod
    async def __syncComponentSources(cls,
                                     component_path: Path,
                                     sources: Dict[str, Dict[str, str]],
                                     licence_check: Callable[[], bool],
                                     log_label: str,
                                     git_name_prefix: str,
                                     git_subject: str,
                                     extra_keep_keys: Set[str],
                                     pre_fetch: Optional[Callable[[], Awaitable[bool]]] = None,
                                     prune: bool = True,
                                     refusal_message: Optional[str] = None) -> bool:
        """Shared source-sync body behind every component's fetch entrypoint.

        Clones/pulls each declared git source to its ref into component_path/<key>, then
        prunes stale git-source directories. Local 'path:' sources are never fetched or
        pruned. Kept as a single implementation: the git environment and prune guards are
        security-relevant.

        Per-caller parameters:
          * `licence_check` — the component's licence predicate;
          * `log_label` — component name used in operator-facing messages;
          * `git_name_prefix` / `git_subject` — GitUtils identity;
          * `extra_keep_keys` — keys the prune always preserves;
          * `pre_fetch` — optional provisioning step before the declared sources;
          * `prune` — False for fetch-only callers (the fetch prompt);
          * `refusal_message` — warning logged on licence refusal, None to stay silent.
        """
        # Check license access, before any git operation.
        # Silent unless the caller named this target: a broad request stays silent, a named
        # one explains the refusal. Warning only, so one refused target does not abort the run.
        if not licence_check():
            if refusal_message is not None:
                logger.warning(refusal_message)
            return False
        # Offline-mode guard on all git I/O.
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error(f"It's not possible to update {log_label} sources in offline mode ...")
            return False
        updated = False
        git_source_keys: Set[str] = set()
        # (0) Provision the 'local' drop-in directory only when 'local' is a declared source
        # (written into config.yml by default; removing it there disables it).
        local_spec = sources.get(ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)
        if local_spec and local_spec.get("path"):
            local_dir = EnvInfo.expand_user(local_spec["path"])
            try:
                FsUtils.mkdir(local_dir)
            except OSError as e:
                logger.warning(f"Could not create the {log_label} 'local' source directory ({local_dir}): {e}")
        # Make git network ops non-interactive so an unattended update fails fast instead of hanging:
        #   - GIT_TERMINAL_PROMPT=0 -> HTTPS without credentials fails (credential helpers still apply);
        #   - GIT_SSH_COMMAND (SSH sources only) -> BatchMode + trust-on-first-use host keys,
        #     extending the user's existing command so its `-i` / jump-host options are kept.
        # Previous values are restored in the finally block.
        has_ssh = any("git" in spec and GitUtils.is_ssh_url(spec["git"]) for spec in sources.values())
        previous_terminal_prompt = os.environ.get("GIT_TERMINAL_PROMPT")
        previous_ssh_cmd = os.environ.get("GIT_SSH_COMMAND")
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        if has_ssh:
            os.environ["GIT_SSH_COMMAND"] = GitUtils.build_git_ssh_command(previous_ssh_cmd)
        try:
            # (1) Optional provisioning step (Sentinel core source).
            if pre_fetch is not None:
                try:
                    if await pre_fetch():
                        updated = True
                except CancelOperation:
                    # Provisioning failed (e.g. declined) — skip without aborting the whole update.
                    logger.verbose(f"{log_label} official source provisioning was skipped.")
            # (2) Fetch each declared git source to its configured ref.
            for source_key, source_spec in sources.items():
                if "git" not in source_spec:
                    # Local 'path:' sources are scanned in place — never cloned or pruned.
                    continue
                git_source_keys.add(source_key)
                source_dir = component_path / source_key
                git_url = source_spec["git"]
                ref = source_spec.get("ref")
                # A 'dev' source is a full clone the operator can commit to and push from;
                # its updates are a safe pull on the current branch (never re-cloned/pruned).
                is_dev = source_spec.get("mode") == "dev"
                source_git = await GitUtils(source_dir, f"{git_name_prefix}-{source_key}", git_subject).initialize(silent=True)
                if not source_git.isAvailable:
                    if is_dev:
                        # Full clone (drop --depth=1) so the developer has real history to
                        # commit and push their own profile changes locally.
                        if await source_git.clone(git_url, ref=ref, optimize_disk_space=False):
                            updated = True
                    # Absent -> clone to the pinned ref.
                    elif await source_git.clone(git_url, ref=ref):
                        updated = True
                elif is_dev:
                    # Dev present -> never re-clone: 'ref' only drove the initial checkout. Safe pull
                    # on the current branch (update() skips a dirty repo), so local work survives.
                    current_branch = source_git.getCurrentBranch()
                    if ref and current_branch is not None and ref != current_branch:
                        logger.warning(f"{log_label} dev source [green]{source_key}[/green] is checked out on "
                                       f"[green]{current_branch}[/green] but its configured ref is "
                                       f"[green]{ref}[/green]. The ref is used only for the initial checkout; "
                                       f"no checkout is being forced.")
                    if await source_git.update():
                        updated = True
                else:
                    # Present -> sync to the configured ref, switching the checkout if it changed.
                    if await source_git.updateToRef(git_url, ref=ref):
                        updated = True
        finally:
            if previous_terminal_prompt is None:
                os.environ.pop("GIT_TERMINAL_PROMPT", None)
            else:
                os.environ["GIT_TERMINAL_PROMPT"] = previous_terminal_prompt
            if has_ssh:
                if previous_ssh_cmd is None:
                    os.environ.pop("GIT_SSH_COMMAND", None)
                else:
                    os.environ["GIT_SSH_COMMAND"] = previous_ssh_cmd
        # (Under sudo, GitUtils.clone()/update() already hand each fetched source back to the
        # invoking user; FsUtils.mkdir() did the same for component_path and the 'local' dir.)
        # (3) Prune stale git-source directories under component_path (never local 'path:' sources).
        # Kept: the caller's extra keys, declared git sources, and 'local' while it is declared.
        keep = set(extra_keep_keys) | git_source_keys
        if ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY in sources:
            keep.add(ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY)
        if prune and component_path.is_dir():
            # Only prune re-clonable directories backing no declared source: -F skips the
            # prompt, so the prune must never reach hand-authored profiles.
            declared_dirs: Set[Path] = set()
            for spec in sources.values():
                declared_path = spec.get("path")
                if declared_path:
                    try:
                        declared_dirs.add(EnvInfo.expand_user(declared_path).resolve())
                    except OSError as e:  # pragma: no cover - defensive (unresolvable path)
                        logger.debug(f"Could not resolve declared {log_label} source path {declared_path}: {e}")
            for stale in [d for d in component_path.iterdir() if d.is_dir() and d.name not in keep]:
                try:
                    resolved_stale = stale.resolve()
                except OSError as e:  # pragma: no cover - defensive (broken symlink / permissions)
                    logger.debug(f"Skipping unresolvable {log_label} source directory {stale}: {e}")
                    continue
                if resolved_stale in declared_dirs:
                    # A declared 'path:' source that lives under component_path: never prune.
                    continue
                if not (stale / ".git").exists():
                    # Not a re-clonable git checkout: pruning it would be unrecoverable data loss.
                    logger.warning(f"Skipping non-git directory [magenta]{stale}[/magenta] during the {log_label} "
                                   f"source prune (it is not a re-clonable checkout). Remove it manually if it is stale.")
                    continue
                if await cls.__staleSourceHasLocalOnlyWork(stale, git_name_prefix, git_subject):
                    # At-risk branch: work that exists nowhere else. -F/--force deliberately does
                    # not skip this confirmation.
                    logger.warning(f"The stale {log_label} source directory [magenta]{stale}[/magenta] holds uncommitted "
                                   f"changes and/or commits that are not present on any remote. Removing it will "
                                   f"permanently delete that work. Push it, or copy it elsewhere, first.")
                    try:
                        confirmed = await ExegolRich.Confirm(
                            f"Permanently delete [magenta]{stale}[/magenta] and the local-only work it contains?",
                            default=False)
                    except EOFError:
                        # No answerable stdin: keep the directory rather than abort the update.
                        confirmed = False
                    if not confirmed:
                        logger.info(f"Keeping the stale {log_label} source directory [magenta]{stale}[/magenta]. "
                                    f"Remove it manually once its local-only work is saved.")
                        continue
                # Clean branch: nothing local-only to lose, so -F/--force skips the confirmation.
                elif not OptionResolver().get(OptionKey.FORCE_MODE):
                    try:
                        confirmed = await ExegolRich.Confirm(
                            f"Remove stale {log_label} source directory [magenta]{stale}[/magenta]?",
                            default=True)
                    except EOFError:
                        # No answerable stdin: keep the directory, an unanswered prompt must not
                        # authorise a deletion. Unattended runs wanting the prune use -F.
                        logger.empty_line()
                        logger.info(f"Keeping the stale {log_label} source directory "
                                       f"[magenta]{stale}[/magenta] (interactive confirmation needed).")
                        continue
                    if not confirmed:
                        continue
                shutil.rmtree(stale, ignore_errors=True)
                logger.verbose(f"Pruned stale {log_label} source directory: {stale}")
                updated = True
        return updated

    @classmethod
    async def __staleSourceHasLocalOnlyWork(cls, stale: Path, git_name_prefix: str, git_subject: str) -> bool:
        """Return True when pruning ``stale`` would destroy work that exists nowhere else.

        Every uncertain outcome resolves to True: an unreadable checkout, a dirty working
        tree, a repository with no remote, or any failure of the local-only-commit probe.
        The inspection is read-only and network-free, so it is valid in offline mode.
        """
        # skip_submodule_update=True: a submodule update would hit the network and modify the inspected directory.
        stale_git = await GitUtils(stale, f"{git_name_prefix}-{stale.name}", git_subject).initialize(
            skip_submodule_update=True, silent=True)
        if not stale_git.isAvailable:
            logger.debug(f"Could not load {stale} as a git repository; treating it as holding local-only work.")
            return True
        if not stale_git.safeCheck():
            # Covers both a dirty working tree (safeCheck warns about it itself) and a
            # repository with no remote — nothing can be on a remote by definition.
            return True
        return stale_git.hasLocalOnlyCommits()

    @staticmethod
    async def __updateGit(gitUtils: GitUtils) -> bool:
        """User procedure to update local git repository"""
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to update a repository in offline mode ...")
            return False
        if not gitUtils.isAvailable:
            logger.empty_line()
            return False
        logger.info(f"Updating Exegol [green]{gitUtils.getName()}[/green] {gitUtils.getSubject()}")
        # Check if pending change -> cancel
        if not gitUtils.safeCheck():
            logger.error("Aborting git update.")
            logger.empty_line()
            return False
        current_branch = gitUtils.getCurrentBranch()
        if current_branch is None:
            logger.warning("HEAD is detached. Please checkout to an existing branch.")
        if logger.isEnabledFor(ExeLog.VERBOSE):
            available_branches = gitUtils.listBranch()
            # Ask to checkout only if there is more than one branch available
            if len(available_branches) > 1:
                logger.info(f"Current git branch : {current_branch}")
                # List & Select git branch
                if current_branch is None or current_branch not in available_branches:
                    if "main" in available_branches:
                        default_choice = "main"
                    elif "master" in available_branches:
                        default_choice = "master"
                    else:
                        default_choice = None
                else:
                    default_choice = current_branch
                selected_branch = cast(str, await ExegolTUI.selectFromList(gitUtils.listBranch(),
                                                                           subject="a git branch",
                                                                           title="[not italic]:palm_tree: [/not italic][gold3]Branch[gold3]",
                                                                           default=default_choice))
            elif len(available_branches) == 0:
                logger.warning("No branch were detected!")
                selected_branch = None
            else:
                # Automatically select the only branch in case of HEAD detachment
                selected_branch = available_branches[0]
            # Checkout new branch
            if selected_branch is not None and selected_branch != current_branch:
                gitUtils.checkout(selected_branch)
        # git pull
        return await gitUtils.update()

    @classmethod
    async def checkForWrapperUpdate(cls) -> bool:
        """Check if there is an exegol wrapper update available.
        Return true if an update is available."""
        logger.debug(f"Last wrapper update check: {DataCache().get_wrapper_data().metadata.get_last_check_text()}")
        # Skipping update check
        if DataCache().get_wrapper_data().metadata.is_outdated() and not OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.debug("Running update check")
            return await cls.__checkUpdate()
        return False

    @classmethod
    async def __checkUpdate(cls) -> bool:
        """Depending on the current version (dev or latest) the method used to find the latest version is not the same.
        For the stable version, the latest version is fetch from GitHub release.
        In dev mode, git is used to find if there is some update available."""
        isUpToDate = True
        remote_version = ""
        current_version = ConstantConfig.version
        async with ExegolStatus("Checking for wrapper update. Please wait.", spinner_style="blue"):
            if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE):
                # Dev version have a letter in the version code and must check updates via git
                logger.debug("Checking update using: dev mode")
                module = await ExegolModules().getWrapperGit(fast_load=True)
                if module.isAvailable:
                    isUpToDate = module.isUpToDate()
                    last_commit = module.get_latest_commit()
                    remote_version = "?" if last_commit is None else str(last_commit)[:8]
                    current_version = str(module.get_current_commit())[:8]
                else:
                    # If Exegol have not been installed from git clone. Auto-check update in this case is only available from mates release
                    logger.verbose("Auto-update checking is not available in the current context")
            else:
                # If there is no letter, it's a stable release, and we can compare faster with the latest git tag
                logger.debug("Checking update using: stable mode")
                try:
                    remote_version = WebRegistryUtils.getLatestWrapperRelease()
                    # On some edge case, remote_version might be None if there is problem
                    if remote_version is None:
                        raise CancelOperation
                    isUpToDate = cls.__compareVersion(remote_version)
                except CancelOperation:
                    # No internet, postpone update check
                    return False

        if not isUpToDate:
            await cls.__tagUpdateAvailable(remote_version, current_version)
        cls.__updateLastCheckTimestamp()
        return not isUpToDate

    @classmethod
    def __updateLastCheckTimestamp(cls) -> None:
        """Update the last_check metadata timestamp with the current date to avoid multiple update checks."""
        DataCache().get_wrapper_data().metadata.update_last_check()
        DataCache().save_updates()

    @classmethod
    def __compareVersion(cls, version: str) -> bool:
        """Compare a remote version with the current one to check if a new release is available."""
        isUpToDate = True
        try:
            for i in range(len(version.split('.'))):
                remote = int(version.split('.')[i])
                local = int(ConstantConfig.version.split('.')[i])
                if remote > local:
                    isUpToDate = False
                    break
        except ValueError:
            logger.warning(f'Unable to parse Exegol version : {version} / {ConstantConfig.version}')
        return isUpToDate

    @classmethod
    async def __get_current_version(cls) -> str:
        """Get the current version of the exegol wrapper. Handle dev version and release stable version depending on the current version."""
        current_version = ConstantConfig.version
        if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE) and ConstantConfig.git_source_installation:
            module = await ExegolModules().getWrapperGit(fast_load=True)
            if module.isAvailable:
                current_version = str(module.get_current_commit())[:8]
        return current_version

    @staticmethod
    async def display_current_version() -> str:
        """Get the current version of the exegol wrapper. Handle dev version and release stable version depending on the current version."""
        version_details = ""
        if ConstantConfig.git_source_installation:
            module = await ExegolModules().getWrapperGit(fast_load=True)
            if module.isAvailable:
                current_branch = module.getCurrentBranch()
                commit_version = ""
                if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE):
                    commit_version = "-" + str(module.get_current_commit())[:8]
                if current_branch is None:
                    current_branch = "HEAD"
                if current_branch != "master" or commit_version != "":
                    version_details = f" [bright_black]\\[{current_branch}{commit_version}][/bright_black]"
        return f"[blue]v{ConstantConfig.version}[/blue]{version_details}"

    @classmethod
    async def __tagUpdateAvailable(cls, latest_version: str, current_version: Optional[str] = None) -> None:
        """Update the 'update available' cache data."""
        DataCache().get_wrapper_data().last_version = latest_version
        DataCache().get_wrapper_data().current_version = (await cls.__get_current_version()) if current_version is None else current_version

    @classmethod
    async def isUpdateAvailable(cls) -> bool:
        """Check if the cache file is present to announce an available update of the exegol wrapper."""
        current_version = await cls.__get_current_version()
        wrapper_data = DataCache().get_wrapper_data()
        # Check if a latest version exist and if the current version is the same, no external update had occurred
        if wrapper_data.last_version != current_version and wrapper_data.current_version == current_version:
            return True
        else:
            # If the version changed, exegol have been updated externally (via pip for example)
            if wrapper_data.current_version != current_version:
                await cls.__untagUpdateAvailable(current_version)
            return False

    @classmethod
    def display_latest_version(cls) -> str:
        last_version = DataCache().get_wrapper_data().last_version
        if len(last_version) == 8 and '.' not in last_version:
            return f"[bright_black]\\[{last_version}][/bright_black]"
        return f"[blue]v{last_version}[/blue]"

    @classmethod
    async def __untagUpdateAvailable(cls, current_version: Optional[str] = None) -> None:
        """Reset the latest version to the current version"""
        if current_version is None:
            current_version = await cls.__get_current_version()
        DataCache().get_wrapper_data().last_version = current_version
        DataCache().get_wrapper_data().current_version = current_version
        DataCache().save_updates()

    @classmethod
    async def __buildSource(cls, build_name: Optional[str] = None) -> str:
        """build user process :
        Ask user is he want to update the git source (to get new& updated build profiles),
        User choice a build name (if not supplied)
        User select the path to the dockerfiles (only from CLI parameter)
        User select a build profile
        Start docker image building
        Return the name of the built image"""
        # Selecting the default path
        # Don't force update source if using a custom build_path
        # Resolved once: resolve() is not memoised, so two reads could disagree.
        requested_build_path = OptionResolver().get(OptionKey.BUILD_PATH)
        if requested_build_path is None:
            build_path = Path(OptionResolver().get(OptionKey.EXEGOL_IMAGES_PATH))
            # Ask to update git
            try:
                # Install sources and check for update available
                source_git = await ExegolModules().getSourceGit()
                if source_git.isAvailable and not source_git.isUpToDate() and \
                        await ExegolRich.Confirm("Do you want to update image sources (in order to update local build profiles)?", default=True):
                    await cls.updateImageSource()
            except CancelOperation:
                logger.critical("An error prevented exegol from downloading the sources for building a local image.")
            except AssertionError:
                # Catch None git object assertions (from isUpToDate method)
                logger.warning("Git update is [orange3]not available[/orange3]. Skipping.")
        else:
            build_path = EnvInfo.expand_user(requested_build_path).absolute()
            # Check if we have a directory or a file to select the project directory
            if not build_path.is_dir():
                build_path = build_path.parent
            # Check if there is Dockerfile profiles
            if not ((build_path / "Dockerfile").is_file() or len(list(build_path.glob("*.dockerfile"))) > 0):
                logger.critical(f"The directory {build_path} doesn't contain any [green]Dockerfile[/green] or [green]*.dockerfile[/green] build profile.")

        # Choose tag name
        blacklisted_build_name = ["stable", "full", "nightly", "ad", "web", "light", "osint", "free"]
        while build_name is None or build_name in blacklisted_build_name or True in [build_name.startswith(x + '-') for x in blacklisted_build_name]:
            if build_name is not None:
                logger.error("This name is reserved and cannot be used for local build. Please choose another one.")
            build_name = await ExegolRich.Ask("Choose a name for the new local image",
                                              default="local")

        # Choose dockerfiles path
        logger.debug(f"Using {build_path} as path for dockerfiles")

        # Choose dockerfile
        profiles = cls.listBuildProfiles(profiles_path=build_path)
        if len(profiles) == 0:
            logger.critical(f"No build profile found in {build_path}. Check your exegol installation, it seems to be broken...")
        # resolver-exempt: positional selecting a Dockerfile stage, not a container-shape default; permanently in RESOLVER_EXCLUDED.
        build_profile: Optional[str] = ParametersManager().build_profile
        build_dockerfile: Optional[str] = None
        if build_profile is not None:
            build_dockerfile = profiles.get(build_profile)
            if build_dockerfile is None:
                logger.error(f"Build profile {build_profile} not found.")
        if build_dockerfile is None:
            build_profile, build_dockerfile = cast(Tuple[str, str], await ExegolTUI.selectFromList(profiles,
                                                                                                   subject="a build profile",
                                                                                                   title="[not italic]:dog: [/not italic][gold3]Build profiles[/gold3]"))
        logger.debug(f"Using {build_profile} build profile ({build_dockerfile})")
        # Docker Build
        await DockerUtils().buildImage(tag=build_name, build_profile=build_profile, build_dockerfile=build_dockerfile, dockerfile_path=build_path.as_posix())
        return build_name

    @classmethod
    async def buildAndLoad(cls, load_after_build: bool) -> Optional[ExegolImage]:
        """Build an image and load it"""
        # Not a creation path either, so the profile tier is never installed here.
        build_name = await cls.__buildSource(OptionResolver().get(OptionKey.IMAGE_TAG))
        if load_after_build:
            return await DockerUtils().getInstalledImage(build_name, ConstantConfig.COMMUNITY_IMAGE_NAME)
        return None

    @classmethod
    def listBuildProfiles(cls, profiles_path: Path) -> Dict:
        """List every build profiles available locally
        Return a dict of options {"key = profile name": "value = dockerfile full name"}"""
        # Default stable profile
        profiles = {}
        if (profiles_path / "Dockerfile").is_file():
            profiles["full"] = "Dockerfile"
        # List file *.dockerfile is the build context directory
        logger.debug(f"Loading build profile from {profiles_path}")
        docker_files = list(profiles_path.glob("*.dockerfile"))
        for file in docker_files:
            # Convert every file to the dict format
            filename = file.name
            profile_name = filename.replace(".dockerfile", "")
            profiles[profile_name] = filename
        logger.debug(f"List docker build profiles : {profiles}")
        return profiles

    @classmethod
    async def listGitStatus(cls) -> Sequence[Dict[str, str]]:
        """Get status of every git modules"""
        result = []
        gits = [await ExegolModules().getSourceGit(fast_load=True, skip_install=True),
                await ExegolModules().getResourcesGit(fast_load=True, skip_install=True)]
        if ConstantConfig.git_source_installation:
            gits.insert(0, await ExegolModules().getWrapperGit(fast_load=True))
        if SessionHandler().has_feature(LicenseFeature.Sentinel):
            gits.append(await ExegolModules().getSentinelCoreGit(fast_load=True, skip_install=True))

        async with ExegolStatus(f"Loading module information", spinner_style="blue") as s:
            for git in gits:
                s.update(status=f"Loading module [green]{git.getName()}[/green] information")
                status = "[bright_black]Unknown[/bright_black]" if OptionResolver().get(OptionKey.OFFLINE_MODE) else git.getTextStatus()
                branch = git.getCurrentBranch()
                if branch is None:
                    if "not supported" in status or "Not installed" in status:
                        branch = "[bright_black]N/A[/bright_black]"
                    else:
                        branch = "[bright_black][g]? :person_shrugging:[/g][/bright_black]"
                result.append({"name": git.getName().capitalize(),
                               "status": status,
                               "current branch": branch})
        return result
