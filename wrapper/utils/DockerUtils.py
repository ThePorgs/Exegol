import json
import os

import docker
import requests
from docker.errors import APIError, DockerException, NotFound

from wrapper.console.TUI import ExegolTUI
from wrapper.exceptions.ExegolExceptions import ContainerNotFound
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


# SDK Documentation : https://docker-py.readthedocs.io/en/stable/index.html

class DockerUtils:
    try:
        # Connect Docker SDK to the local docker instance.
        # Docker connection setting is loaded from the user environment variables.
        __client = docker.from_env()
    except DockerException as err:
        logger.error(err)
        logger.critical("Unable to connect to docker (from env config). Is docker install on your local machine ? "
                        "Exiting.")
    __images = None
    __containers = None

    # # # Container Section # # #

    @classmethod
    def listContainers(cls):
        """List available docker containers.
        Return a list of ExegolContainer"""
        logger.verbose("List of Exegol containers")
        if cls.__containers is None:
            cls.__containers = []
            # TODO add error handling
            docker_containers = cls.__client.containers.list(all=True, filters={"name": "exegol-"})
            for container in docker_containers:
                cls.__containers.append(ExegolContainer(container))
        return cls.__containers

    @classmethod
    def createContainer(cls, model: ExegolContainerTemplate, temporary=False):
        """Create an Exegol container from an ExegolContainerTemplate configuration.
        Return an ExegolContainer if the creation was successful."""
        logger.info("Creating new exegol container")
        model.prepare()
        logger.debug(model)
        if model.config.isCommonResourcesEnable():
            volume = cls.__loadCommonVolume()
            if volume is None:
                logger.warning("Error while creating common resources volume")
        try:
            container = cls.__client.containers.run(model.image.getFullName(),
                                                    detach=True,
                                                    name=model.hostname,
                                                    hostname=model.hostname,
                                                    devices=model.config.getDevices(),
                                                    environment=model.config.getEnvs(),
                                                    network_mode=model.config.getNetworkMode(),
                                                    ports=model.config.getPorts(),
                                                    privileged=model.config.getPrivileged(),
                                                    shm_size=model.config.shm_size,
                                                    stdin_open=model.config.interactive,
                                                    tty=model.config.tty,
                                                    mounts=model.config.getVolumes(),
                                                    remove=temporary,
                                                    working_dir=model.config.getWorkingDir())
        except APIError as err:
            logger.error(err.explanation)
            logger.debug(err)
            logger.critical("Error while creating exegol container. Exiting.")
            return
        if container is not None:
            logger.success("Exegol container successfully created !")
        else:
            logger.critical("Unknown error while creating exegol container. Exiting.")
            return
        return ExegolContainer(container, model)

    @classmethod
    def getContainer(cls, tag):
        """Get an ExegolContainer from tag name."""
        container = cls.__client.containers.list(all=True, filters={"name": f"exegol-{tag}"})  # TODO add error handling
        if container is None or len(container) == 0:
            raise ContainerNotFound
        return ExegolContainer(container[0])

    # # # Volumes Section # # #

    @classmethod
    def __loadCommonVolume(cls):
        """Load or create the common resources volume for exegol containers
        (must be created before the container, SDK limitation)
        Return the docker volume object"""
        os.makedirs(ConstantConfig.COMMON_SHARE_PATH, exist_ok=True)
        try:
            # Check if volume already exist
            volume = cls.__client.volumes.get(ConstantConfig.COMMON_SHARE_NAME)
        except NotFound:
            try:
                # Creating a docker volume bind to a host path
                # Docker volume are more easily shared by container
                # Docker volume can load data from container image on host's folder creation
                volume = cls.__client.volumes.create(ConstantConfig.COMMON_SHARE_NAME, driver="local",
                                                     driver_opts={'o': 'bind',
                                                                  'device': ConstantConfig.COMMON_SHARE_PATH,
                                                                  'type': 'none'})
            except APIError as err:
                logger.error(f"Error while creating common share docker volume : {err}")
                return None
        except APIError as err:
            logger.error(f"Unexpected error by Docker SDK : {err}")
            return None
        return volume

    # # # Image Section # # #

    @classmethod
    def listImages(cls):
        """List available docker images.
        Return a list of ExegolImage"""
        logger.verbose("List of Exegol images")
        if cls.__images is None:
            remote_images = cls.__listRemoteImages()
            local_images = cls.__listLocalImages()
            cls.__images = ExegolImage.mergeImages(remote_images, local_images)
        return cls.__images

    @classmethod
    def __listLocalImages(cls, tag=None):
        """List local docker images already installed.
        Return a list of docker images objects"""
        logger.debug("Fetching local image tags, digests (and other attributes)")
        return cls.__client.images.list(ConstantConfig.IMAGE_NAME + "" if tag is None else ":" + tag,
                                        filters={"dangling": False})  # TODO add error handling

    @classmethod
    def __listRemoteImages(cls):
        """List remote dockerhub images available.
        Return a list of ExegolImage"""
        logger.debug("Fetching remote image tags, digests and sizes")
        try:
            remote_images_request = requests.get(
                url="https://hub.docker.com/v2/repositories/{}/tags".format(ConstantConfig.IMAGE_NAME),
                timeout=(5, 10), verify=True)  # TODO add verify as optional
        except requests.exceptions.ConnectionError as err:
            logger.warning("Connection Error: you probably have no internet, skipping online queries")
            logger.debug(f"Error: {err}")
            return []
        remote_results = []
        remote_images_list = json.loads(remote_images_request.text)
        for docker_image in remote_images_list["results"]:
            exegol_image = ExegolImage(name=docker_image.get('name', 'NONAME'),
                                       digest=docker_image["images"][0]["digest"],
                                       size=docker_image.get("full_size"))
            remote_results.append(exegol_image)
        return remote_results

    @classmethod
    def updateImage(cls, image: ExegolImage):
        """Update an ExegolImage"""  # TODO add local image support / move this procedure
        logger.info(f"Updating exegol image : {image.getName()}")
        name = image.update()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            try:
                # TODO add error handling
                ExegolTUI.downloadDockerLayer(
                    cls.__client.api.pull(repository=ConstantConfig.IMAGE_NAME,
                                          tag=name,
                                          stream=True,
                                          decode=True))
                logger.success(f"Image successfully updated")
                # TODO remove old image version ? /!\ Collision with existing containers
            except APIError as err:
                if err.status_code == 500:
                    logger.error("Error while contacting docker hub. You probably don't have internet. Aborting.")
                    logger.debug(f"Error: {err}")
                else:
                    logger.error(f"An error occurred while downloading this image : {err}")

    @classmethod
    def removeImage(cls, image: ExegolImage):
        """Remove an ExegolImage from disk"""
        logger.info(f"Removing image '{image.getName()}'")
        tag = image.remove()
        if tag is None:  # Skip removal if image is not installed locally.
            return
        try:
            cls.__client.images.remove(image.getFullName(), force=False, noprune=False)  # TODO add error handling
            logger.success("Docker image successfully removed.")
        except APIError as err:
            # Handle docker API error code
            if err.status_code == 409:
                logger.error("This image cannot be deleted because it is currently used by a container. Aborting.")
            elif err.status_code == 404:
                logger.error("This image doesn't exist locally. Aborting.")
            else:
                logger.error(f"An error occurred while removing this image : {err}")

    @classmethod
    def buildImage(cls, tag, path=None):
        """Build a docker image from source"""
        logger.info(f"Building exegol image : {tag}")
        if path is None:
            path = ConstantConfig.build_context_path
        logger.info("Starting build. Please wait, this might be [bold](very)[/bold] long.")
        logger.verbose(f"Creating build context from [gold]{path}[/gold]")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
            # TODO add error handling
            ExegolTUI.buildDockerImage(
                cls.__client.api.build(path=path,
                                       dockerfile='Dockerfile',
                                       tag=f"{ConstantConfig.IMAGE_NAME}:{tag}",
                                       rm=True,
                                       forcerm=True,
                                       pull=True,
                                       decode=True))
            logger.success(f"Exegol image successfully built")
        except APIError as err:
            logger.debug(f"Error: {err}")
            if err.status_code == 500:
                logger.error("Error while contacting docker hub. You probably don't have internet. Aborting.")
                logger.debug(f"Error: {err}")
            else:
                logger.error(f"An error occurred while building this image : {err}")
