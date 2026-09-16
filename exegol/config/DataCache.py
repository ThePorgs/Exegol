import json
from typing import List

from exegol.model.CacheModels import ContainerCacheModel, ContainersCacheModel, ImageCacheModel, WrapperCacheModel, CacheDB, ImagesCacheModel
from exegol.utils.DataFileUtils import DataFileUtils
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class DataCache(DataFileUtils, metaclass=MetaSingleton):
    """This class allows loading cached information defined configurations

    Example of data:
    {
        wrapper: {
            update: {
                metadata: {
                    last_check DATE
                }
                last_version: STR
            }
        }
        images:
            metadata: {
                    last_check: DATE
            }
            data: [
                {
                    name: STR (tag name)
                    last_version: STR (x.y.z|commit_id)
                    type: STR (local|remote)
                }
            ]
        containers:
            metadata: {
                    last_check: DATE
            }
            data: [
                {
                    name: STR (container tag, without the 'exegol-' prefix)
                }
            ]
    }
    """

    def __init__(self) -> None:
        # Cache data
        self.__cache_data = CacheDB()

        # Config file options
        super().__init__(".datacache", "json")

    def _process_data(self) -> None:
        if type(self._raw_data) is dict and len(self._raw_data) >= 2:
            try:
                self.__cache_data.load(**self._raw_data)
            except (TypeError, NotImplementedError):
                # An unreadable cache must never break a normal execution, it will be rebuilt from scratch
                logger.debug("Unsupported cache data format, resetting the cache.")
                self.__cache_data = CacheDB()

    def _build_file_content(self) -> str:
        return json.dumps(self.__cache_data, cls=self.ObjectJSONEncoder)

    def save_updates(self) -> None:
        self._create_config_file()

    def get_wrapper_data(self) -> WrapperCacheModel:
        """Get Wrapper information from cache"""
        return self.__cache_data.wrapper

    def get_images_data(self) -> ImagesCacheModel:
        """Get Images information from cache"""
        return self.__cache_data.images

    def get_containers_data(self) -> ContainersCacheModel:
        """Get Containers information from cache"""
        return self.__cache_data.containers

    def update_container_cache(self, names: List[str]) -> None:
        """Refresh container cache data.
        This cache is only used to supply CLI autocompletion, it must never be used for correctness."""
        if [c.name for c in self.__cache_data.containers.data] == names:
            # Nothing changed, skip the file update
            return
        logger.debug("Updating container cache data")
        self.__cache_data.containers = ContainersCacheModel([ContainerCacheModel(name) for name in names])
        self.save_updates()

    def add_container_cache(self, name: str) -> None:
        """Add a single container to the cache (autocompletion data)"""
        names = [c.name for c in self.__cache_data.containers.data]
        if name not in names:
            names.append(name)
            self.update_container_cache(names)

    def remove_container_cache(self, name: str) -> None:
        """Remove a single container from the cache (autocompletion data)"""
        self.update_container_cache([c.name for c in self.__cache_data.containers.data if c.name != name])

    async def update_image_cache(self, images: List) -> None:
        """Refresh image cache data"""
        logger.debug("Updating image cache data")
        cache_images = []
        for img in images:
            name = img.getName()
            version = img.getLatestVersion()
            if "N/A" in version:
                continue
            remote_id = img.getLatestRemoteId()
            image_type = "local" if img.isLocal() else "remote"
            logger.debug(f"└── {name} (version: {version})\t→ ({image_type}) {remote_id}")
            cache_images.append(
                ImageCacheModel(
                    name,
                    version,
                    remote_id,
                    image_type
                )
            )
        self.__cache_data.images = ImagesCacheModel(cache_images)
        self.save_updates()
