import datetime
from typing import List, Optional, Dict, Union, Sequence, cast

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


class MetadataCacheModel:
    """MetadataCacheModel store a timestamp to compare with the last update"""

    def __init__(self, last_check=None, time_format: str = "%d/%m/%Y"):
        self.__TIME_FORMAT = time_format
        if last_check is None:
            last_check = datetime.date.today().strftime(self.__TIME_FORMAT)
        self.last_check: str = last_check

    def update_last_check(self) -> None:
        self.last_check = datetime.date.today().strftime(self.__TIME_FORMAT)

    def get_last_check(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.last_check, self.__TIME_FORMAT)

    def get_last_check_text(self) -> str:
        return self.last_check

    def is_outdated(self, days: int = 15, hours: int = 0) -> bool:
        """Check if the cache must be considered as expired."""
        now = datetime.datetime.now()
        last_check = self.get_last_check()
        if last_check > now:
            logger.debug("Incoherent last check date detected. Metadata must be updated.")
            return True
        # Check if the last update is older than the max delay configures (by default, return True after at least 15 days)
        return (last_check + datetime.timedelta(days=days, hours=hours)) < now


class ImageCacheModel:
    """This model store every important information for image caching."""

    def __init__(self, name: str, last_version: str, digest: str, source: str):
        self.name: str = name
        self.last_version: str = last_version
        self.digest: str = digest
        self.source: str = source

    def __str__(self) -> str:
        return f"{self.name}:{self.last_version} ({self.source}: {self.digest})"

    def __repr__(self) -> str:
        return str(self)


class ImagesCacheModel:
    """This model can store multiple image and the date of the last update"""

    def __init__(self, data: Sequence[Union[ImageCacheModel, Dict]], metadata: Optional[Dict] = None):
        # An old default date will be used until data are provided
        default_date: Optional[str] = "01/01/1990" if len(data) == 0 else None
        # Create or load (meta)data
        self.metadata: MetadataCacheModel = MetadataCacheModel(default_date) if metadata is None else MetadataCacheModel(**metadata)
        self.data: List[ImageCacheModel] = []
        if len(data) > 0:
            if type(data[0]) is dict:
                for img in data:
                    self.data.append(ImageCacheModel(**cast(Dict, img)))
            elif type(data[0]) is ImageCacheModel:
                self.data = cast(List[ImageCacheModel], data)
            else:
                raise NotImplementedError

    def __str__(self) -> str:
        return f"{len(self.data)} images ({self.metadata.last_check})"

    def __repr__(self) -> str:
        return str(self)


class WrapperCacheModel:
    """Caching wrapper update information (last version / last update)"""

    def __init__(self, last_version: Optional[str] = None, current_version: Optional[str] = None, metadata: Optional[Dict] = None):
        default_date: Optional[str] = None
        if last_version is None:
            last_version = ConstantConfig.version
            default_date = "01/01/1990"
        if current_version is None:
            current_version = ConstantConfig.version
        self.metadata: MetadataCacheModel = MetadataCacheModel(default_date) if metadata is None else MetadataCacheModel(**metadata)
        self.last_version: str = last_version
        self.current_version: str = current_version

    def __str__(self) -> str:
        return f"{self.current_version} -> {self.last_version} ({self.metadata.last_check})"

    def __repr__(self) -> str:
        return str(self)


class CacheDB:
    """Main object of the exegol cache"""

    def __init__(self) -> None:
        self.wrapper: WrapperCacheModel = WrapperCacheModel()
        self.images: ImagesCacheModel = ImagesCacheModel([])

    def load(self, wrapper: Dict, images: Dict) -> None:
        """Load the CacheDB data from a raw Dict object"""
        self.wrapper = WrapperCacheModel(**wrapper)
        self.images = ImagesCacheModel(**images)
