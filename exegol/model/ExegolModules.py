from pathlib import Path
from typing import Optional, Union

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.console.ExegolPrompt import ExegolRich
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ExeLog import logger
from exegol.utils.GitUtils import GitUtils
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.SessionHandler import SessionHandler


class ExegolModules(metaclass=MetaSingleton):
    """Singleton class dedicated to the centralized management of the project modules"""

    def __init__(self) -> None:
        """Init project git modules to None until their first call"""
        # Git modules
        self.__git_wrapper: Optional[GitUtils] = None
        self.__git_source: Optional[GitUtils] = None
        self.__git_resources: Optional[GitUtils] = None
        self.__git_sentinel_core: Optional[GitUtils] = None

        # Git loading mode
        self.__wrapper_fast_loaded = False

    async def getWrapperGit(self, fast_load: bool = False) -> GitUtils:
        """GitUtils local singleton getter.
        Set fast_load to True to disable submodule init/update."""
        # If the module have been previously fast loaded and must be reuse later in standard mode, it can be recreated
        if self.__git_wrapper is None or (not fast_load and self.__wrapper_fast_loaded):
            self.__wrapper_fast_loaded = fast_load
            self.__git_wrapper = await GitUtils().initialize(skip_submodule_update=fast_load)
        return self.__git_wrapper

    async def getSourceGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils source submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_source is None:
            self.__git_source = await GitUtils(OptionResolver().get(OptionKey.EXEGOL_IMAGES_PATH), "images").initialize(skip_submodule_update=fast_load)
        if not self.__git_source.isAvailable and not skip_install:
            await self.__init_images_repo()
        return self.__git_source

    async def getResourcesGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils resource repo/submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        # Resolved once, from the same registry entry ContainerConfig uses to bind-mount this
        # tree, so the updated tree and the mounted tree cannot diverge.
        resources_path = OptionResolver().get(OptionKey.EXEGOL_RESOURCES_PATH)
        download_allowed = OptionResolver().get(OptionKey.ENABLE_EXEGOL_RESOURCES)
        if self.__git_resources is None:
            self.__git_resources = await GitUtils(resources_path, "resources", "").initialize(skip_submodule_update=fast_load)
        if not self.__git_resources.isAvailable and not skip_install and download_allowed:
            await self.__init_resources_repo()
        return self.__git_resources

    async def getSentinelCoreGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils Sentinel core repo singleton getter (mirrors getResourcesGit).
        The core source lives at component_path/core.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip the installation process of the module if not available.
        The auto-install (clone) path only runs for licensed Enterprise sessions.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_sentinel_core is None:
            # Discovery root: never profile-supplied (see ProfileFieldMap.PROFILE_TIER_DEAD).
            self.__git_sentinel_core = await GitUtils(OptionResolver().get(OptionKey.SENTINEL_PROFILE_PATH) / ConstantConfig.SENTINEL_CORE_SOURCE_KEY, "sentinel-core", "sentinel library").initialize(skip_submodule_update=fast_load)
        # License gate: mirror ContainerConfig.enableSentinel's enterprise_feature_access() check.
        if not self.__git_sentinel_core.isAvailable and not skip_install and SessionHandler().enterprise_feature_access():
            await self.__init_sentinel_core_repo()
        return self.__git_sentinel_core

    async def __init_images_repo(self) -> None:
        """Initialization procedure of exegol images module.
        Raise CancelOperation if the initialization failed."""
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to install 'Exegol Images' in offline mode. Skipping the operation.")
            raise CancelOperation
        # If git wrapper is ready and exegol images location is the corresponding submodule, running submodule update
        # if not, git clone resources
        if ConstantConfig.git_source_installation and (await self.getWrapperGit(fast_load=True)).isAvailable:
            # When resources are load from git submodule, git objects are stored in the root .git directory
            if (await self.getWrapperGit(fast_load=True)).submoduleSourceUpdate("exegol-images"):
                self.__git_source = None
                await self.getSourceGit()
            else:
                # Error during install, raise error to avoid update process
                raise CancelOperation
        else:
            assert self.__git_source is not None
            if not await self.__git_source.clone(ConstantConfig.EXEGOL_IMAGES_REPO):
                # Error during install, raise error to avoid update process
                raise CancelOperation

    async def __init_resources_repo(self) -> None:
        """Initialization procedure of exegol resources module.
        Raise CancelOperation if the initialization failed."""
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to install 'Exegol resources' in offline mode. Skipping the operation.")
            raise CancelOperation
        if OptionResolver().get(OptionKey.FORCE_MODE) or await ExegolRich.Confirm("Do you want to download exegol resources? (~1G)", True):
            # If git wrapper is ready and exegol resources location is the corresponding submodule, running submodule update
            # if not, git clone resources
            if OptionResolver().get(OptionKey.EXEGOL_RESOURCES_PATH) == ConstantConfig.src_root_path_obj / 'exegol-resources' and \
                    (await self.getWrapperGit()).isAvailable:
                # When resources are load from git submodule, git objects are stored in the root .git directory
                await self.__warningExcludeFolderAV(ConstantConfig.src_root_path_obj)
                if (await self.getWrapperGit()).submoduleSourceUpdate("exegol-resources"):
                    self.__git_resources = None
                    await self.getResourcesGit()
                else:
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
            else:
                await self.__warningExcludeFolderAV(OptionResolver().get(OptionKey.EXEGOL_RESOURCES_PATH))
                assert self.__git_resources is not None
                if not await self.__git_resources.clone(ConstantConfig.EXEGOL_RESOURCES_REPO):
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
        else:
            # User cancel installation, skip update update
            raise CancelOperation

    async def __init_sentinel_core_repo(self) -> None:
        """Initialization procedure of the Sentinel core source module.
        Raise CancelOperation if the initialization failed."""
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to install the Sentinel 'core' source in offline mode. Skipping the operation.")
            raise CancelOperation
        # No submodule branch: the core repo is public over HTTPS, so a runtime clone covers
        # every install mode.
        if ConstantConfig.git_source_installation:
            # TODO(optional): submoduleSourceUpdate("exegol-sentinel-core") if a submodule checkout is ever preferred.
            logger.advanced("Sentinel 'core' source uses the runtime-clone path (submodule branch not shipped).")
        assert self.__git_sentinel_core is not None
        if not await self.__git_sentinel_core.clone(ConstantConfig.EXEGOL_SENTINEL_CORE_REPO):
            # Error during install, raise error to avoid update process
            raise CancelOperation

    async def isExegolResourcesReady(self) -> bool:
        """Update Exegol-resources from git (submodule)"""
        return (await self.getResourcesGit(fast_load=True)).isAvailable

    @staticmethod
    async def __warningExcludeFolderAV(directory: Union[str, Path]) -> None:
        """Generic procedure to warn the user that not antivirus compatible files will be downloaded and that
        the destination folder should be excluded from the scans to avoid any problems"""
        logger.warning(f"If you are using an [orange3][g]Anti-Virus[/g][/orange3] on your host, you should exclude the folder {directory} before starting the download.")
        while not OptionResolver().get(OptionKey.FORCE_MODE) and not await ExegolRich.Confirm(f"Are you ready to start the download?", True):
            pass
