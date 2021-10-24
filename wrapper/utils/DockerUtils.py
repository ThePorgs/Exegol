import json

import docker
import requests
from docker.errors import APIError, DockerException

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
        __client = docker.from_env()
    except DockerException as err:
        logger.error(err)
        logger.critical("Unable to connect to docker. Is docker install on your local machine ? Exiting.")
        exit(0)
    __images = None
    __containers = None

    # # # Container Section # # #

    @classmethod
    def listContainers(cls):
        logger.info("Available containers")
        if cls.__containers is None:
            cls.__containers = []
            docker_containers = cls.__client.containers.list(all=True, filters={"name": "exegol-"})  # TODO add error handling
            for container in docker_containers:
                cls.__containers.append(ExegolContainer(container))
        return cls.__containers

    @classmethod
    def createContainer(cls, model: ExegolContainerTemplate, temporary=False):
        logger.info("Creating new exegol container")
        logger.debug(model)
        try:
            container = cls.__client.containers.run(model.image.getFullName(),
                                                    detach=True,
                                                    name=model.hostname,
                                                    hostname=model.hostname,
                                                    devices=model.config.devices,
                                                    environment=model.config.envs,
                                                    network_mode=model.config.getNetworkMode(),
                                                    ports=model.config.ports,
                                                    privileged=model.config.privileged,
                                                    shm_size=model.config.shm_size,
                                                    stdin_open=model.config.interactive,
                                                    tty=model.config.tty,
                                                    mounts=model.config.mounts,
                                                    remove=temporary,
                                                    working_dir=model.config.getWorkingDir())
        except APIError as err:
            logger.critical("Error while creating exegol container.")
            logger.error(err.explanation)
            logger.debug(err)
            logger.info("Exiting")
            exit(0)
            return
        if container is not None:
            logger.success("Exegol container successfully created !")
        else:
            logger.error("Unknown error while creating exegol container. Exiting.")
            exit(0)
        return ExegolContainer(container, model)

    @classmethod
    def getContainer(cls, tag):
        container = cls.__client.containers.list(all=True, filters={"name": f"exegol-{tag}"})  # TODO add error handling
        if container is None or len(container) == 0:
            raise ContainerNotFound
        return ExegolContainer(container[0])

    # # # Image Section # # #

    @classmethod
    def listImages(cls):
        logger.info("Available images")
        if cls.__images is None:
            remote_images = cls.__listRemoteImages()
            local_images = cls.__listLocalImages()
            cls.__images = ExegolImage.mergeImages(remote_images, local_images)
        return cls.__images

    @classmethod
    def __listLocalImages(cls, tag=None):
        logger.debug("Fetching local image tags, digests (and other attributes)")
        return cls.__client.images.list(ExegolImage.image_name + "" if tag is None else ":" + tag,
                                        filters={"dangling": False})  # TODO add error handling

    @classmethod
    def __listRemoteImages(cls):  # TODO check if SDK can replace raw request
        logger.debug("Fetching remote image tags, digests and sizes")
        try:
            remote_images_request = requests.get(
                url="https://hub.docker.com/v2/repositories/{}/tags".format(ExegolImage.image_name),
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
            cls.__client.images.list(ExegolImage.image_name, filters={"dangling": False})  # TODO add error handling
        return remote_results

    @classmethod
    def updateImage(cls, image: ExegolImage):
        logger.info(f"Updating exegol image : {image.getName()}")
        name = image.update()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            try:
                # TODO add error handling
                ExegolTUI.downloadDockerLayer(
                    cls.__client.api.pull(repository=ExegolImage.image_name,
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
        logger.info(f"Removing image '{image.getName()}'")
        tag = image.remove()
        if tag is None:  # Skip removal if image doesn't exist locally.
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
        logger.info(f"Building exegol image : {tag}")
        if path is None:
            path = ConstantConfig.dockerfile_path
        logger.info("Starting build. Please wait, this might be [bold](very)[/bold] long.")
        logger.verbose(f"Creating build context from [gold]{path}[/gold]")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
            # TODO add error handling
            ExegolTUI.buildDockerImage(
                cls.__client.api.build(path=path,
                                       tag=f"{ExegolImage.image_name}:{tag}",
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
