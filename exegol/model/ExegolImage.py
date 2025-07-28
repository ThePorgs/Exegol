import re
from datetime import datetime
from enum import IntFlag, auto as enum_auto, Enum
from typing import Optional, List, Union, Tuple, Dict, Set

from docker.models.containers import Container
from docker.models.images import Image

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.DataCache import DataCache
from exegol.config.UserConfig import UserConfig
from exegol.console import ConsoleFormat
from exegol.console.ConsoleFormat import get_display_date
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.manager.TaskManager import TaskManager
from exegol.model.SelectableInterface import SelectableInterface
from exegol.model.SupabaseModels import SupabaseImage
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.SessionHandler import SessionHandler
from exegol.utils.SupabaseUtils import SupabaseUtils
from exegol.utils.WebRegistryUtils import WebRegistryUtils


class ExegolImage(SelectableInterface):
    """Class of an exegol image. Container every information about the docker image."""

    class Filters(IntFlag):
        INSTALLED = enum_auto()

    class Labels(Enum):
        tag = "org.exegol.tag"
        version = "org.exegol.version"
        build_date = "org.exegol.build_date"
        app = "org.exegol.app"

    def __init__(self,
                 name: str = "NONAME",
                 meta_img: Optional[SupabaseImage] = None,
                 image_id: Optional[str] = None,
                 docker_image: Optional[Image] = None,
                 isUpToDate: bool = False):
        """Docker image default value"""
        # Prepare parameters
        if meta_img:
            version_parsed = meta_img.version
            name = meta_img.tag
            self.__version_specific: bool = False
        else:
            version_parsed = self.tagNameParsing(name)
            self.__version_specific = bool(version_parsed)
        # Init attributes
        self.__image: Optional[Image] = docker_image
        self.__name: str = name
        self.__display_name: str = ''
        self.__arch = ""
        self.__entrypoint: Optional[Union[str, List[str]]] = None
        self.__repository: str = ''
        self.__license: Optional[str] = None
        # Latest version available of the current image (or current version if version specific)
        self.__profile_version: str = version_parsed if version_parsed else "[bright_black]N/A[/bright_black]"
        self.__profile_digest: str = ""
        # Version of the docker image installed
        self.__image_version: str = self.__profile_version
        # This mode allows to know if the version has been retrieved from the tag and is part of the image name or
        # if it is retrieved from the tags (ex: nightly)
        self.__version_label_mode: bool = False
        self.__build_date: Union[datetime, str] = ""
        # Remote image size
        self.__dl_size: str = "[bright_black]N/A[/bright_black]"
        # Local uncompressed image's size
        self.__disk_size: str = "[bright_black]N/A[/bright_black]"
        # Remote image ID
        self.__digest: str = "[bright_black]N/A[/bright_black]"
        # Local docker image ID
        self.__image_id: str = "[bright_black]Not installed[/bright_black]"
        # Status
        self.__is_official: bool = False
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
            if meta_img:
                self.__is_remote = True
                self.__setRepository(meta_img.repository)
                self.__license = meta_img.license
                self.__build_date = meta_img.build_date
                self.__setArch(meta_img.arch)
                if meta_img.download_size is not None:
                    self.__dl_size = self.__processSize(meta_img.download_size)
                self.__disk_size = self.__processSize(meta_img.disk_size)
                self.__setDigest(meta_img.repo_digest)
                self.__setLatestRemoteId(meta_img.repo_digest)  # Meta id is always the latest one
        # Debug every Exegol image init
        # logger.debug(f"└── {self.__name}\t→ ({self.getType()}) {self.__digest}")

    def __initFromDockerImage(self) -> None:
        """Parse Docker object to set up self configuration on creation."""
        assert self.__image is not None
        # If docker object exists, image is already installed
        self.__is_install = True
        self.__is_remote = not (len(self.__image.attrs["RepoDigests"]) == 0 and self.__checkLocalLabel())
        # Set init values from docker object
        if len(self.__image.attrs["RepoTags"]) > 0:
            # Tag as outdated until the latest tag is found
            self.__outdated = True
            # Tag as a version specific until the latest tag is found
            self.__version_specific = True
            custom_image = True
            tag_name = self.__name  # Init with old name
            self.__name = ""
            for repo_tag in self.__image.attrs["RepoTags"]:
                tag_name = repo_tag.split(':')[-1]
                if not self.isOfficialImage(repo_tag, suffix=":") or self.isLocal():
                    # Ignoring external images (set container using external image as outdated)
                    continue
                custom_image = False
                version_parsed = self.tagNameParsing(tag_name)
                # Check if a non-version tag (the latest tag) is supplied, if so, this image must NOT be removed
                if not version_parsed:
                    self.__outdated = False
                    self.__version_specific = False
                    self.__name = tag_name
                else:
                    self.__setImageVersion(version_parsed)

            # if no version has been found, restoring latest name found
            if not self.__name:
                self.__name = tag_name

            # Tag image as custom if needed
            if custom_image:
                # Handle custom and local images
                self.__outdated = False
                self.__version_specific = False
                if not self.isLocal():
                    self.setCustomStatus("[bright_black]Unmanaged[/bright_black]")  # Block auto-load function
                else:
                    self.__is_update = True  # Local images cannot be updated

            if self.isVersionSpecific():
                if "N/A" in self.__image_version:
                    logger.debug(f"Current '{self.__name}' image is version specific but no version tag were found!")
                else:
                    self.__profile_version = self.__image_version
        else:
            # If tag is <none>, try to find labels value, if not set fallback to default value
            self.__name = self.parseAliasTagName(self.__image)
            self.__display_name = f"{self.getName()} [orange3](untag)[/orange3]"
            self.__outdated = True
            self.__version_specific = True
            if self.isLocal():
                # Outdated image if retag by a more recent image or failed build
                self.setCustomStatus("[orange3]Outdated local image[/orange3]")
        self.__setRealSize(self.__image.attrs["Size"])
        self.__entrypoint = self.__image.attrs.get("Config", {}).get("Entrypoint")
        # Set build date from labels
        self.__build_date = self.__image.labels.get(self.Labels.build_date.value, '') if self.__image.labels is not None else ''
        self.__setArch(WebRegistryUtils.parseArch(self.__image))
        self.__labelVersionParsing()
        # Set local image ID
        self.__setImageId(self.__image.attrs["Id"])
        # If this image is remote, set digest ID
        if self.__is_remote:
            repo, digest = self.__parseRepoDigests()
            self.__setDigest(digest)
            self.__setRepository(repo)
        # Default status, must be refreshed later if some parameters will be changed externally
        self.syncStatus()

    def filter(self, filters: int) -> bool:
        """
        Apply bitwise filter
        :param filters:
        :return:
        """
        match = True
        if match and filters & self.Filters.INSTALLED:
            match = self.isInstall()
        return match

    def resetDockerImage(self) -> None:
        """During an image upgrade, the docker image and local parsed variable must be
        reset before parsing the new upgraded image"""
        self.__image = None
        self.__image_version = "[bright_black]N/A[/bright_black]"
        self.__digest = "[bright_black]N/A[/bright_black]"
        self.__image_id = "Reset"
        self.__build_date = ""
        self.__disk_size = "[bright_black]N/A[/bright_black]"

    def setDockerObject(self, docker_image: Image) -> None:
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
        self.__build_date = self.__image.labels.get(self.Labels.build_date.value, '') if self.__image.labels is not None else ''
        # Check if local image is sync with remote digest id (check up-to-date status)
        image_repo, image_digest = self.__parseRepoDigests()
        self.__is_update = (self.__profile_digest if self.__profile_digest else self.__digest) == image_digest
        # If this image is remote, set digest ID
        self.__is_remote = not (len(self.__image.attrs["RepoDigests"]) == 0 and self.__checkLocalLabel())
        if self.__is_remote:
            self.__setDigest(image_digest)
            self.__setRepository(image_repo)
        # Add version tag (if available)
        for repo_tag in docker_image.attrs["RepoTags"]:
            tmp_name, tmp_tag = repo_tag.split(':')
            version_parsed = self.tagNameParsing(tmp_tag)
            if tmp_name in ConstantConfig.OFFICIAL_REPOSITORIES and version_parsed:
                self.__setImageVersion(version_parsed)
        # backup plan: Use label to retrieve image version
        self.__labelVersionParsing()

    def setMetaImage(self, meta: SupabaseImage) -> None:
        self.__is_remote = True
        self.__setRepository(meta.repository)
        self.__license = meta.license
        if self.__version_specific:
            # Solve conflict for same name / tag but multiple arch
            self.__version_specific = False
            self.__name = meta.tag
            self.__outdated = self.__version_specific
        if meta.download_size is not None:
            self.__dl_size = self.__processSize(meta.download_size)
        if not self.__dl_size:
            self.__disk_size = self.__processSize(meta.disk_size)
        if not self.__build_date:
            self.__build_date = meta.build_date
        self.__setLatestVersion(meta.version)
        self.__setLatestRemoteId(meta.repo_digest)
        # Check if local image is sync with remote digest id (check up-to-date status)
        self.__is_update = self.__digest == self.__profile_digest
        if not self.__digest:
            # If the digest is lost (multiple-arch but same tag installed locally) fallback to meta id (only if latest)
            self.__setDigest(meta.repo_digest)
            self.__is_update = self.__image_version == self.__profile_version
        # Refresh status after metadata update
        self.syncStatus()

    def setAsDiscontinued(self) -> None:
        logger.debug(f"The image '{self.getName()}' (digest: {self.getRemoteId()}) has not been found remotely, "
                     f"considering it as discontinued.")
        # If there are still remote images but the image has not found any match it is because it has been deleted/discontinued
        self.__is_discontinued = True
        # Discontinued image can no longer be updated
        self.__is_update = True
        # Status must be updated after changing previous criteria
        self.syncStatus()

    def setupAsLegacy(self, legacy_tag: str) -> None:
        """Used to pull legacy version specific image not installed locally"""
        self.__name = legacy_tag
        self.__setImageVersion(self.tagNameParsing(legacy_tag))
        self.__is_update = False
        self.__outdated = True
        self.__version_specific = True

    def __labelVersionParsing(self) -> None:
        """Fallback version parsing using image's label (if exist).
        This method can only be used if version has not been provided from the image's tag."""
        if "N/A" in self.__image_version and self.__image is not None and self.__image.labels is not None:
            version_label = self.__image.labels.get(self.Labels.version.value)
            if version_label is not None:
                self.__setImageVersion(version_label, source_tag=False)
                if self.isVersionSpecific():
                    self.__profile_version = self.__image_version

    @classmethod
    def parseAliasTagName(cls, image: Image) -> str:
        """Create a tag name alias from labels when image's tag is lost"""
        if image.labels is None:
            return "[bright_black]Unknown[/bright_black]"
        return image.labels.get(cls.Labels.tag.value, "<none>") + "-" + image.labels.get(cls.Labels.version.value, "v?")

    def __checkLocalLabel(self) -> bool:
        """Check if the local label is set. Default to yes for old build"""
        assert self.__image is not None
        if self.__image.labels is None:
            return True
        return self.__image.labels.get(self.Labels.version.value, "local").lower() == "local"

    def syncStatus(self) -> None:
        """When the image is loaded from a docker object, docker repository metadata are not present.
        It's not (yet) possible to know if the current image is up-to-date."""
        if "Unmanaged" in self.__custom_status:
            return
        if ("N/A" in self.__profile_version and
                not self.isLocal() and
                not self.isUpToDate() and
                not self.__is_discontinued and
                not self.__outdated):
            self.setCustomStatus("[bright_black]Unknown[/bright_black]")
        elif "Unknown" in self.__custom_status:
            self.setCustomStatus()

    def syncContainerData(self, container: Container) -> None:
        """Synchronization between the container and the image.
        If the image has been updated, the tag is lost,
        but it is saved in the properties of the container that still uses it."""
        if self.isLocked():
            original_name = container.attrs["Config"]["Image"]
            if ':' in original_name:
                original_name = original_name.split(":")[1]
            if self.__name == 'NONAME':
                self.__name = original_name
                version_parsed = self.tagNameParsing(self.__name)
                self.__version_specific = bool(version_parsed)
                self.__setImageVersion(version_parsed)
            self.__display_name = f'{original_name} [orange3](outdated' \
                                  f'{f" v.{self.getImageVersion()}" if "N/A" not in self.getImageVersion() else ""})[/orange3]'

    async def autoLoad(self, from_cache: bool = True) -> 'ExegolImage':
        """If the current image is in an unknown state, it's possible to load remote data specifically."""
        if "Unknown" in self.__custom_status and \
                not self.isVersionSpecific() and \
                "N/A" in self.__profile_version and \
                not ParametersManager().offline_mode:
            logger.debug(f"Auto-load remote version for the specific image '{self.__name}'")
            # Find remote metadata for the specific current image
            async with ExegolStatus(f"Synchronization of the [green]{self.__name}[/green] image status...",
                                    spinner_style="blue"):
                remote_digest = None
                version = None
                if from_cache:
                    cache_images = DataCache().get_images_data()
                    # Cache can be directly use for 3 days after this delay a direct call must be made to check for update. Use info action to update the cache.
                    if not cache_images.metadata.is_outdated(days=3):
                        for img in cache_images.data:
                            if img.name == self.__name:
                                version = img.last_version
                                remote_digest = img.digest
                                break
                if self.__is_remote and (version is None or remote_digest is None):
                    if self.isOfficialImage(self.__repository):
                        remote_digest, version = await SupabaseUtils.get_tag_version(self.__name, self.__arch)
            if remote_digest is not None:
                self.__setLatestRemoteId(remote_digest)
                if self.__digest:
                    # Compare current and remote latest digest for up-to-date status
                    self.__is_update = self.__digest == self.__profile_digest
            if version is not None:
                # Set latest remote version
                self.__setLatestVersion(version)
                if remote_digest is None:
                    # Fallback to version matching
                    self.__is_update = self.__is_update or self.__image_version == version
            if version or remote_digest:
                self.setCustomStatus()
        return self

    def updateCheck(self) -> Optional[str]:
        """If this image can be updated, return its name, otherwise return None"""
        if self.__is_remote:
            if not self.__is_official:
                logger.warning("Custom images cannot be updated. Skipping.")
            elif self.__is_update:
                logger.warning("This image is already up to date. Skipping.")
            else:
                return self.__name
        else:
            logger.error("Local images cannot be updated.")
        return None

    def isUpToDate(self) -> bool:
        if not self.__is_remote:
            return True  # Local image cannot be updated
        return self.__is_update

    def canBePulled(self) -> bool:
        """Check if this image can be pulled. True if this image is remote, official and the licence match the current exegol activation"""
        if self.__is_remote:
            return (self.__license is None or self.__license == "") or \
                (self.__license == "Professional" and SessionHandler().pro_feature_access()) or \
                (self.__license == "Enterprise" and SessionHandler().enterprise_feature_access())
        return False

    async def pullAuthNeeded(self) -> bool:
        """Check if pulling this image need an authentication to the registry"""
        await TaskManager.wait_for(TaskManager.TaskId.LoadLicense, clean_task=False)
        if not self.canBePulled():
            if self.__license not in ["Professional", "Enterprise"]:
                logger.critical("You wrapper is not up-to-date. You need to update it first before downloading this image.")
            msg = "You need to activate Exegol with a license to download a pre-built Exegol image."
            if SessionHandler().is_enrolled():
                msg = "Your license does not allow you to download this image."
            msg += f" ({self.getDisplayRepository()} access needed)"
            logger.critical(msg)
        return self.__license is not None and self.__license != "" and self.__repository != ConstantConfig.COMMUNITY_IMAGE_NAME

    def removeCheck(self) -> Optional[str]:
        """If this image can be removed, return its name, otherwise return None"""
        if self.__is_install:
            return self.__name
        else:
            logger.error("This image is not installed locally. Skipping.")
            return None

    @classmethod
    def mergeImages(cls, remote_images: List[SupabaseImage], local_images: List[Image]) -> List['ExegolImage']:
        """Compare and merge local images and remote images.
        Use case to process :
            - up-to-date : "Version specific" image can use exact digest_id matching. Latest image must match corresponding tag
            - outdated : Don't match digest_id but match (latest) tag
            - local image : don't have any 'RepoDigests' because they are local
            - discontinued : image with 'RepoDigests' properties but not found in remote images (maybe too old)
            - unknown : no internet connection = no information from the registry
            - not install : other remote images without any match
        Return a list of ordered ExegolImage."""
        logger.debug("Comparing and merging local and remote images data")
        results = []
        # Convert array to dict
        remote_img_dict: Dict[str, SupabaseImage] = {}
        for r_img in remote_images:
            remote_img_dict[r_img.tag] = r_img
        remote_tag_matched: Set[str] = set()

        # Searching a match for each local image
        logger.debug("Searching a match for each image installed")
        for img in local_images:
            current_local_img = ExegolImage(docker_image=img)
            # quick handle of local images
            if current_local_img.isLocal():
                results.append(current_local_img)
                continue
            selected: Optional[SupabaseImage] = None

            skip_image = False
            if len(img.attrs.get('RepoTags', [])) == 0:
                # If RepoTags is lost, fallback to label and RepoDigests (happen when there is multiple arch install on the same tag name)
                for sub_image in img.attrs.get('RepoDigests'):
                    current_image, current_id = sub_image.split('@')
                    for remote in remote_images:
                        if remote.repo_digest == current_id:
                            selected = remote
                            break
                #current_tag = img.attrs.get('Config', {}).get('Labels', {}).get(cls.Labels.tag.value)
                # Get tag from ExegolImage object instead of labels to handle the untagged outdated nightly case
                current_tag = current_local_img.getName()
                if selected is None and current_tag is not None:
                    selected = remote_img_dict.get(current_tag)
            else:
                for sub_image in img.attrs.get('RepoTags'):
                    # parse multi-tag images (latest tag / version specific tag)
                    current_image, current_tag = sub_image.split(':')
                    tag_match = remote_img_dict.get(current_tag)
                    # filter only lastest tag and skip version specific tags
                    if tag_match:
                        if tag_match.tag not in remote_tag_matched:
                            selected = tag_match
                            if tag_match.tag == "free":  # Solve full / free conflict
                                break
                        else:
                            # Handle duplicate legacy image
                            skip_image = True
                            break
            if skip_image:
                continue
            if selected:
                # Remote match found
                remote_tag_matched.add(selected.tag)
                current_local_img.setMetaImage(selected)
            else:
                if len(remote_images) > 0 and not current_local_img.isVersionSpecific() and not current_local_img.isLocked():
                    # If there is some result from internet but no match and this is not a local image, this image is probably discontinued or the remote image is too old (relative to other images)
                    # Excluding local version specific / outdated images
                    current_local_img.setAsDiscontinued()
                # If there are no remote images, the user probably doesn't have internet and can't know the status of the images from the registry (default: Unknown)
            results.append(current_local_img)

        # Add remote image left
        for current_remote in remote_images:
            if current_remote.tag in remote_tag_matched:
                continue
            results.append(ExegolImage(meta_img=current_remote))

        # the merged images are finally reorganized for greater readability
        return cls.__reorderImages(results)

    @classmethod
    def __reorderImages(cls, images: List['ExegolImage']) -> List['ExegolImage']:
        """Reorder ExegolImages depending on their status"""
        uptodate, outdated, local_build, deprecated, pullable = [], [], [], [], []
        for img in images.copy():
            # First up-to-date
            if img.isUpToDate() and not img.isLegacy() and not img.isLocal():
                uptodate.append(img)  # The current image if added to the corresponding groups
                images.remove(img)  # and is removed from the pool (last image without any match will be last)
            # Second need upgrade
            elif not img.isLocal() and img.isInstall():
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
            # Five Can be pulled (check license level)
            elif img.canBePulled():
                pullable.append(img)
                images.remove(img)
        # apply images order
        result = uptodate + outdated + local_build + deprecated + pullable
        # then not installed & other
        result.extend(images)  # Adding left images
        return result

    @staticmethod
    def __processSize(size: Union[int, float], precision: int = 1, compression_factor: float = 1) -> str:
        """Text formatter from size number to human-readable size."""
        if size < 1000:
            # Size is supplied in GB
            return f"{size} GB"
        # https://stackoverflow.com/a/32009595
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        calc: float = size * compression_factor
        while calc > 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            calc = calc / 1024  # apply the division
        return "%.*f %s" % (precision, calc, suffixes[suffix_index])

    def __eq__(self, other) -> bool:
        """Operation == overloading for ExegolImage object"""
        # How to compare two ExegolImage
        if type(other) is ExegolImage:
            return self.getName() == other.getName() and self.__digest == other.__digest and self.__arch == other.__arch
        # How to compare ExegolImage with str
        elif type(other) is str:
            return self.getName() == other
        else:
            logger.error(f"Error, {type(other)} compare to ExegolImage is not implemented")
            raise NotImplementedError

    def __str__(self) -> str:
        """Default object text formatter, debug only"""
        return f"{self.getName()} ({self.__image_version}/{self.__profile_version} {self.__arch}) - {self.__disk_size} - " + \
            (f"({self.getStatus()}, {self.__dl_size})" if self.__is_remote else f"{self.getStatus()}")

    def __repr__(self) -> str:
        return re.sub(r"(\[/?[^]]+])", '', str(self)).replace(':arrow_right:', '->')

    def setCustomStatus(self, status: str = "") -> None:
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
                    status += f" (currently v.{self.getImageVersion()})"
            status += "[/orange3]"
            return status
        else:
            if self.canBePulled():
                return "[bright_black]Not installed[/bright_black]"
            else:
                return f"[bright_black]{self.getDisplayLicense()} only[/bright_black]"

    def getType(self) -> str:
        """Image type getter"""
        return "remote" if self.__is_remote else "local"

    def __setDigest(self, digest: Optional[str]) -> None:
        """Remote image digest setter"""
        if digest is not None:
            self.__digest = digest

    def __setRepository(self, repo: str) -> None:
        """Remote repository setter"""
        self.__repository = repo
        self.__is_official = self.isOfficialImage(repo)

    def __parseRepoDigests(self) -> Tuple[str, str]:
        """Parse the repository of a local image.
        Return repository path and digest id from the current docker object."""
        assert self.__image is not None
        default_repo = ""
        default_digest = ""
        for digest_id in self.__image.attrs["RepoDigests"]:
            default_repo, default_digest = digest_id.split('@')
            # Find digest id from the right repository
            if self.isOfficialImage(default_repo):
                break
        return default_repo, default_digest

    def setRepository(self, repository: str) -> None:
        """Set the current image repository. For legacy compatibility of community images."""
        self.__repository = repository

    def getRepository(self) -> str:
        """Image repository getter"""
        return self.__repository

    def getRemoteId(self) -> str:
        """Remote digest getter"""
        return self.__digest

    def __setLatestRemoteId(self, digest: str) -> None:
        """Remote latest digest getter"""
        self.__profile_digest = digest

    def getLatestRemoteId(self) -> str:
        """Remote latest digest getter"""
        return self.__profile_digest

    def __setImageId(self, image_id: Optional[str]) -> None:
        """Local image id setter"""
        if image_id is not None:
            self.__image_id = image_id.split(":")[1][:12]

    def getLocalId(self) -> str:
        """Local id getter"""
        return self.__image_id

    def getKey(self) -> str:
        """Universal unique key getter (from SelectableInterface)"""
        return self.getName()

    def __setRealSize(self, value: int) -> None:
        """On-Disk image size setter"""
        self.__disk_size = self.__processSize(value)

    def getRealSize(self) -> str:
        """Image size getter. If the image is installed, return the on-disk size, otherwise return the remote size"""
        return self.__disk_size if self.__is_install else f"[bright_black]{self.__disk_size}[/bright_black]"

    def getRealSizeRaw(self) -> str:
        """Image size getter without color. If the image is installed, return the on-disk size, otherwise return the remote size"""
        return self.__disk_size if self.__is_install else self.__disk_size

    def getDownloadSize(self) -> str:
        """Remote size getter"""
        if not self.__is_remote:
            return "local"
        return self.__dl_size

    def getEntrypointConfig(self) -> Optional[Union[str, List[str]]]:
        """Image's entrypoint configuration getter.
        Exegol images before 3.x.x don't have any entrypoint set (because /.exegol/entrypoint.sh don't exist yet. In this case, this getter will return None."""
        return self.__entrypoint

    def getBuildDate(self) -> str:
        """Build date getter"""
        if not self.__build_date:
            # Handle empty string
            return "[bright_black]N/A[/bright_black]"
        elif isinstance(self.__build_date, datetime):
            return self.__build_date.astimezone().strftime("%d/%m/%Y %H:%M")
        elif isinstance(self.__build_date, str) and "N/A" not in self.__build_date.upper():
            return get_display_date(self.__build_date)
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

    def isLegacy(self) -> bool:
        """Getter legacy status.
        If current image is legacy and no longer supported"""
        return self.__is_discontinued

    def isVersionSpecific(self) -> bool:
        """Is the current image a version specific version?
        Image version specific container a '-' in the name,
        latest image don't."""
        return self.__version_specific

    def hasVersionTag(self) -> bool:
        """If the current image has version specific tags in the registry"""
        if self.__license is None or self.__license == "" or self.__name == "nightly":
            return False
        return self.__is_official

    def getName(self) -> str:
        """Image's tag name getter"""
        if self.__is_official or self.__repository == "":
            return self.__name
        else:
            return self.__repository + ":" + self.__name

    def getDisplayLicense(self) -> str:
        """Image's license getter"""
        if self.__license is None or self.__license == "":
            return "Community"
        if self.__license == "Professional":
            return "Pro / Enterprise"
        return self.__license.capitalize()

    def getDisplayRepository(self) -> str:
        """Image's repository name getter"""
        if self.__repository == ConstantConfig.IMAGE_NAME:
            return self.getDisplayLicense() if self.__license else "Official"
        elif self.__repository == ConstantConfig.COMMUNITY_IMAGE_NAME:
            return "Community"
        elif self.__repository in UserConfig().custom_images:
            return "Custom"
        elif self.isLocal():
            return "Local"
        return "[bright_black]Unknown[/bright_black]"

    def getDisplayName(self) -> str:
        """Image's display name getter"""
        result = self.__display_name if self.__display_name else self.getName()
        if self.getArch().split('/')[0] != ParametersManager().arch or logger.isEnabledFor(ExeLog.VERBOSE):
            color = ConsoleFormat.getArchColor(self.getArch())
            result += f" [{color}]({self.getArch()})[/{color}]"
        return result

    def getArch(self) -> str:
        """Image's arch getter"""
        return self.__arch if self.__arch else "amd64"

    def __setArch(self, arch: str) -> None:
        """Image's arch setter."""
        self.__arch = arch

    def getLatestVersionName(self) -> str:
        """Image's tag name with latest version getter"""
        return self.__formatVersionName(self.__profile_version)

    def getInstalledVersionName(self) -> str:
        """Image's tag name with installed version getter"""
        return self.__formatVersionName(self.__image_version)

    def __formatVersionName(self, version: str) -> str:
        """From the selected version, format the image tag name"""
        result_name = self.__name
        if not (self.__version_specific or self.__version_label_mode or 'N/A' in version):
            result_name += "-" + version
        return result_name

    def __setImageVersion(self, version: str, source_tag: bool = True) -> None:
        """Image's tag version setter.
        Set source_tag as true if the information is retrieve from the image's tag name.
        If the version is retrieve from the label, set source_tag as False."""
        self.__image_version = version
        self.__version_label_mode = not source_tag

    def getImageVersion(self) -> str:
        """Image's tag version getter"""
        return self.__image_version

    def __setLatestVersion(self, version: str) -> None:
        """Image's tag version setter"""
        self.__profile_version = version

    def getLatestVersion(self) -> str:
        """Latest image version getter"""
        return self.__profile_version

    def getFullName(self) -> str:
        """Dockerhub image's full name getter"""
        return f"{self.__repository}:{self.__name}"

    def getFullVersionName(self) -> str:
        """Dockerhub image's full (installed) version name getter"""
        return f"{self.__repository}:{self.getInstalledVersionName()}"

    def getDockerRef(self) -> str:
        """Find and return the right id to target the current image for docker.
        If tag is lost, fallback to local image id."""
        assert self.__image is not None
        if self.getFullName() in self.__image.attrs.get('RepoTags', []):
            return self.getFullName()
        elif self.getFullVersionName() in self.__image.attrs.get('RepoTags', []):
            return self.getFullVersionName()
        return self.getLocalId()

    @staticmethod
    def isOfficialImage(image_name: str, suffix: str = "") -> bool:
        for repository in ConstantConfig.OFFICIAL_REPOSITORIES:
            if image_name.startswith(repository + suffix):
                return True
        return False

    @staticmethod
    def tagNameParsing(tag_name: str) -> str:
        parts = tag_name.split('-')
        version = '-'.join(parts[1:])
        # Code for future multi parameter from tag name (e.g. ad-debian-1.2.3)
        """
        first_parameter = ""
        # Try to detect legacy tag name or new latest name
        if len(parts) == 2:
            # If there is any '.' in the second part, it's a version format
            if "." in parts[1]:
                # Legacy version format
                version = parts[1]
            else:
                # Latest arch specific image
                first_parameter = parts[1]
        elif len(parts) >= 3:
            # Arch + version format
            first_parameter = parts[1]
            # Additional - stored in version
            version = '-'.join(parts[2:])

        return version, first_parameter
        """
        return version
