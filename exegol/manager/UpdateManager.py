import os
import re
from datetime import datetime, timedelta, date
from typing import Optional, Dict, cast, Tuple, Sequence

from rich.prompt import Prompt

from exegol.console.ExegolPrompt import Confirm
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.utils.ConstantConfig import ConstantConfig
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.ExeLog import logger, console, ExeLog
from exegol.utils.GitUtils import GitUtils
from exegol.utils.WebUtils import WebUtils


class UpdateManager:
    """Procedure class for updating the exegol tool and docker images"""
    __UPDATE_TAG_FILE = ".update.meta"
    __LAST_CHECK_FILE = ".lastcheck.meta"
    __TIME_FORMAT = "%d/%m/%Y"

    @classmethod
    def updateImage(cls, tag: Optional[str] = None, install_mode: bool = False) -> Optional[ExegolImage]:
        """User procedure to build/pull docker image"""
        # List Images
        image_args = ParametersManager().imagetag
        # Select image
        if image_args is not None and tag is None:
            tag = image_args
        if tag is None:
            # Filter for updatable images
            if install_mode:
                available_images = [i for i in DockerUtils.listImages() if not i.isLocked()]
            else:
                available_images = [i for i in DockerUtils.listImages() if i.isInstall() and not i.isUpToDate() and not i.isLocked()]
                if len(available_images) == 0:
                    logger.success("All images already installed are up to date!")
                    return None
            try:
                # Interactive selection
                selected_image = ExegolTUI.selectFromTable(available_images,
                                                           object_type=ExegolImage,
                                                           allow_None=install_mode)
            except IndexError:
                # No images are available
                if install_mode:
                    # If no image are available in install mode,
                    # either the user does not have internet,
                    # or the image repository has been changed and no docker image is available
                    logger.critical("Exegol can't be installed offline")
                return None
        else:
            try:
                # Find image by name
                selected_image = DockerUtils.getImage(tag)
            except ObjectNotFound:
                # If the image do not exist, ask to build it
                if install_mode:
                    return cls.__askToBuild(tag)
                else:
                    logger.error(f"Image '{tag}' was not found. If you wanted to build a local image, you can use the 'install' action instead.")
                    return None

        if selected_image is not None and type(selected_image) is ExegolImage:
            # Update existing ExegolImage
            if DockerUtils.downloadImage(selected_image, install_mode):
                sync_result = None
                # Name comparison allow detecting images without version tag
                if not selected_image.isVersionSpecific() and selected_image.getName() != selected_image.getLatestVersionName():
                    with console.status(f"Synchronizing version tag information. Please wait.", spinner_style="blue"):
                        # Download associated version tag.
                        sync_result = DockerUtils.downloadVersionTag(selected_image)
                    # Detect if an error have been triggered during the download
                    if type(sync_result) is str:
                        logger.error(f"Error while downloading version tag, {sync_result}")
                        sync_result = None
                # if version tag have been successfully download, returning ExegolImage from docker response
                if sync_result is not None and type(sync_result) is ExegolImage:
                    return sync_result
                return DockerUtils.getInstalledImage(selected_image.getName())
        elif type(selected_image) is str:
            # Build a new image using TUI selected name, confirmation has already been requested by TUI
            return cls.buildAndLoad(selected_image)
        else:
            # Unknown use case
            logger.critical(f"Unknown selected image type: {type(selected_image)}. Exiting.")
        return cast(Optional[ExegolImage], selected_image)

    @classmethod
    def __askToBuild(cls, tag: str) -> Optional[ExegolImage]:
        """Build confirmation process and image building"""
        # Need confirmation from the user before starting building.
        if ParametersManager().build_profile is not None or \
                Confirm("Do you want to build locally a custom image?", default=False):
            return cls.buildAndLoad(tag)
        return None

    @classmethod
    def updateWrapper(cls) -> bool:
        """Update wrapper source code from git"""
        result = cls.__updateGit(ExegolModules().getWrapperGit())
        if result:
            cls.__untagUpdateAvailable()
        return result

    @classmethod
    def updateImageSource(cls) -> bool:
        """Update image source code from git submodule"""
        return cls.__updateGit(ExegolModules().getSourceGit())

    @classmethod
    def updateResources(cls) -> bool:
        """Update Exegol-resources from git (submodule)"""
        try:
            if not ExegolModules().isExegolResourcesReady() and not Confirm('Do you want to update exegol resources.', default=True):
                return False
            return cls.__updateGit(ExegolModules().getResourcesGit())
        except CancelOperation:
            # Error during installation, skipping operation
            return False

    @staticmethod
    def __updateGit(gitUtils: GitUtils) -> bool:
        """User procedure to update local git repository"""
        if ParametersManager().offline_mode:
            logger.error("It's not possible to update a repository in offline mode ...")
            return False
        if not gitUtils.isAvailable:
            logger.empty_line()
            return False
        logger.info(f"Updating Exegol [green]{gitUtils.getName()}[/green] {gitUtils.getSubject()}")
        # Check if pending change -> cancel
        if not gitUtils.safeCheck():
            logger.error("Aborting git update.")
            logger.empty_line()
            return False
        current_branch = gitUtils.getCurrentBranch()
        if current_branch is None:
            logger.warning("HEAD is detached. Please checkout to an existing branch.")
            current_branch = "unknown"
        if logger.isEnabledFor(ExeLog.VERBOSE) or current_branch not in ["master", "main"]:
            available_branches = gitUtils.listBranch()
            # Ask to checkout only if there is more than one branch available
            if len(available_branches) > 1:
                logger.info(f"Current git branch : {current_branch}")
                # List & Select git branch
                if current_branch == 'unknown' or current_branch not in available_branches:
                    if "main" in available_branches:
                        default_choice = "main"
                    elif "master" in available_branches:
                        default_choice = "master"
                    else:
                        default_choice = None
                else:
                    default_choice = current_branch
                selected_branch = cast(str, ExegolTUI.selectFromList(gitUtils.listBranch(),
                                                                     subject="a git branch",
                                                                     title="[not italic]:palm_tree: [/not italic][gold3]Branch[gold3]",
                                                                     default=default_choice))
            elif len(available_branches) == 0:
                logger.warning("No branch were detected!")
                selected_branch = None
            else:
                # Automatically select the only branch in case of HEAD detachment
                selected_branch = available_branches[0]
            # Checkout new branch
            if selected_branch is not None and selected_branch != current_branch:
                gitUtils.checkout(selected_branch)
        # git pull
        gitUtils.update()
        logger.empty_line()
        return True

    @classmethod
    def checkForWrapperUpdate(cls) -> bool:
        """Check if there is an exegol wrapper update available.
        Return true if an update is available."""
        # Skipping update check
        if cls.__triggerUpdateCheck() and not ParametersManager().offline_mode:
            logger.debug("Running update check")
            return cls.__checkUpdate()
        return False

    @classmethod
    def __triggerUpdateCheck(cls):
        """Check if an update check must be triggered.
        Return true to check for new update"""
        if (ConstantConfig.exegol_config_path / cls.__LAST_CHECK_FILE).is_file():
            with open(ConstantConfig.exegol_config_path / cls.__LAST_CHECK_FILE, 'r') as metafile:
                lastcheck = datetime.strptime(metafile.read().strip(), cls.__TIME_FORMAT)
        else:
            return True
        logger.debug(f"Last update check: {lastcheck.strftime(cls.__TIME_FORMAT)}")
        now = datetime.now()
        if lastcheck > now:
            logger.debug("Incoherent last check date detected. Updating metafile.")
            return True
        # Check for a new update after at least 15 days
        time_delta = timedelta(days=15)
        return (lastcheck + time_delta) < now

    @classmethod
    def __checkUpdate(cls) -> bool:
        """Depending on the current version (dev or latest) the method used to find the latest version is not the same.
        For the stable version, the latest version is fetch from GitHub release.
        In dev mode, git is used to find if there is some update available."""
        isUpToDate = True
        with console.status("Checking for wrapper update. Please wait.", spinner_style="blue"):
            if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE):
                # Dev version have a letter in the version code and must check updates via git
                logger.debug("Checking update using: dev mode")
                module = ExegolModules().getWrapperGit(fast_load=True)
                if module.isAvailable:
                    isUpToDate = module.isUpToDate()
                else:
                    # If Exegol have not been installed from git clone. Auto-check update in this case is only available from mates release
                    logger.verbose("Auto-update checking is not available in the current context")
            else:
                # If there is no letter, it's a stable release, and we can compare faster with the latest git tag
                logger.debug("Checking update using: stable mode")
                try:
                    remote_version = WebUtils.getLatestWrapperRelease()
                    # On some edge case, remote_version might be None if there is problem
                    if remote_version is None:
                        raise CancelOperation
                    isUpToDate = cls.__compareVersion(remote_version)
                except CancelOperation:
                    # No internet, postpone update check
                    return False

        if not isUpToDate:
            cls.__tagUpdateAvailable()
        cls.__updateLastCheckFile()
        return not isUpToDate

    @classmethod
    def __updateLastCheckFile(cls):
        """Update the .lastcheck.meta file with the current date to avoid multiple update checks."""
        with open(ConstantConfig.exegol_config_path / cls.__LAST_CHECK_FILE, 'w') as metafile:
            metafile.write(date.today().strftime(cls.__TIME_FORMAT))

    @classmethod
    def __compareVersion(cls, version) -> bool:
        """Compare a remote version with the current one to check if a new release is available."""
        isUpToDate = True
        try:
            for i in range(len(version.split('.'))):
                remote = int(version.split('.')[i])
                local = int(ConstantConfig.version.split('.')[i])
                if remote > local:
                    isUpToDate = False
                    break
        except ValueError:
            logger.warning(f'Unable to parse Exegol version : {version} / {ConstantConfig.version}')
        return isUpToDate

    @classmethod
    def __tagUpdateAvailable(cls):
        """Create the 'update available' cache file."""
        if not ConstantConfig.exegol_config_path.is_dir():
            logger.verbose(f"Creating exegol home folder: {ConstantConfig.exegol_config_path}")
            os.mkdir(ConstantConfig.exegol_config_path)
        tag_file = ConstantConfig.exegol_config_path / cls.__UPDATE_TAG_FILE
        if not tag_file.is_file():
            with open(tag_file, 'w') as lockfile:
                lockfile.write(ConstantConfig.version)

    @classmethod
    def isUpdateTag(cls) -> bool:
        """Check if the cache file is present to announce an available update of the exegol wrapper."""
        if (ConstantConfig.exegol_config_path / cls.__UPDATE_TAG_FILE).is_file():
            # Fetch the previously locked version
            with open(ConstantConfig.exegol_config_path / cls.__UPDATE_TAG_FILE, 'r') as lockfile:
                locked_version = lockfile.read()
            # If the current version is the same, no external update had occurred
            if locked_version == ConstantConfig.version:
                return True
            else:
                # If the version changed, exegol have been updated externally (via pip for example)
                cls.__untagUpdateAvailable()
                return False
        else:
            return False

    @classmethod
    def __untagUpdateAvailable(cls):
        """Remove the 'update available' cache file."""
        tag_file = ConstantConfig.exegol_config_path / cls.__UPDATE_TAG_FILE
        if tag_file.is_file():
            os.remove(tag_file)

    @classmethod
    def __buildSource(cls, build_name: Optional[str] = None) -> str:
        """build user process :
        Ask user is he want to update the git source (to get new& updated build profiles),
        User choice a build name (if not supplied)
        User select a build profile
        Start docker image building
        Return the name of the built image"""
        # Ask to update git
        try:
            if ExegolModules().getSourceGit().isAvailable and not ExegolModules().getSourceGit().isUpToDate() and \
                    Confirm("Do you want to update image sources (in order to update local build profiles)?", default=True):
                cls.updateImageSource()
        except AssertionError:
            # Catch None git object assertions
            logger.warning("Git update is [orange3]not available[/orange3]. Skipping.")
        # Choose tag name
        blacklisted_build_name = ["stable", "full"]
        while build_name is None or build_name in blacklisted_build_name:
            if build_name is not None:
                logger.error("This name is reserved and cannot be used for local build. Please choose another one.")
            build_name = Prompt.ask("[bold blue][?][/bold blue] Choice a name for your build",
                                    default="local")
        # Choose dockerfile
        profiles = cls.listBuildProfiles()
        build_profile: Optional[str] = ParametersManager().build_profile
        build_dockerfile: Optional[str] = None
        if build_profile is not None:
            build_dockerfile = profiles.get(build_profile)
            if build_dockerfile is None:
                logger.error(f"Build profile {build_profile} not found.")
        if build_dockerfile is None:
            build_profile, build_dockerfile = cast(Tuple[str, str], ExegolTUI.selectFromList(profiles,
                                                                                             subject="a build profile",
                                                                                             title="[not italic]:dog: [/not italic][gold3]Profile[/gold3]"))
        logger.debug(f"Using {build_profile} build profile ({build_dockerfile})")
        # Docker Build
        DockerUtils.buildImage(build_name, build_profile, build_dockerfile)
        return build_name

    @classmethod
    def buildAndLoad(cls, tag: str):
        """Build an image and load it"""
        build_name = cls.__buildSource(tag)
        return DockerUtils.getInstalledImage(build_name)

    @classmethod
    def listBuildProfiles(cls) -> Dict:
        """List every build profiles available locally
        Return a dict of options {"key = profile name": "value = dockerfile full name"}"""
        # Default stable profile
        profiles = {"full": "Dockerfile"}
        # List file *.dockerfile is the build context directory
        logger.debug(f"Loading build profile from {ConstantConfig.build_context_path}")
        docker_files = list(ConstantConfig.build_context_path_obj.glob("*.dockerfile"))
        for file in docker_files:
            # Convert every file to the dict format
            filename = file.name
            profile_name = filename.replace(".dockerfile", "")
            profiles[profile_name] = filename
        logger.debug(f"List docker build profiles : {profiles}")
        return profiles

    @classmethod
    def listGitStatus(cls) -> Sequence[Dict[str, str]]:
        """Get status of every git modules"""
        result = []
        gits = [ExegolModules().getWrapperGit(fast_load=True),
                ExegolModules().getSourceGit(fast_load=True),
                ExegolModules().getResourcesGit(fast_load=True, skip_install=True)]

        with console.status(f"Loading module information", spinner_style="blue") as s:
            for git in gits:
                s.update(status=f"Loading module [green]{git.getName()}[/green] information")
                status = "[bright_black]Unknown[/bright_black]" if ParametersManager().offline_mode else git.getTextStatus()
                branch = git.getCurrentBranch()
                if branch is None:
                    if "not supported" in status:
                        branch = "[bright_black]N/A[/bright_black]"
                    else:
                        branch = "[bright_black][g]? :person_shrugging:[/g][/bright_black]"
                result.append({"name": git.getName().capitalize(),
                               "status": status,
                               "current branch": branch})
        return result
