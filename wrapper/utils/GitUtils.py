from git import Repo, Remote, InvalidGitRepositoryError

from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


# SDK Documentation : https://gitpython.readthedocs.io/en/stable/index.html

class GitUtils:

    def __init__(self):
        """Init git local repository object / SDK"""
        path = ConstantConfig.root_path
        logger.debug(f"Loading git at {path}")
        self.__gitRepo: Repo = None
        self.__gitRemote: Remote = None
        try:
            self.__gitRepo = Repo(path)
            logger.debug("Git repository successfully loaded")
            logger.success(f"Current git branch : {self.getCurrentBranch()}")
            if len(self.__gitRepo.remotes) > 0:
                self.__gitRemote = self.__gitRepo.remotes['origin']
            else:
                logger.warning("No remote git origin found on repository")
                logger.debug(self.__gitRepo.remotes)
        except InvalidGitRepositoryError:
            logger.warning("Error while loading local git repository. Skipping all git operation.")

    def getCurrentBranch(self):
        """Get current git branch name"""
        return str(self.__gitRepo.active_branch)

    def listBranch(self):
        """Return a list of str of all remote git branch available"""
        result = []
        if self.__gitRemote is None:
            return result
        for branch in self.__gitRemote.fetch():
            result.append(branch.name.split('/')[1])
        return result

    def safeCheck(self) -> bool:
        """Check the status of the local git repository,
        if there is pending change it is not safe to apply some operations"""
        if self.__gitRepo is None:
            return False
        if self.__gitRepo.is_dirty():
            logger.warning("Local git have unsaved change. Skipping operation.")
        return not self.__gitRepo.is_dirty()

    def isUpToDate(self, branch=None):
        """Check if the local git repository is up-to-date.
        This method compare the last commit local and remote first,
        if this commit don't match, check the last 15 previous commit (for dev use cases)."""
        if branch is None:
            branch = self.getCurrentBranch()
        current_commit = self.__gitRepo.branches[branch].commit
        remote_commit_id = str(self.__gitRemote.fetch()[f'{self.__gitRemote}/{branch}'].commit)
        i = 0
        # Search previous 15 commit for ahead commit (only for dev)
        COMMIT_CHECK_NUMBER = 15
        # TODO find better way to check if up-to-date with ahead commit
        while i < COMMIT_CHECK_NUMBER:
            if str(current_commit) == remote_commit_id:
                return True  # Current branch is up to date if current commit is the last remote commit
            i += 1
            parents = current_commit.parents
            if len(parents) == 0 or len(parents) > 1:
                break  # Stop searching on merge commit or end of tree
            current_commit = parents[0]  # Selecting parent for next iteration
        return False

    def update(self):
        """Update local git repository within current branch"""
        if not self.safeCheck():
            return
        if self.isUpToDate():
            logger.info("Git branch is already up-to-date.")
            return
        if self.__gitRemote is not None:
            self.__gitRemote.pull()  # TODO need some test, fast-forward only / try catch ?
            logger.success("Git successfully updated")

    def checkout(self, branch):
        """Change local git branch"""
        if not self.safeCheck():
            return
        if branch == self.getCurrentBranch():
            logger.warning(f"Branch '{branch}' is already the current branch")
            return
        self.__gitRepo.heads[branch].checkout()
        logger.success(f"Git successfully checkout to '{branch}'")
