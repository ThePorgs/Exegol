from typing import Optional, Union, Dict

from docker.models.images import Image


class MetaImages:
    """Meta model to store and organise multi-arch images from registry API"""

    def __init__(self, digest: str, image_name: str, tag_name: str, images_size: Dict[str, int]) -> None:
        """Create a MetaImage object to handle multi-arch docker registry images in a single point"""
        self.tag_name: str = tag_name
        self.image: str = image_name
        self.images_size: Dict[str, int] = images_size  # Arch : size
        self.images_size_left = self.images_size.copy()
        self.meta_id: str = digest
        self.version: str = '-'.join(self.tag_name.split('-')[1:])
        self.is_latest: bool = not bool(self.version)  # Current image is latest if no version have been found from tag name

    def __str__(self) -> str:
        return f"{self.tag_name} ({self.version}) [{self.meta_id}] {self.images_size.keys()}"

    def __repr__(self) -> str:
        return self.__str__()
