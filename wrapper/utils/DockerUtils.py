import json
import os
from typing import List, Optional

import docker
import requests
from docker import DockerClient
from docker.errors import APIError, DockerException, NotFound
from docker.models.images import Image
from docker.models.volumes import Volume

from wrapper.console.TUI import ExegolTUI
from wrapper.console.cli.ParametersManager import ParametersManager
from wrapper.exceptions.ExegolExceptions import ObjectNotFound
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


# SDK Documentation : https://docker-py.readthedocs.io/en/stable/index.html

# Utility class between exegol and the Docker SDK
class DockerUtils:
    try:
        # Connect Docker SDK to the local docker instance.
        # Docker connection setting is loaded from the user environment variables.
        __client: DockerClient = docker.from_env()
    except DockerException as err:
        logger.error(err)
        logger.critical(
            "Unable to connect to docker (from env config). Is docker installed and running on your machine? "
            "Exiting.")
    __images: Optional[List[ExegolImage]] = None
    __containers: Optional[List[ExegolContainer]] = None

    # # # Container Section # # #

    @classmethod
    def listContainers(cls) -> List[ExegolContainer]:
        """List available docker containers.
        Return a list of ExegolContainer"""
        if cls.__containers is None:
            logger.verbose("Listing local Exegol containers")
            cls.__containers = []
            try:
                docker_containers = cls.__client.containers.list(all=True, filters={"name": "exegol-"})
            except APIError as err:
                logger.debug(err)
                logger.critical(err.explanation)
                return
            logger.raw(f"[bold blue][*][/bold blue] Number of Exegol containers: {len(docker_containers)}{os.linesep}", markup=True)
            for container in docker_containers:
                cls.__containers.append(ExegolContainer(container))
        return cls.__containers

    @classmethod
    def createContainer(cls, model: ExegolContainerTemplate, temporary: bool = False,
                        command: str = None) -> ExegolContainer:
        """Create an Exegol container from an ExegolContainerTemplate configuration.
        Return an ExegolContainer if the creation was successful."""
        logger.info("Creating new exegol container")
        model.prepare()
        if command is not None:
            # Overwriting container starting command, shouldn't be used, prefer using config.setContainerCommand()
            model.config.setContainerCommand(command)
        logger.debug(model)
        if model.config.isCommonResourcesEnable():
            volume = cls.__loadCommonVolume()
            if volume is None:
                logger.warning("Error while creating common resources volume")
        try:
            container = cls.__client.containers.run(model.image.getFullName(),
                                                    command=model.config.getContainerCommand(),
                                                    detach=True,
                                                    name=model.hostname,
                                                    hostname=model.hostname,
                                                    devices=model.config.getDevices(),
                                                    environment=model.config.getEnvs(),
                                                    network_mode=model.config.getNetworkMode(),
                                                    ports=model.config.getPorts(),
                                                    privileged=model.config.getPrivileged(),
                                                    cap_add=model.config.getCapabilities(),
                                                    sysctls=model.config.getSysctls(),
                                                    shm_size=model.config.shm_size,
                                                    stdin_open=model.config.interactive,
                                                    tty=model.config.tty,
                                                    mounts=model.config.getVolumes(),
                                                    remove=temporary,
                                                    auto_remove=temporary,
                                                    working_dir=model.config.getWorkingDir())
        except APIError as err:
            logger.error(err.explanation.decode('utf-8') if type(err.explanation) is bytes else err.explanation)
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
    def getContainer(cls, tag: str) -> ExegolContainer:
        """Get an ExegolContainer from tag name."""
        try:
            # Fetch potential container match from DockerSDK
            container = cls.__client.containers.list(all=True, filters={"name": f"exegol-{tag}"})
        except APIError as err:
            logger.debug(err)
            logger.critical(err.explanation)
            return
        # Check if there is at least 1 result. If no container was found, raise ObjectNotFound.
        if container is None or len(container) == 0:
            raise ObjectNotFound
        # Filter results with exact name matching
        for c in container:
            if c.name == f"exegol-{tag}":
                # When the right container have been found, select it and stop the search
                return ExegolContainer(c)
        # When there is some close container's name,
        # docker may return some results but none of them correspond to the request.
        # In this case, ObjectNotFound is raised
        raise ObjectNotFound

    # # # Volumes Section # # #

    @classmethod
    def __loadCommonVolume(cls) -> Volume:
        """Load or create the common resource volume for exegol containers
        (must be created before the container, SDK limitation)
        Return the docker volume object"""
        try:
            os.makedirs(ConstantConfig.common_share_path, exist_ok=True)
        except PermissionError:
            logger.error("Unable to create the shared resource folder on the filesystem locally.")
            logger.critical(f"Insufficient permission to create the folder: {ConstantConfig.common_share_path}")
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
                                                                  'device': ConstantConfig.common_share_path,
                                                                  'type': 'none'})
            except APIError as err:
                logger.error(f"Error while creating common share docker volume.")
                logger.debug(err)
                logger.critical(err.explanation)
                return None
        except APIError as err:
            logger.critical(f"Unexpected error by Docker SDK : {err}")
            return None
        return volume

    # # # Image Section # # #

    @classmethod
    def listImages(cls) -> List[ExegolImage]:
        """List available docker images.
        Return a list of ExegolImage"""
        if cls.__images is None:
            logger.verbose("Listing local and remote Exegol images")
            remote_images = cls.__listRemoteImages()
            local_images = cls.__listLocalImages()
            cls.__images = ExegolImage.mergeImages(remote_images, local_images)
        return cls.__images

    @classmethod
    def listInstalledImages(cls) -> List[ExegolImage]:
        """List installed docker images.
        Return a list of ExegolImage"""
        images = cls.listImages()
        # Selecting only installed image
        return [img for img in images if img.isInstall()]

    @classmethod
    def getImage(cls, tag: str) -> ExegolImage:
        """Get an ExegolImage from tag name."""
        # Fetch every images available
        images = cls.listImages()
        # Find a match
        for i in images:
            if i.getName() == tag:
                return i
        raise ObjectNotFound

    @classmethod
    def getInstalledImage(cls, tag: str) -> ExegolImage:
        """Get an already installed ExegolImage from tag name."""
        docker_local_image = cls.__listLocalImages(tag)
        if docker_local_image is None or len(docker_local_image) == 0:
            raise ObjectNotFound
        # DockerSDK image search is an exact matching, no need to add more check
        return ExegolImage(docker_image=docker_local_image[0])

    @classmethod
    def __listLocalImages(cls, tag: Optional[str] = None) -> List[Image]:
        """List local docker images already installed.
        Return a list of docker images objects"""
        logger.debug("Fetching local image tags, digests (and other attributes)")
        try:
            image_name = ConstantConfig.IMAGE_NAME + ("" if tag is None else f":{tag}")
            return cls.__client.images.list(image_name, filters={"dangling": False})
        except APIError as err:
            logger.debug(err)
            logger.critical(err.explanation)
            return

    @classmethod
    def __listRemoteImages(cls) -> List[ExegolImage]:
        """List remote dockerhub images available.
        Return a list of ExegolImage"""
        logger.debug("Fetching remote image tags, digests and sizes")
        try:
            remote_images_request = requests.get(
                url="https://hub.docker.com/v2/repositories/{}/tags".format(ConstantConfig.IMAGE_NAME),
                timeout=(5, 10), verify=ParametersManager().verify)
        except requests.exceptions.ConnectionError as err:
            logger.warning("Connection Error: you probably have no internet, skipping online queries")
            logger.debug(f"Error: {err}")
            return []
        except requests.exceptions.RequestException as err:
            logger.warning("Unknown connection Error. Skipping online queries.")
            logger.error(f"Error: {err}")
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
    def updateImage(cls, image: ExegolImage) -> bool:
        """Update an ExegolImage"""  # TODO add local image support / move this procedure
        logger.info(f"Updating exegol image : {image.getName()}")
        name = image.updateCheck()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            try:
                ExegolTUI.downloadDockerLayer(
                    cls.__client.api.pull(repository=ConstantConfig.IMAGE_NAME,
                                          tag=name,
                                          stream=True,
                                          decode=True))
                logger.success(f"Image successfully updated")
                return True
                # TODO remove old image version ? /!\ Collision with existing containers
            except APIError as err:
                if err.status_code == 500:
                    logger.debug(f"Error: {err}")
                    logger.error("Error while contacting docker hub. You probably don't have internet. Aborting.")
                else:
                    logger.critical(f"An error occurred while downloading this image : {err}")
        return False

    @classmethod
    def removeImage(cls, image: ExegolImage) -> bool:
        """Remove an ExegolImage from disk"""
        logger.info(f"Removing image '{image.getName()}'")
        tag = image.removeCheck()
        if tag is None:  # Skip removal if image is not installed locally.
            return False
        try:
            cls.__client.images.remove(image.getFullName(), force=False, noprune=False)
            logger.success("Docker image successfully removed.")
            return True
        except APIError as err:
            # Handle docker API error code
            if err.status_code == 409:
                logger.error("This image cannot be deleted because it is currently used by a container. Aborting.")
            elif err.status_code == 404:
                logger.error("This image doesn't exist locally. Aborting.")
            else:
                logger.critical(f"An error occurred while removing this image : {err}")
        return False

    @classmethod
    def buildImage(cls, tag: str, build_profile: Optional[str] = None):
        """Build a docker image from source"""
        logger.info(f"Building exegol image : {tag}")
        if build_profile is None:
            build_profile = "Dockerfile"
        logger.info("Starting build. Please wait, this might be [bold](very)[/bold] long.")
        logger.verbose(
            f"Creating build context from [gold]{ConstantConfig.build_context_path}[/gold] with [green][b]{build_profile}[/b][/green]")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
            # dockerfile is the Dockerfile filename
            ExegolTUI.buildDockerImage(
                cls.__client.api.build(path=ConstantConfig.build_context_path,
                                       dockerfile=build_profile,
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
                logger.critical(f"An error occurred while building this image : {err}")

    @classmethod
    def clearCache(cls):
        """Remove class's images and containers data cache
        Only needed if the list as to be updated in the same runtime at a later moment"""
        cls.__containers = None
        cls.__images = None
