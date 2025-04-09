import json

from exegol.model.CacheModels import *
from exegol.utils.DataFileUtils import DataFileUtils
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
    }
    """

    def __init__(self) -> None:
        # Cache data
        self.__cache_data = CacheDB()

        # Config file options
        super().__init__(".datacache", "json")

    def _process_data(self) -> None:
        if len(self._raw_data) >= 2:
            self.__cache_data.load(**self._raw_data)

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

    def update_image_cache(self, images: List) -> None:
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
