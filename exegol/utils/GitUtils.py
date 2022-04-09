from typing import Optional, List

from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


# SDK Documentation : https://gitpython.readthedocs.io/en/stable/index.html

class GitUtils:
    """Utility class between exegol and the Git SDK"""

    def __init__(self):
        """Init git local repository object / SDK"""
        path = ConstantConfig.src_root_path_obj
        self.isAvailable = False
        # Check if .git directory exist
        try:
            if not (path / '.git').is_dir():
                raise ReferenceError
        except ReferenceError:
            logger.warning("Exegol has not been installed via git clone. Skipping wrapper auto-update operation.")
            if path.name == "site-packages":
                logger.info("If you have installed Exegol with pip, check for an update with the command "
                            "[green]pip3 install exegol --upgrade[/green]")
        # locally import git in case git is not installed of the system
        try:
            from git import Repo, Remote, InvalidGitRepositoryError, FetchInfo
        except ModuleNotFoundError:
            logger.debug("Git module is not installed.")
            return
        except ImportError:
            logger.error("Unable to find git tool locally. Skipping git operations.")
            return
        logger.debug(f"Loading git at {path}")
        self.__gitRepo: Optional[Repo] = None
        self.__gitRemote: Optional[Remote] = None
        self.__fetchBranchInfo: Optional[FetchInfo] = None

        try:
            self.__gitRepo = Repo(str(path))
            self.isAvailable = True
            logger.debug("Git repository successfully loaded")
            if len(self.__gitRepo.remotes) > 0:
                self.__gitRemote = self.__gitRepo.remotes['origin']
            else:
                logger.warning("No remote git origin found on repository")
                logger.debug(self.__gitRepo.remotes)
        except InvalidGitRepositoryError as err:
            logger.verbose(err)
            logger.warning("Error while loading local git repository. Skipping all git operation.")

    def getCurrentBranch(self) -> str:
        """Get current git branch name"""
        assert self.isAvailable
        assert self.__gitRepo is not None
        return str(self.__gitRepo.active_branch)

    def listBranch(self) -> List[str]:
        """Return a list of str of all remote git branch available"""
        assert self.isAvailable
        result: List[str] = []
        if self.__gitRemote is None:
            return result
        for branch in self.__gitRemote.fetch():
            branch_parts = branch.name.split('/')
            if len(branch_parts) < 2:
                logger.warning(f"Branch name is not correct: {branch.name}")
                result.append(branch.name)
            else:
                result.append(branch_parts[1])
        return result

    def safeCheck(self) -> bool:
        """Check the status of the local git repository,
        if there is pending change it is not safe to apply some operations"""
        assert self.isAvailable
        if self.__gitRepo is None or self.__gitRemote is None:
            return False
        if self.__gitRepo.is_dirty():
            logger.warning("Local git have unsaved change. Skipping source update.")
        return not self.__gitRepo.is_dirty()

    def isUpToDate(self, branch: Optional[str] = None) -> bool:
        """Check if the local git repository is up-to-date.
        This method compare the last commit local and the ancestor."""
        assert self.isAvailable
        if branch is None:
            branch = self.getCurrentBranch()
        assert self.__gitRepo is not None
        assert self.__gitRemote is not None
        # Get last local commit
        current_commit = self.__gitRepo.heads[branch].commit
        # Get last remote commit
        fetch_result = self.__gitRemote.fetch()
        self.__fetchBranchInfo = fetch_result[f'{self.__gitRemote}/{branch}']

        logger.debug(f"Fetch flags : {self.__fetchBranchInfo.flags}")
        logger.debug(f"Fetch note : {self.__fetchBranchInfo.note}")
        logger.debug(f"Fetch old commit : {self.__fetchBranchInfo.old_commit}")
        logger.debug(f"Fetch remote path : {self.__fetchBranchInfo.remote_ref_path}")
        from git import FetchInfo
        # Bit check to detect flags info
        if self.__fetchBranchInfo.flags & FetchInfo.HEAD_UPTODATE != 0:
            logger.debug("HEAD UP TO DATE flag detected")
        if self.__fetchBranchInfo.flags & FetchInfo.FAST_FORWARD != 0:
            logger.debug("FAST FORWARD flag detected")
        if self.__fetchBranchInfo.flags & FetchInfo.ERROR != 0:
            logger.debug("ERROR flag detected")
        if self.__fetchBranchInfo.flags & FetchInfo.FORCED_UPDATE != 0:
            logger.debug("FORCED_UPDATE flag detected")
        if self.__fetchBranchInfo.flags & FetchInfo.REJECTED != 0:
            logger.debug("REJECTED flag detected")
        if self.__fetchBranchInfo.flags & FetchInfo.NEW_TAG != 0:
            logger.debug("NEW TAG flag detected")

        remote_commit = self.__fetchBranchInfo.commit
        # Check if remote_commit is an ancestor of the last local commit (check if there is local commit ahead)
        return self.__gitRepo.is_ancestor(remote_commit, current_commit)

    def update(self) -> bool:
        """Update local git repository within current branch"""
        assert self.isAvailable
        if not self.safeCheck():
            return False
        if self.isUpToDate():
            logger.info("Git branch is already up-to-date.")
            return False
        if self.__gitRemote is not None:
            logger.info(f"Updating local git '{self.getCurrentBranch()}'")
            self.__gitRemote.pull()
            logger.success("Git successfully updated")
            return True
        return False

    def checkout(self, branch: str) -> bool:
        """Change local git branch"""
        assert self.isAvailable
        if not self.safeCheck():
            return False
        if branch == self.getCurrentBranch():
            logger.warning(f"Branch '{branch}' is already the current branch")
            return False
        assert self.__gitRepo is not None
        self.__gitRepo.heads[branch].checkout()
        logger.success(f"Git successfully checkout to '{branch}'")
        return True
