from typing import Optional, Set, Union

from docker.models.images import Image as DockerImage
from podman.domain.images import Image as PodmanImage

from exegol.utils.ExeLog import logger
from exegol.utils.WebUtils import WebUtils


class MetaImages:
    """Meta model to store and organise multi-arch images"""

    def __init__(self, dockerhub_data):
        """Create a MetaImage object to handle multi-arch docker registry images in a single point"""
        # Raw data
        self.__dockerhub_images: dict = dockerhub_data.get('images')
        # Attributes
        self.name: str = dockerhub_data.get('name', '')
        self.multi_arch: bool = len(self.__dockerhub_images) > 1
        self.list_arch: Set[str] = set(
            [self.parseArch(a) for a in self.__dockerhub_images])
        self.meta_id: Optional[str] = dockerhub_data.get("digest")
        if not self.meta_id:
            if self.multi_arch:
                logger.debug(f"Missing ID for image {self.name}, manual fetching ! May slow down the process..")
                self.meta_id = WebUtils.getMetaDigestId(self.name)
            else:
                # Single arch image dont need virtual meta_id
                self.__dockerhub_images[0].get('digest')
        self.version: str = self.tagNameParsing(self.name)
        self.is_latest: bool = not bool(self.version)  # Current image is latest if no version have been found from tag name
        # Post-process data
        self.__image_match = set()

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

    @staticmethod
    def parseArch(docker_image: Union[dict, DockerImage, PodmanImage]) -> str:
        """Parse and format arch in dockerhub style from registry dict struct.
        Return arch in format 'arch/variant'."""
        arch_key = "architecture"
        variant_key = "variant"
        # Support Docker and Podman image struct with specific dict key
        if isinstance(docker_image, (DockerImage, PodmanImage)):
            docker_image = docker_image.attrs
            arch_key = "Architecture"
            variant_key = "Variant"
        arch = docker_image.get(arch_key, "amd64")
        variant = docker_image.get(variant_key)
        if variant:
            arch += f"/{variant}"
        return arch

    def getDockerhubImageForArch(self, arch: str) -> Optional[dict]:
        """Find a docker image corresponding to a specific arch"""
        for img in self.__dockerhub_images:
            if self.parseArch(img) == arch:
                self.__image_match.add(arch)
                return img
        return None

    def getImagesLeft(self):
        """Return every image not previously selected."""
        result = []
        for img in self.__dockerhub_images:
            if self.parseArch(img) not in self.__image_match:
                result.append(img)
        return result

    def setVersionSpecific(self, meta_version: 'MetaImages'):
        self.version = meta_version.version

    def __str__(self):
        return f"{self.name} ({self.version}) [{self.meta_id}] {self.list_arch}"

    def __repr__(self):
        return self.__str__()
