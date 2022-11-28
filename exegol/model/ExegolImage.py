from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from docker.models.containers import Container
from docker.models.images import Image

from exegol.console import ConsoleFormat
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.model.MetaImages import MetaImages
from exegol.model.SelectableInterface import SelectableInterface
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, ExeLog, console
from exegol.utils.WebUtils import WebUtils


class ExegolImage(SelectableInterface):
    """Class of an exegol image. Container every information about the docker image."""

    def __init__(self,
                 name: str = "NONAME",
                 dockerhub_data: Optional[Dict[str, Any]] = None,
                 meta_img: MetaImages = None,
                 image_id: Optional[str] = None,
                 docker_image: Optional[Image] = None,
                 isUpToDate: bool = False):
        """Docker image default value"""
        # Prepare parameters
        if meta_img:
            version_parsed = meta_img.version
            name = meta_img.name
            self.__version_specific: bool = not meta_img.is_latest
        else:
            version_parsed = MetaImages.tagNameParsing(name)
            self.__version_specific = bool(version_parsed)
        # Init attributes
        self.__image: Image = docker_image
        self.__name: str = name
        self.__alt_name: str = ''
        self.__arch = ""
        self.__entrypoint: Optional[Union[str, List[str]]] = None
        # Latest version available of the current image (or current version if version specific)
        self.__profile_version: str = version_parsed if version_parsed else "[bright_black]N/A[/bright_black]"
        # Version of the docker image installed
        self.__image_version: str = self.__profile_version
        # This mode allows to know if the version has been retrieved from the tag and is part of the image name or
        # if it is retrieved from the tags (ex: nightly)
        self.__version_label_mode: bool = False
        self.__build_date = "[bright_black]N/A[/bright_black]"
        # Remote image size
        self.__dl_size: str = "[bright_black]N/A[/bright_black]"
        # Local uncompressed image's size
        self.__disk_size: str = "[bright_black]N/A[/bright_black]"
        # Remote image ID
        self.__digest: str = "[bright_black]N/A[/bright_black]"
        # Local docker image ID
        self.__image_id: str = "[bright_black]Not installed[/bright_black]"
        # Status
        self.__is_remote: bool = False
        self.__is_install: bool = False
        self.__is_update: bool = isUpToDate  # Default is false except if the image has been updated in the current runtime context
        self.__is_discontinued: bool = False
        # The latest version is merged with the latest one, every other version is old and must be removed
        self.__outdated: bool = self.__version_specific
        self.__custom_status: str = ""
        # Process data
        if docker_image is not None:
            self.__initFromDockerImage()
        else:
            self.__setImageId(image_id)
            if dockerhub_data:
                self.__is_remote = True
                self.__setArch(MetaImages.parseArch(dockerhub_data))
                self.__dl_size = self.__processSize(dockerhub_data.get("size", 0))
            if meta_img:
                self.__setDigest(meta_img.meta_id)
        logger.debug(f"└── {self.__name}\t→ ({self.getType()}) {self.__digest}")

    def __initFromDockerImage(self):
        """Parse Docker object to set up self configuration on creation."""
        # If docker object exists, image is already installed
        self.__is_install = True
        # Set init values from docker object
        if len(self.__image.attrs["RepoTags"]) > 0:
            # Tag as outdated until the latest tag is found
            self.__outdated = True
            # Tag as a version specific until the latest tag is found
            self.__version_specific = True
            name = self.__name  # Init with old name
            self.__name = None
            for repo_tag in self.__image.attrs["RepoTags"]:
                repo, name = repo_tag.split(':')
                if not repo.startswith(ConstantConfig.IMAGE_NAME):
                    # Ignoring external images (set container using external image as outdated)
                    continue
                version_parsed = MetaImages.tagNameParsing(name)
                # Check if a non-version tag (the latest tag) is supplied, if so, this image must NOT be removed
                if not version_parsed:
                    self.__outdated = False
                    self.__version_specific = False
                    self.__name = name
                else:
                    self.__setImageVersion(version_parsed)

            # if no version has been found, restoring previous name
            if self.__name is None:
                self.__name = name

            if self.isVersionSpecific():
                if "N/A" in self.__image_version:
                    logger.debug(f"Current '{self.__name}' image is version specific but no version tag were found!")
                else:
                    self.__profile_version = self.__image_version
        else:
            # If tag is <none>, try to find labels value, if not set fallback to default value
            self.__name = self.parseAliasTagName(self.__image)
            self.__alt_name = f"{self.__name} [orange3](untag)[/orange3]"
            self.__outdated = True
            self.__version_specific = True
        self.__setRealSize(self.__image.attrs["Size"])
        self.__entrypoint = self.__image.attrs.get("Config", {}).get("Entrypoint")
        # Set build date from labels
        self.__build_date = self.__image.labels.get('org.exegol.build_date', '[bright_black]N/A[/bright_black]')
        self.__setArch(MetaImages.parseArch(self.__image))
        self.__labelVersionParsing()
        # Set local image ID
        self.__setImageId(self.__image.attrs["Id"])
        # If this image is remote, set digest ID
        self.__is_remote = not (len(self.__image.attrs["RepoDigests"]) == 0 and self.__checkLocalLabel())
        if self.__is_remote:
            self.__setDigest(self.__parseDigest(self.__image))
        # Default status, must be refreshed later if some parameters will be changed externally
        self.syncStatus()

    def setDockerObject(self, docker_image: Image):
        """Docker object setter. Parse object to set up self configuration."""
        self.__image = docker_image
        # When a docker image exist, image is locally installed
        self.__is_install = True
        # Set real size on disk
        self.__setRealSize(self.__image.attrs["Size"])
        self.__entrypoint = self.__image.attrs.get("Config", {}).get("Entrypoint")
        # Set local image ID
        self.__setImageId(docker_image.attrs["Id"])
        # Set build date from labels
        self.__build_date = self.__image.labels.get('org.exegol.build_date', '[bright_black]N/A[/bright_black]')
        # Check if local image is sync with remote digest id (check up-to-date status)
        self.__is_update = self.__digest == self.__parseDigest(docker_image)
        # Add version tag (if available)
        for repo_tag in docker_image.attrs["RepoTags"]:
            tmp_name, tmp_tag = repo_tag.split(':')
            version_parsed = MetaImages.tagNameParsing(tmp_tag)
            if tmp_name == ConstantConfig.IMAGE_NAME and version_parsed:
                self.__setImageVersion(version_parsed)
        # backup plan: Use label to retrieve image version
        self.__labelVersionParsing()

    def setMetaImage(self, meta: MetaImages):
        dockerhub_data = meta.getDockerhubImageForArch(self.getArch())
        self.__is_remote = True
        if self.__version_specific:
            # Solve conflict for same name / tag but multiple arch
            self.__version_specific = not meta.is_latest
            self.__name = meta.name
            self.__outdated = self.__version_specific
        if dockerhub_data is not None:
            self.__dl_size = self.__processSize(dockerhub_data.get("size", 0))
        self.__setLatestVersion(meta.version)
        if not self.__digest and meta.is_latest and meta.meta_id:
            # If the digest is lost (multiple same image installed locally) fallback to meta id (only if latest)
            self.__digest = meta.meta_id
        # Check if local image is sync with remote digest id (check up-to-date status)
        self.__is_update = self.__digest == meta.meta_id
        # Refresh status after metadata update
        self.syncStatus()

    def setAsDiscontinued(self):
        logger.debug(f"The image '{self.getName()}' (digest: {self.getRemoteId()}) has not been found remotely, "
                     f"considering it as discontinued.")
        # If there are still remote images but the image has not found any match it is because it has been deleted/discontinued
        self.__is_discontinued = True
        # Discontinued image can no longer be updated
        self.__is_update = True
        # Status must be updated after changing previous criteria
        self.syncStatus()

    def __labelVersionParsing(self):
        """Fallback version parsing using image's label (if exist).
        This method can only be used if version has not been provided from the image's tag."""
        if "N/A" in self.__image_version:
            logger.debug("Try to retrieve image version from labels")
            version_label = self.__image.labels.get("org.exegol.version")
            if version_label is not None:
                self.__setImageVersion(version_label, source_tag=False)
                if self.isVersionSpecific():
                    self.__profile_version = self.__image_version

    @classmethod
    def parseAliasTagName(cls, image: Image) -> str:
        """Create a tag name alias from labels when image's tag is lost"""
        return image.labels.get("org.exegol.tag", "<none>") + "-" + image.labels.get("org.exegol.version", "v?")

    def __checkLocalLabel(self):
        """Check if the local label is set. Default to yes for old build"""
        return self.__image.labels.get("org.exegol.version", "local").lower() == "local"

    def syncStatus(self):
        """When the image is loaded from a docker object, docker repository metadata are not present.
        It's not (yet) possible to know if the current image is up-to-date."""
        if "N/A" in self.__profile_version and not self.isLocal() and not self.isUpToDate() and not self.__is_discontinued and not self.__outdated:
            self.__custom_status = "[bright_black]Unknown[/bright_black]"
        else:
            self.__custom_status = ""

    def syncContainerData(self, container: Container):
        """Synchronization between the container and the image.
        If the image has been updated, the tag is lost,
        but it is saved in the properties of the container that still uses it."""
        if self.isLocked():
            original_name = container.attrs["Config"]["Image"]
            if ':' in original_name:
                original_name = original_name.split(":")[1]
            if self.__name == 'NONAME':
                self.__name = original_name
                version_parsed = MetaImages.tagNameParsing(self.__name)
                self.__version_specific = bool(version_parsed)
                self.__setImageVersion(version_parsed)
            self.__alt_name = f'{original_name} [orange3](outdated' \
                              f'{f" v.{self.getImageVersion()}" if "N/A" not in self.getImageVersion() else ""})[/orange3]'

    def autoLoad(self) -> 'ExegolImage':
        """If the current image is in an unknown state, it's possible to load remote data specifically."""
        if "Unknown" in self.__custom_status and \
                not self.isVersionSpecific() and \
                "N/A" in self.__profile_version and \
                not ParametersManager().offline_mode:
            logger.debug(f"Auto-load remote version for the specific image '{self.__name}'")
            # Find remote metadata for the specific current image
            with console.status(f"Synchronization of the [green]{self.__name}[/green] image status...", spinner_style="blue"):
                remote_digest = WebUtils.getMetaDigestId(self.__name)
                version = WebUtils.getRemoteVersion(self.__name)
            if remote_digest is not None and self.__digest:
                # Compare current and remote latest digest for up-to-date status
                self.__is_update = self.__digest == remote_digest
            if version is not None:
                # Fallback to version matching
                self.__is_update = self.__is_update or self.__image_version == version
                # Set latest remote version
                self.__setLatestVersion(version)
            self.__custom_status = ""
        return self

    def updateCheck(self) -> Optional[str]:
        """If this image can be updated, return its name, otherwise return None"""
        if self.__is_remote:
            if self.__is_update:
                logger.warning("This image is already up to date. Skipping.")
                return None
            return self.__name
        else:
            logger.error("Local images cannot be updated.")
            return None

    def isUpToDate(self) -> bool:
        if not self.__is_remote:
            return True  # Local image cannot be updated
        return self.__is_update

    def removeCheck(self) -> Optional[str]:
        """If this image can be removed, return its name, otherwise return None"""
        if self.__is_install:
            return self.__name
        else:
            logger.error("This image is not installed locally. Skipping.")
            return None

    @classmethod
    def __mergeMetaImages(cls, images: List[MetaImages]):
        """Select latest (remote) images and merge them with their version's specific equivalent"""
        latest_images, version_images = [], []
        # Splitting images by type : latest or version specific
        for img in images:
            if img.is_latest:
                latest_images.append(img)
            else:
                version_images.append(img)

        # Test each combination
        for main_image in latest_images:
            for version_specific in version_images:
                if main_image.meta_id == version_specific.meta_id:
                    # Set exact profile version to the remaining latest image
                    main_image.setVersionSpecific(version_specific)
                    try:
                        # Remove duplicates image from the result array (don't need to be returned, same object)
                        images.remove(version_specific)
                    except ValueError:
                        # already been removed
                        pass

    @classmethod
    def mergeImages(cls, remote_images: List[MetaImages], local_images: List[Image]) -> List['ExegolImage']:
        """Compare and merge local images and remote images.
        Use case to process :
            - up-to-date : "Version specific" image can use exact digest_id matching. Latest image must match corresponding tag
            - outdated : Don't match digest_id but match (latest) tag
            - local image : don't have any 'RepoDigests' because they are local
            - discontinued : image with 'RepoDigests' properties but not found in remote images (maybe too old)
            - unknown : no internet connection = no information from the registry
            - not install : other remote images without any match
        Return a list of ordered ExegolImage."""
        results = []
        latest_installed: List[str] = []
        cls.__mergeMetaImages(remote_images)
        # Convert array to dict
        remote_img_dict = {}
        for r_img in remote_images:
            remote_img_dict[r_img.name] = r_img

        # Find a match for each local image
        for img in local_images:
            current_local_img = ExegolImage(docker_image=img)
            # quick handle of local images
            if current_local_img.isLocal():
                results.append(current_local_img)
                continue
            current_arch = current_local_img.getArch()
            selected = None
            default = None
            for sub_image in img.attrs.get('RepoTags'):
                # parse multi-tag images (latest tag / version specific tag)
                current_tag = sub_image.split(':')[1]
                tag_match = remote_img_dict.get(current_tag)
                if tag_match and current_arch in tag_match.list_arch:
                    default = tag_match
                    # if the selected remote image have a meta_id, it's a latest tag
                    if default.is_latest:
                        selected = default

            if len(img.attrs.get('RepoTags', [])) == 0:
                # If RepoTags is lost, fallback to RepoDigests (happen when there is multiple arch install on the same tag name)
                for sub_image in img.attrs.get('RepoDigests'):
                    current_id = sub_image.split('@')[-1]
                    for remote in remote_images:
                        if remote.meta_id == current_id:
                            selected = remote
                            break
            if selected is None:
                # if no latest tag have been found, use version specific metadata
                selected = default
            if selected:
                # Remote match found
                current_local_img.setMetaImage(selected)
            else:
                if len(remote_images) > 0:
                    # If there is some result from internet but no match and this is not a local image, this image is probably discontinued or the remote image is too old (relative to other images)
                    current_local_img.setAsDiscontinued()
                # If there are no remote images, the user probably doesn't have internet and can't know the status of the images from the registry (default: Unknown)
            results.append(current_local_img)
            latest_installed.append(current_local_img.getName())

        # Add remote image left
        for current_remote in remote_images:
            img_selected = None
            img_default = None
            for img in current_remote.getImagesLeft():
                # the remaining uninstalled images are filtered with the currently selected architecture
                if MetaImages.parseArch(img) == ParametersManager().arch:
                    img_selected = ExegolImage(meta_img=current_remote, dockerhub_data=img)
                    break
                # OR if no exact arch match is found, try to default to another available arch
                elif current_remote.name not in latest_installed:
                    # fallback to the first option or one corresponding to the host's arch (may happen if the arch parameter has been overwritten by user)
                    if img_default is None or MetaImages.parseArch(img) == EnvInfo.arch:
                        img_default = ExegolImage(meta_img=current_remote, dockerhub_data=img)
            if img_selected is None:
                img_selected = img_default
            if img_selected:
                results.append(img_selected)

        # the merged images are finally reorganized for greater readability
        return cls.__reorderImages(results)

    @classmethod
    def __reorderImages(cls, images: List['ExegolImage']) -> List['ExegolImage']:
        """Reorder ExegolImages depending on their status"""
        uptodate, outdated, local_build, deprecated = [], [], [], []
        for img in images.copy():
            # First up-to-date
            if img.isUpToDate():
                uptodate.append(img)  # The current image if added to the corresponding groups
                images.remove(img)  # and is removed from the pool (last image without any match will be last)
            # Second need upgrade
            elif (not img.isLocal()) and img.isInstall():
                outdated.append(img)
                images.remove(img)
            # Third local
            elif img.isLocal():
                local_build.append(img)
                images.remove(img)
            # Fourth deprecated
            elif img.isLocked() and img.isInstall():
                deprecated.append(img)
                images.remove(img)
        # apply images order
        result = uptodate + outdated + local_build + deprecated
        # then not installed & other
        result.extend(images)  # Adding left images
        return result

    @staticmethod
    def __processSize(size: int, precision: int = 1) -> str:
        """Text formatter from size number to human-readable size."""
        # https://stackoverflow.com/a/32009595
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        calc: float = size
        while calc > 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            calc = calc / 1024  # apply the division
        return "%.*f%s" % (precision, calc, suffixes[suffix_index])

    def __eq__(self, other):
        """Operation == overloading for ExegolImage object"""
        # How to compare two ExegolImage
        if type(other) is ExegolImage:
            return self.__name == other.__name and self.__digest == other.__digest and self.__arch == other.__arch
        # How to compare ExegolImage with str
        elif type(other) is str:
            return self.__name == other
        else:
            logger.error(f"Error, {type(other)} compare to ExegolImage is not implemented")
            raise NotImplementedError

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.__name} ({self.__image_version}/{self.__profile_version} {self.__arch}) - {self.__disk_size} - " + \
               (f"({self.getStatus()}, {self.__dl_size})" if self.__is_remote else f"{self.getStatus()}")

    def setCustomStatus(self, status: str):
        """Manual image's status overwrite"""
        self.__custom_status = status

    def getStatus(self, include_version: bool = True) -> str:
        """Formatted text getter of image's status.
        Parameter include_version allow choosing if the image version must be printed or not.
        When image version is already print in the user context, no need to duplicate the information.
        The status update available always print his version because the latest version is not print elsewhere."""
        image_version = '' if (not include_version) or 'N/A' in self.getImageVersion() else f' (v.{self.getImageVersion()})'
        if self.__custom_status != "":
            return self.__custom_status
        elif not self.__is_remote:
            return "[blue]Local image[/blue]"
        elif self.__outdated and self.__is_install:
            return f"[orange3]Outdated{image_version}[/orange3]"
        elif self.__is_discontinued:
            return "[red]Discontinued[/red]"
        elif self.__is_update:
            return f"[green]Up to date{image_version}[/green]"
        elif self.__is_install:
            status = f"[orange3]Update available"
            if self.getImageVersion():
                if self.getLatestVersion():
                    status += f" (v.{self.getImageVersion()} :arrow_right: v.{self.getLatestVersion()})"
                else:
                    status += f" (v.{self.getImageVersion()})"
            status += "[/orange3]"
            return status
        else:
            return "[bright_black]Not installed[/bright_black]"

    def getType(self) -> str:
        """Image type getter"""
        return "remote" if self.__is_remote else "local"

    def __setDigest(self, digest: Optional[str]):
        """Remote image digest setter"""
        if digest is not None:
            self.__digest = digest

    @staticmethod
    def __parseDigest(docker_image: Image) -> str:
        """Parse the remote image digest ID.
        Return digest id from the docker object."""
        for digest_id in docker_image.attrs["RepoDigests"]:
            if digest_id.startswith(ConstantConfig.IMAGE_NAME):  # Find digest id from the right repository
                return digest_id.split('@')[1]
        return ""

    def getRemoteId(self) -> str:
        """Remote digest getter"""
        return self.__digest

    def __setImageId(self, image_id: Optional[str]):
        """Local image id setter"""
        if image_id is not None:
            self.__image_id = image_id.split(":")[1][:12]

    def getLocalId(self) -> str:
        """Local id getter"""
        return self.__image_id

    def getKey(self) -> str:
        """Universal unique key getter (from SelectableInterface)"""
        return self.getName()

    def __setRealSize(self, value: int):
        """On-Disk image size setter"""
        self.__disk_size = self.__processSize(value)

    def getRealSize(self) -> str:
        """On-Disk size getter"""
        return self.__disk_size

    def getDownloadSize(self) -> str:
        """Remote size getter"""
        if not self.__is_remote:
            return "local"
        return self.__dl_size

    def getSize(self) -> str:
        """Image size getter. If the image is installed, return the on-disk size, otherwise return the remote size"""
        return self.__disk_size if self.__is_install else f"[bright_black]{self.__dl_size} (compressed)[/bright_black]"

    def getEntrypointConfig(self) -> Optional[Union[str, List[str]]]:
        """Image's entrypoint configuration getter.
        Exegol images before 3.x.x don't have any entrypoint set (because /.exegol/entrypoint.sh don't exist yet. In this case, this getter will return None."""
        return self.__entrypoint

    def getBuildDate(self):
        """Build date getter"""
        if "N/A" not in self.__build_date.upper():
            return datetime.strptime(self.__build_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y %H:%M")
        else:
            return self.__build_date

    def isInstall(self) -> bool:
        """Installation status getter"""
        return self.__is_install

    def isLocal(self) -> bool:
        """Local type getter"""
        return not self.__is_remote

    def isLocked(self) -> bool:
        """Getter locked status.
        If current image is locked, it must be removed"""
        return self.__outdated

    def isVersionSpecific(self) -> bool:
        """Is the current image a version specific version?
        Image version specific container a '-' in the name,
        latest image don't."""
        return self.__version_specific

    def getName(self) -> str:
        """Image's tag name getter"""
        return self.__name

    def getDisplayName(self) -> str:
        """Image's display name getter"""
        result = self.__alt_name if self.__alt_name else self.__name
        if self.getArch() != ParametersManager().arch or logger.isEnabledFor(ExeLog.VERBOSE):
            color = ConsoleFormat.getArchColor(self.getArch())
            result += f" [{color}]({self.getArch()})[/{color}]"
        return result

    def getArch(self) -> str:
        """Image's arch getter"""
        return self.__arch if self.__arch else "amd64"

    def __setArch(self, arch: str):
        """Image's arch setter."""
        self.__arch = arch

    def getLatestVersionName(self) -> str:
        """Image's tag name with latest version getter"""
        return self.__formatVersionName(self.__profile_version)

    def getInstalledVersionName(self) -> str:
        """Image's tag name with installed version getter"""
        return self.__formatVersionName(self.__image_version)

    def __formatVersionName(self, version):
        """From the selected version, format the image tag name"""
        result_name = self.__name
        if not (self.__version_specific or self.__version_label_mode or 'N/A' in version):
            result_name += "-" + version
        return result_name

    def __setImageVersion(self, version: str, source_tag: bool = True):
        """Image's tag version setter.
        Set source_tag as true if the information is retrieve from the image's tag name.
        If the version is retrieve from the label, set source_tag as False."""
        self.__image_version = version
        self.__version_label_mode = not source_tag

    def getImageVersion(self) -> str:
        """Image's tag version getter"""
        return self.__image_version

    def __setLatestVersion(self, version: str):
        """Image's tag version setter"""
        self.__profile_version = version

    def getLatestVersion(self) -> str:
        """Latest image version getter"""
        return self.__profile_version

    def getFullName(self) -> str:
        """Dockerhub image's full name getter"""
        return f"{ConstantConfig.IMAGE_NAME}:{self.__name}"

    def getFullVersionName(self) -> str:
        """Dockerhub image's full (installed) version name getter"""
        return f"{ConstantConfig.IMAGE_NAME}:{self.getInstalledVersionName()}"

    def getDockerRef(self) -> str:
        """Find and return the right id to target the current image for docker.
        If tag is lost, fallback to local image id."""
        if self.getFullName() in self.__image.attrs.get('RepoTags', []):
            return self.getFullName()
        elif self.getFullVersionName() in self.__image.attrs.get('RepoTags', []):
            return self.getFullVersionName()
        return self.getLocalId()
