from pathlib import Path
from typing import Optional, Union

from exegol.console.ExegolPrompt import Confirm
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.GitUtils import GitUtils
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.UserConfig import UserConfig


class ExegolModules(metaclass=MetaSingleton):
    """Singleton class dedicated to the centralized management of the project modules"""

    def __init__(self):
        """Init project git modules to None until their first call"""
        self.__git_wrapper: Optional[GitUtils] = None
        self.__git_source: Optional[GitUtils] = None
        self.__git_resources: Optional[GitUtils] = None

    def getWrapperGit(self, fast_load: bool = False) -> GitUtils:
        """GitUtils local singleton getter.
        Set fast_load to True to disable submodule init/update."""
        if self.__git_wrapper is None:
            self.__git_wrapper = GitUtils(skip_submodule_update=fast_load)
        return self.__git_wrapper

    def getSourceGit(self, fast_load: bool = False) -> GitUtils:
        """GitUtils source submodule singleton getter.
        Set fast_load to True to disable submodule init/update."""
        # Be sure that submodules are init first
        self.getWrapperGit()
        if self.__git_source is None:
            self.__git_source = GitUtils(ConstantConfig.src_root_path_obj / "exegol-docker-build", "images",
                                         skip_submodule_update=fast_load)
        return self.__git_source

    def getResourcesGit(self, fast_load: bool = False, skip_install: bool = False) -> GitUtils:
        """GitUtils resource repo/submodule singleton getter.
        Set fast_load to True to disable submodule init/update.
        Set skip_install to skip to installation process of the modules if not available.
        if skip_install is NOT set, the CancelOperation exception is raised if the installation failed."""
        if self.__git_resources is None:
            self.__git_resources = GitUtils(UserConfig().exegol_resources_path, "resources", "",
                                            skip_submodule_update=fast_load)
        if not self.__git_resources.isAvailable and not skip_install:
            self.__init_resources_repo()
        return self.__git_resources

    def __init_resources_repo(self):
        """Initialization procedure of exegol resources module.
        Raise CancelOperation if the initialization failed."""
        if Confirm("Do you want to download exegol resources? (~1G)", True):
            # If git wrapper is ready and exegol resources location is the corresponding submodule, running submodule update
            # if not, git clone resources
            if UserConfig().exegol_resources_path == ConstantConfig.src_root_path_obj / 'exegol-resources' and \
                    self.getWrapperGit().isAvailable:
                # When resources are load from git submodule, git objects are stored in the root .git directory
                self.__warningExcludeFolderAV(ConstantConfig.src_root_path_obj)
                if self.getWrapperGit().submoduleSourceUpdate("exegol-resources"):
                    self.__git_resources = None
                    self.getResourcesGit()
                else:
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
            else:
                self.__warningExcludeFolderAV(UserConfig().exegol_resources_path)
                if not self.__git_resources.clone(ConstantConfig.EXEGOL_RESOURCES_REPO):
                    # Error during install, raise error to avoid update process
                    raise CancelOperation
        else:
            # User cancel installation, skip update update
            raise CancelOperation

    def isExegolResourcesReady(self) -> bool:
        """Update Exegol-resources from git (submodule)"""
        return self.getResourcesGit(fast_load=True).isAvailable

    @staticmethod
    def __warningExcludeFolderAV(directory: Union[str, Path]):
        """Generic procedure to warn the user that not antivirus compatible files will be downloaded and that
        the destination folder should be excluded from the scans to avoid any problems"""
        logger.warning(f"If you are using an [orange3][g]Anti-Virus[/g][/orange3] on your host, you should exclude the folder {directory} before starting the download.")
        while not Confirm(f"Are you ready to start the download?", True):
            pass
