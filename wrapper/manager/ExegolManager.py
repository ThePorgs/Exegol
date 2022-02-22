import binascii
import logging
import os
from typing import Union, List, Tuple, Optional, cast, Sequence

from wrapper.console.TUI import ExegolTUI
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.console.cli.actions.GenericParameters import ContainerCreation
from wrapper.exceptions.ExegolExceptions import ObjectNotFound
from wrapper.manager.UpdateManager import UpdateManager
from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.model.SelectableInterface import SelectableInterface
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.EnvInfo import EnvInfo
from wrapper.utils.ExeLog import logger, console
from wrapper.console.ExegolPrompt import Confirm


# Main procedure of exegol
class ExegolManager:
    __container: Union[Optional[ExegolContainer], List[ExegolContainer]] = None
    __image: Union[Optional[ExegolImage], List[ExegolImage]] = None

    @staticmethod
    def info():
        """Print a list of available images and containers on the current host"""
        ExegolManager.print_version()
        logger.empty_line()
        with console.status(f"Loading information", spinner_style="blue"):
            images = DockerUtils.listImages()
            containers = DockerUtils.listContainers()
        # List and print images
        ExegolTUI.printTable(images)
        logger.empty_line()
        # List and print containers
        ExegolTUI.printTable(containers)

    @classmethod
    def start(cls):
        logger.info("Starting exegol")
        container = cls.__loadOrCreateContainer()
        if not container.isNew():
            # Check and warn user if some parameters dont apply to the current sessionh
            cls.__checkUselessParameters()
        container.start()
        container.spawnShell()

    @classmethod
    def exec(cls):
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
        logger.info("Stopping exegol")
        container = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        for c in container:
            c.stop(timeout=2)

    @classmethod
    def install(cls):
        UpdateManager.updateImage(install_mode=True)

    @classmethod
    def update(cls):
        UpdateManager.updateGit()
        UpdateManager.updateImage()

    @classmethod
    def uninstall(cls):
        logger.info("Uninstalling an exegol image")
        images = cls.__loadOrInstallImage(multiple=True, must_exist=True)
        all_name = ", ".join([x.getName() for x in images])
        if not Confirm(f"Are you sure you want to [red]permanently remove[/red] the following images? [orange3][ {all_name} ][/orange3]",
                       default=False):
            logger.error("Aborting operation.")
            return
        for img in images:
            DockerUtils.removeImage(img)

    @classmethod
    def remove(cls):
        logger.info("Removing an exegol container")
        containers = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        all_name = ", ".join([x.name for x in containers])
        if not Confirm(f"Are you sure you want to [red]permanently remove[/red] the following containers? [orange3][ {all_name} ][/orange3]",
                       default=False):
            logger.error("Aborting operation.")
            return
        for c in containers:
            c.remove()

    @classmethod
    def print_version(cls):
        logger.raw(f"[bold blue][*][/bold blue] Exegol is currently in version v{ConstantConfig.version}{os.linesep}",
                   level=logging.INFO, markup=True)
        logger.debug(f"Host OS: {EnvInfo.getHostOs()}")
        if EnvInfo.isWindowsHost():
            logger.debug(f"Python environment: {EnvInfo.current_platform}")
            logger.debug(f"Docker engine: {EnvInfo.getDockerEngine().upper()}")
            if EnvInfo.is_linux_shell:
                logger.debug(f"Windows release: Not available on a linux shell")
            else:
                logger.debug(f"Windows release: {EnvInfo.windows_release}")

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
        image_selection = None
        # While an image have not been selected
        while image_selection is None:
            try:
                if image_tag is None:
                    # Interactive (TUI) image selection
                    image_selection = cls.__interactiveSelection(ExegolImage, multiple, must_exist)
                else:
                    # Select image by tag name (non-interactive)
                    image_selection = DockerUtils.getInstalledImage(image_tag)
            except ObjectNotFound:
                # ObjectNotFound is raised when the image_tag provided by the user does not match any existing image.
                if image_tag is not None:
                    logger.warning(f"The image named '{image_tag}', has not been found.")
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
    def __checkImageInstallationStatus(cls, image_selection, multiple: bool = False, must_exist: bool = False) -> Tuple[
        bool, Optional[Union[ExegolImage, ExegolContainer, List[ExegolImage], List[ExegolContainer]]]]:
        """Checks if the selected images are installed and ready for use.
        returns false if the images are supposed to be already installed."""
        # Checks if one or more images have been selected and unifies the format into a list.
        reverse_type = False
        if type(image_selection) is ExegolImage:
            check_img = [image_selection]
            # Tag of the operation to reverse it before the return
            reverse_type = True
        else:
            check_img = image_selection

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
                    if DockerUtils.updateImage(check_img[i]):
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
        container_tag = override_container if override_container is not None else ParametersManager().containertag
        try:
            if container_tag is None:
                # Interactive container selection
                cls.__container = cast(Union[Optional[ExegolContainer], List[ExegolContainer]],
                                       cls.__interactiveSelection(ExegolContainer, multiple, must_exist))
            else:
                # Try to find the corresponding container
                container = DockerUtils.getContainer(container_tag)
                if multiple:
                    cls.__container = [container]
                else:
                    cls.__container = container
        except (ObjectNotFound, IndexError):
            # ObjectNotFound is raised when the container_tag provided by the user does not match any existing container.
            # IndexError is raise when no container exist (raised from TUI interactive selection)
            # Create container
            if must_exist:
                logger.error("Container not found")
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
        if ParametersManager().common_resources:
            config.enableCommonVolume()
        if ParametersManager().workspace_path:
            if ParametersManager().mount_current_dir:
                logger.warning(
                    f'Workspace conflict detected (-cwd cannot be use with -w). Using: {ParametersManager().workspace_path}')
            config.setWorkspaceShare(ParametersManager().workspace_path)
        if ParametersManager().privileged:
            config.enablePrivileged()
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
    def __createContainer(cls, name: str) -> ExegolContainer:
        """Create an ExegolContainer"""
        logger.verbose("Configuring new exegol container")
        # Create exegol config
        config = cls.__prepareContainerConfig()
        image: ExegolImage = cast(ExegolImage, cls.__loadOrInstallImage())
        model = ExegolContainerTemplate(name, config, image)

        # Recap
        ExegolTUI.printContainerRecap(model)
        # TODO handle interactive config

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
