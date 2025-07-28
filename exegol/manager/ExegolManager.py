import binascii
import logging
import os
from asyncio import gather
from typing import Union, List, Tuple, Optional, cast, Sequence, Type

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.UserConfig import UserConfig
from exegol.console import ConsoleFormat
from exegol.console.ConsoleFormat import boolFormatter
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.console.cli.actions.GenericParameters import ContainerCreation
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.manager.LicenseManager import LicenseManager
from exegol.manager.TaskManager import TaskManager
from exegol.manager.UpdateManager import UpdateManager
from exegol.model.ExegolContainer import ExegolContainer
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.SessionHandler import SessionHandler


class ExegolManager:
    """Contains the main procedures of all actions available in Exegol"""

    # Cache data
    __container: Union[Optional[ExegolContainer], List[ExegolContainer]] = None
    __image: Union[Optional[ExegolImage], List[ExegolImage]] = None

    # Runtime default configuration
    __interactive_mode = False

    @classmethod
    async def info(cls) -> None:
        """Print a list of available images and containers on the current host"""
        if logger.isEnabledFor(ExeLog.VERBOSE):
            logger.verbose("Listing user configurations")
            ExegolTUI.printTable(UserConfig().get_configs(), title="[not italic]:brain: [/not italic][gold3][g]User configurations[/g][/gold3]")
        if logger.isEnabledFor(ExeLog.ADVANCED):
            logger.verbose("Listing git repositories")
            ExegolTUI.printTable(await UpdateManager.listGitStatus(), title="[not italic]:octopus: [/not italic][gold3][g]Project modules[/g][/gold3]")
        if bool(ParametersManager().containertag):
            # If the user have supplied a container name, show container config
            container = await cls.__loadOrCreateContainer(ParametersManager().containertag, must_exist=True)
            if container is not None:
                assert type(container) is ExegolContainer
                await ExegolTUI.printContainerRecap(container)
        else:
            # Without any parameter, show all images and containers info
            # Fetch data
            TaskManager.add_task(
                DockerUtils().listImages(include_version_tag=False, include_custom=True),
                TaskManager.TaskId.ImageList)
            TaskManager.add_task(
                DockerUtils().listContainers(),
                TaskManager.TaskId.ContainerList)
            images, containers = await TaskManager.gather(TaskManager.TaskId.ImageList, TaskManager.TaskId.ContainerList)
            # List and print images
            color = ConsoleFormat.getArchColor(ParametersManager().arch)
            logger.verbose(f"Listing local and remote Exegol images (filtering for architecture [{color}]{ParametersManager().arch}[/{color}])")
            ExegolTUI.printTable(images)
            # List and print containers
            logger.verbose("Listing local Exegol containers")
            logger.raw(f"[bold blue][*][/bold blue] Number of Exegol containers: {len(containers)}{os.linesep}",
                       markup=True)
            ExegolTUI.printTable(containers)

    @classmethod
    async def start(cls) -> None:
        """Create and/or start an exegol container to finally spawn an interactive shell"""
        logger.info("Starting exegol")
        # Check if the first positional parameter have been supplied
        cls.__interactive_mode = not bool(ParametersManager().containertag)
        if not cls.__interactive_mode:
            logger.info("Arguments supplied with the command, skipping interactive mode")
        container = await cls.__loadOrCreateContainer()
        assert container is not None and type(container) is ExegolContainer
        if not container.isNew():
            # Check and warn user if some parameters don't apply to the current session
            cls.__checkUselessParameters()
        await gather(
            container.start(),
            TaskManager.wait_for_all())
        await container.spawnShell()

    @classmethod
    async def upgrade(cls) -> None:
        """Upgrade exegol to the latest version"""
        if not SessionHandler().pro_feature_access():
            logger.critical("Exegol upgrade is only available for Pro or Enterprise users.")
        container = await cls.__loadOrCreateContainer(multiple=True, must_exist=True, filters=[ExegolContainer.Filters.OUTDATED])
        assert container is not None and type(container) is list
        for c in container:
            try:
                previous_image = c.image
                await cls.__backupAndUpgrade(c)

                # If the image used is deprecated, it must be deleted after the removal of its container
                if previous_image.isLocked() and UserConfig().auto_remove_images:
                    await DockerUtils().removeImage(previous_image, upgrade_mode=True, silent_error=True)
            except CancelOperation:
                logger.error(f"Something unexpected happened during the [green]{c.name}[/green] container upgrade process.")

    @classmethod
    async def exec(cls) -> None:
        """Create and/or start an exegol container to execute a specific command.
        The execution can be seen in console output or be relayed in the background as a daemon."""
        logger.info("Starting exegol")
        if ParametersManager().tmp:
            container = await cls.__createTmpContainer(ParametersManager().selector)
            if not ParametersManager().daemon:
                await container.exec(command=ParametersManager().exec, as_daemon=False, is_tmp=True)
                await container.stop(timeout=2)
            else:
                # Command is passed at container creation in __createTmpContainer()
                logger.success(f"Command executed as entrypoint of the container {container.getDisplayName()}")
        else:
            container = cast(ExegolContainer, await cls.__loadOrCreateContainer(override_container=ParametersManager().selector))
            await container.exec(command=ParametersManager().exec, as_daemon=ParametersManager().daemon)

    @classmethod
    async def stop(cls) -> None:
        """Stop an exegol container"""
        logger.info("Stopping exegol")
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
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to update Exegol in offline mode. Please retry later with an internet connection.")
        if not ParametersManager().skip_git:
            await UpdateManager.updateWrapper()
            await UpdateManager.updateResources()
        if not ParametersManager().skip_images:
            await UpdateManager.updateImage()

    @classmethod
    async def uninstall(cls) -> None:
        """Remove an exegol image"""
        logger.info("Uninstalling an exegol image")
        # Set log level to verbose in order to show every image installed including the outdated.
        if not logger.isEnabledFor(ExeLog.VERBOSE):
            logger.setLevel(ExeLog.VERBOSE)
        images = await cls.__loadOrInstallImage(multiple=True, filters=[ExegolImage.Filters.INSTALLED])
        assert type(images) is list
        if len(images) == 0:
            return
        all_name = ", ".join([x.getName() for x in images])
        if not ParametersManager().force_mode and not await ExegolRich.Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following images? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for img in images:
            await DockerUtils().removeImage(img)

    @classmethod
    async def remove(cls) -> None:
        """Remove an exegol container"""
        logger.info("Removing an exegol container")
        containers = await cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        assert type(containers) is list
        if len(containers) == 0:
            logger.error("No containers were selected. Exiting.")
            return
        all_name = ", ".join([x.name for x in containers])
        if not ParametersManager().force_mode and not await ExegolRich.Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following containers? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for c in containers:
            # Check if containers have backups
            backup_history = c.getExistingBackupContainers()
            if len(backup_history) > 0:
                all_backup_names = ', '.join([x[1] for x in backup_history])
                if ParametersManager().force_mode:
                    logger.info(f"The container [green]{c.name}[/green] has [green]{len(backup_history)}[/green] backup containers that will be removed too [orange3][ {all_backup_names} ][/orange3]")
                elif not await ExegolRich.Confirm(f"The container [green]{c.name}[/green] has [green]{len(backup_history)}[/green] backup containers [orange3][ {all_backup_names} ][/orange3], do you want to remove them too?", default=True):
                    logger.critical("Cannot remove container without also removing its backups. Aborting.")

            await c.remove(backup_history=[x[0] for x in backup_history])
            # If the image used is deprecated, it must be deleted after the removal of its container
            if c.image.isLocked() and UserConfig().auto_remove_images:
                await DockerUtils().removeImage(c.image, upgrade_mode=True)

    @classmethod
    async def activate(cls) -> None:
        """Activate an exegol license"""
        if ParametersManager().revoke:
            await (await LicenseManager.get()).revoke_exegol()
        elif (await LicenseManager.get()).is_activated():
            logger.success("Exegol is activated")
        else:
            await (await LicenseManager.get()).activate_exegol(skip_prompt=True)

    @classmethod
    async def print_version(cls) -> None:
        """Show exegol version (and context configuration on debug mode)"""

        logger.raw(f"[bold blue][*][/bold blue] Exegol {SessionHandler().get_license_type_display()} is currently in version {await UpdateManager.display_current_version()}{os.linesep}",
                   level=logging.INFO, markup=True)
        await LicenseManager.get()
        logger.raw(
            f"[bold magenta][*][/bold magenta] More about Exegol at: [underline magenta]{ConstantConfig.landing}[/underline magenta]{os.linesep}",
            level=logging.INFO, markup=True)

        cls.print_sponsors()
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
        if UserConfig().auto_check_updates:
            await UpdateManager.checkForWrapperUpdate()
        if await UpdateManager.isUpdateAvailable():
            logger.empty_line()
            update_message = f"An [green]Exegol[/green] update is [orange3]available[/orange3] ({await UpdateManager.display_current_version()} :arrow_right: {UpdateManager.display_latest_version()})"
            if ConstantConfig.git_source_installation:
                if await ExegolRich.Confirm(f"{update_message}, do you want to update ?", default=True):
                    await UpdateManager.updateWrapper()
            else:
                logger.info(update_message)
                update_command = None
                if ConstantConfig.pipx_installed:
                    update_command = "You can update your exegol wrapper with the command [green]pipx upgrade exegol[/green]"
                elif ConstantConfig.uv_installed:
                    update_command = "You can update your exegol wrapper with the command [green]uv tool upgrade exegol[/green]"
                elif ConstantConfig.pip_installed:
                    update_command = "If you have installed Exegol with pip, update with the command [green]pip3 install exegol --upgrade[/green]"
                else:
                    await ExegolRich.Acknowledge("Installation method not found (not among pip/pipx/uv/sources). You should update your wrapper manually.")
                if update_command:
                    await ExegolRich.Acknowledge(update_command)
        else:
            logger.empty_line(log_level=logging.DEBUG)

    @classmethod
    def print_sponsors(cls) -> None:
        """Show exegol sponsors"""
        # logger.success("""We thank [link=https://www.capgemini.com/fr-fr/carrieres/offres-emploi/][blue]Capgemini[/blue][/link] for supporting the project [bright_black](helping with dev)[/bright_black] :pray:""")
        # logger.success("""We thank [link=https://www.hackthebox.com/][green]HackTheBox[/green][/link] for sponsoring the [bright_black]multi-arch[/bright_black] support :green_heart:""")
        pass

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
        image_tag = override_image if override_image is not None else ParametersManager().imagetag
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

                    if ParametersManager().select_all:
                        image_selection = image_list
                    else:
                        # Interactive (TUI) image selection
                        image_selection = cast(Union[Optional[ExegolImage], List[ExegolImage]],
                                               await cls.__interactiveSelection(ExegolImage, image_list, multiple, must_exist))
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
        container_tag: Optional[str] = override_container if override_container is not None else ParametersManager().containertag
        container_tags: Optional[List[str]] = None
        if ParametersManager().multicontainertag:
            container_tags = []
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
                if ParametersManager().select_all:
                    # Select all container
                    cls.__container = container_list
                else:
                    # Interactive container selection
                    cls.__container = cast(Union[Optional[ExegolContainer], List[ExegolContainer]],
                                           await cls.__interactiveSelection(ExegolContainer, container_list, multiple, must_exist))
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
                    logger.warning(f"The container named '{container_tag}' has not been found")
                return [] if multiple else None
            logger.info(f"Creating new container named '{container_tag}'")
            return await cls.__createContainer(container_tag)
        assert cls.__container is not None
        return cast(Union[Optional[ExegolContainer], List[ExegolContainer]], cls.__container)

    @classmethod
    async def __interactiveSelection(cls,
                                     object_type: Type[Union[ExegolImage, ExegolContainer]],
                                     object_list: Sequence[SelectableInterface],
                                     multiple: bool = False,
                                     must_exist: bool = False) -> \
            Union[Optional[ExegolImage], Optional[ExegolContainer], Sequence[ExegolImage], Sequence[ExegolContainer]]:
        """Interactive object selection process, depending on object_type.
        object_type can be ExegolImage or ExegolContainer."""
        user_selection: Union[SelectableInterface, Sequence[SelectableInterface], str]
        if multiple:
            user_selection = await ExegolTUI.multipleSelectFromTable(object_list, object_type=object_type)
        else:
            user_selection = await ExegolTUI.selectFromTable(object_list, object_type=object_type, allow_None=object_type is ExegolContainer)
            # Check if the user has chosen an existing object
            if type(user_selection) is str:
                # Otherwise, create a new object with the supplied name
                if object_type is ExegolContainer:
                    user_selection = await cls.__createContainer(user_selection)
        return cast(Union[ExegolImage, ExegolContainer, List[ExegolImage], List[ExegolContainer]], user_selection)

    @classmethod
    async def __createContainer(cls, name: Optional[str]) -> ExegolContainer:
        """Create an ExegolContainer"""
        if name is None:
            name = await ExegolRich.Ask("[bold blue][?][/bold blue] Enter the name of your new exegol container", default="default")
        logger.verbose("Configuring new exegol container")
        # Create exegol config
        image: Optional[ExegolImage] = cast(ExegolImage, await cls.__loadOrInstallImage(show_custom=True))
        assert image is not None  # load or install return an image
        if name is None:
            name = await ExegolRich.Ask("[bold blue][?][/bold blue] Enter the name of your new exegol container", default="default")
        model = await ExegolContainerTemplate.newContainer(name, image, hostname=ParametersManager().hostname)

        # Recap
        await ExegolTUI.printContainerRecap(model)
        if cls.__interactive_mode:
            if not model.image.isUpToDate() and \
                    await ExegolRich.Confirm("Do you want to [green]update[/green] the selected image?", False):
                image = await UpdateManager.updateImage(model.image.getName())
                if image is not None:
                    model.image = image
                    await ExegolTUI.printContainerRecap(model)
            command_options = []
            while not await ExegolRich.Confirm("Is the container configuration [green]correct[/green]?", default=True):
                command_options = await model.config.interactiveConfig(model.name)
                await ExegolTUI.printContainerRecap(model)
            logger.info(f"Command line of the configuration: "
                        f"[green]exegol start {model.name} {model.image.getName()} {' '.join(command_options)}[/green]")
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
        model = await ExegolContainerTemplate.newContainer(name, image, hostname=ParametersManager().hostname)
        # When container exec a command as a daemon, the execution must be set on the container's entrypoint
        if ParametersManager().daemon:
            # Using formatShellCommand to support zsh aliases
            exec_payload, str_cmd = ExegolContainer.formatShellCommand(ParametersManager().exec, entrypoint_mode=True)
            model.config.entrypointRunCmd()
            model.config.addEnv("CMD", str_cmd)
            model.config.addEnv("DISABLE_AUTO_UPDATE", "true")
        # Workspace must be disabled for temporary container because host directory is never deleted
        model.config.disableDefaultWorkspace()

        # Mount entrypoint as a volume (because in tmp mode the container is created with run instead of create method)
        model.config.addVolume(ConstantConfig.entrypoint_context_path_obj, "/.exegol/entrypoint.sh", must_exist=True, read_only=True)

        container = DockerUtils().createContainer(model, temporary=True)
        await container.postCreateSetup(is_temporary=True)
        return container

    @classmethod
    def __checkUselessParameters(cls) -> None:
        """Checks if the container creation parameters have not been filled in when the container already existed"""
        # Get defaults parameters
        creation_parameters = ContainerCreation([]).__dict__
        # Get parameters from user input
        user_inputs = ParametersManager().parameters.__dict__
        detected = []
        for param in creation_parameters.keys():
            # Skip parameters useful in a start context
            if param in ('containertag',):
                continue
            # For each parameter, check if it's not None and different from the default
            current_option = creation_parameters.get(param)
            if user_inputs.get(param) is not None and current_option is not None and \
                    user_inputs.get(param) != current_option.kwargs.get('default'):
                # If the supplied parameter is positional, getting his printed name
                name = current_option.kwargs.get('metavar')
                if not name:
                    # if not, using the args name
                    detected.append(' / '.join(current_option.args))
                else:
                    detected.append(name)
        if len(detected) > 0:
            logger.warning(f"These parameters ({', '.join(detected)}) have been entered although the container already "
                           f"exists, they will not be taken into account.")

    @classmethod
    async def __backupAndUpgrade(cls, c: ExegolContainer) -> None:
        logger.empty_line()

        current_image_tag = c.image.getName().split('-')[0]
        if ParametersManager().image_tag is None or ParametersManager().image_tag == current_image_tag:

            # Check update conditions
            if not c.image.isLocked():
                if "Unknown" in c.image.getStatus():
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
            new_image = await DockerUtils().getInstalledImage(ParametersManager().image_tag)
            logger.info(f"Upgrading container [green]{c.name}[/green], your container will migrate from [blue]{current_image_tag}[/blue] to the [blue]{new_image.getName()}[/blue] image")

        skipping_msg = ""
        if not new_image.isUpToDate():
            skipping_msg = f"Run [green]exegol update {new_image.getName()}[/green] to install the new version [green]{new_image.getLatestVersion()}[/green] of your image first."
            logger.warning(f"You're upgrading to an outdated version of the [blue]{new_image.getName()}[/blue] image ([orange3]{new_image.getImageVersion()}[/orange3] :arrow_right: [green]{new_image.getLatestVersion()}[/green])")
            if not ParametersManager().force_mode and not await ExegolRich.Confirm(f"Are you sure you want to upgrade your container [green]{c.name}[/green] to an outdated image?", default=False):
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

        remove_container = ParametersManager().no_backup or (
                    not ParametersManager().force_mode and
                    not await ExegolRich.Confirm("Do you want to [green]keep[/green] your old container as a backup?", default=True))

        backup_items = [
            "Your [green]my-resources[/green] customization" if c.config.isMyResourcesEnable() else "",
            "The container [green]/workspace[/green] directory",
            "Your [green]bash/zsh[/green] command history",
            "Your [green]exegol-history[/green] database" if exh_backup_supported else "",
            "Your [green]TriliumNext[/green] notes",
            "The following files: /etc/hosts /etc/resolv.conf /opt/tools/Exegol-history/profile.sh",
            "The following configurations: [green]Proxychains[/green]"
        ]
        backup_text = '\n    - '.join([i for i in backup_items if i])
        details = f"""You are about to upgrade your container and transfer:
    - {backup_text}
"""
        # TODO improve upgrade with
        #  Config of: Responder?
        #  DB of Responder, neo4j, postgres, nxc?, firefox, hashcat potfile, john?

        logger.warning(details)
        if (not ParametersManager().force_mode and
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
