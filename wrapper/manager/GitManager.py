import pathlib

from git import Repo, Remote, InvalidGitRepositoryError

from wrapper.utils.ExeLog import logger


class GitManager:

    def __init__(self):
        path = pathlib.Path(__file__).parent.parent.parent.resolve()
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
        pass

    def getCurrentBranch(self):
        return str(self.__gitRepo.active_branch)

    def listBranch(self):
        result = []
        if self.__gitRemote is None:
            return result
        for branch in self.__gitRemote.fetch():
            result.append(branch.name.split('/')[1])
        return result

    def safeCheck(self) -> bool:
        if self.__gitRepo is None:
            return False
        if self.__gitRepo.is_dirty():
            logger.warning("Local git have unsaved change. Skipping operation.")
        return not self.__gitRepo.is_dirty()

    def isUpToDate(self, branch=None):
        if branch is None:
            branch = self.getCurrentBranch()
        current_commit = self.__gitRepo.branches[branch].commit
        remote_commit_id = str(self.__gitRemote.fetch()[f'{self.__gitRemote}/{branch}'].commit)
        i = 0
        # Search previous 15 commit for ahead commit (only for dev)
        # TODO find better way to check if up-to-date with ahead commit
        while i < 15:
            if str(current_commit) == remote_commit_id:
                return True  # Current branch is up to date if current commit is the last remote commit
            i += 1
            parents = current_commit.parents
            if len(parents) == 0 or len(parents) > 1:
                break  # Stop searching on merge commit or end of tree
            current_commit = parents[0]  # Selecting parent for next iteration
        return False

    def update(self):
        if not self.safeCheck():
            return
        if self.isUpToDate():
            logger.info("Git branch is already up-to-date.")
            return
        if self.__gitRemote is not None:
            self.__gitRemote.pull()  # TODO need some test, fast-forward only / try catch ?
            logger.success("Git successfully updated")

    def checkout(self, branch):
        if not self.safeCheck():
            return
        if branch == self.getCurrentBranch():
            logger.warning(f"Branch '{branch}' is already the current branch")
            return
        self.__gitRepo.heads[branch].checkout()
        logger.success(f"Git successfully checkout to '{branch}'")
