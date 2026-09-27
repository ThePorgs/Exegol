import binascii
import logging
import os
from asyncio import gather
from typing import TYPE_CHECKING, Any, Callable, Union, List, NamedTuple, Tuple, Optional, cast, Sequence, Type

from rich.markup import escape

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import CREATION_ONLY_WARNING_SURFACE, OptionKey, OptionResolver, OptionScope
from exegol.config.UserConfig import UserConfig
from exegol.console.cli.OptionsEnum import SentinelUpdateStrategy
from exegol.config.StaticContainerPath import StaticContainerPath
from exegol.console import ConsoleFormat
from exegol.console.ConsoleFormat import boolFormatter
from exegol.console.ExegolPrompt import ExegolRich, stdinCanAnswer
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.manager.LicenseManager import LicenseManager
from exegol.manager.TaskManager import TaskManager
from exegol.manager.UpdateManager import UpdateManager
from exegol.model.ContainerProfileSelectable import ContainerProfileSelectable
from exegol.model.ExegolContainer import ExegolContainer
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.model.LicensesTypes import LicenseFeature
from exegol.model.SelectableInterface import SelectableInterface
from exegol.profile.ProfileAskUser import ask_user_for_value
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.SessionHandler import SessionHandler

if TYPE_CHECKING:
    # Type-checking only: importing exegol.profile at runtime would read UserConfig() at
    # import time for every command, so runtime imports stay function-local.
    from exegol.profile.ContainerProfile import ContainerProfile
    from exegol.profile.ProfileManagerBase import ProfileManagerBase


