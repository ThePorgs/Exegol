from pathlib import Path
from typing import Optional, List

from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger, console


# SDK Documentation : https://gitpython.readthedocs.io/en/stable/index.html

class GitUtils:
    """Utility class between exegol and the Git SDK"""

    def __init__(self,
                 path: Optional[Path] = None,
                 name: str = "wrapper",
                 subject: str = "source code",
                 skip_submodule_update: bool = False):
        """Init git local repository object / SDK"""
        if path is None:
            path = ConstantConfig.src_root_path_obj
        self.isAvailable = False
        self.__is_submodule = False
        self.__git_disable = False
        self.__repo_path = path
        self.__git_name: str = name
        self.__git_subject: str = subject
        abort_loading = False
        # Check if .git directory exist
        try:
            test_git_dir = self.__repo_path / '.git'
            if test_git_dir.is_file():
                logger.debug("Git submodule repository detected")
                self.__is_submodule = True
            elif not test_git_dir.is_dir():
                raise ReferenceError
        except ReferenceError:
            if self.__git_name == "wrapper":
                logger.warning("Exegol has not been installed via git clone. Skipping wrapper auto-update operation.")
                if ConstantConfig.pip_installed:
                    logger.info("If you have installed Exegol with pip, check for an update with the command "
                                "[green]pip3 install exegol --upgrade[/green]")
            abort_loading = True
        # locally import git in case git is not installed of the system
        try:
            from git import Repo, Remote, InvalidGitRepositoryError, FetchInfo
        except ModuleNotFoundError:
            self.__git_disable = True
            logger.debug("Git module is not installed.")
            return
        except ImportError:
            self.__git_disable = True
            logger.error("Unable to find git tool locally. Skipping git operations.")
            return
        self.__gitRepo: Optional[Repo] = None
        self.__gitRemote: Optional[Remote] = None
        self.__fetchBranchInfo: Optional[FetchInfo] = None

        if abort_loading:
            return
        logger.debug(f"Loading git at {self.__repo_path}")
        try:
            self.__gitRepo = Repo(self.__repo_path)
            logger.debug(f"Repo path: {self.__gitRepo.git_dir}")
            self.__init_repo(skip_submodule_update)
        except InvalidGitRepositoryError as err:
            logger.verbose(err)
            logger.warning("Error while loading local git repository. Skipping all git operation.")

    def __init_repo(self, skip_submodule_update: bool = False):
        self.isAvailable = True
        assert self.__gitRepo is not None
        logger.debug("Git repository successfully loaded")
        if len(self.__gitRepo.remotes) > 0:
            self.__gitRemote = self.__gitRepo.remotes['origin']
        else:
            logger.warning("No remote git origin found on repository")
            logger.debug(self.__gitRepo.remotes)
        if not skip_submodule_update:
            self.__initSubmodules()

    def clone(self, repo_url: str, optimize_disk_space: bool = True) -> bool:
        if self.isAvailable:
            logger.warning(f"The {self.getName()} repo is already cloned.")
            return False
        # locally import git in case git is not installed of the system
        try:
            from git import Repo, Remote, InvalidGitRepositoryError, FetchInfo
        except ModuleNotFoundError:
            logger.debug("Git module is not installed.")
            return False
        except ImportError:
            logger.error(f"Unable to find git on your machine. The {self.getName()} repository cannot be cloned.")
            logger.warning("Please install git to support this feature.")
            return False
        custom_options = []
        if optimize_disk_space:
            custom_options.append('--depth=1')
        # TODO add progress bar via TUI
        from git import GitCommandError
        try:
            with console.status(f"Downloading {self.getName()} git repository", spinner_style="blue"):
                self.__gitRepo = Repo.clone_from(repo_url, str(self.__repo_path), multi_options=custom_options)
        except GitCommandError as e:
            # GitPython user \n only
            error = GitUtils.formatStderr(e.stderr)
            logger.error(f"Unable to clone the git repository. {error}")
            return False
        self.__init_repo()
        return True

    def getCurrentBranch(self) -> Optional[str]:
        """Get current git branch name"""
        if not self.isAvailable:
            return None
        assert self.__gitRepo is not None
        try:
            return str(self.__gitRepo.active_branch)
        except TypeError:
            logger.debug("Git HEAD is detached, cant find the current branch.")
            return None
        except ValueError:
            logger.error(f"Unable to find current git branch in the {self.__git_name} repository. Check the path in the .git file from {self.__repo_path / '.git'}")
            return None

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
        # Submodule changes must be ignored to update the submodules sources independently of the wrapper
        is_dirty = self.__gitRepo.is_dirty(submodules=False)
        if is_dirty:
            logger.warning("Local git have unsaved change. Skipping source update.")
        return not is_dirty

    def isUpToDate(self, branch: Optional[str] = None) -> bool:
        """Check if the local git repository is up-to-date.
        This method compare the last commit local and the ancestor."""
        assert self.isAvailable
        if branch is None:
            branch = self.getCurrentBranch()
            if branch is None:
                logger.warning("No branch is currently attached to the git repository. The up-to-date status cannot be checked.")
                return False
        assert self.__gitRepo is not None
        assert self.__gitRemote is not None
        # Get last local commit
        current_commit = self.__gitRepo.heads[branch].commit
        # Get last remote commit
        fetch_result = self.__gitRemote.fetch()
        try:
            self.__fetchBranchInfo = fetch_result[f'{self.__gitRemote}/{branch}']
        except IndexError:
            logger.warning("The selected branch is local and cannot be updated.")
            return True

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
        # Check if the git branch status is not detached
        if self.getCurrentBranch() is None:
            return False
        if self.isUpToDate():
            logger.success(f"Git branch [green]{self.getCurrentBranch()}[/green] is already up-to-date.")
            return False
        if self.__gitRemote is not None:
            logger.info(f"Using branch [green]{self.getCurrentBranch()}[/green] on {self.getName()} repository")
            with console.status(f"Updating git [green]{self.getName()}[/green]", spinner_style="blue"):
                self.__gitRemote.pull(refspec=self.getCurrentBranch())
            logger.success("Git successfully updated")
            return True
        return False

    def __initSubmodules(self):
        """Init (and update git object not source code) git sub repositories (only depth=1)"""
        logger.verbose(f"Git {self.getName()} init submodules")
        # These module are init / updated manually
        blacklist_heavy_modules = ["exegol-resources"]
        # Submodules dont have depth submodule limits
        depth_limit = not self.__is_submodule
        with console.status(f"Initialization of git submodules", spinner_style="blue") as s:
            try:
                submodules = self.__gitRepo.iter_submodules()
            except ValueError:
                logger.error(f"Unable to find any git submodule from '{self.getName()}' repository. Check the path in the file {self.__repo_path / '.git'}")
                return
            for subm in submodules:
                # Submodule update are skipped if blacklisted or if the depth limit is set
                if subm.name in blacklist_heavy_modules or \
                        (depth_limit and ('/' in subm.name or '\\' in subm.name)):
                    continue
                s.update(status=f"Downloading git submodules [green]{subm.name}[/green]")
                from git.exc import GitCommandError
                try:
                    subm.update(recursive=True)
                except GitCommandError as e:
                    error = GitUtils.formatStderr(e.stderr)
                    logger.debug(f"Unable tu update git submodule {subm.name}: {e}")
                    if "unable to access" in error:
                        logger.error("You don't have internet to update git submodule. Skipping operation.")
                    else:
                        logger.error("Unable to update git submodule. Skipping operation.")
                        logger.error(error)
                except ValueError:
                    logger.error(f"Unable to update git submodule '{subm.name}'. Check the path in the file '{Path(subm.path) / '.git'}'")

    def submoduleSourceUpdate(self, name: str) -> bool:
        """Update source code from the 'name' git submodule"""
        if not self.isAvailable:
            return False
        assert self.__gitRepo is not None
        try:
            submodule = self.__gitRepo.submodule(name)
        except ValueError:
            logger.debug(f"Git submodule '{name}' not found.")
            return False
        from git.exc import RepositoryDirtyError
        try:
            from git.exc import GitCommandError
            try:
                # TODO add TUI progress
                with console.status(f"Downloading submodule [green]{name}[/green]", spinner_style="blue"):
                    submodule.update(to_latest_revision=True)
            except GitCommandError as e:
                logger.debug(f"Unable tu update git submodule {name}: {e}")
                if "unable to access" in e.stderr:
                    logger.error("You don't have internet to update git submodule. Skipping operation.")
                else:
                    logger.error("Unable to update git submodule. Skipping operation.")
                    logger.error(e.stderr)
                return False
            logger.success(f"Submodule [green]{name}[/green] successfully updated.")
            return True
        except RepositoryDirtyError:
            logger.warning(f"Submodule {name} cannot be updated automatically as long as there are local modifications.")
            logger.error("Aborting git submodule update.")
        logger.empty_line()
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
        from git.exc import GitCommandError
        try:
            # If git local branch didn't exist, change HEAD to the origin branch and create a new local branch
            if branch not in self.__gitRepo.heads:
                self.__gitRepo.references['origin/' + branch].checkout()
                self.__gitRepo.create_head(branch)
            self.__gitRepo.heads[branch].checkout()
        except GitCommandError as e:
            logger.error("Unable to checkout to the selected branch. Skipping operation.")
            logger.debug(e)
            return False
        except IndexError as e:
            logger.error("Unable to find the selected branch. Skipping operation.")
            logger.debug(e)
            return False
        logger.success(f"Git successfully checkout to '{branch}'")
        return True

    def getTextStatus(self) -> str:
        """Get text status from git object for rich print."""
        if self.isAvailable:
            from git.exc import GitCommandError
            try:
                if self.isUpToDate():
                    result = "[green]Up to date[/green]"
                else:
                    result = "[orange3]Update available[/orange3]"
            except GitCommandError:
                # Offline error catch
                result = "[green]Installed[/green] [bright_black](offline)[/bright_black]"
        else:
            if self.__git_disable:
                result = "[red]Missing dependencies[/red]"
            elif self.__git_name == ["wrapper", "images"] and \
                    (ConstantConfig.pip_installed or not ConstantConfig.git_source_installation):
                result = "[bright_black]Auto-update not supported[/bright_black]"
            else:
                result = "[bright_black]Not installed[/bright_black]"
        return result

    def getName(self) -> str:
        """Git name getter"""
        return self.__git_name

    def getSubject(self) -> str:
        """Git subject getter"""
        return self.__git_subject

    def isSubModule(self) -> bool:
        """Git submodule status getter"""
        return self.__is_submodule

    @classmethod
    def formatStderr(cls, stderr):
        return stderr.replace('\n', '').replace('stderr:', '').strip().strip("'")

    def __repr__(self) -> str:
        """Developer debug object representation"""
        return f"GitUtils '{self.__git_name}': {'Active' if self.isAvailable else 'Disable'}"
