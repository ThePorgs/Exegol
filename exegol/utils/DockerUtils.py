import os
from datetime import datetime
from typing import List, Optional, Union, cast

import docker
from docker import DockerClient
from docker.errors import APIError, DockerException, NotFound, ImageNotFound
from docker.models.images import Image
from docker.models.volumes import Volume
from requests import ReadTimeout

from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ObjectNotFound
from exegol.model.ExegolContainer import ExegolContainer
from exegol.model.ExegolContainerTemplate import ExegolContainerTemplate
from exegol.model.ExegolImage import ExegolImage
from exegol.model.MetaImages import MetaImages
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, console, ExeLog
from exegol.utils.UserConfig import UserConfig
from exegol.utils.WebUtils import WebUtils


# SDK Documentation : https://docker-py.readthedocs.io/en/stable/index.html


class DockerUtils:
    """Utility class between exegol and the Docker SDK"""
    try:
        # Connect Docker SDK to the local docker instance.
        # Docker connection setting is loaded from the user environment variables.
        __client: DockerClient = docker.from_env()
        # Check if the docker daemon is serving linux container
        __daemon_info = __client.info()
        if __daemon_info.get("OSType", "linux").lower() != "linux":
            logger.critical(
                f"Docker daemon is not serving linux container ! Docker OS Type is: {__daemon_info.get('OSType', 'linux')}")
        EnvInfo.initData(__daemon_info)
    except DockerException as err:
        if 'ConnectionRefusedError' in str(err):
            logger.critical("Unable to connect to docker (from env config). Is docker running on your machine? "
                            "Exiting.")
        elif 'FileNotFoundError' in str(err):
            logger.critical("Unable to connect to docker. Is docker installed on your machine? "
                            "Exiting.")
        else:
            logger.error(err)
            logger.critical(
                "Unable to connect to docker (from env config). Is docker operational and accessible? on your machine? "
                "Exiting.")
    __images: Optional[List[ExegolImage]] = None
    __containers: Optional[List[ExegolContainer]] = None

    @classmethod
    def clearCache(cls):
        """Remove class's images and containers data cache
        Only needed if the list has to be updated in the same runtime at a later moment"""
        cls.__containers = None
        cls.__images = None

    @classmethod
    def getDockerInfo(cls) -> dict:
        """Fetch info from docker daemon"""
        return cls.__daemon_info

    # # # Container Section # # #

    @classmethod
    def listContainers(cls) -> List[ExegolContainer]:
        """List available docker containers.
        Return a list of ExegolContainer"""
        if cls.__containers is None:
            cls.__containers = []
            try:
                docker_containers = cls.__client.containers.list(all=True, filters={"name": "exegol-"})
            except APIError as err:
                logger.debug(err)
                logger.critical(err.explanation)
                # Not reachable, critical logging will exit
                return  # type: ignore
            for container in docker_containers:
                cls.__containers.append(ExegolContainer(container))
        return cls.__containers

    @classmethod
    def createContainer(cls, model: ExegolContainerTemplate, temporary: bool = False) -> ExegolContainer:
        """Create an Exegol container from an ExegolContainerTemplate configuration.
        Return an ExegolContainer if the creation was successful."""
        logger.info("Creating new exegol container")
        model.prepare()
        logger.debug(model)
        # Preload docker volume before container creation
        for volume in model.config.getVolumes():
            if volume.get('Type', '?') == "volume":
                docker_volume = cls.__loadDockerVolume(volume_path=volume['Source'], volume_name=volume['Target'])
                if docker_volume is None:
                    logger.warning(f"Error while creating docker volume '{volume['Target']}'")
        entrypoint, command = model.config.getEntrypointCommand(model.image.getEntrypointConfig())
        logger.debug(f"Entrypoint: {entrypoint}")
        logger.debug(f"Cmd: {command}")
        try:
            container = cls.__client.containers.run(model.image.getDockerRef(),
                                                    entrypoint=entrypoint,
                                                    command=command,
                                                    detach=True,
                                                    name=model.hostname,
                                                    hostname=model.hostname,
                                                    extra_hosts={model.hostname: '127.0.0.1'},
                                                    devices=model.config.getDevices(),
                                                    environment=model.config.getEnvs(),
                                                    labels=model.config.getLabels(),
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
            # Not reachable, critical logging will exit
            return  # type: ignore
        if container is not None:
            logger.success("Exegol container successfully created !")
        else:
            logger.critical("Unknown error while creating exegol container. Exiting.")
            # Not reachable, critical logging will exit
            return  # type: ignore
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
            # Not reachable, critical logging will exit
            return  # type: ignore
        # Check if there is at least 1 result. If no container was found, raise ObjectNotFound.
        if container is None or len(container) == 0:
            raise ObjectNotFound
        # Filter results with exact name matching
        for c in container:
            if c.name == f"exegol-{tag}":
                # When the right container is found, select it and stop the search
                return ExegolContainer(c)
        # When there is some close container's name,
        # docker may return some results but none of them correspond to the request.
        # In this case, ObjectNotFound is raised
        raise ObjectNotFound

    # # # Volumes Section # # #

    @classmethod
    def __loadDockerVolume(cls, volume_path: str, volume_name: str) -> Volume:
        """Load or create a docker volume for exegol containers
        (must be created before the container, SDK limitation)
        Return the docker volume object"""
        try:
            os.makedirs(volume_path, exist_ok=True)
        except PermissionError:
            logger.error("Unable to create the volume folder on the filesystem locally.")
            logger.critical(f"Insufficient permission to create the folder: {volume_path}")
        try:
            # Check if volume already exist
            volume = cls.__client.volumes.get(volume_name)
            path = volume.attrs.get('Options', {}).get('device', '')
            if path != volume_path:
                try:
                    cls.__client.api.remove_volume(name=volume_name)
                    raise NotFound('Volume must be reloaded')
                except APIError as e:
                    if e.status_code == 409:
                        logger.warning("The path of the volume specified by the user is not the same as in the existing docker volume. "
                                       "The user path will be [red]ignored[/red] as long as the docker volume already exists.")
                        logger.verbose("The volume is already used by some container and cannot be automatically removed.")
                        logger.debug(e.explanation)
                    else:
                        raise NotFound('Volume must be reloaded')
        except NotFound:
            try:
                # Creating a docker volume bind to a host path
                # Docker volume are more easily shared by container
                # Docker volume can load data from container image on host's folder creation
                volume = cls.__client.volumes.create(volume_name, driver="local",
                                                     driver_opts={'o': 'bind',
                                                                  'device': volume_path,
                                                                  'type': 'none'})
            except APIError as err:
                logger.error(f"Error while creating docker volume '{volume_name}'.")
                logger.debug(err)
                logger.critical(err.explanation)
                return None  # type: ignore
        except APIError as err:
            logger.critical(f"Unexpected error by Docker SDK : {err}")
            return None  # type: ignore
        return volume

    # # # Image Section # # #

    @classmethod
    def listImages(cls, include_version_tag: bool = False, include_locked: bool = False) -> List[ExegolImage]:
        """List available docker images.
        Return a list of ExegolImage"""
        if cls.__images is None:
            remote_images = cls.__listRemoteImages()
            local_images = cls.__listLocalImages()
            cls.__images = ExegolImage.mergeImages(remote_images, local_images)
        result = cls.__images
        if not (logger.isEnabledFor(ExeLog.VERBOSE) or include_locked):
            # ToBeRemoved images are only shown in verbose mode
            result = [i for i in result if not i.isLocked()]
        if not include_version_tag:
            # Version specific images not installed are excluded by default
            result = [img for img in result if not img.isVersionSpecific() or img.isInstall()]
        return result

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
        images = cls.listImages(include_version_tag=True, include_locked=True)
        match: Optional[ExegolImage] = None
        # Find a match
        for i in images:
            if i.getName() == tag:
                # If there is a locked image keep it as default
                if i.isLocked():
                    match = i
                else:
                    # Return the first non-outdated image
                    return i
        # If there is any match without lock (outdated) status, return the last outdated image found.
        if match is not None:
            return match
        # If there is no match at all, raise ObjectNotFound to handle the error
        raise ObjectNotFound

    @classmethod
    def getInstalledImage(cls, tag: str) -> ExegolImage:
        """Get an already installed ExegolImage from tag name."""
        try:
            if cls.__images is None:
                try:
                    docker_local_image = cls.__client.images.get(f"{ConstantConfig.IMAGE_NAME}:{tag}")
                    # DockerSDK image get is an exact matching, no need to add more check
                except APIError as err:
                    if err.status_code == 404:
                        # try to find it in recovery mode
                        logger.verbose("Unable to find your image. Trying to find in recovery mode.")
                        recovery_images = cls.__findLocalRecoveryImages(include_untag=True)
                        match = []
                        for img in recovery_images:
                            if ExegolImage.parseAliasTagName(img) == tag:
                                match.append(ExegolImage(docker_image=img))
                        if len(match) == 1:
                            return match[0]
                        elif len(match) > 1:
                            return cast(ExegolImage, ExegolTUI.selectFromTable(match))
                        raise ObjectNotFound
                    else:
                        logger.critical(f"Error on image loading: {err}")
                        return  # type: ignore
                return ExegolImage(docker_image=docker_local_image).autoLoad()
            else:
                for img in cls.__images:
                    if img.getName() == tag:
                        if not img.isInstall() or not img.isUpToDate():
                            # Refresh local image status in case of installation/upgrade operations
                            cls.__findImageMatch(img)
                        return img
        except ObjectNotFound:
            logger.critical(f"The desired image is not installed or do not exist ({ConstantConfig.IMAGE_NAME}:{tag}). Exiting.")
        return  # type: ignore

    @classmethod
    def __listLocalImages(cls, tag: Optional[str] = None) -> List[Image]:
        """List local docker images already installed.
        Return a list of docker images objects"""
        logger.debug("Fetching local image tags, digests (and other attributes)")
        try:
            image_name = ConstantConfig.IMAGE_NAME + ("" if tag is None else f":{tag}")
            images = cls.__client.images.list(image_name, filters={"dangling": False})
        except APIError as err:
            logger.debug(err)
            logger.critical(err.explanation)
            # Not reachable, critical logging will exit
            return  # type: ignore
        # Filter out image non-related to the right repository
        result = []
        ids = set()
        for img in images:
            # len tags = 0 handle exegol <none> images (nightly image lost their tag after update)
            if len(img.attrs.get('RepoTags', [])) == 0 or \
                    ConstantConfig.IMAGE_NAME in [repo_tag.split(':')[0] for repo_tag in img.attrs.get("RepoTags", [])]:
                result.append(img)
                ids.add(img.id)

        # Try to find lost Exegol images
        recovery_images = cls.__findLocalRecoveryImages()
        for img in recovery_images:
            # Docker can keep track of 2 images maximum with RepoTag or RepoDigests, after it's hard to track origin without labels, so this recovery option is "best effort"
            if img.id in ids:
                # Skip image from other repo and image already found
                logger.debug(f"Duplicate found in recovery mode! {img}")
                continue
            else:
                result.append(img)
                ids.add(img.id)
        return result

    @classmethod
    def __findLocalRecoveryImages(cls, include_untag: bool = False) -> List[Image]:
        """This method try to recovery untagged docker images.
        Set include_untag option to recover images with a valid RepoDigest (no not dangling) but without tag."""
        try:
            # Try to find lost Exegol images
            recovery_images = cls.__client.images.list(filters={"dangling": True})
            if include_untag:
                recovery_images += cls.__client.images.list(ConstantConfig.IMAGE_NAME, filters={"dangling": False})
        except APIError as err:
            logger.debug(f"Error occurred in recovery mode: {err}")
            return []
        result = []
        id_list = set()
        for img in recovery_images:
            # Docker can keep track of 2 images maximum with RepoTag or RepoDigests, after it's hard to track origin without labels, so this recovery option is "best effort"
            if len(img.attrs.get('RepoTags', [1])) > 0 or (not include_untag and len(img.attrs.get('RepoDigests', [1])) > 0) or img.id in id_list:
                # Skip image from other repo and image already found
                continue
            if img.labels.get('org.exegol.app', '') == "Exegol":
                result.append(img)
                id_list.add(img.id)
        return result

    @classmethod
    def __listRemoteImages(cls) -> List[MetaImages]:
        """List remote dockerhub images available.
        Return a list of ExegolImage"""
        logger.debug("Fetching remote image tags, digests and sizes")
        remote_results = []
        # Define max number of tags to download from dockerhub (in order to limit download time and discard historical versions)
        page_size = 20
        page_max = 2
        current_page = 0
        url: Optional[str] = f"https://{ConstantConfig.DOCKER_HUB}/v2/repositories/{ConstantConfig.IMAGE_NAME}/tags?page_size={page_size}"
        # Handle multi-page tags from registry
        with console.status(f"Loading registry information from [green]{url}[/green]", spinner_style="blue") as s:
            while url is not None:
                if current_page == page_max:
                    logger.debug("Max page limit reached. In non-verbose mode, downloads will stop there.")
                    if not logger.isEnabledFor(ExeLog.VERBOSE):
                        break
                current_page += 1
                logger.debug(f"Fetching information from: {url}")
                s.update(status=f"Fetching registry information from [green]{url}[/green]")
                docker_repo_response = WebUtils.runJsonRequest(url, "Dockerhub")
                if docker_repo_response is None:
                    logger.warning("Skipping online queries.")
                    return []
                error_message = docker_repo_response.get("message")
                if error_message:
                    logger.error(f"Dockerhub send an error message: {error_message}")
                for docker_images in docker_repo_response.get("results", []):
                    meta_image = MetaImages(docker_images)
                    remote_results.append(meta_image)
                url = docker_repo_response.get("next")  # handle multiple page tags
        # Remove duplication (version specific / latest release)
        return remote_results

    @classmethod
    def __findImageMatch(cls, remote_image: ExegolImage):
        """From a Remote ExegolImage, try to find a local match (using Remote DigestID).
        This method is useful if the image repository name is also lost"""
        try:
            docker_image = cls.__client.images.get(f"{ConstantConfig.IMAGE_NAME}@{remote_image.getRemoteId()}")
        except ImageNotFound:
            raise ObjectNotFound
        remote_image.setDockerObject(docker_image)

    @classmethod
    def downloadImage(cls, image: ExegolImage, install_mode: bool = False) -> bool:
        """Download/pull an ExegolImage"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to download a docker image in offline mode ...")
            return False
        # Switch to install mode if the selected image is not already installed
        install_mode = install_mode or not image.isInstall()
        logger.info(f"{'Installing' if install_mode else 'Updating'} exegol image : {image.getName()}")
        name = image.updateCheck()
        if name is not None:
            logger.info(f"Starting download. Please wait, this might be (very) long.")
            logger.debug(f"Downloading {ConstantConfig.IMAGE_NAME}:{name} ({image.getArch()})")
            try:
                ExegolTUI.downloadDockerLayer(
                    cls.__client.api.pull(repository=ConstantConfig.IMAGE_NAME,
                                          tag=name,
                                          stream=True,
                                          decode=True,
                                          platform="linux/" + image.getArch()))
                logger.success(f"Image successfully updated")
                # Remove old image
                if not install_mode and image.isInstall() and UserConfig().auto_remove_images:
                    cls.removeImage(image, upgrade_mode=not install_mode)
                return True
            except APIError as err:
                if err.status_code == 500:
                    logger.error(f"Error: {err.explanation}")
                    logger.error(f"Error while contacting docker registry. Aborting.")
                elif err.status_code == 404:
                    logger.critical(f"The image has not been found on the docker registry: {err.explanation}")
                else:
                    logger.debug(f"Error: {err}")
                    logger.critical(f"An error occurred while downloading this image: {err.explanation}")
        return False

    @classmethod
    def downloadVersionTag(cls, image: ExegolImage) -> Union[ExegolImage, str]:
        """Pull a docker image for a specific version tag and return the corresponding ExegolImage"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to download a docker image in offline mode ...")
            return ""
        try:
            image = cls.__client.images.pull(repository=ConstantConfig.IMAGE_NAME,
                                             tag=image.getLatestVersionName(),
                                             platform="linux/" + image.getArch())
            return ExegolImage(docker_image=image, isUpToDate=True)
        except APIError as err:
            if err.status_code == 500:
                return f"error while contacting docker registry: {err.explanation}"
            elif err.status_code == 404:
                return f"matching tag doesn't exist: {err.explanation}"
            else:
                logger.debug(f"Error: {err}")
                return f"en unknown error occurred while downloading this image : {err.explanation}"

    @classmethod
    def removeImage(cls, image: ExegolImage, upgrade_mode: bool = False) -> bool:
        """Remove an ExegolImage from disk"""
        logger.verbose(f"Removing {'previous ' if upgrade_mode else ''}image [green]{image.getName()}[/green]...")
        tag = image.removeCheck()
        if tag is None:  # Skip removal if image is not installed locally.
            return False
        try:
            with console.status(f"Removing {'previous ' if upgrade_mode else ''}image [green]{image.getName()}[/green]...", spinner_style="blue"):
                if not image.isVersionSpecific() and image.getInstalledVersionName() != image.getName() and not upgrade_mode:
                    # Docker can't remove multiple images at the same tag, version specific tag must be remove first
                    logger.debug(f"Removing image {image.getFullVersionName()}")
                    cls.__client.images.remove(image.getFullVersionName(), force=False, noprune=False)
                logger.debug(f"Removing image {image.getLocalId()} ({image.getFullVersionName() if upgrade_mode else image.getFullName()})")
                cls.__client.images.remove(image.getLocalId(), force=False, noprune=False)
            logger.success(f"{'Previous d' if upgrade_mode else 'D'}ocker image successfully removed.")
            return True
        except APIError as err:
            # Handle docker API error code
            logger.verbose(err.explanation)
            if err.status_code == 409:
                if upgrade_mode:
                    logger.error(f"The '{image.getName()}' image cannot be deleted yet, "
                                 "all containers using this old image must be deleted first.")
                else:
                    logger.error(f"The '{image.getName()}' image cannot be deleted because "
                                 f"it is currently used by a container. Aborting.")
            elif err.status_code == 404:
                logger.error(f"This image doesn't exist locally {image.getLocalId()} ({image.getFullName()}). Aborting.")
            else:
                logger.critical(f"An error occurred while removing this image : {err}")
        except ReadTimeout:
            logger.error(f"The deletion of the image has timeout, the deletion may be incomplete.")
        return False

    @classmethod
    def buildImage(cls, tag: str, build_profile: Optional[str] = None, build_dockerfile: Optional[str] = None):
        """Build a docker image from source"""
        if ParametersManager().offline_mode:
            logger.critical("It's not possible to build a docker image in offline mode. The build process need access to internet ...")
            return False
        logger.info(f"Building exegol image : {tag}")
        if build_profile is None or build_dockerfile is None:
            build_profile = "full"
            build_dockerfile = "Dockerfile"
        logger.info("Starting build. Please wait, this might be [bold](very)[/bold] long.")
        logger.verbose(f"Creating build context from [gold]{ConstantConfig.build_context_path}[/gold] with "
                       f"[green][b]{build_profile}[/b][/green] profile ({ParametersManager().arch}).")
        if EnvInfo.arch != ParametersManager().arch:
            logger.warning("Building an image for a different host architecture can cause unexpected problems and slowdowns!")
        try:
            # path is the directory full path where Dockerfile is.
            # tag is the name of the final build
            # dockerfile is the Dockerfile filename
            ExegolTUI.buildDockerImage(
                cls.__client.api.build(path=ConstantConfig.build_context_path,
                                       dockerfile=build_dockerfile,
                                       tag=f"{ConstantConfig.IMAGE_NAME}:{tag}",
                                       buildargs={"TAG": f"{build_profile}",
                                                  "VERSION": "local",
                                                  "BUILD_DATE": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')},
                                       platform="linux/" + ParametersManager().arch,
                                       rm=True,
                                       forcerm=True,
                                       pull=True,
                                       decode=True))
            logger.success(f"Exegol image successfully built")
        except APIError as err:
            logger.debug(f"Error: {err}")
            if err.status_code == 500:
                logger.error(f"Error: {err.explanation}")
                logger.error("Error while contacting docker hub. You probably don't have internet. Aborting.")
                logger.debug(f"Error: {err}")
            else:
                logger.critical(f"An error occurred while building this image : {err}")