class ExegolManager:
    """Contains the main procedures of all actions available in Exegol"""

    # Cache data
    __container: Union[Optional[ExegolContainer], List[ExegolContainer]] = None
    __image: Union[Optional[ExegolImage], List[ExegolImage]] = None
    # Container profile resolved from `exegol start --profile`, injected by __createContainer().
    __resolved_profile: Optional["ContainerProfile"] = None
    # Its name, kept separately because ContainerProfile does not carry it.
    __resolved_profile_name: Optional[str] = None

    # Runtime default configuration
    __interactive_mode = False

    # Label for the unfetched-source prompt, shared with UpdateManager.updateProfileSources().
    __PROFILE_SOURCE_LABEL = "container profile"

    @classmethod
    async def info(cls) -> None:
        """Print the requested info sections in a fixed order, whatever the flag order.

        Order: config, sources, profile, sentinel, images, containers. Flags combine as a
        union and `--all` wins. A named section replaces the default images + containers
        pair; the container positional adds its recap to any section request.
        """
        # `--all` is OR-ed into every section decision below.
        info_all = bool(OptionResolver().get(OptionKey.INFO_ALL))
        # The log level only changes how sections render, never which ones run.
        want_config = info_all or bool(OptionResolver().get(OptionKey.INFO_CONFIG))
        want_sources = info_all or bool(OptionResolver().get(OptionKey.INFO_SOURCES))
        # Profile selectors carry a value: bare lists, `NAME` narrows to one entry.
        # resolver-exempt: selector, not a value — `--profile` picks which profile supplies the profile tier, so resolving it through that tier is circular.
        profile_selection = ParametersManager().profile
        # resolver-exempt: selector, not a value — on `exegol info`, `--sentinel` names which Sentinel profile to describe; resolving it through the profile tier would be circular, and no container is built here.
        sentinel_selection = ParametersManager().sentinel
        want_profile = info_all or profile_selection is not None
        want_sentinel = info_all or sentinel_selection is not None
        # The container positional is a target, not a section: it composes with section
        # requests (`exegol info demo --config` shows both).
        # resolver-exempt: positional, not a flag — `containertag` has no argparse dest and names which container to act on.
        named_container = ParametersManager().containertag
        show_recap = bool(named_container)
        # A named section replaces the default images + containers pair; `--all` restores it.
        want_default = info_all or not (want_config or want_sources or want_profile or want_sentinel)

        if want_config:
            logger.verbose("Listing user configurations")
            ExegolTUI.printTable(UserConfig().get_configs(), title="[not italic]:brain: [/not italic][gold3][g]User configurations[/g][/gold3]")

        if want_sources:
            logger.verbose("Listing git repositories")
            ExegolTUI.printTable(await UpdateManager.listGitStatus(), title="[not italic]:octopus: [/not italic][gold3][g]Project sources[/g][/gold3]")

        if want_profile:
            # Presence test, not `or`: `--profile ""` must stay '' so the blank-name guard fires.
            # `silent`: a broad request (`--all`) stays quiet, a named one explains a refusal.
            await cls.__printContainerProfiles(
                profile_selection if profile_selection is not None else True, silent=info_all)

        if want_sentinel:
            # Same presence test and `silent` rule as above.
            await cls.__printSentinelProfileSelection(
                sentinel_selection if sentinel_selection is not None else True, silent=info_all)

        if want_default:
            # A named container shows its recap instead of the container table; the image
            # table is still shown under `--all`.
            show_images = info_all or not show_recap
            if show_images:
                # Fetch data. `add_task` and `gather` must stay adjacent in this branch: tasks are
                # class-level, so an abandoned one would leak into the next `info()`.
                TaskManager.add_task(
                    DockerUtils().listImages(include_version_tag=False, include_custom=True),
                    TaskManager.TaskId.ImageList)
                TaskManager.add_task(
                    DockerUtils().listContainers(with_size=logger.isEnabledFor(ExeLog.VERBOSE)),
                    TaskManager.TaskId.ContainerList)
                images, containers = await TaskManager.gather(TaskManager.TaskId.ImageList, TaskManager.TaskId.ContainerList)
                # List and print images
                # Resolved once so the colour and the name describe the same architecture.
                arch = OptionResolver().get(OptionKey.ARCH)
                color = ConsoleFormat.getArchColor(arch)
                logger.verbose(f"Listing local and remote Exegol images (filtering for architecture [{color}]{arch}[/{color}])")
                ExegolTUI.printTable(images)
                if not show_recap:
                    # List and print containers
                    logger.verbose("Listing local Exegol containers")
                    logger.raw(f"[bold blue][*][/bold blue] Number of Exegol containers: {len(containers)}{os.linesep}",
                               markup=True)
                    ExegolTUI.printTable(containers)
        # Outside `want_default` so a section request does not drop the named container; last
        # to keep the canonical order.
        if show_recap:
            # If the user have supplied a container name, show container config
            container = await cls.__loadOrCreateContainer(named_container, must_exist=True)
            if container is not None and isinstance(container, ExegolContainer):
                await ExegolTUI.printContainerRecap(container)

    @classmethod
    async def start(cls) -> None:
        """Create and/or start an exegol container to finally spawn an interactive shell"""
        # Check if the first positional parameter have been supplied
        # resolver-exempt: positional, not a flag — `containertag` has no argparse dest and names which container to start.
        cls.__interactive_mode = not bool(ParametersManager().containertag)
        if not cls.__interactive_mode:
            logger.info("Skipping interactive mode (arguments supplied)")
        # resolver-exempt: selector, not a value — `--profile` picks which profile supplies the profile tier, so resolving it through that tier is circular.
        profile_selection = ParametersManager().profile
        # None means the flag was not typed. Empty or unknown names are handled by the picker
        # fallback in __resolveProfileSelection().
        if profile_selection is not None:
            resolved, resolved_name = await cls.__resolveProfileSelection(profile_selection)
            # Assign both together so the name and the profile never diverge.
            if resolved is not None:
                cls.__resolved_profile = resolved
                cls.__resolved_profile_name = resolved_name
        container = await cls.__loadOrCreateContainer()
        assert container is not None and type(container) is ExegolContainer
        if not container.isNew():
            # A profile is ignored entirely for an existing container, never partially applied.
            cls.__warnProfileIgnored(container.name)
            # Check and warn user if some parameters don't apply to the current session
            cls.__checkUselessParameters()
        await gather(
            container.start(),
            TaskManager.wait_for_all())
        await container.spawnShell()

    @classmethod
    async def upgrade(cls) -> None:
        """Upgrade exegol to the latest version"""
        # Await the licence load before reading the tier, or a valid Pro licence still
        # needing a refresh would be denied.
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        if not SessionHandler().pro_feature_access():
            logger.critical(SessionHandler.pro_access_message("upgrade"))
        container = await cls.__loadOrCreateContainer(multiple=True, must_exist=True, filters=[ExegolContainer.Filters.OUTDATED])
        assert container is not None and type(container) is list
        for c in container:
            try:
                previous_image = c.image
                await cls.__backupAndUpgrade(c)

                # If the image used is deprecated, it must be deleted after the removal of its container
                # Dest-less option read from config.yml (its profile tier is always empty).
                if previous_image.isLocked() and OptionResolver().get(OptionKey.AUTO_REMOVE_IMAGES):
                    await DockerUtils().removeImage(previous_image, upgrade_mode=True, silent_error=True)
            except CancelOperation:
                logger.error(f"Something unexpected happened during the [green]{c.name}[/green] container upgrade process.")

    @classmethod
    async def exec(cls) -> None:
        """Create and/or start an exegol container to execute a specific command.
        The execution can be seen in console output or be relayed in the background as a daemon."""
        # Resolved once into locals: resolve() is not memoised, so repeated reads could disagree.
        use_tmp_container = OptionResolver().get(OptionKey.TMP)
        selector = OptionResolver().get(OptionKey.SELECTOR)
        as_daemon = OptionResolver().get(OptionKey.DAEMON)
        command = OptionResolver().get(OptionKey.EXEC)
        if use_tmp_container:
            container = await cls.__createTmpContainer(selector)
            if not as_daemon:
                await container.exec(command=command, as_daemon=False, is_tmp=True)
                await container.stop(timeout=2)
            else:
                # Command is passed at container creation in __createTmpContainer()
                logger.success(f"Command executed as entrypoint of the container {container.getDisplayName()}")
        else:
            container = cast(ExegolContainer, await cls.__loadOrCreateContainer(override_container=selector))
            await container.exec(command=command, as_daemon=as_daemon)

    @classmethod
    async def stop(cls) -> None:
        """Stop an exegol container"""
        logger.info("Stopping container(s)")
        container = await cls.__loadOrCreateContainer(multiple=True, must_exist=True, filters=[ExegolContainer.Filters.STARTED])
        assert container is not None and type(container) is list
        for c in container:
            await c.stop(timeout=5)

    @classmethod
    async def restart(cls) -> None:
        """Stop and start an exegol container"""
        container = cast(ExegolContainer, await cls.__loadOrCreateContainer(must_exist=True))
        if container:
            await container.stop(timeout=5)
            # Regenerate the Sentinel config from current host sources while the container is
            # stopped. Automatic for 'on_restart'; for 'disabled' only when --sentinel-refresh
            # is set. The strategy is read from the immutable label.
            if container.config.isSentinelEnable():
                # Read the Sentinel update strategy from the container metadata
                strategy = SentinelUpdateStrategy.from_value(container.config.getSentinelStrategy())
                if strategy == SentinelUpdateStrategy.ON_RESTART or OptionResolver().get(OptionKey.SENTINEL_REFRESH):
                    container.config.regenerateSentinelConfig()
                else:
                    logger.verbose(f"Sentinel: update strategy is '{SentinelUpdateStrategy.DISABLED.value}', keeping the cached config (use --sentinel-refresh to force)")
            await container.start()
            logger.success(f"Container [green]{container.name}[/green] successfully restarted!")
            await container.spawnShell()

    @classmethod
    async def install(cls) -> None:
        """Pull or build a docker exegol image"""
        try:
            if not await ExegolModules().isExegolResourcesReady():
                raise CancelOperation
        except CancelOperation:
            # Error during installation, skipping operation
            logger.warning("Exegol resources have not been downloaded, the feature cannot be enabled")
        await UpdateManager.updateImage(install_mode=True)

    @classmethod
    async def build(cls) -> None:
        """Build a docker exegol image"""
        await UpdateManager.buildAndLoad(load_after_build=False)

    @classmethod
    async def update(cls) -> None:
        """Update python wrapper (git installation required) and Pull a docker exegol image"""
        # Offline check first: every update target needs the network.
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.critical("Exegol cannot be updated without Internet access. Skipping.")

        update_wrapper = OptionResolver().get(OptionKey.UPDATE_WRAPPER)
        update_resources = OptionResolver().get(OptionKey.UPDATE_RESOURCES)
        update_sentinel = OptionResolver().get(OptionKey.UPDATE_SENTINEL)
        update_profile = OptionResolver().get(OptionKey.UPDATE_PROFILE)
        # Presence test: `-i` is None when absent, True when bare, else the tag, so
        # `--image ""` still counts as requested.
        update_image = OptionResolver().get(OptionKey.IMAGE_TAG) is not None

        # No target named means all of them; the chain order, not the flag order, applies.
        update_everything = not (update_wrapper or update_resources or update_sentinel
                                 or update_profile or update_image)

        if update_everything or update_wrapper:
            # A package-manager install has no checkout to pull. Only a named `--wrapper`
            # explains that (a bare `exegol update` stays quiet), as a warning so the other
            # targets still run. Checked here rather than in updateWrapper() since it is
            # about this request.
            if ConstantConfig.git_source_installation:
                await UpdateManager.updateWrapper()
            elif update_wrapper:
                logger.warning("The wrapper self-update requires a git-source installation. "
                               "This Exegol was installed with a package manager, so upgrade it the same way: "
                               "[magenta]pip install --upgrade exegol[/magenta], "
                               "[magenta]pipx upgrade exegol[/magenta] or [magenta]uv tool upgrade exegol[/magenta].")
        if update_everything or update_resources:
            # updateResources() itself refuses when resources are disabled in config.yml: the
            # config choice wins over the selector.
            await UpdateManager.updateResources()
        # The licence gate lives in the shared sync body; only whether its refusal is
        # printed is decided here (named target: explain, bare update: stay quiet).
        if update_everything or update_sentinel:
            await UpdateManager.updateSentinelSources(explain_refusal=update_sentinel)
        if update_everything or update_profile:
            await UpdateManager.updateProfileSources(explain_refusal=update_profile)
        if update_everything or update_image:
            # No tag argument: `updateImage()` reads OptionKey.IMAGE_TAG itself.
            await UpdateManager.updateImage()

    @classmethod
    async def uninstall(cls) -> None:
        """Remove an exegol image"""
        logger.info("Uninstalling image")
        # Set log level to verbose in order to show every image installed including the outdated.
        if not logger.isEnabledFor(ExeLog.VERBOSE):
            logger.setLevel(ExeLog.VERBOSE)
        images = await cls.__loadOrInstallImage(multiple=True, filters=[ExegolImage.Filters.INSTALLED])
        assert type(images) is list
        if len(images) == 0:
            return
        all_name = ", ".join([x.getName() for x in images])
        if not OptionResolver().get(OptionKey.FORCE_MODE) and not await ExegolRich.Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following images? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for img in images:
            await DockerUtils().removeImage(img)

    @classmethod
    async def remove(cls) -> None:
        """Remove an exegol container"""
        logger.info("Removing container(s)")
        containers = await cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        assert type(containers) is list
        if len(containers) == 0:
            logger.error("No containers were selected. Exiting.")
            return
        all_name = ", ".join([x.name for x in containers])
        # Force-mode reads are not shared: each guards a different confirmation.
        if not OptionResolver().get(OptionKey.FORCE_MODE) and not await ExegolRich.Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following containers? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for c in containers:
            # Check if containers have backups
            backup_history = c.getExistingBackupContainers()
            if len(backup_history) > 0:
                all_backup_names = ', '.join([x[1] for x in backup_history])
                if OptionResolver().get(OptionKey.FORCE_MODE):
                    logger.info(f"The container [green]{c.name}[/green] has [green]{len(backup_history)}[/green] backup containers that will be removed too [orange3][ {all_backup_names} ][/orange3]")
                elif not await ExegolRich.Confirm(f"The container [green]{c.name}[/green] has [green]{len(backup_history)}[/green] backup containers [orange3][ {all_backup_names} ][/orange3], do you want to remove them too?", default=True):
                    logger.critical("Cannot remove container without also removing its backups. Aborting.")

            await c.remove(backup_history=[x[0] for x in backup_history])
            # If the image used is deprecated, it must be deleted after the removal of its container
            if c.image.isLocked() and OptionResolver().get(OptionKey.AUTO_REMOVE_IMAGES):
                await DockerUtils().removeImage(c.image, upgrade_mode=True)

    @classmethod
    async def activate(cls) -> None:
        """Activate an exegol license"""
        licence_manager = await LicenseManager.get()
        if OptionResolver().get(OptionKey.REVOKE):
            await licence_manager.revoke_exegol()
        elif licence_manager.is_activated():
            licence_manager.display_license()
            logger.success("Exegol is activated")
        else:
            await licence_manager.activate_exegol(skip_prompt=True)

    @classmethod
    async def completion(cls) -> None:
        """Print the shell completion script of the exegol wrapper"""
        import argcomplete
        shell = OptionResolver().get(OptionKey.SHELL_TYPE)
        if shell is None:
            # Auto-detect the user's shell from its environment
            shell = os.path.basename(EnvInfo.get_user_shell() or "")
            if shell not in ("bash", "zsh", "fish", "tcsh"):
                shell = "bash"
            logger.info(f"No shell supplied, using the auto-detected shell: [green]{shell}[/green]")
        logger.info(f"Add the following script to your shell configuration, "
                    f"check [green]exegol completion -h[/green] for ready-to-use commands.")
        # Using a raw print here: the rich console would wrap and colorize the shell script and corrupt it
        print(argcomplete.shellcode(["exegol"], shell=shell, use_defaults=False))

    @classmethod
    async def print_version(cls) -> None:
        """Show exegol version (and context configuration on debug mode)"""

        logger.raw(f"[bold blue][*][/bold blue] Exegol {SessionHandler().get_license_type_display()} is currently in version {await UpdateManager.display_current_version()}{os.linesep}",
                   level=logging.INFO, markup=True)
        await LicenseManager.get()
        logger.raw(
            f"[bold magenta][*][/bold magenta] More about Exegol at: [underline magenta]{ConstantConfig.landing}[/underline magenta]{os.linesep}",
            level=logging.INFO, markup=True)

        if 'a' in ConstantConfig.version:
            logger.empty_line()
            logger.warning("You are currently using an [red]Alpha[/red] version of Exegol, which may be unstable. "
                           "This version is a work in progress and bugs are expected.")
        elif 'b' in ConstantConfig.version:
            logger.empty_line()
            logger.warning("You are currently using a [orange3]Beta[/orange3] version of Exegol, which may be unstable.")

    @classmethod
    async def print_debug_banner(cls) -> None:
        """Print header debug info"""
        package_engine = "pip"
        if ConstantConfig.pipx_installed:
            package_engine = "pipx"
        elif ConstantConfig.uv_installed:
            package_engine = "uv"
        logger.debug(f"Pip installation: {boolFormatter(ConstantConfig.pip_installed)} [bright_black]({package_engine})[/bright_black]")
        logger.debug(f"Git source installation: {boolFormatter(ConstantConfig.git_source_installation)}")
        logger.debug(f"Host OS: {EnvInfo.getHostOs().value} [bright_black]({EnvInfo.getDockerEngine().value})[/bright_black]")
        logger.debug(f"Arch: {EnvInfo.arch}")
        if EnvInfo.arch != EnvInfo.raw_arch:
            logger.debug(f"Raw arch: {EnvInfo.raw_arch}")
        if EnvInfo.isWindowsHost():
            logger.debug(f"Windows release: {EnvInfo.getWindowsRelease()}")
            logger.debug(f"Python environment: {EnvInfo.current_platform}")
            logger.debug(f"Docker engine: {EnvInfo.getDockerEngine().value}")
        logger.debug(f"Docker desktop: {boolFormatter(EnvInfo.isDockerDesktop())}")
        logger.debug(f"Shell type: {EnvInfo.getShellType()}")
        if OptionResolver().get(OptionKey.AUTO_CHECK_UPDATES):
            await UpdateManager.checkForWrapperUpdate()
        if await UpdateManager.isUpdateAvailable():
            logger.empty_line()
            update_message = f"An [green]Exegol[/green] update is [orange3]available[/orange3] ({await UpdateManager.display_current_version()} :arrow_right: {UpdateManager.display_latest_version()})"
            if ConstantConfig.git_source_installation:
                if UserConfig().interactive_update_warning:
                    if await ExegolRich.Confirm(f"{update_message}, do you want to update ?", default=True):
                        await UpdateManager.updateWrapper()
                else:
                    logger.warning(update_message)
            else:
                logger.info(update_message)
                if ConstantConfig.pipx_installed:
                    update_command = "You can update your exegol wrapper with the command [green]pipx upgrade exegol[/green]"
                elif ConstantConfig.uv_installed:
                    update_command = "You can update your exegol wrapper with the command [green]uv tool upgrade exegol[/green]"
                elif ConstantConfig.pip_installed:
                    update_command = "If you have installed Exegol with pip, update with the command [green]pip3 install exegol --upgrade[/green]"
                else:
                    update_command = "Installation method not found (not among pip/pipx/uv/sources). You should update your wrapper manually."
                if update_command:
                    if UserConfig().interactive_update_warning:
                        await ExegolRich.Acknowledge(update_command)
                    else:
                        logger.warning(update_command)
        else:
            logger.empty_line(log_level=logging.DEBUG)

    #: Facts that differ between `exegol info --profile` and `--sentinel`; the rest is
    #: shared by __printProfileSurface().
    class _ProfileSurface(NamedTuple):
        noun: str                          # "container profile" / "Sentinel profile"
        flag: str                          # the CLI flag, for the name-required error
        emoji: str                         # table-title icon
        title: str                         # "Container profile" / "Sentinel profile", title case
        fetch_label: str                   # label the fetch prompt words itself with
        empty_hint: str                    # what to drop in component_path to create one
        declares_noun: str                 # "option" / "rule", for the empty-detail message
        # Typed against the base so mypy checks the calls made by the shared body.
        build: Callable[[], "ProfileManagerBase[Any]"]
        fetch: Callable[..., Any]          # the fetch-only entrypoint (never a pruning one)

    @classmethod
    async def __printProfileSurface(cls, surface: "ExegolManager._ProfileSurface",
                                    selection: Union[bool, str], silent: bool = False) -> None:
        """Handle `exegol info <flag> [name]`: list every profile, or show one.

        Shared by both profile kinds: per-kind data lives in :class:`_ProfileSurface`, and
        rendering in each manager's ``list_rows()`` / ``describe()``. A ``True`` selection
        lists. ``silent`` marks a broad request (``--all``) and only affects the fetch prompt.

        The licence gate stays in each caller.
        """
        # `<flag> ""` is explicitly set: do not fall into list mode.
        if selection is not True and not str(selection).strip():
            logger.error(f"A {surface.noun} name is required: use `exegol info {surface.flag}` with no "
                         f"value to list every available profile.")
            return
        try:
            manager = surface.build()
            manager.load_profiles()
        except Exception as e:
            # A read-only listing must never kill the CLI over one bad file on disk.
            logger.debug(f"Skipping {surface.noun} listing: {e}")
            return
        # Offer to fetch declared but missing git sources, then resume the listing. Outside the
        # try above: a fetch failure is reported and the pre-fetch state still prints.
        # `--all` skips the prompt only when stdin cannot answer it (unattended runs).
        if not (silent and not stdinCanAnswer()):
            try:
                if await UpdateManager.promptFetchMissingSources(manager.missing_git_source_roots(),
                                                                 surface.fetch_label,
                                                                 surface.fetch):
                    manager.load_profiles()
            except Exception as e:
                logger.error(f"{surface.title} source fetch failed: {e}")
        if selection is True:
            rows = manager.list_rows()
            if not rows:
                # Name the directory to create, from the manager's actual path.
                logger.info(f"No {surface.noun}s available yet. {surface.empty_hint} in "
                            f"{manager.component_path / ConstantConfig.DEFAULT_LOCAL_SOURCE_KEY} to create one.")
                return
            ExegolTUI.printTable(rows, title=f"[not italic]{surface.emoji} [/not italic][gold3][g]{surface.title}s[/g][/gold3]")
            return
        profile = manager.get_profile(str(selection))
        if profile is None:
            # get_profile already said why; add the names that do exist.
            available = [f"{source_key}.{name}"
                         for source_key, mapping in manager.get_namespaced_profiles().items()
                         for name in mapping]
            if available:
                logger.info(f"Available {surface.noun}s: {', '.join(available)}")
            return
        # `selection` is operator-typed: escape it for the logger and the title.
        safe_selection = escape(str(selection))
        title = f"[not italic]{surface.emoji} [/not italic][gold3][g]{surface.title}: {safe_selection}[/g][/gold3]"
        # The manager decides both emptiness (None) and the best shape to render.
        detail = manager.describe(profile, title)
        if detail is None:
            logger.info(f"{surface.title} '{safe_selection}' declares no {surface.declares_noun}.")
            return
        ExegolTUI.printRenderable(detail)

    @classmethod
    async def __printSentinelProfileSelection(cls, selection: Union[bool, str], silent: bool = False) -> None:
        """`exegol info --sentinel [name]`, gated on the Sentinel feature rather than the tier."""

        # Await before the feature read: a session without a cached JWT has no features yet.
        # `clean_task=False` keeps the task awaitable by the other gate sites.
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        if not SessionHandler().has_feature(LicenseFeature.Sentinel):
            # A broad request (`--all`) stays quiet, a named one explains the refusal. The
            # return stays unconditional either way.
            if not silent:
                logger.warning(SessionHandler.feature_access_message("Sentinel"))
            return

        def build() -> "ProfileManagerBase[Any]":
            # Function-local import: avoids reading UserConfig() at import time.
            from exegol.sentinel.SentinelProfileManager import SentinelProfileManager
            return SentinelProfileManager()

        await cls.__printProfileSurface(cls._ProfileSurface(
            noun="Sentinel profile",
            flag="--sentinel",
            emoji=":shield:",
            title="Sentinel profile",
            fetch_label="Sentinel",
            empty_hint="Drop a YAML file declaring a 'profiles:' block",
            declares_noun="rule",
            build=build,
            fetch=UpdateManager.fetchSentinelSources,
        ), selection, silent=silent)

    @classmethod
    async def __printContainerProfiles(cls, selection: Union[bool, str], silent: bool = False) -> None:
        """`exegol info --profile [name]`, gated on the Pro tier (warn and return)."""

        # Await before the tier read, for the reason the Sentinel half states.
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        if not SessionHandler().pro_feature_access():
            # A broad request stays quiet, a named one explains; the return is unconditional.
            if not silent:
                logger.warning(SessionHandler.pro_access_message("container profile"))
            return

        def build() -> "ProfileManagerBase[Any]":
            # Function-local import, same reason as the Sentinel half.
            from exegol.profile.ContainerProfileManager import ContainerProfileManager
            return ContainerProfileManager()

        await cls.__printProfileSurface(cls._ProfileSurface(
            noun="container profile",
            flag="--profile",
            emoji=":gear:",
            title="Container profile",
            fetch_label=cls.__PROFILE_SOURCE_LABEL,
            empty_hint="Drop a YAML file",
            declares_noun="option",
            build=build,
            fetch=UpdateManager.fetchProfileSources,
        ), selection, silent=silent)

    @classmethod
    async def __resolveProfileSelection(cls, selection: str) -> Tuple[Optional["ContainerProfile"], Optional[str]]:
        """Resolve `exegol start --profile <name>` to ``(profile, name)``, or exit.

        An empty or unknown name falls back to the picker when stdin can answer, otherwise
        it is fatal. The picker never resolves to "no profile", so a typo cannot create a
        container without the requested shape. Missing git sources are offered for fetch
        before a name is declared unknown. The name is returned because ``ContainerProfile``
        does not carry it.
        """
        # Licence gate first, so it covers every path including the picker fallbacks. Await
        # the licence load before reading the tier; `clean_task=False` keeps it awaitable by
        # the gate in info(). The explicit returns matter when the fatal logger does not exit
        # (`setCriticalMethod("raise")` or tests).
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        if not SessionHandler().pro_feature_access():
            logger.critical(SessionHandler.pro_access_message("container profile"))
            return None, None
        # `--profile ""` is explicitly set but not a name: picker fallback 1 of 2.
        if not str(selection).strip():
            if stdinCanAnswer():
                return await cls.__pickContainerProfile()
            # Off a terminal: same guard as `exegol info --profile ""`.
            logger.error("A container profile name is required: `exegol start --profile <name>` selects a "
                         "named container profile. Run `exegol info --profile` to list the available ones.")
            logger.critical("A container profile name is required.")
            return None, None
        # Function-local import: avoids reading UserConfig() at import time.
        from exegol.profile.ContainerProfileManager import ContainerProfileManager
        cpm = ContainerProfileManager()
        cpm.load_profiles()
        # The profile may live in a declared but unfetched source: offer to fetch, then retry.
        if await UpdateManager.promptFetchMissingSources(cpm.missing_git_source_roots(),
                                                         cls.__PROFILE_SOURCE_LABEL,
                                                         UpdateManager.fetchProfileSources):
            cpm.load_profiles()
        profile = cpm.get_profile(str(selection))
        if profile is None:
            # Picker fallback 2 of 2, after the fetch prompt. `selection` is operator-typed.
            if stdinCanAnswer():
                logger.warning(f"Container profile '{escape(str(selection))}' not found. "
                               f"Pick one of the profiles below.")
                return await cls.__pickContainerProfile()
            # get_profile already said why; add the names that do exist, then exit.
            available = [f"{source_key}.{name}"
                         for source_key, mapping in cpm.get_namespaced_profiles().items()
                         for name in mapping]
            detail = (f"Available container profiles: {escape(', '.join(available))}." if available
                      else "No container profiles are available.")
            logger.critical(f"Container profile '{escape(str(selection))}' not found. {detail}")
            return None, None
        return profile, str(selection)

    @classmethod
    async def __pickContainerProfile(cls) -> Tuple[Optional["ContainerProfile"], Optional[str]]:
        """Let the operator pick one of the discovered profiles.

        Only reached from __resolveProfileSelection()'s fallbacks. There is no "none" choice
        and an empty profile directory is fatal, so a container is never created without the
        requested profile.
        """
        # Function-local import: avoids reading UserConfig() at import time.
        from exegol.profile.ContainerProfileManager import ContainerProfileManager
        cpm = ContainerProfileManager()
        cpm.load_profiles()
        # Offer to fetch missing git sources before concluding there are no profiles.
        if await UpdateManager.promptFetchMissingSources(cpm.missing_git_source_roots(),
                                                         cls.__PROFILE_SOURCE_LABEL,
                                                         UpdateManager.fetchProfileSources):
            cpm.load_profiles()
        profiles_by_source = cpm.get_namespaced_profiles()
        if not profiles_by_source:
            # Name the directory from the manager's actual path (escaped: paths may hold brackets).
            logger.critical(f"No container profiles found in {escape(str(cpm.component_path))}. Create one first.")
            return None, None
        # wrapNamespaced() qualifies only names defined by several sources and keeps the sorted
        # order; render_source colours the Source column like `exegol info --profile`.
        wrapped = ContainerProfileSelectable.wrapNamespaced(profiles_by_source, cpm.render_source)
        selected = cast(ContainerProfileSelectable,
                        await ExegolTUI.selectFromTable(wrapped,
                                                        object_type=ContainerProfileSelectable,
                                                        allow_none=False))
        # getKey(), not .name: an ambiguous bare name would be rejected by the start path.
        return selected.profile, selected.getKey()

    @classmethod
    def __warnProfileIgnored(cls, container_name: str) -> None:
        """Warn that `--profile` was ignored because the container already exists.

        One generic line, no per-option diff. start() then proceeds normally: the profile
        tier was never installed.
        """
        if cls.__resolved_profile is None:
            return
        logger.warning(f'Profile "{escape(str(cls.__resolved_profile_name))}" was passed but ignored: '
                       f'container "{escape(container_name)}" already exists. '
                       f'Profiles only apply at container creation.')

    @classmethod
    async def __loadOrInstallImage(cls,
                                   override_image: Optional[str] = None,
                                   multiple: bool = False,
                                   show_custom: bool = False,
                                   filters: Optional[List[ExegolImage.Filters]] = None) -> Union[Optional[ExegolImage], List[ExegolImage]]:
        """Select / Load (and install) an ExegolImage
        When multiple is set to True, return a list of ExegolImage
        When the action supports multi selection, the parameter filters must be supplied
        When filters include ExegolImage.Filters.INSTALLED, return None if no image are installed
        Otherwise, always return an ExegolImage"""
        if cls.__image is not None:
            # Return cache
            return cls.__image
        must_exist = filters is not None and ExegolImage.Filters.INSTALLED in filters
        # Resolver read: on the start path the profile tier is installed by now, so a
        # profile's `image.tag` applies when no tag was typed.
        image_tag = override_image if override_image is not None else OptionResolver().get(OptionKey.IMAGE_TAG)
        # resolver-exempt: positional target list, not a flag — `multiimagetag` has no argparse dest and selects which images to act on.
        image_tags = ParametersManager().multiimagetag
        image_selection: Union[Optional[ExegolImage], List[ExegolImage]] = None
        # While an image have not been selected
        while image_selection is None:
            try:
                if image_tag is None and (image_tags is None or len(image_tags) == 0):
                    image_list: List[ExegolImage] = await DockerUtils().listImages(include_custom=show_custom)
                    if filters is not None:
                        filters_sum = sum(filters)
                        image_list = [i for i in image_list if i.filter(filters_sum)]

                    if OptionResolver().get(OptionKey.SELECT_ALL):
                        image_selection = image_list
                    else:
                        # Interactive (TUI) image selection
                        image_selection = cast(Union[Optional[ExegolImage], List[ExegolImage]],
                                               await cls.__interactiveSelection(ExegolImage, image_list, multiple))
                else:
                    # Select image by tag name (non-interactive)
                    if multiple:
                        image_selection = []
                        for image_tag in image_tags:
                            image_selection.append(await DockerUtils().getInstalledImage(image_tag))
                    else:
                        image_selection = await DockerUtils().getInstalledImage(image_tag)
            except ObjectNotFound:
                # ObjectNotFound is raised when the image_tag provided by the user does not match any existing image.
                if image_tag is not None:
                    logger.warning(f"The image named '{image_tag}' has not been found.")
                # If the user's selected image have not been found,
                # offer to build a local image with this name
                # (only if must_exist is not set)
                if not must_exist:
                    image_selection = await UpdateManager.updateImage(image_tag)
                # Allow the user to interactively select another installed image
                image_tag = None
            except IndexError:
                # IndexError is raised when no image are available (not applicable when multiple is set, return an empty array)
                # (raised from TUI interactive selection)
                if must_exist:
                    # If there is no image installed, return none
                    logger.error("Nothing to do.")
                    return [] if multiple else None
                elif image_tag is not None:
                    # If the user's selected image have not been found, offer the choice to build a local image at this name
                    # (only if must_exist is not set)
                    image_selection = await UpdateManager.updateImage(image_tag)
                    image_tag = None
                else:
                    logger.critical("No image are installed or available, check your internet connection and install an image with the command [green]exegol install[/green].")
            # Checks if an image has been selected
            if image_selection is None:
                # If not, retry the selection
                logger.error("No image has been selected.")
                continue

            # Check if every image are installed
            install_status, checked_images = await cls.__checkImageInstallationStatus(image_selection, multiple, must_exist)
            if not install_status:
                # If one of the image is not install where it supposed to, restart the selection
                # allowing him to interactively choose another image
                image_selection, image_tag = None, None
                continue

            cls.__image = cast(Union[Optional[ExegolImage], List[ExegolImage]], checked_images)
        return cls.__image

    @classmethod
    async def __checkImageInstallationStatus(cls,
                                             image_selection: Union[ExegolImage, List[ExegolImage]],
                                             multiple: bool = False,
                                             must_exist: bool = False
                                             ) -> Tuple[bool, Optional[Union[ExegolImage, ExegolContainer, List[ExegolImage], List[ExegolContainer]]]]:
        """Checks if the selected images are installed and ready for use.
        returns false if the images are supposed to be already installed."""
        # Checks if one or more images have been selected and unifies the format into a list.
        reverse_type = False
        check_img: List[ExegolImage]
        if type(image_selection) is ExegolImage:
            check_img = [image_selection]
            # Tag of the operation to reverse it before the return
            reverse_type = True
        elif type(image_selection) is list:
            check_img = image_selection
        else:
            check_img = []

        # Check if every image are installed
        for i in range(len(check_img)):
            if not check_img[i].isInstall():
                # Is must_exist is set, every image are supposed to be already installed
                if must_exist:
                    logger.error(f"The selected image '{check_img[i].getName()}' is not installed.")
                    # If one of the image is not install, return False to restart the selection
                    return False, None
                else:
                    # Check if the selected image is installed and install it
                    logger.warning("The selected image is not installed.")
                    # Download remote image
                    if await DockerUtils().downloadImage(check_img[i], install_mode=True):
                        # Select installed image
                        check_img[i] = await DockerUtils().getInstalledImage(check_img[i].getName(), check_img[i].getRepository())
                    else:
                        logger.error("This image cannot be installed.")
                        return False, None

        if reverse_type and not multiple:
            # Restoration of the original type
            return True, check_img[0]
        return True, check_img

    @classmethod
    async def __loadOrCreateContainer(cls,
                                      override_container: Optional[str] = None,
                                      multiple: bool = False,
                                      must_exist: bool = False,
                                      filters: Optional[List[ExegolContainer.Filters]] = None) -> Union[Optional[ExegolContainer], List[ExegolContainer]]:
        """Select one or more ExegolContainer
        Or create a new ExegolContainer if no one already exist (and must_exist is not set)
        When must_exist is set to True, return None if no container exist
        When multiple is set to True, return a list of ExegolContainer"""
        if cls.__container is not None:
            # Return cache
            return cls.__container
        # resolver-exempt: positional, not a flag — `containertag` has no argparse dest and names which container to load.
        container_tag: Optional[str] = override_container if override_container is not None else ParametersManager().containertag
        container_tags: Optional[List[str]] = None
        # resolver-exempt: positional target list, not a flag — `multicontainertag` has no argparse dest and names which containers to act on.
        if ParametersManager().multicontainertag:
            container_tags = []
            # resolver-exempt: positional target list, not a flag — same `multicontainertag` selector as above.
            for tag in ParametersManager().multicontainertag:
                # Prevent duplicate tag selection
                if tag not in container_tags:
                    container_tags.append(tag)
        try:
            if container_tag is None and (container_tags is None or len(container_tags) == 0):
                container_list: List[ExegolContainer] = await DockerUtils().listContainers()
                if filters is not None:
                    filters_sum = sum(filters)
                    container_list = [c for c in container_list if c.filter(filters_sum)]
                if OptionResolver().get(OptionKey.SELECT_ALL):
                    # Select all container
                    cls.__container = container_list
                else:
                    # Interactive container selection
                    cls.__container = cast(Union[Optional[ExegolContainer], List[ExegolContainer]],
                                           await cls.__interactiveSelection(ExegolContainer, container_list, multiple))
            else:
                # Try to find the corresponding container
                if multiple:
                    cls.__container = []
                    assert container_tags is not None
                    # test each user tag
                    for container_tag in container_tags:
                        try:
                            cls.__container.append(DockerUtils().getContainer(container_tag))
                        except ObjectNotFound:
                            # on multi select, an object not found is not critical
                            if must_exist:
                                # If the selected tag doesn't match any container, print an alert and continue
                                logger.warning(f"The container named '{container_tag}' has not been found")
                            else:
                                # If there is a multi select without must_exist flag, raise an error
                                # because multi container creation is not supported
                                raise NotImplementedError
                else:
                    assert container_tag is not None
                    cls.__container = DockerUtils().getContainer(container_tag)
        except (ObjectNotFound, IndexError):
            # ObjectNotFound is raised when the container_tag provided by the user does not match any existing container.
            # IndexError is raise when no container exist (raised from TUI interactive selection)
            # Create container
            if must_exist:
                if container_tag is not None:
                    logger.warning(f"Container '{container_tag}' has not been found")
                return [] if multiple else None
            logger.info(f"Creating new container [green]{container_tag if container_tag else ''}[/green]")
            return await cls.__createContainer(container_tag)
        assert cls.__container is not None
        return cast(Union[Optional[ExegolContainer], List[ExegolContainer]], cls.__container)

    @classmethod
    async def __interactiveSelection(cls,
                                     object_type: Type[Union[ExegolImage, ExegolContainer]],
                                     object_list: Sequence[SelectableInterface],
                                     multiple: bool = False) -> \
            Union[Optional[ExegolImage], Optional[ExegolContainer], Sequence[ExegolImage], Sequence[ExegolContainer]]:
        """Interactive object selection process, depending on object_type.
        object_type can be ExegolImage or ExegolContainer."""
        user_selection: Union[SelectableInterface, Sequence[SelectableInterface], Sequence[str], str]
        if multiple:
            user_selection = await ExegolTUI.multipleSelectFromTable(object_list, object_type=object_type)
        else:
            user_selection = await ExegolTUI.selectFromTable(object_list, object_type=object_type, allow_none=object_type is ExegolContainer)
            # Check if the user has chosen an existing object
            if type(user_selection) is str:
                # Otherwise, create a new object with the supplied name
                if object_type is ExegolContainer:
                    user_selection = await cls.__createContainer(user_selection)
        return cast(Union[ExegolImage, ExegolContainer, List[ExegolImage], List[ExegolContainer]], user_selection)

    @classmethod
    async def __createContainer(cls, name: Optional[str]) -> ExegolContainer:
        """Create an ExegolContainer"""
        # The only place the profile tier is installed. OptionResolver is a process-lifetime
        # singleton, so installing it earlier would apply the profile to resumed containers.
        # This method only runs when a container is really created, hence no teardown.
        if cls.__resolved_profile is not None:
            from exegol.profile.ProfileApplication import apply_profile
            apply_profile(cls.__resolved_profile)
        if name is None:
            name = await ExegolRich.Ask("Enter new container name", default="default")
        logger.verbose("Configuring new exegol container")
        # Create exegol config
        image: Optional[ExegolImage] = cast(ExegolImage, await cls.__loadOrInstallImage(show_custom=True))
        assert image is not None  # load or install return an image
        # Resolver read: a profile's `network.hostname` applies when `--hostname` is not typed,
        # and `network.hostname_ask_user` turns that into a prompt offering it as the default.
        # Must stay after apply_profile() above: the profile tier is installed there and nowhere
        # else, so an earlier read could never see a profile-supplied ask flag. The fallback
        # default mirrors `ExegolContainerTemplate.newContainer`'s naming rule and moves with it.
        hostname = await ask_user_for_value(OptionKey.HOSTNAME_ASK_USER,
                                            OptionKey.HOSTNAME,
                                            "Enter the container hostname",
                                            fallback_default=name if name.startswith("exegol-") else f"exegol-{name}")
        model = await ExegolContainerTemplate.newContainer(name, image, hostname=hostname)

        # Recap
        await ExegolTUI.printContainerRecap(model)
        if cls.__interactive_mode:
            if not model.image.isUpToDate() and ExegolImage.UNKNOWN_STATUS not in model.image.getStatus() and \
                    await ExegolRich.Confirm("Do you want to [green]update[/green] the selected image?", False):
                image = await UpdateManager.updateImage(model.image.getName())
                if image is not None:
                    model.image = image
                    await ExegolTUI.printContainerRecap(model)
            command_options = []
            while not await ExegolRich.Confirm("Is the container configuration [green]correct[/green]?", default=True):
                command_options = await model.config.interactiveConfig(model.name, cls.__resolved_profile_name)
                await ExegolTUI.printContainerRecap(model)
            # Escape each operator-authored value (profile name, paths, container name), not the
            # assembled line: the [green] tags are real markup and command_options must stay
            # shell-pasteable.
            logger.info(f"Command line of the configuration: "
                        f"[green]exegol start {escape(model.name)} {escape(model.image.getName())} "
                        f"{escape(' '.join(command_options))}[/green]")
            logger.info("To use exegol [orange3]without interaction[/orange3], "
                        "read CLI options with [green]exegol start -h[/green]")

        container = DockerUtils().createContainer(model)
        await container.postCreateSetup()
        return container

    @classmethod
    async def __createTmpContainer(cls, image_name: Optional[str] = None) -> ExegolContainer:
        """Create a temporary ExegolContainer with custom entrypoint"""
        logger.verbose("Configuring new exegol container")
        name = f"tmp-{binascii.b2a_hex(os.urandom(4)).decode('ascii')}"
        # Create exegol config
        image: ExegolImage = cast(ExegolImage, await cls.__loadOrInstallImage(override_image=image_name))
        # Resolver read like __createContainer(); no profile tier is installed on this path.
        model = await ExegolContainerTemplate.newContainer(name, image, hostname=OptionResolver().get(OptionKey.HOSTNAME))
        # When container exec a command as a daemon, the execution must be set on the container's entrypoint
        # Read again rather than shared with exec(): `exegol start --tmp` reaches this without it.
        if OptionResolver().get(OptionKey.DAEMON):
            # Using formatShellCommand to support zsh aliases
            exec_payload, str_cmd = ExegolContainer.formatShellCommand(OptionResolver().get(OptionKey.EXEC), entrypoint_mode=True)
            model.config.entrypointRunCmd()
            model.config.addEnv("CMD", str_cmd)
            model.config.addEnv("DISABLE_AUTO_UPDATE", "true")
        # Workspace must be disabled for temporary container because host directory is never deleted
        model.config.disableDefaultWorkspace()

        # Mount entrypoint as a volume (because in tmp mode the container is created with run instead of create method)
        model.config.addVolume(ConstantConfig.entrypoint_context_path_obj, StaticContainerPath.EXEGOL_ENTRYPOINT.value, must_exist=True, read_only=True)

        container = DockerUtils().createContainer(model, temporary=True)
        await container.postCreateSetup(is_temporary=True)
        return container

    @classmethod
    def __checkUselessParameters(cls) -> None:
        """Checks if the container creation parameters have not been filled in when the container already existed"""
        resolver = OptionResolver()
        # Registered creation-only options: the resolver answers whether the user typed them.
        registered = {spec.dest: spec for spec in resolver.registryForScope(OptionScope.CREATION_ONLY)}
        detected = []
        for param, display_override in CREATION_ONLY_WARNING_SURFACE:
            # Skip parameters useful in a start context
            if param in ('containertag',):
                continue
            # An OptionKey names a registered option, a bare string an unregistered one. The
            # membership test also keeps non-CREATION_ONLY options out.
            if isinstance(param, OptionKey) and param in registered:
                # A profile-supplied or UserConfig-supplied value is an effective value,
                # not a discarded user request, so only the CLI tier counts here.
                supplied = resolver.isExplicit(param)
                name: Optional[str] = registered[param].display_name
            else:
                # Unregistered creation-only dests all default to None: non-null means typed.
                supplied = getattr(ParametersManager(), param) is not None
                name = display_override
            if supplied and name is not None:
                detected.append(name)
        if len(detected) > 0:
            logger.warning(f"These parameters ({', '.join(detected)}) have been entered although the container already "
                           f"exists, they will not be taken into account.")

    @classmethod
    async def __backupAndUpgrade(cls, c: ExegolContainer) -> None:
        logger.empty_line()

        current_image_tag = c.image.getName().split('-')[0]
        # `UPGRADE_IMAGE_TAG` (`upgrade --image`, dest `image_tag`) is the upgrade target, not
        # `IMAGE_TAG` (start's `imagetag` positional). Resolved once: both reads below use it.
        upgrade_target = OptionResolver().get(OptionKey.UPGRADE_IMAGE_TAG)
        if upgrade_target is None or upgrade_target == current_image_tag:

            # Check update conditions
            if not c.image.isLocked():
                if ExegolImage.UNKNOWN_STATUS in c.image.getStatus():
                    await c.image.autoLoad()
                if c.image.isUpToDate():
                    logger.error(f"Container [green]{c.name}[/green] is already using the latest version of [blue]{current_image_tag}[/blue]. No need to upgrade, skipping.")
                    return

            # Tips to upgrade from free image
            if current_image_tag == "free":
                logger.info(f"[orange3][Tips][/orange3] you can use the [green]--image IMAGE[/green] option to upgrade your container to a {SessionHandler().get_license_type_display()} image (e.g., 'full'').")
                logger.empty_line()

            new_image: ExegolImage = await DockerUtils().getInstalledImage(current_image_tag)
            logger.info(f"Upgrading container [green]{c.name}[/green] using [green]{new_image.getName()}[/green] image")
        else:
            # Upgrade to a different image tag
            new_image = await DockerUtils().getInstalledImage(upgrade_target)
            logger.info(f"Upgrading container [green]{c.name}[/green], your container will migrate from [blue]{current_image_tag}[/blue] to the [blue]{new_image.getName()}[/blue] image")

        skipping_msg = ""
        if not new_image.isUpToDate():
            skipping_msg = f"Run [green]exegol update {new_image.getName()}[/green] to install the new version [green]{new_image.getLatestVersion()}[/green] of your image first."
            logger.warning(f"You're upgrading to an outdated version of the [blue]{new_image.getName()}[/blue] image ([orange3]{new_image.getImageVersion()}[/orange3] :arrow_right: [green]{new_image.getLatestVersion()}[/green])")
            if not OptionResolver().get(OptionKey.FORCE_MODE) and not await ExegolRich.Confirm(f"Are you sure you want to upgrade your container [green]{c.name}[/green] to an outdated image?", default=False):
                if await ExegolRich.Confirm(f"Do you want to update your [green]{new_image.getName()}[/green] image now?", default=False):
                    image_update = await UpdateManager.updateImage(new_image.getName())
                    if image_update is None:
                        logger.error(f"An error occurred during image update. Skipping upgrade of container [green]{c.name}[/green].")
                        return
                    new_image = image_update
                else:
                    logger.info(f"Skipping upgrade of container [green]{c.name}[/green]. {skipping_msg}")
                    return

        # Check if the new image is the same as the container's current image
        if c.image.getLocalId() == new_image.getLocalId():
            logger.error(f"Cannot upgrade [green]{c.name}[/green] because it's already using the latest local [blue]{new_image.getName()}[/blue] image (version [orange3]{new_image.getImageVersion()}[/orange3]), skipping.")
            if not new_image.isUpToDate():
                logger.info(skipping_msg)
            return

        # Start container and run pre-backup checks
        if not c.isRunning():
            await c.start()
        async with ExegolStatus(f"Running pre-backup checks", spinner_style="blue"):
            # Test if exh can be backup
            backup_directory_exist = await c.exec(f"[ -d {ExegolContainer.BACKUP_DIRECTORY} ]", as_daemon=False, quiet=True, show_output=False) == 0
            if not backup_directory_exist:
                exh_backup_supported = await c.exec("exegol-history version", as_daemon=False, quiet=True, show_output=False) == 0

        if backup_directory_exist:
            logger.error(f"The directory {ExegolContainer.BACKUP_DIRECTORY} already exists in the container [green]{c.name}[/green]. "
                         f"It needs to be removed manually before trying to upgrade this container.")
            return

        remove_container = OptionResolver().get(OptionKey.NO_BACKUP) or (
                    not OptionResolver().get(OptionKey.FORCE_MODE) and
                    not await ExegolRich.Confirm("Do you want to [green]keep[/green] your old container as a backup?", default=True))

        backup_items = [
            "Your [green]my-resources[/green] customization" if c.config.isMyResourcesEnable() else "",
            "The container [green]/workspace[/green] directory",
            "Your [green]bash[/green],[green]zsh[/green],[green]python3[/green] command history",
            f"Your {'[green]exegol-history[/green],' if exh_backup_supported else ''}[green]NetExec[/green],[green]Responder[/green],[green]Firefox[/green] database and configuration",
            "Your [green]TriliumNext[/green] notes",
            "Your [green]Hashcat[/green],[green]John[/green] potfiles",
            "The following files: /etc/hosts /etc/resolv.conf /opt/tools/Exegol-history/profile.sh",
            "The following configurations: [green]Proxychains[/green]"
        ]
        backup_text = '\n    - '.join([i for i in backup_items if i])
        details = f"""You are about to upgrade your container and transfer:
    - {backup_text}
"""
        # TODO improve upgrade with
        #  DB of neo4j, postgres

        logger.warning(details)
        if (not OptionResolver().get(OptionKey.FORCE_MODE) and
                not await ExegolRich.Confirm(f"The list above will be [orange3]{'kept' if remove_container else 'transferred'} "
                                             f"to the new container[/orange3], [red]nothing more{', without backup' if remove_container else ''}[/red]! "
                                             f"Do you want to proceed with the upgrade of [green]{c.name}[/green]?", default=False)):
            logger.critical("Aborting operation.")

        logger.warning("Please don't cancel this operation while it's running! You might loose some data!")

        # Start container data Backup
        await c.backup(backup_exh=exh_backup_supported)
        logger.success(f"Container [green]{c.name}[/green] data has been backed up.")

        # Get previous backups that still exist
        backup_history = c.getExistingBackupContainers()

        if remove_container:
            # Remove the container without removing the workspace
            await c.remove(container_only=True)
        else:
            await c.stop()
            # Renaming old container
            c.rename_as_old()
            # Add and update backup history references
            backup_history.append((c.getFullId(), ''))

        # Updating previous backup containers references
        c.config.setBackupHistory(','.join([x[0] for x in backup_history]) if len(backup_history) > 0 else None)

        # Update container's exegol image to the new image target
        c.image = new_image

        # Create a new container from template
        container = DockerUtils().createContainer(c)
        await container.postCreateSetup()

        # Restore data on new container
        if await container.restore():
            logger.success(f"Container [green]{c.name}[/green] successfully upgraded to the [green]{c.image.getLatestVersionName().replace('-', ' ')}[/green] image!")
        else:
            logger.warning("The container was upgraded, but errors occurred during data restoration. Consult the previous messages to recover the missing data in your new container")
        logger.info(f"You can now open a shell in your new container with [green]exegol start {c.name}[/green]")
