import logging
from typing import Union, List

from wrapper.console.TUI import ExegolTUI
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.exceptions.ExegolExceptions import ObjectNotFound
from wrapper.manager.UpdateManager import UpdateManager
from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger


# Main procedure of exegol
class ExegolManager:
    __container = None
    __image = None

    @staticmethod
    def info():
        """Print a list of available images and containers on the current host"""
        ExegolManager.banner()
        # List and print images
        images = DockerUtils.listImages()
        ExegolTUI.printTable(images)
        # List and print containers
        containers = DockerUtils.listContainers()
        ExegolTUI.printTable(containers)

    @classmethod
    def start(cls):
        logger.info("Starting exegol")
        container = cls.__loadOrCreateContainer()
        container.start()
        container.spawnShell()

    @classmethod
    def exec(cls):
        logger.info("Starting exegol")
        container = cls.__loadOrCreateContainer()
        raise NotImplementedError
        # container.exec()

    @classmethod
    def stop(cls):
        logger.info("Stopping exegol")
        container = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        for c in container:
            c.stop()

    @classmethod
    def uninstall(cls):
        logger.info("Uninstalling an exegol image")
        images = cls.__loadOrInstallImage(multiple=True, must_exist=True)
        for img in images:
            DockerUtils.removeImage(img)

    @classmethod
    def remove(cls):
        logger.info("Removing an exegol container")
        containers = cls.__loadOrCreateContainer(multiple=True, must_exist=True)
        for c in containers:
            c.remove()

    @classmethod
    def banner(cls):
        banner = f"""
     _____                      _ 
    |  ___|                    | |
    | |_____  _____  __ _  ___ | |
    |  __|\ \/ / _ \/ _` |/ _ \| |
    | |___ >  <  __/ (_| | (_) | |
    \____|/_/\_\___|\__, |\___/|_|
                    __/ |        
                   |___/      v{ConstantConfig.version}

"""
        logger.raw(banner, level=logging.INFO)

    @classmethod
    def __loadOrInstallImage(cls,
                             multiple: bool = False,
                             must_exist: bool = False) -> Union[ExegolImage, List[ExegolImage]]:
        """Select / Load (and install) an ExegolImage
        When must_exist is set to True, return None if no image are installed
        When multiple is set to True, return a list of ExegolImage
        Otherwise, always return an ExegolImage"""
        if cls.__image is not None:
            # Return cache
            return cls.__image
        image_tag = None  # TODO add image tag option
        image_selection = None
        # While an image have not been selected
        while image_selection is None:
            try:
                if image_tag is None:
                    # List all images available
                    images = DockerUtils.listInstalledImages() if must_exist else DockerUtils.listImages()
                    # Interactive choice with TUI
                    if multiple:
                        # When multiple is set, allow user to select multiple objects
                        image_selection = ExegolTUI.multipleSelectFromTable(images, object_type=ExegolImage)
                    else:
                        image_selection = ExegolTUI.selectFromTable(images, object_type=ExegolImage,
                                                                    allow_None=not must_exist)
                    # Check if the user has chosen an existing image
                    if type(image_selection) is str:
                        # Otherwise create a new image with the supplied name (on the next loop)
                        image_tag = image_selection
                        raise ObjectNotFound
                else:
                    # Select image by tag name
                    image_selection = DockerUtils.getImage(image_tag)
            except ObjectNotFound:
                # ObjectNotFound is raised when the image_tag provided by the user does not match any existing image.
                if image_tag is not None:
                    # Only print this warning when the image name have been interactively selected
                    logger.warning(f"The image named '{image_tag}', has not been found.")
                # If the user's selected image have not been found, offer the choice to build a local image at this name
                # (only if must_exist is not set)
                if not must_exist:
                    image_selection = UpdateManager.updateImage(image_tag)
                image_tag = None
                # Allow the user to interactively select another installed image
                if must_exist:
                    continue
            except IndexError:
                # IndexError is raised when no image are available (not applicable when multiple is set, return an empty array)
                if must_exist:
                    # If there is no image installed, return none
                    return [] if multiple else None
                else:
                    # If the user's selected image have not been found, offer the choice to build a local image at this name
                    # (only if must_exist is not set)
                    image_selection = UpdateManager.updateImage(image_tag)
                    image_tag = None
            # Check if multiple image have been selected
            if type(image_selection) is ExegolImage:
                check_img = [image_selection]
            else:
                check_img = image_selection
            assert check_img is not None  # TODO add more check / critical logger (when user say no to building)
            # Check if every image are installed
            for i in range(len(check_img)):
                if not check_img[i].isInstall():
                    # When the user parameter specify an uninstalled image, allow him to interactively choose an another image
                    if must_exist:
                        logger.error(f"The selected image '{check_img[i].getName()}' is not installed.")
                        # If one of the image is not install, restart the selection
                        image_selection = None
                        image_tag = None
                    else:
                        # Check if the selected image is installed and install it
                        logger.warning("The selected image is not installed.")
                        # Download remote image
                        DockerUtils.updateImage(check_img[i])
                        # Select installed image
                        check_img[i] = DockerUtils.getImage(check_img[i].getName())
            # Depending on multiple, return ExegolImage or an array of ExegolImage
            if not multiple:
                cls.__image = check_img[0]
            else:
                cls.__image = check_img
        return cls.__image

    @classmethod
    def __loadOrCreateContainer(cls,
                                multiple: bool = False,
                                must_exist: bool = False) -> Union[ExegolContainer, List[ExegolContainer]]:
        """Select one or multipleExegolContainer
        Or create a new ExegolContainer if no one already exist (and must_exist is not set)
        When must_exist is set to True, return None if no container exist
        When multiple is set to True, return a list of ExegolContainer"""
        if cls.__container is not None:
            # Return cache
            return cls.__container
        container_tag = ParametersManager().containertag
        try:
            if container_tag is None:
                # List all images available
                containers = DockerUtils.listContainers()
                # Interactive choice with TUI
                if multiple:
                    container = ExegolTUI.multipleSelectFromTable(containers, object_type=ExegolContainer)
                else:
                    container = ExegolTUI.selectFromTable(containers, object_type=ExegolContainer,
                                                          allow_None=not must_exist)
                # Check if the user has chosen an existing container
                if type(container) is ExegolContainer or (multiple and type(container) is list):
                    cls.__container = container
                else:
                    # Otherwise create a new container with the supplied name
                    cls.__container = cls.__createContainer(container)
            else:
                # Try to find the corresponding container
                container = DockerUtils.getContainer(container_tag)
                if multiple:
                    cls.__container = [container]
                else:
                    cls.__container = container
        except (ObjectNotFound, IndexError):
            # ObjectNotFound is raised when the container_tag provided by the user does not match any existing container.
            # IndexError is raise when no container exist
            # Create container
            if must_exist:
                return [] if multiple else None
            return cls.__createContainer(container_tag)
        return cls.__container

    @classmethod
    def __createContainer(cls, name: str) -> ExegolContainer:
        """Create an ExegolContainer"""
        logger.info("Creating new exegol container")
        # Create default exegol config
        config = ContainerConfig()
        # TODO enable features depending on user input
        model = ExegolContainerTemplate(name, config, cls.__loadOrInstallImage())
        return DockerUtils.createContainer(model)
