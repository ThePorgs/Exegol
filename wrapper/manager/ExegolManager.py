from wrapper.console.TUI import ExegolTUI
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.exceptions.ExegolExceptions import ObjectNotFound
from wrapper.manager.UpdateManager import UpdateManager
from wrapper.model.ContainerConfig import ContainerConfig
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger


class ExegolManager:
    __container = None
    __image = None

    @staticmethod
    def info():
        """Print a list of available images and containers on the current host"""
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
    def stop(cls):
        logger.info("Stopping exegol")
        container = cls.__loadOrCreateContainer(must_exist=True)
        if container is not None:
            container.stop()

    @classmethod
    def uninstall(cls):
        logger.info("Uninstalling an exegol image")
        image = cls.__loadOrInstallImage(must_exist=True)  # TODO add multiple selection
        if image is not None:
            DockerUtils.removeImage(image)

    @classmethod
    def remove(cls):
        logger.info("Removing an exegol container")
        container = cls.__loadOrCreateContainer(must_exist=True)  # TODO add multiple selection
        if container is not None:
            container.remove()

    @classmethod
    def __loadOrInstallImage(cls, must_exist=False) -> ExegolImage:
        """Select / Load (and install) an ExegolImage
        When must_exist is set to True, return None if no image are installed
        Otherwise, always return an ExegolImage"""
        if cls.__image is not None:
            # Return cache
            return cls.__image
        image_tag = None  # TODO add image tag option
        image = None
        # While an image have not been selected
        while image is None:
            try:
                if image_tag is None:
                    # List all images available
                    images = DockerUtils.listInstalledImages() if must_exist else DockerUtils.listImages()
                    # Interactive choice with TUI
                    image = ExegolTUI.selectFromTable(images, object_type=ExegolImage, allow_None=not must_exist)
                    # Check if the user has chosen an existing image
                    if type(image) is str:
                        # Otherwise create a new image with the supplied name
                        image_tag = image
                        raise ObjectNotFound
                else:
                    # Select image by tag name
                    image = DockerUtils.getImage(image_tag)
            except ObjectNotFound:
                # ObjectNotFound is raised when the image_tag provided by the user does not match any existing image.
                if image_tag is not None:
                    # Only print this warning when the image name have been interactively selected
                    logger.warning(f"The image named '{image_tag}', has not been found.")
                # If the user's selected image have not been found, offer the choice to build a local image at this name
                # (only if must_exist is not set)
                if not must_exist:
                    image = UpdateManager.updateImage(image_tag)
                image_tag = None
                # Allow the user to interactively select another installed image
                if must_exist:
                    continue
            except IndexError:
                # IndexError is raised when no image are available
                if must_exist:
                    # If there is no image installed, return none
                    return None
                else:
                    # If the user's selected image have not been found, offer the choice to build a local image at this name
                    # (only if must_exist is not set)
                    image = UpdateManager.updateImage(image_tag)
                    image_tag = None
            # When the user parameter specify an uninstalled image, allow him to interactively choose an another image
            if must_exist and not image.isInstall():
                logger.error("The selected image is not installed.")
                image = None
                image_tag = None
        # Check if the selected image is installed
        if not image.isInstall():
            logger.warning("The selected image is not installed.")
            # Download remote image
            DockerUtils.updateImage(image)
            # Select installed image
            cls.__image = DockerUtils.getImage(image.getName())
        else:
            cls.__image = image
        return cls.__image

    @classmethod
    def __loadOrCreateContainer(cls, must_exist=False) -> ExegolContainer:
        """Select or create an ExegolContainer"""
        if cls.__container is not None:
            # Return cache
            return cls.__container
        container_tag = ParametersManager().containertag
        try:
            if container_tag is None:
                # List all images available
                containers = DockerUtils.listContainers()
                # Interactive choice with TUI
                container = ExegolTUI.selectFromTable(containers, object_type=ExegolContainer,
                                                      allow_None=not must_exist)
                # Check if the user has chosen an existing container
                if type(container) is ExegolContainer:
                    cls.__container = container
                else:
                    # Otherwise create a new container with the supplied name
                    cls.__container = cls.__createContainer(container)
            else:
                # Try to find the corresponding container
                cls.__container = DockerUtils.getContainer(container_tag)
        except (ObjectNotFound, IndexError):
            # ObjectNotFound is raised when the container_tag provided by the user does not match any existing container.
            # IndexError is raise when no container exist
            # Create container
            if must_exist:
                return None
            return cls.__createContainer(container_tag)
        return cls.__container

    @classmethod
    def __createContainer(cls, name) -> ExegolContainer:
        """Create an ExegolContainer"""
        logger.info("Creating new exegol container")
        # Create default exegol config
        config = ContainerConfig()
        # TODO enable features depending on user input
        model = ExegolContainerTemplate(name, config, cls.__loadOrInstallImage())
        return DockerUtils.createContainer(model)
