import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, List, cast, AsyncContextManager

from git import Commit, NoSuchPathError
from git.exc import GitCommandError, RepositoryDirtyError, UnsafeProtocolError, UnsafeOptionError
from gitdb.exc import ODBError
from git.util import CallableRemoteProgress
from rich.markup import escape
from rich.progress import TextColumn, BarColumn

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.EnvInfo import EnvInfo
from exegol.config.OptionResolver import OptionKey, OptionResolver
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.MetaGitProgress import MetaGitProgress, clone_update_progress, SubmoduleUpdateProgress
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import mkdir, chown_to_user


# SDK Documentation : https://gitpython.readthedocs.io/en/stable/index.html

class GitUtils:
    """Utility class between exegol and the Git SDK"""

    def __init__(self,
                 path: Optional[Path] = None,
                 name: str = "wrapper",
                 subject: str = "source code"):
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
            elif sys.platform == "win32":
                # Skip next platform specific code (temp fix for mypy static code analysis)
                pass
            elif not EnvInfo.is_windows_shell and os.getuid() != 0 and test_git_dir.lstat().st_uid != os.getuid():
                raise PermissionError(test_git_dir.owner())
        except ReferenceError:
            if self.__git_name == "wrapper":
                logger.warning("Exegol has [red]not[/red] been installed via git clone. Skipping wrapper auto-update operation.")
                if ConstantConfig.pipx_installed:
                    logger.info("If you have installed Exegol with pipx, check for an update with the command "
                                "[green]pipx upgrade exegol[/green]")
                elif ConstantConfig.uv_installed:
                    logger.info("If you have installed Exegol with uv, check for an update with the command "
                                "[green]uv tool upgrade exegol[/green]")
                elif ConstantConfig.pip_installed:
                    logger.info("If you have installed Exegol with pip, check for an update with the command "
                                "[green]pip3 install exegol --upgrade[/green]")
            abort_loading = True
        except PermissionError as e:
            logger.error(f"The repository {self.__git_name} has been cloned as [red]{e.args[0]}[/red].")
            logger.error("The current user does not have the necessary rights to perform the self-update operations.")
            logger.error("Please reinstall exegol (with git clone) without sudo.")
            abort_loading = True
        # locally import git in case git is not installed of the system
        try:
            from git import Repo, Remote, FetchInfo
        except ModuleNotFoundError:
            self.__git_disable = True
            logger.warning("Git module is not installed. Python module 'GitPython' is missing, please install it with pip.")
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

    async def initialize(self, skip_submodule_update: bool = False, silent: bool = False) -> "GitUtils":
        from git import Repo, InvalidGitRepositoryError
        if not self.__repo_path.is_dir():
            mkdir(self.__repo_path)
        try:
            self.__gitRepo = Repo(self.__repo_path)
            logger.debug(f"Repo path: {self.__gitRepo.git_dir}")
            await self.__init_repo(skip_submodule_update)
        except NoSuchPathError as err:
            if not silent:
                logger.debug(err)
                logger.warning(f"The {self.__repo_path} path does not exist. Skipping git operation.")
        except InvalidGitRepositoryError as err:
            if not silent:
                logger.verbose(err)
                logger.warning("Error while loading local git repository. Skipping all git operation.")
        return self

    async def __init_repo(self, skip_submodule_update: bool = False) -> None:
        self.isAvailable = True
        assert self.__gitRepo is not None
        logger.debug("Git repository successfully loaded")
        if len(self.__gitRepo.remotes) > 0:
            self.__gitRemote = self.__gitRepo.remotes['origin']
        else:
            logger.warning("No remote git origin found on repository")
            logger.debug(self.__gitRepo.remotes)
        if not skip_submodule_update:
            await self.__initSubmodules()

    def __reown_repo(self) -> None:
        """Chown the repository back to the invoking user after a git write run under sudo
        (no-op unless root on Linux, see FsUtils.chown_to_user)."""
        chown_to_user(self.__repo_path)

    @staticmethod
    def _looks_like_sha(ref: str) -> bool:
        """Return True if ref looks like an abbreviated or full git commit SHA (7-40 hex chars)."""
        return re.fullmatch(r'[0-9a-fA-F]{7,40}', ref) is not None

    @staticmethod
    def is_ssh_url(repo_url: str) -> bool:
        """Return True for an SSH git remote: ``ssh://…`` or the scp-like ``user@host:path``."""
        url = repo_url.strip()
        if url.lower().startswith("ssh://"):
            return True
        # scp-like syntax has no scheme and a ':' after a 'user@host' prefix (before any '/').
        return "://" not in url and re.match(r"^[^/\s]+@[^/\s]+:", url) is not None

    @staticmethod
    def build_git_ssh_command(base_command: Optional[str] = None) -> str:
        """Build a non-interactive ``GIT_SSH_COMMAND`` for cloning/pulling SSH git sources.

        Uses ``StrictHostKeyChecking=accept-new`` on OpenSSH >= 7.6 (trust unknown hosts, refuse
        changed keys), else ``yes``. ``BatchMode=yes`` makes a missing key fail fast instead of hanging.

        ``base_command`` (the user's existing ``GIT_SSH_COMMAND``) is kept and our options are
        appended; ssh uses the first value seen for an ``-o`` option, so user settings win.
        """
        policy = "yes"
        try:
            # timeout: a wedged `ssh` must not hang `exegol update` (TimeoutExpired is caught below).
            proc = subprocess.run(["ssh", "-V"], capture_output=True, text=True, timeout=5)
            version_text = (proc.stderr or "") + (proc.stdout or "")
            m = re.search(r"OpenSSH_(\d+)\.(\d+)", version_text)
            if m and (int(m.group(1)), int(m.group(2))) >= (7, 6):
                policy = "accept-new"
        except Exception as e:
            logger.debug(f"Unable to detect the ssh version, using StrictHostKeyChecking=yes: {e}")
        base = (base_command or "").strip() or "ssh"
        return f"{base} -o StrictHostKeyChecking={policy} -o BatchMode=yes -o ConnectTimeout=15"

    @staticmethod
    def _ssh_host_hint(repo_url: str) -> Optional[str]:
        """Extract the ``ssh-keyscan`` host argument (``[-p PORT] HOST``) from an SSH URL."""
        url = repo_url.strip()
        host: Optional[str] = None
        port: Optional[str] = None
        if url.lower().startswith("ssh://"):
            rest = url[len("ssh://"):]
            authority = rest.split("/", 1)[0]
            if "@" in authority:
                authority = authority.split("@", 1)[1]
            if ":" in authority:
                host, port = authority.split(":", 1)
            else:
                host = authority
        elif GitUtils.is_ssh_url(url):
            host = url.split("@", 1)[1].split(":", 1)[0]
        if not host:
            return None
        return f"-p {port} {host}" if port else host

    def __warn_ssh_host_key(self, repo_url: str) -> None:
        """Emit a clear, actionable warning when an SSH clone fails host-key verification."""
        logger.warning(f"SSH host key verification failed for the [green]{self.getName()}[/green] source: the host is "
                       f"unknown or its key changed since it was recorded in known_hosts. Skipping this source.")
        host_hint = GitUtils._ssh_host_hint(repo_url)
        if host_hint:
            logger.warning("If you trust this host, register its key then re-run the update:")
            logger.raw(f"ssh-keyscan -H {host_hint} >> ~/.ssh/known_hosts\n")

    def __warn_git_auth(self, repo_url: str) -> None:
        """Emit an actionable warning when a clone needs credentials that were not available
        non-interactively (private HTTPS repo with no helper, or a rejected SSH key)."""
        if GitUtils.is_ssh_url(repo_url):
            detail = "no usable SSH key was found (load your SSH agent or configure a deploy key on the host)"
        else:
            detail = ("no non-interactive git credentials were available (configure a git credential helper / "
                      "stored token on the host)")
        logger.warning(f"Authentication is required to clone the [green]{self.getName()}[/green] source but {detail}. "
                       f"Skipping this source.")

    async def clone(self, repo_url: str, optimize_disk_space: bool = True, ref: Optional[str] = None, quiet_success: bool = False) -> bool:
        # quiet_success: log the success as verbose (updateToRef logs its own success message).
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to clone a repository in offline mode ...")
            return False
        if self.isAvailable:
            logger.warning(f"The {self.getName()} repo is already cloned.")
            return False
        # locally import git in case git is not installed of the system
        try:
            from git import Repo, Remote, InvalidGitRepositoryError, FetchInfo, Git
        except ModuleNotFoundError:
            logger.debug("Git module is not installed.")
            return False
        except ImportError:
            logger.error(f"Unable to find git on your machine. The {self.getName()} repository cannot be cloned.")
            logger.warning("Please install git to support this feature.")
            return False
        custom_options: List[str] = []
        if optimize_disk_space:
            custom_options.append('--depth=1')
        # Resolve the requested ref (branch, tag or SHA) into clone options.
        is_sha_ref = ref is not None and GitUtils._looks_like_sha(ref)
        use_revision = False
        if ref is not None and not is_sha_ref:
            # --branch works for both a branch name and a lightweight/annotated tag.
            custom_options += ['--branch', ref]
        elif ref is not None:  # is_sha_ref is True here (branch/tag handled above)
            # `git clone --revision <sha>` is only available since git 2.49 (2025-03).
            try:
                supports_revision = tuple(Git().version_info[:2]) >= (2, 49)
            except Exception as e:  # pragma: no cover - defensive; version_info should always resolve
                logger.debug(f"Unable to read git version, assuming no --revision support: {e}")
                supports_revision = False
            if supports_revision:
                use_revision = True
                custom_options += ['--revision', ref]
            else:
                # Old git: skip the direct clone and go straight to the fetch-by-SHA fallback.
                if not await self.__clone_sha_fallback(repo_url, ref, optimize_disk_space, quiet_success):
                    return False
                await self.__init_repo()
                self.__reown_repo()
                return True
        # Keep the progress handler: it consumes git's stderr, so on failure the error lines
        # must be read back from it (GitCommandError.stderr is empty).
        clone_progress = CallableRemoteProgress(clone_update_progress)
        try:
            async with cast(AsyncContextManager,
                            MetaGitProgress(TextColumn("{task.description}", justify="left"),
                                            BarColumn(bar_width=None),
                                            "•",
                                            "[progress.percentage]{task.percentage:>3.1f}%",
                                            "[bold]{task.completed}/{task.total}[/bold]")) as progress:
                progress.add_task(f"[bold red]Cloning {self.getName()} git repository", start=True)
                # cast: GitPython's stub types progress as a bare callable, but it accepts a
                # RemoteProgress instance at runtime (to_progress_instance returns it as-is).
                self.__gitRepo = Repo.clone_from(repo_url, str(self.__repo_path), multi_options=custom_options, progress=cast(Any, clone_progress))
            if quiet_success:
                logger.verbose(f"The Git repository {self.getName()} was successfully cloned!")
            else:
                logger.success(f"The Git repository {self.getName()} was successfully cloned!")
        except GitCommandError as e:
            # When the progress handler consumed stderr, GitCommandError.stderr is empty —
            # rebuild the message from the lines the handler captured (prefer real errors).
            if not e.stderr.strip():
                captured = clone_progress.error_lines or clone_progress.other_lines
                rebuilt = "\n".join(line for line in captured if line and line.strip())
                error = GitUtils.formatStderr(rebuilt)
            else:
                # GitPython user \n only
                error = GitUtils.formatStderr(e.stderr)
            # Some git builds reject --revision despite the version gate: fall back to fetch-by-SHA.
            # Match option-support errors only, so a bad SHA or auth failure is not escalated to a full clone.
            lowered_clone_error = error.lower()
            if use_revision and ref is not None and ('unknown option' in lowered_clone_error
                                 or 'unknown switch' in lowered_clone_error
                                 or 'unrecognized option' in lowered_clone_error
                                 or 'does not allow' in lowered_clone_error):
                logger.debug(f"`git clone --revision` unavailable ({error}); using fetch-by-SHA fallback.")
                if not await self.__clone_sha_fallback(repo_url, ref, optimize_disk_space, quiet_success):
                    return False
                await self.__init_repo()
                self.__reown_repo()
                return True
            lowered_error = error.lower()
            logger.debug(f"Git error received: {escape(error)}")
            # SSH first-contact / changed-key failures get a targeted, actionable message.
            if GitUtils.is_ssh_url(repo_url) and (
                    'host key verification failed' in lowered_error
                    or 'remote host identification has changed' in lowered_error):
                self.__warn_ssh_host_key(repo_url)
                return False
            # Missing-credential failures (private HTTPS repo with no helper, or rejected SSH key).
            if ('terminal prompts disabled' in lowered_error
                    or 'authentication failed' in lowered_error
                    or 'could not read username' in lowered_error
                    or 'could not read password' in lowered_error
                    or 'permission denied (publickey)' in lowered_error):
                self.__warn_git_auth(repo_url)
                return False
            logger.error(f"Unable to clone the git repository. {error}")
            return False
        except (UnsafeProtocolError, UnsafeOptionError) as e:
            # Raised by GitPython before running git (e.g. 'helper::' URL); not a GitCommandError.
            # Skip the source instead of aborting the whole `exegol update`.
            logger.error(f"Refusing to clone the [green]{self.getName()}[/green] source: "
                         f"unsafe git URL or option ({e}). Skipping this source.")
            return False
        await self.__init_repo()
        self.__reown_repo()
        return True

    async def __clone_sha_fallback(self, repo_url: str, sha: str, optimize_disk_space: bool = True, quiet_success: bool = False) -> bool:
        """Clone a specific commit SHA on git versions without `clone --revision`.

        Strategy: `git init` + `remote add origin` + `fetch --depth 1 origin <sha>`
        + `checkout FETCH_HEAD`. If the server rejects the SHA-in-want request, fall
        back to a full clone (`--no-single-branch`) then `checkout <sha>`.
        """
        from git import Repo, GitCommandError
        # Start from a clean target dir (a failed --revision clone may have left partial content).
        # The wipe always proceeds (otherwise the source stays stale), but warns when the
        # directory is not a git checkout, since its content was not cloned by Exegol.
        if self.__repo_path.exists():
            if not self.__repo_path.is_dir():
                # A file here is not a previous clone and rmtree cannot remove it: skip this source.
                logger.error(f"Cannot clone [green]{self.getName()}[/green] into "
                             f"[magenta]{self.__repo_path}[/magenta]: the path already exists and is "
                             f"not a directory. Move or remove it manually first.")
                return False
            try:
                occupied = any(self.__repo_path.iterdir())
            except OSError as e:
                # Only decides whether to warn; unreadable is treated as occupied.
                logger.debug(f"Unable to inspect {self.__repo_path} before reclaiming it ({e}).")
                occupied = True
            if occupied and not (self.__repo_path / ".git").exists():
                logger.warning(f"Replacing the content of [magenta]{self.__repo_path}[/magenta] to clone "
                               f"[green]{self.getName()}[/green] at its configured commit: this directory is "
                               f"not a git checkout, so everything currently in it is being permanently "
                               f"removed. Keep no irreplaceable work in a managed source directory (use a "
                               f"'dev' mode source for content you intend to edit and keep).")
            try:
                shutil.rmtree(self.__repo_path)
            except OSError as e:
                # e.g. permission denied or a symlink: skip the source instead of aborting the update.
                logger.error(f"Cannot clone [green]{self.getName()}[/green]: unable to reclaim "
                             f"[magenta]{self.__repo_path}[/magenta] ({e}). Move or remove it manually first.")
                return False
        mkdir(self.__repo_path)
        # Progress handler of the full-clone fallback, kept to read back error lines (see clone()).
        fallback_progress: Optional[CallableRemoteProgress] = None
        try:
            async with ExegolStatus(f"Cloning [green]{self.getName()}[/green] at pinned commit", spinner_style="blue"):
                repo = Repo.init(str(self.__repo_path))
                repo.create_remote('origin', repo_url)
                fetch_options: List[str] = []
                if optimize_disk_space:
                    fetch_options.append('--depth=1')
                try:
                    repo.git.fetch('origin', sha, *fetch_options)
                    repo.git.checkout('FETCH_HEAD')
                except GitCommandError as e:
                    logger.debug(f"Fetch-by-SHA failed ({GitUtils.formatStderr(e.stderr)}); falling back to a full clone.")
                    # Final fallback: full clone then checkout the requested SHA.
                    shutil.rmtree(self.__repo_path)
                    mkdir(self.__repo_path)
                    fallback_progress = CallableRemoteProgress(clone_update_progress)
                    # cast: GitPython's stub types progress as a bare callable, but it accepts a
                    # RemoteProgress instance at runtime (to_progress_instance returns it as-is).
                    repo = Repo.clone_from(repo_url, str(self.__repo_path), multi_options=['--no-single-branch'], progress=cast(Any, fallback_progress))
                    repo.git.checkout(sha)
            self.__gitRepo = repo
            if quiet_success:
                logger.verbose(f"The Git repository {self.getName()} was successfully cloned!")
            else:
                logger.success(f"The Git repository {self.getName()} was successfully cloned!")
            return True
        except GitCommandError as e:
            # When the fallback progress handler consumed stderr, GitCommandError.stderr is
            # empty — rebuild the message from the lines the handler captured (prefer real errors).
            if not e.stderr.strip() and fallback_progress is not None:
                captured = fallback_progress.error_lines or fallback_progress.other_lines
                error = GitUtils.formatStderr("\n".join(line for line in captured if line and line.strip()))
            else:
                error = GitUtils.formatStderr(e.stderr)
            logger.error(f"Unable to clone the git repository. {error}")
            return False

    def getCurrentBranch(self) -> Optional[str]:
        """Get current git branch name"""
        if not self.isAvailable:
            return None
        assert self.__gitRepo is not None
        try:
            return str(self.__gitRepo.active_branch)
        except TypeError:
            logger.debug("Git HEAD is detached, can't find the current branch.")
            return None
        except ValueError:
            logger.error(f"Unable to find current git branch in the {self.__git_name} repository. Check the path in the .git file from {self.__repo_path / '.git'}")
            return None

    def listBranch(self) -> List[str]:
        """Return a list of str of all remote git branch available"""
        assert self.isAvailable
        assert not OptionResolver().get(OptionKey.OFFLINE_MODE)
        result: List[str] = []
        if self.__gitRemote is None:
            return result
        for branch in self.__gitRemote.fetch():
            branch_parts = branch.name.split('/')
            if len(branch_parts) < 2:
                logger.warning(f"Branch name is not correct: {branch.name}")
                result.append(branch.name)
            else:
                result.append('/'.join(branch_parts[1:]))
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

    def hasLocalOnlyCommits(self) -> bool:
        """Return True when a commit is reachable from a local branch or HEAD but from no remote ref or tag.

        Used before a destructive prune. Local refs only (works offline). Unlike isUpToDate(),
        a branch ahead of its remote counts. Fails safe: any error returns True. A SHA clone has
        no remote refs or tags, so it is reported at-risk (an extra prompt, never data loss).
        """
        assert self.isAvailable
        if self.__gitRepo is None:
            return True
        try:
            # Local branches/HEAD minus remote refs and tags. `--tags` is needed: a tag-pinned
            # clone has no remote-tracking refs. All args are constants, so no '--' is needed.
            output = cast(str, self.__gitRepo.git.rev_list(
                "--branches", "HEAD", "--not", "--remotes", "--tags", "-1", "--format=%H"))
        except Exception as e:
            logger.debug(f"Could not determine local-only commits for {self.__repo_path}: {e}")
            return True
        return bool(output.strip())

    def isUpToDate(self, branch: Optional[str] = None) -> bool:
        """Check if the local git repository is up-to-date.
        This method compare the last commit local and the ancestor."""
        assert self.isAvailable
        assert not OptionResolver().get(OptionKey.OFFLINE_MODE)
        if branch is None:
            branch = self.getCurrentBranch()
            if branch is None:
                logger.warning("No branch is currently attached to the git repository. The up-to-date status cannot be checked.")
                return False
        assert self.__gitRepo is not None
        assert self.__gitRemote is not None
        # Get last local commit
        current_commit = self.get_current_commit()
        # Get last remote commit
        if not self.__fetch_update(branch):
            return True

        assert self.__fetchBranchInfo is not None

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

        remote_commit = self.get_latest_commit()
        assert remote_commit is not None
        # Check if remote_commit is an ancestor of the last local commit (check if there is local commit ahead)
        return self.__gitRepo.is_ancestor(remote_commit, current_commit)

    def __fetch_update(self, branch: Optional[str] = None) -> bool:
        """Fetch latest update from remote"""
        if self.__gitRemote is None:
            return False
        try:
            fetch_result = self.__gitRemote.fetch()
        except GitCommandError as e:
            logger.warning(f"Unable to fetch information from remote git repository: {e.stderr}")
            return False
        if branch is None:
            branch = self.getCurrentBranch()
        try:
            self.__fetchBranchInfo = fetch_result[f'{self.__gitRemote}/{branch}']
        except IndexError:
            logger.warning("The selected branch is local and cannot be updated.")
            return False
        return True

    def get_current_commit(self) -> Commit:
        """Fetch current commit id on the current branch."""
        assert self.isAvailable
        assert self.__gitRepo is not None
        branch = self.getCurrentBranch()
        if branch is None:
            return self.__gitRepo.head.commit
        # Get last local commit
        return self.__gitRepo.heads[branch].commit

    def get_commit_sha(self) -> str:
        """Return the full hex SHA of the checked-out commit (branch, tag or detached HEAD)."""
        return self.get_current_commit().hexsha

    def get_latest_commit(self) -> Optional[Commit]:
        """Fetch latest remote commit id on the current branch."""
        assert self.isAvailable
        assert not OptionResolver().get(OptionKey.OFFLINE_MODE)
        if self.__fetchBranchInfo is None:
            if not self.__fetch_update():
                logger.debug("The latest commit cannot be retrieved.")
                return None
        assert self.__fetchBranchInfo is not None
        return self.__fetchBranchInfo.commit

    async def update(self) -> bool:
        """Update local git repository within current branch"""
        assert self.isAvailable
        assert not OptionResolver().get(OptionKey.OFFLINE_MODE)
        if not self.safeCheck():
            return False
        # Check if the git branch status is not detached
        if self.getCurrentBranch() is None:
            return False
        if self.isUpToDate():
            logger.info(f"Git branch [green]{self.getCurrentBranch()}[/green] is already up-to-date.")
            return False
        if self.__gitRemote is not None:
            logger.info(f"Using branch [green]{self.getCurrentBranch()}[/green] on {self.getName()} repository")
            async with ExegolStatus(f"Updating git [green]{self.getName()}[/green]", spinner_style="blue"):
                self.__gitRemote.pull(refspec=self.getCurrentBranch())
            logger.success("Git successfully updated")
            self.__reown_repo()
            return True
        return False

    @staticmethod
    def __resolve_remote_sha(ls_remote_output: str) -> Optional[str]:
        """Return the commit SHA a ref resolves to from ``git ls-remote`` output.
        For an annotated tag, prefer the dereferenced (``^{}``) commit — that is the commit
        a checkout of the tag actually lands on."""
        deref: Optional[str] = None
        first: Optional[str] = None
        for line in ls_remote_output.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            sha, name = parts[0], parts[1]
            if name.endswith("^{}"):
                deref = sha
            elif first is None:
                first = sha
        return deref or first

    async def updateToRef(self, repo_url: str, ref: Optional[str] = None, optimize_disk_space: bool = True) -> bool:
        """Ensure an already-cloned (shallow) repository is at ``ref`` (branch, tag or SHA).

        Re-clones at ``ref`` when its remote commit differs from HEAD (handles a changed ref or
        new commits); re-cloning keeps proper branch/tag pointers. With ``ref=None``, falls back
        to update(). Returns True when the repository was re-synced."""
        if ref is None:
            return await self.update()
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to update a repository in offline mode ...")
            return False
        if not self.isAvailable or self.__gitRepo is None:
            return False
        try:
            current = self.__gitRepo.head.commit.hexsha
        except Exception:  # pragma: no cover - defensive
            current = ""
        if GitUtils._looks_like_sha(ref):
            # A pinned SHA is immutable: already satisfied when HEAD is that commit.
            if current and current.startswith(ref):
                logger.info(f"The source [green]{self.getName()}[/green] is already at pinned commit [green]{ref}[/green].")
                return False
        else:
            # Resolve the branch/tag to its current remote commit and compare with HEAD.
            try:
                # '--' so a URL or ref starting with '-' is never parsed as an option.
                ls_remote = self.__gitRepo.git.ls_remote("--", repo_url, ref)
            except GitCommandError as e:
                logger.error(f"Unable to resolve ref [green]{ref}[/green] on [green]{self.getName()}[/green]: {GitUtils.formatStderr(e.stderr)}")
                return False
            target = GitUtils.__resolve_remote_sha(cast(str, ls_remote))
            if target is None:
                logger.error(f"Ref [green]{ref}[/green] was not found on the [green]{self.getName()}[/green] remote.")
                return False
            if target == current:
                logger.verbose(f"The source [green]{self.getName()}[/green] is already up-to-date on [green]{ref}[/green].")
                return False
        # Re-clone into a sibling directory and swap it in only on success, so a failed
        # clone leaves the existing checkout intact.
        tmp_path = self.__repo_path.with_name(self.__repo_path.name + ".new")
        shutil.rmtree(tmp_path, ignore_errors=True)
        staged = GitUtils(tmp_path, self.getName(), self.getSubject())
        if not await staged.clone(repo_url, optimize_disk_space=optimize_disk_space, ref=ref, quiet_success=True):
            # Clone failed: the previous checkout is untouched and still usable.
            shutil.rmtree(tmp_path, ignore_errors=True)
            return False
        backup_path = self.__repo_path.with_name(self.__repo_path.name + ".old")
        shutil.rmtree(backup_path, ignore_errors=True)
        try:
            if self.__repo_path.exists():
                os.replace(self.__repo_path, backup_path)
            os.replace(tmp_path, self.__repo_path)
        except OSError as e:
            logger.error(f"Unable to swap in the updated [green]{self.getName()}[/green] source: {e}")
            # Best-effort rollback to the previous checkout.
            if backup_path.exists() and not self.__repo_path.exists():
                try:
                    os.replace(backup_path, self.__repo_path)
                except OSError as rollback_error:  # pragma: no cover - defensive
                    logger.debug(f"Rollback of the {self.getName()} source failed: {rollback_error}")
            shutil.rmtree(tmp_path, ignore_errors=True)
            return False
        shutil.rmtree(backup_path, ignore_errors=True)
        # Re-open the freshly swapped-in checkout on this instance.
        self.isAvailable = False
        self.__gitRepo = None
        await self.initialize(skip_submodule_update=True, silent=True)
        logger.success(f"The source [green]{self.getName()}[/green] was updated to [green]{ref}[/green]")
        return True

    async def __initSubmodules(self) -> None:
        """Init (and update git object not source code) git sub repositories (only depth=1)"""
        if OptionResolver().get(OptionKey.OFFLINE_MODE):
            logger.error("It's not possible to update any submodule in offline mode ...")
            return
        logger.verbose(f"Git {self.getName()} init submodules")
        # These modules are init / updated manually
        blacklist_heavy_modules = ["exegol-resources", "exegol-images"]
        if self.__gitRepo is None:
            return
        async with ExegolStatus(f"Initialization of git submodules", spinner_style="blue") as s:
            try:
                # Depth 1 only: `iter_submodules()` would also yield the nested submodules of
                # blacklisted modules, bypassing the blacklist.
                submodules = self.__gitRepo.submodules
            except ValueError:
                logger.error(f"Unable to find any git submodule from '{self.getName()}' repository. Check the path in the file {self.__repo_path / '.git'}")
                return
            for current_sub in submodules:
                logger.debug(f"Loading repo submodules: {current_sub}")
                # Submodule update are skipped if blacklisted or if the depth limit is set
                if current_sub.name in blacklist_heavy_modules:
                    continue
                s.update(status=f"Downloading git submodules [green]{current_sub.name}[/green]")
                from git.exc import GitCommandError
                try:
                    # TODO add TUI with progress
                    current_sub.update(recursive=True)
                except GitCommandError as e:
                    error = GitUtils.formatStderr(e.stderr)
                    logger.debug(f"Unable tu update git submodule {current_sub.name}: {e}")
                    if "unable to access" in error:
                        logger.error("You don't have internet to update git submodule. Skipping operation.")
                    else:
                        logger.error("Unable to update git submodule. Skipping operation.")
                        logger.error(error)
                except ValueError:
                    logger.error(f"Unable to update git submodule '{current_sub.name}'. Check the path in the file '{Path(current_sub.path) / '.git'}'")
                except RepositoryDirtyError as e:
                    logger.debug(e)
                    logger.error(f"Sub-repository {current_sub.name} have uncommitted local changes. Unable to automatically update this repository.")
                except ODBError as e:
                    # gitdb errors (BadName, BadObject...) match none of the handlers above and would
                    # abort the whole update. Often transient: skip this submodule.
                    logger.debug(f"Unable to update git submodule {current_sub.name}: {e!r}")
                    logger.error(f"Unable to resolve a git object for submodule '{current_sub.name}'. Skipping operation.")
        # Submodule updates write into .git as root under sudo: reown, even if a submodule
        # failed (objects may already be written).
        self.__reown_repo()

    def submoduleSourceUpdate(self, name: str) -> bool:
        """Update source code from the 'name' git submodule"""
        assert not OptionResolver().get(OptionKey.OFFLINE_MODE)
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
                with MetaGitProgress(TextColumn("{task.description}", justify="left"),
                                     BarColumn(bar_width=None),
                                     "•",
                                     "[progress.percentage]{task.percentage:>3.1f}%",
                                     "[bold]{task.completed}/{task.total}[/bold]") as progress:
                    progress.add_task(f"[bold red]Downloading submodule [green]{name}[/green]", start=True)
                    submodule.update(to_latest_revision=True, progress=SubmoduleUpdateProgress())
                    progress.remove_task(progress.tasks[0].id)
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
    def formatStderr(cls, stderr: str) -> str:
        return stderr.replace('\n', '').replace('stderr:', '').strip().strip("'")

    def __repr__(self) -> str:
        """Developer debug object representation"""
        return f"GitUtils '{self.__git_name}': {'Active' if self.isAvailable else 'Disable'}"
