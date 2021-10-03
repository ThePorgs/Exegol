import json

import docker
import requests
from docker.errors import APIError

from wrapper.console.TUI import ExegolTUI
from wrapper.exceptions.ExegolExceptions import ContainerNotFound
from wrapper.model.ExegolContainer import ExegolContainer
from wrapper.model.ExegolContainerTemplate import ExegolContainerTemplate
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


# SDK Documentation : https://docker-py.readthedocs.io/en/stable/index.html

class DockerUtils:
    __client = docker.from_env()
    __images = None
    __containers = None

    # # # Container Section # # #

    @classmethod
    def listContainers(cls):
        logger.info("Available containers")
        result = []
        docker_containers = cls.__client.containers.list(all=True, filters={"name": "exegol-"})
        for container in docker_containers:
            result.append(ExegolContainer(container))
        return result

    @classmethod
    def createContainer(cls, model: ExegolContainerTemplate, temporary=False):
        logger.info("Creating new exegol container")
        logger.debug(model)
        container = cls.__client.containers.create(model.image.getFullName(),
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
        if container is not None:
            logger.success("Exegol container successfully created !")
        return ExegolContainer(container, model)

    @classmethod
    def getContainer(cls, tag):
        container = cls.__client.containers.list(all=True, filters={"name": f"exegol-{tag}"})
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
                                        filters={"dangling": False})

    @classmethod
    def __listRemoteImages(cls):
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
            cls.__client.images.list(ExegolImage.image_name, filters={"dangling": False})
        return remote_results

    @classmethod
    def updateImage(cls, image: ExegolImage):
        logger.info(f"Updating exegol image : {image.getName()}")
        name = image.update()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            try:
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
            cls.__client.images.remove(image.getFullName(), force=False, noprune=False)
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
            path = ConstantConfig.root_path
        logger.info("Starting build. Please wait, this might be [bold](very)[/bold] long.")
        logger.verbose(f"Creating build context from [gold]{path}[/gold]")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
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
