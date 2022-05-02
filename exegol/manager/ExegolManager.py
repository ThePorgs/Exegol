import binascii
import logging
import os
from typing import Union, List, Tuple, Optional, cast, Sequence

from exegol.console.ConsoleFormat import boolFormatter
from exegol.console.ExegolPrompt import Confirm
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.console.cli.actions.GenericParameters import ContainerCreation
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.manager.UpdateManager import UpdateManager
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolContainer import ExegolContainer
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.UserConfig import UserConfig


class ExegolManager:
    """Contains the main procedures of all actions available in Exegol"""

    # Cache data
    __container: Union[Optional[ExegolContainer], List[ExegolContainer]] = None
    __image: Union[Optional[ExegolImage], List[ExegolImage]] = None

    # Runtime default configuration
    __interactive_mode = False

    @classmethod
    def info(cls):
        """Print a list of available images and containers on the current host"""
        ExegolManager.print_version()
        if logger.isEnabledFor(ExeLog.VERBOSE):
            logger.verbose("Listing user configurations")
            ExegolTUI.printTable(UserConfig().get_configs(), title="[not italic]:brain: [/not italic][gold3][g]User configurations[/g][/gold3]")
        if logger.isEnabledFor(ExeLog.ADVANCED):
            logger.verbose("Listing git repositories")
            ExegolTUI.printTable(UpdateManager.listGitStatus(), title="[not italic]:octopus: [/not italic][gold3][g]Project modules[/g][/gold3]")
        if bool(ParametersManager().containertag):
            # If the user have supplied a container name, show container config
            container = cls.__loadOrCreateContainer(ParametersManager().containertag, must_exist=True)
            if container is not None:
                ExegolTUI.printContainerRecap(container)
        else:
            # Without any parameter, show all images and containers info
            # Fetch data
            images = DockerUtils.listImages(include_version_tag=False)
            containers = DockerUtils.listContainers()
            # List and print images
            logger.verbose("Listing local and remote Exegol images")
            ExegolTUI.printTable(images)
            # List and print containers
            logger.verbose("Listing local Exegol containers")
            logger.raw(f"[bold blue][*][/bold blue] Number of Exegol containers: {len(containers)}{os.linesep}",
                       markup=True)
            ExegolTUI.printTable(containers)

    @classmethod
    def start(cls):
        """Create and/or start an exegol container to finally spawn an interactive shell"""
        ExegolManager.print_version()
        logger.info("Starting exegol")
        # TODO add console logging capabilities
        # Check if the first positional parameter have been supplied
        cls.__interactive_mode = not bool(ParametersManager().containertag)
        if not cls.__interactive_mode:
            logger.info("Arguments supplied with the command, skipping interactive mode")
        container = cls.__loadOrCreateContainer()
        if not container.isNew():
            # Check and warn user if some parameters don't apply to the current session
            cls.__checkUselessParameters()
        container.start()
        container.spawnShell()

    @classmethod
    def exec(cls):
        """Create and/or start an exegol container to execute a specific command.
        The execution can be seen in console output or be relayed in the background as a daemon."""
        ExegolManager.print_version()
        logger.info("Starting exegol")
        if ParametersManager().tmp:
            container = cls.__createTmpContainer(ParametersManager().selector)
            if not ParametersManager().daemon:
                container.exec(command=ParametersManager().exec, as_daemon=False)
                container.stop(timeout=2)
            else:
                logger.success(f"Command executed as entrypoint of the container {container.hostname}")
        else:
            container = cls.__loadOrCreateContainer(override_container=ParametersManager().selector)
            container.exec(command=ParametersManager().exec, as_daemon=ParametersManager().daemon)

    @classmethod
    def stop(cls):
        """Stop an exegol container"""
        ExegolManager.print_version()
        logger.info("Stopping exegol")
        container = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        for c in container:
            c.stop(timeout=2)

    @classmethod
    def install(cls):
        """Pull or build a docker exegol image"""
        ExegolManager.print_version()
        try:
            if not ExegolModules().isExegolResourcesReady():
                raise CancelOperation
        except CancelOperation:
            # Error during installation, skipping operation
            logger.warning("Exegol resources have not been downloaded, the feature cannot be enabled")
        UpdateManager.updateImage(install_mode=True)

    @classmethod
    def update(cls):
        """Update python wrapper (git installation required) and Pull a docker exegol image"""
        ExegolManager.print_version()
        if not ParametersManager().skip_git:
            UpdateManager.updateWrapper()
            UpdateManager.updateImageSource()
            UpdateManager.updateResources()
        if not ParametersManager().skip_images:
            UpdateManager.updateImage()

    @classmethod
    def uninstall(cls):
        """Remove an exegol image"""
        ExegolManager.print_version()
        logger.info("Uninstalling an exegol image")
        # Set log level to verbose in order to show every image installed including the outdated.
        if not logger.isEnabledFor(ExeLog.VERBOSE):
            logger.setLevel(ExeLog.VERBOSE)
        images = cls.__loadOrInstallImage(multiple=True, must_exist=True)
        if len(images) == 0:
            logger.error("No images were selected. Exiting.")
            return
        all_name = ", ".join([x.getName() for x in images])
        if not ParametersManager().force_mode and not Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following images? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for img in images:
            DockerUtils.removeImage(img)

    @classmethod
    def remove(cls):
        """Remove an exegol container"""
        ExegolManager.print_version()
        logger.info("Removing an exegol container")
        containers = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        if len(containers) == 0:
            logger.error("No containers were selected. Exiting.")
            return
        all_name = ", ".join([x.name for x in containers])
        if not ParametersManager().force_mode and not Confirm(
                f"Are you sure you want to [red]permanently remove[/red] the following containers? [orange3][ {all_name} ][/orange3]",
                default=False):
            logger.error("Aborting operation.")
            return
        for c in containers:
            c.remove()
            # If the image used is deprecated, it must be deleted after the removal of its container
            if c.image.isLocked():
                DockerUtils.removeImage(c.image, upgrade_mode=True)

    @classmethod
    def print_version(cls):
        """Show exegol version (and context configuration on debug mode)"""
        logger.raw(f"[bold blue][*][/bold blue] Exegol is currently in version [blue]v{ConstantConfig.version}[/blue]{os.linesep}",
                   level=logging.INFO, markup=True)
        logger.debug(f"Pip installation: {boolFormatter(ConstantConfig.pip_installed)}")
        logger.debug(f"Git source installation: {boolFormatter(ConstantConfig.git_source_installation)}")
        logger.debug(f"Host OS: {EnvInfo.getHostOs()}")
        if EnvInfo.isWindowsHost():
            logger.debug(f"Python environment: {EnvInfo.current_platform}")
            logger.debug(f"Docker engine: {EnvInfo.getDockerEngine().upper()}")
            logger.debug(f"Windows release: {EnvInfo.getWindowsRelease()}")

    @classmethod
    def __loadOrInstallImage(cls,
                             override_image: Optional[str] = None,
                             multiple: bool = False,
                             must_exist: bool = False) -> Union[Optional[ExegolImage], List[ExegolImage]]:
        """Select / Load (and install) an ExegolImage
        When must_exist is set to True, return None if no image are installed
        When multiple is set to True, return a list of ExegolImage
        Otherwise, always return an ExegolImage"""
        if cls.__image is not None:
            # Return cache
            return cls.__image
        image_tag = override_image if override_image is not None else ParametersManager().imagetag
        image_tags = ParametersManager().multiimagetag
        image_selection: Union[Optional[ExegolImage], List[ExegolImage]] = None
        # While an image have not been selected
        while image_selection is None:
            try:
                if image_tag is None and (image_tags is None or len(image_tags) == 0):
                    # Interactive (TUI) image selection
                    image_selection = cast(Union[Optional[ExegolImage], List[ExegolImage]],
                                           cls.__interactiveSelection(ExegolImage, multiple, must_exist))
                else:
                    # Select image by tag name (non-interactive)
                    if multiple:
                        image_selection = []
                        for image_tag in image_tags:
                            image_selection.append(DockerUtils.getInstalledImage(image_tag))
                    else:
                        image_selection = DockerUtils.getInstalledImage(image_tag)
            except ObjectNotFound:
                # ObjectNotFound is raised when the image_tag provided by the user does not match any existing image.
                if image_tag is not None:
                    logger.warning(f"The image named '{image_tag}' has not been found.")
                # If the user's selected image have not been found,
                # offer to build a local image with this name
                # (only if must_exist is not set)
                if not must_exist:
                    image_selection = UpdateManager.updateImage(image_tag)
                # Allow the user to interactively select another installed image
                image_tag = None
            except IndexError:
                # IndexError is raised when no image are available (not applicable when multiple is set, return an empty array)
                # (raised from TUI interactive selection)
                if must_exist:
                    # If there is no image installed, return none
                    logger.error("No images were found")
                    return [] if multiple else None
                else:
                    # If the user's selected image have not been found, offer the choice to build a local image at this name
                    # (only if must_exist is not set)
                    image_selection = UpdateManager.updateImage(image_tag)
                    image_tag = None
            # Checks if an image has been selected
            if image_selection is None:
                # If not, retry the selection
                logger.error("No image has been selected.")
                continue

            # Check if every image are installed
            install_status, checked_images = cls.__checkImageInstallationStatus(image_selection, multiple, must_exist)
            if not install_status:
                # If one of the image is not install where it supposed to, restart the selection
                # allowing him to interactively choose another image
                image_selection, image_tag = None, None
                continue

            cls.__image = cast(Union[Optional[ExegolImage], List[ExegolImage]], checked_images)
        return cls.__image

    @classmethod
    def __checkImageInstallationStatus(cls,
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
                    if DockerUtils.downloadImage(check_img[i], install_mode=True):
                        # Select installed image
                        check_img[i] = DockerUtils.getInstalledImage(check_img[i].getName())
                    else:
                        logger.error("This image cannot be installed.")
                        return False, None

        if reverse_type and not multiple:
            # Restoration of the original type
            return True, check_img[0]
        return True, check_img

    @classmethod
    def __loadOrCreateContainer(cls,
                                override_container: Optional[str] = None,
                                multiple: bool = False,
                                must_exist: bool = False) -> Union[Optional[ExegolContainer], List[ExegolContainer]]:
        """Select one or multipleExegolContainer
        Or create a new ExegolContainer if no one already exist (and must_exist is not set)
        When must_exist is set to True, return None if no container exist
        When multiple is set to True, return a list of ExegolContainer"""
        if cls.__container is not None:
            # Return cache
            return cls.__container
        container_tag: Optional[str] = override_container if override_container is not None else ParametersManager().containertag
        container_tags: Optional[Sequence[str]] = ParametersManager().multicontainertag
        try:
            if container_tag is None and (container_tags is None or len(container_tags) == 0):
                # Interactive container selection
                cls.__container = cast(Union[Optional[ExegolContainer], List[ExegolContainer]],
                                       cls.__interactiveSelection(ExegolContainer, multiple, must_exist))
            else:
                # Try to find the corresponding container
                if multiple:
                    cls.__container = []
                    assert container_tags is not None
                    # test each user tag
                    for container_tag in container_tags:
                        try:
                            cls.__container.append(DockerUtils.getContainer(container_tag))
                        except ObjectNotFound:
                            # on multi select, an object not found is not critical
                            if must_exist:
                                # If the selected tag doesn't match any container, print an alert and continue
                                logger.warning(f"The container named '{container_tag}' has not been found")
                            else:
                                # If there is a multi select without must_exist flag, raise an error
                                # because multi container creation is not supported
                                raise NotImplemented
                else:
                    assert container_tag is not None
                    cls.__container = DockerUtils.getContainer(container_tag)
        except (ObjectNotFound, IndexError):
            # ObjectNotFound is raised when the container_tag provided by the user does not match any existing container.
            # IndexError is raise when no container exist (raised from TUI interactive selection)
            # Create container
            if must_exist:
                logger.warning(f"The container named '{container_tag}' has not been found")
                return [] if multiple else None
            return cls.__createContainer(container_tag)
        assert cls.__container is not None
        return cast(Union[Optional[ExegolContainer], List[ExegolContainer]], cls.__container)

    @classmethod
    def __interactiveSelection(cls,
                               object_type: type,
                               multiple: bool = False,
                               must_exist: bool = False) -> \
            Union[ExegolImage, ExegolContainer, Sequence[ExegolImage], Sequence[ExegolContainer]]:
        """Interactive object selection process, depending on object_type.
        object_type can be ExegolImage or ExegolContainer."""
        object_list: Sequence[SelectableInterface]
        # Object listing depending on the type
        if object_type is ExegolContainer:
            # List all images available
            object_list = DockerUtils.listContainers()
        elif object_type is ExegolImage:
            # List all images available
            object_list = DockerUtils.listInstalledImages() if must_exist else DockerUtils.listImages()
        else:
            logger.critical("Unknown object type during interactive selection. Exiting.")
            raise Exception
        # Interactive choice with TUI
        user_selection: Union[SelectableInterface, Sequence[SelectableInterface], str]
        if multiple:
            user_selection = ExegolTUI.multipleSelectFromTable(object_list, object_type=object_type)
        else:
            user_selection = ExegolTUI.selectFromTable(object_list, object_type=object_type,
                                                       allow_None=not must_exist)
            # Check if the user has chosen an existing object
            if type(user_selection) is str:
                # Otherwise, create a new object with the supplied name
                if object_type is ExegolContainer:
                    user_selection = cls.__createContainer(user_selection)
                else:
                    # Calling buildAndLoad directly, no need to ask confirmation, already done by TUI.
                    user_selection = UpdateManager.buildAndLoad(user_selection)
        return cast(Union[ExegolImage, ExegolContainer, List[ExegolImage], List[ExegolContainer]], user_selection)

    @classmethod
    def __prepareContainerConfig(cls):
        """Create Exegol configuration with user input"""
        # Create default exegol config
        config = ContainerConfig()
        # Container configuration from user CLI options
        if ParametersManager().X11:
            config.enableGUI()
        if ParametersManager().share_timezone:
            config.enableSharedTimezone()
        config.setNetworkMode(ParametersManager().host_network)
        if ParametersManager().shared_resources:
            config.enableSharedResources()
        if ParametersManager().exegol_resources:
            config.enableExegolResources()
        if ParametersManager().workspace_path:
            if ParametersManager().mount_current_dir:
                logger.warning(
                    f'Workspace conflict detected (-cwd cannot be use with -w). Using: {ParametersManager().workspace_path}')
            config.setWorkspaceShare(ParametersManager().workspace_path)
        elif ParametersManager().mount_current_dir:
            config.enableCwdShare()
        if ParametersManager().privileged:
            config.setPrivileged()
        if ParametersManager().volumes is not None:
            for volume in ParametersManager().volumes:
                config.addRawVolume(volume)
        if ParametersManager().devices is not None:
            for device in ParametersManager().devices:
                config.addDevice(device)
        if ParametersManager().vpn is not None:
            config.enableVPN()
        if ParametersManager().envs is not None:
            for env in ParametersManager().envs:
                config.addRawEnv(env)
        return config

    @classmethod
    def __createContainer(cls, name: Optional[str]) -> ExegolContainer:
        """Create an ExegolContainer"""
        logger.verbose("Configuring new exegol container")
        # Create exegol config
        image: Optional[ExegolImage] = cast(ExegolImage, cls.__loadOrInstallImage())
        config = cls.__prepareContainerConfig()
        assert image is not None  # load or install return an image
        model = ExegolContainerTemplate(name, config, image)

        # Recap
        ExegolTUI.printContainerRecap(model)
        if cls.__interactive_mode:
            if not model.image.isUpToDate() and \
                    Confirm("Do you want to [green]update[/green] the selected image?", False):
                image = UpdateManager.updateImage(model.image.getName())
                if image is not None:
                    model.image = image
                    ExegolTUI.printContainerRecap(model)
            command_options = []
            while not Confirm("Is the container configuration [green]correct[/green]?", default=True):
                command_options = model.config.interactiveConfig(model.name)
                ExegolTUI.printContainerRecap(model)
            logger.info(f"Command line of the configuration: "
                        f"[green]exegol start {model.name} {model.image.getName()} {' '.join(command_options)}[/green]")
            logger.info("To use exegol [orange3]without interaction[/orange3], "
                        "read CLI options with [green]exegol start -h[/green]")

        container = DockerUtils.createContainer(model)
        container.postStartSetup()
        return container

    @classmethod
    def __createTmpContainer(cls, image_name: Optional[str] = None) -> ExegolContainer:
        """Create a temporary ExegolContainer with custom entrypoint"""
        logger.verbose("Configuring new exegol container")
        # Create exegol config
        config = cls.__prepareContainerConfig()
        # When container exec a command as a daemon, the execution must be set on the container's entrypoint
        if ParametersManager().daemon:
            # Using formatShellCommand to support zsh aliases
            cmd = ExegolContainer.formatShellCommand(ParametersManager().exec)
            config.setContainerCommand(cmd)
        # Workspace must be disabled for temporary container because host directory is never deleted
        config.disableDefaultWorkspace()
        name = f"tmp-{binascii.b2a_hex(os.urandom(4)).decode('ascii')}"
        image: ExegolImage = cast(ExegolImage, cls.__loadOrInstallImage(override_image=image_name))
        model = ExegolContainerTemplate(name, config, image)

        container = DockerUtils.createContainer(model, temporary=True)
        container.postStartSetup()
        return container

    @classmethod
    def __checkUselessParameters(cls):
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
            if user_inputs.get(param) is not None and \
                    user_inputs.get(param) != creation_parameters.get(param).kwargs.get('default'):
                # If the supplied parameter is positional, getting his printed name
                name = creation_parameters.get(param).kwargs.get('metavar')
                if name is None:
                    # if not, using the args name
                    detected.append(' / '.join(creation_parameters.get(param).args))
                else:
                    detected.append(name)
        if len(detected) > 0:
            logger.warning(f"These parameters ({', '.join(detected)}) have been entered although the container already "
                           f"exists, they will not be taken into account.")
