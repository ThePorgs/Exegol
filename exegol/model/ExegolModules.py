from pathlib import Path
from typing import Optional, Union

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.UserConfig import UserConfig
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ExeLog import logger
from exegol.utils.GitUtils import GitUtils
from exegol.utils.MetaSingleton import MetaSingleton


class ExegolModules(metaclass=MetaSingleton):
    """Singleton class dedicated to the centralized management of the project modules"""

    def __init__(self) -> None:
        """Init project git modules to None until their first call"""
        # Git modules
        self.__git_wrapper: Optional[GitUtils] = None
        self.__git_source: Optional[GitUtils] = None
        self.__git_resources: Optional[GitUtils] = None

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
            self.__git_source = await GitUtils(UserConfig().exegol_images_path, "images").initialize(skip_submodule_update=fast_load)
        if not self.__git_source.isAvailable and not skip_install:
            await self.__init_images_repo()
        return self.__git_source

    async def getResourcesGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils resource repo/submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_resources is None:
            self.__git_resources = await GitUtils(UserConfig().exegol_resources_path, "resources", "").initialize(skip_submodule_update=fast_load)
        if not self.__git_resources.isAvailable and not skip_install and UserConfig().enable_exegol_resources:
            await self.__init_resources_repo()
        return self.__git_resources

    async def __init_images_repo(self) -> None:
        """Initialization procedure of exegol images module.
        Raise CancelOperation if the initialization failed."""
        if ParametersManager().offline_mode:
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
        if ParametersManager().offline_mode:
            logger.error("It's not possible to install 'Exegol resources' in offline mode. Skipping the operation.")
            raise CancelOperation
        if await ExegolRich.Confirm("Do you want to download exegol resources? (~1G)", True):
            # If git wrapper is ready and exegol resources location is the corresponding submodule, running submodule update
            # if not, git clone resources
            if UserConfig().exegol_resources_path == ConstantConfig.src_root_path_obj / 'exegol-resources' and \
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
                await self.__warningExcludeFolderAV(UserConfig().exegol_resources_path)
                assert self.__git_resources is not None
                if not await self.__git_resources.clone(ConstantConfig.EXEGOL_RESOURCES_REPO):
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
        else:
            # User cancel installation, skip update update
            raise CancelOperation

    async def isExegolResourcesReady(self) -> bool:
        """Update Exegol-resources from git (submodule)"""
        return (await self.getResourcesGit(fast_load=True)).isAvailable

    @staticmethod
    async def __warningExcludeFolderAV(directory: Union[str, Path]) -> None:
        """Generic procedure to warn the user that not antivirus compatible files will be downloaded and that
        the destination folder should be excluded from the scans to avoid any problems"""
        logger.warning(f"If you are using an [orange3][g]Anti-Virus[/g][/orange3] on your host, you should exclude the folder {directory} before starting the download.")
        while not await ExegolRich.Confirm(f"Are you ready to start the download?", True):
            pass
