import re
from pathlib import Path
from typing import Optional, Dict, cast, Tuple, Sequence

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.DataCache import DataCache
from exegol.config.UserConfig import UserConfig
from exegol.console.ExegolPrompt import ExegolRich
from exegol.console.ExegolStatus import ExegolStatus
from exegol.console.TUI import ExegolTUI
from exegol.console.cli.ParametersManager import ParametersManager
from exegol.exceptions.ExegolExceptions import ObjectNotFound, CancelOperation
from exegol.model.ExegolImage import ExegolImage
from exegol.model.ExegolModules import ExegolModules
from exegol.utils.DockerUtils import DockerUtils
from exegol.utils.ExeLog import logger, ExeLog
from exegol.utils.GitUtils import GitUtils
from exegol.utils.WebRegistryUtils import WebRegistryUtils


class UpdateManager:
    """Procedure class for updating the exegol tool and docker images"""

    @classmethod
    async def updateImage(cls, tag: Optional[str] = None, install_mode: bool = False) -> Optional[ExegolImage]:
        """User procedure to build/pull docker image"""
        # List Images
        image_args = ParametersManager().imagetag
        # Select image
        if image_args is not None and tag is None:
            tag = image_args
        if tag is None:
            all_images = await DockerUtils().listImages()
            # Filter for updatable images
            if install_mode:
                available_images = [i for i in all_images if not i.isLocked()]
            else:
                available_images = [i for i in all_images if i.isInstall() and not i.isUpToDate() and not i.isLocked()]
                if len(available_images) == 0:
                    logger.success("All images already installed are up to date!")
                    return None
            try:
                # Interactive selection
                selected_image = await ExegolTUI.selectFromTable(available_images,
                                                                 object_type=ExegolImage,
                                                                 allow_None=False)
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
                selected_image = await DockerUtils().getOfficialImageFromList(tag)
            except ObjectNotFound:
                logger.error(f"Image '{tag}' was not found. If you wanted to build a local image, you can use the 'build' action instead.")
                return None

        if selected_image is not None and type(selected_image) is ExegolImage:
            # Update existing ExegolImage
            if await DockerUtils().downloadImage(selected_image, install_mode):
                sync_result = None
                # Name comparison allow detecting images without version tag
                if not selected_image.isVersionSpecific() and selected_image.hasVersionTag():
                    async with ExegolStatus(f"Synchronizing version tag information. Please wait.", spinner_style="blue"):
                        # Download associated version tag.
                        sync_result = await DockerUtils().downloadVersionTag(selected_image)
                    # Detect if an error have been triggered during the download
                    if type(sync_result) is str:
                        logger.error(f"Error while downloading version tag, {sync_result}")
                        sync_result = None
                # if version tag have been successfully download, returning ExegolImage from docker response
                if sync_result is not None and type(sync_result) is ExegolImage:
                    return sync_result
                # Version-specific images must skip cache to avoid loading latest image
                return await DockerUtils().getInstalledImage(selected_image.getName(), selected_image.getRepository(), skip_cache=selected_image.isVersionSpecific())
        else:
            # Unknown use case
            logger.critical(f"Unknown selected image '{selected_image}'. Exiting.")
        return cast(Optional[ExegolImage], selected_image)

    @classmethod
    async def updateWrapper(cls) -> bool:
        """Update wrapper source code from git"""
        result = await cls.__updateGit(await ExegolModules().getWrapperGit())
        if result:
            await cls.__untagUpdateAvailable()
            logger.empty_line()
            logger.warning("After this wrapper update, remember to update Exegol [bold]requirements[bold]! ([magenta]python3 -m pip install --upgrade -r requirements.txt[/magenta])")
            logger.empty_line()
        return result

    @classmethod
    async def updateImageSource(cls) -> bool:
        """Update image source code from git submodule"""
        return await cls.__updateGit(await ExegolModules().getSourceGit())

    @classmethod
    async def updateResources(cls) -> bool:
        """Update Exegol-resources from git (submodule)"""
        if not UserConfig().enable_exegol_resources:
            logger.info("Skipping disabled Exegol resources.")
            return False
        try:
            if not await ExegolModules().isExegolResourcesReady() and not await ExegolRich.Confirm('Do you want to update exegol resources.', default=True):
                return False
            return await cls.__updateGit(await ExegolModules().getResourcesGit())
        except CancelOperation:
            # Error during installation, skipping operation
            return False

    @staticmethod
    async def __updateGit(gitUtils: GitUtils) -> bool:
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
        if logger.isEnabledFor(ExeLog.VERBOSE):
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
                selected_branch = cast(str, await ExegolTUI.selectFromList(gitUtils.listBranch(),
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
        return await gitUtils.update()

    @classmethod
    async def checkForWrapperUpdate(cls) -> bool:
        """Check if there is an exegol wrapper update available.
        Return true if an update is available."""
        logger.debug(f"Last wrapper update check: {DataCache().get_wrapper_data().metadata.get_last_check_text()}")
        # Skipping update check
        if DataCache().get_wrapper_data().metadata.is_outdated() and not ParametersManager().offline_mode:
            logger.debug("Running update check")
            return await cls.__checkUpdate()
        return False

    @classmethod
    async def __checkUpdate(cls) -> bool:
        """Depending on the current version (dev or latest) the method used to find the latest version is not the same.
        For the stable version, the latest version is fetch from GitHub release.
        In dev mode, git is used to find if there is some update available."""
        isUpToDate = True
        remote_version = ""
        current_version = ConstantConfig.version
        async with ExegolStatus("Checking for wrapper update. Please wait.", spinner_style="blue"):
            if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE):
                # Dev version have a letter in the version code and must check updates via git
                logger.debug("Checking update using: dev mode")
                module = await ExegolModules().getWrapperGit(fast_load=True)
                if module.isAvailable:
                    isUpToDate = module.isUpToDate()
                    last_commit = module.get_latest_commit()
                    remote_version = "?" if last_commit is None else str(last_commit)[:8]
                    current_version = str(module.get_current_commit())[:8]
                else:
                    # If Exegol have not been installed from git clone. Auto-check update in this case is only available from mates release
                    logger.verbose("Auto-update checking is not available in the current context")
            else:
                # If there is no letter, it's a stable release, and we can compare faster with the latest git tag
                logger.debug("Checking update using: stable mode")
                try:
                    remote_version = WebRegistryUtils.getLatestWrapperRelease()
                    # On some edge case, remote_version might be None if there is problem
                    if remote_version is None:
                        raise CancelOperation
                    isUpToDate = cls.__compareVersion(remote_version)
                except CancelOperation:
                    # No internet, postpone update check
                    return False

        if not isUpToDate:
            await cls.__tagUpdateAvailable(remote_version, current_version)
        cls.__updateLastCheckTimestamp()
        return not isUpToDate

    @classmethod
    def __updateLastCheckTimestamp(cls) -> None:
        """Update the last_check metadata timestamp with the current date to avoid multiple update checks."""
        DataCache().get_wrapper_data().metadata.update_last_check()
        DataCache().save_updates()

    @classmethod
    def __compareVersion(cls, version: str) -> bool:
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
    async def __get_current_version(cls) -> str:
        """Get the current version of the exegol wrapper. Handle dev version and release stable version depending on the current version."""
        current_version = ConstantConfig.version
        if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE) and ConstantConfig.git_source_installation:
            module = await ExegolModules().getWrapperGit(fast_load=True)
            if module.isAvailable:
                current_version = str(module.get_current_commit())[:8]
        return current_version

    @staticmethod
    async def display_current_version() -> str:
        """Get the current version of the exegol wrapper. Handle dev version and release stable version depending on the current version."""
        version_details = ""
        if ConstantConfig.git_source_installation:
            module = await ExegolModules().getWrapperGit(fast_load=True)
            if module.isAvailable:
                current_branch = module.getCurrentBranch()
                commit_version = ""
                if re.search(r'[a-z]', ConstantConfig.version, re.IGNORECASE):
                    commit_version = "-" + str(module.get_current_commit())[:8]
                if current_branch is None:
                    current_branch = "HEAD"
                if current_branch != "master" or commit_version != "":
                    version_details = f" [bright_black]\\[{current_branch}{commit_version}][/bright_black]"
        return f"[blue]v{ConstantConfig.version}[/blue]{version_details}"

    @classmethod
    async def __tagUpdateAvailable(cls, latest_version: str, current_version: Optional[str] = None) -> None:
        """Update the 'update available' cache data."""
        DataCache().get_wrapper_data().last_version = latest_version
        DataCache().get_wrapper_data().current_version = (await cls.__get_current_version()) if current_version is None else current_version

    @classmethod
    async def isUpdateAvailable(cls) -> bool:
        """Check if the cache file is present to announce an available update of the exegol wrapper."""
        current_version = await cls.__get_current_version()
        wrapper_data = DataCache().get_wrapper_data()
        # Check if a latest version exist and if the current version is the same, no external update had occurred
        if wrapper_data.last_version != current_version and wrapper_data.current_version == current_version:
            return True
        else:
            # If the version changed, exegol have been updated externally (via pip for example)
            if wrapper_data.current_version != current_version:
                await cls.__untagUpdateAvailable(current_version)
            return False

    @classmethod
    def display_latest_version(cls) -> str:
        last_version = DataCache().get_wrapper_data().last_version
        if len(last_version) == 8 and '.' not in last_version:
            return f"[bright_black]\\[{last_version}][/bright_black]"
        return f"[blue]v{last_version}[/blue]"

    @classmethod
    async def __untagUpdateAvailable(cls, current_version: Optional[str] = None) -> None:
        """Reset the latest version to the current version"""
        if current_version is None:
            current_version = await cls.__get_current_version()
        DataCache().get_wrapper_data().last_version = current_version
        DataCache().get_wrapper_data().current_version = current_version
        DataCache().save_updates()

    @classmethod
    async def __buildSource(cls, build_name: Optional[str] = None) -> str:
        """build user process :
        Ask user is he want to update the git source (to get new& updated build profiles),
        User choice a build name (if not supplied)
        User select the path to the dockerfiles (only from CLI parameter)
        User select a build profile
        Start docker image building
        Return the name of the built image"""
        # Selecting the default path
        # Don't force update source if using a custom build_path
        if ParametersManager().build_path is None:
            build_path = Path(UserConfig().exegol_images_path)
            # Ask to update git
            try:
                # Install sources and check for update available
                source_git = await ExegolModules().getSourceGit()
                if source_git.isAvailable and not source_git.isUpToDate() and \
                        await ExegolRich.Confirm("Do you want to update image sources (in order to update local build profiles)?", default=True):
                    await cls.updateImageSource()
            except CancelOperation:
                logger.critical("An error prevented exegol from downloading the sources for building a local image.")
            except AssertionError:
                # Catch None git object assertions (from isUpToDate method)
                logger.warning("Git update is [orange3]not available[/orange3]. Skipping.")
        else:
            build_path = Path(ParametersManager().build_path).expanduser().absolute()
            # Check if we have a directory or a file to select the project directory
            if not build_path.is_dir():
                build_path = build_path.parent
            # Check if there is Dockerfile profiles
            if not ((build_path / "Dockerfile").is_file() or len(list(build_path.glob("*.dockerfile"))) > 0):
                logger.critical(f"The directory {build_path} doesn't contain any [green]Dockerfile[/green] or [green]*.dockerfile[/green] build profile.")

        # Choose tag name
        blacklisted_build_name = ["stable", "full", "nightly", "ad", "web", "light", "osint", "free"]
        while build_name is None or build_name in blacklisted_build_name or True in [build_name.startswith(x + '-') for x in blacklisted_build_name]:
            if build_name is not None:
                logger.error("This name is reserved and cannot be used for local build. Please choose another one.")
            build_name = await ExegolRich.Ask("[bold blue][?][/bold blue] Choose a name for the new local image",
                                              default="local")

        # Choose dockerfiles path
        logger.debug(f"Using {build_path} as path for dockerfiles")

        # Choose dockerfile
        profiles = cls.listBuildProfiles(profiles_path=build_path)
        if len(profiles) == 0:
            logger.critical(f"No build profile found in {build_path}. Check your exegol installation, it seems to be broken...")
        build_profile: Optional[str] = ParametersManager().build_profile
        build_dockerfile: Optional[str] = None
        if build_profile is not None:
            build_dockerfile = profiles.get(build_profile)
            if build_dockerfile is None:
                logger.error(f"Build profile {build_profile} not found.")
        if build_dockerfile is None:
            build_profile, build_dockerfile = cast(Tuple[str, str], await ExegolTUI.selectFromList(profiles,
                                                                                                   subject="a build profile",
                                                                                                   title="[not italic]:dog: [/not italic][gold3]Build profiles[/gold3]"))
        logger.debug(f"Using {build_profile} build profile ({build_dockerfile})")
        # Docker Build
        await DockerUtils().buildImage(tag=build_name, build_profile=build_profile, build_dockerfile=build_dockerfile, dockerfile_path=build_path.as_posix())
        return build_name

    @classmethod
    async def buildAndLoad(cls, load_after_build: bool) -> Optional[ExegolImage]:
        """Build an image and load it"""
        build_name = await cls.__buildSource(ParametersManager().imagetag)
        if load_after_build:
            return await DockerUtils().getInstalledImage(build_name, ConstantConfig.COMMUNITY_IMAGE_NAME)
        return None

    @classmethod
    def listBuildProfiles(cls, profiles_path: Path) -> Dict:
        """List every build profiles available locally
        Return a dict of options {"key = profile name": "value = dockerfile full name"}"""
        # Default stable profile
        profiles = {}
        if (profiles_path / "Dockerfile").is_file():
            profiles["full"] = "Dockerfile"
        # List file *.dockerfile is the build context directory
        logger.debug(f"Loading build profile from {profiles_path}")
        docker_files = list(profiles_path.glob("*.dockerfile"))
        for file in docker_files:
            # Convert every file to the dict format
            filename = file.name
            profile_name = filename.replace(".dockerfile", "")
            profiles[profile_name] = filename
        logger.debug(f"List docker build profiles : {profiles}")
        return profiles

    @classmethod
    async def listGitStatus(cls) -> Sequence[Dict[str, str]]:
        """Get status of every git modules"""
        result = []
        gits = [await ExegolModules().getWrapperGit(fast_load=True),
                await ExegolModules().getSourceGit(fast_load=True, skip_install=True),
                await ExegolModules().getResourcesGit(fast_load=True, skip_install=True)]

        async with ExegolStatus(f"Loading module information", spinner_style="blue") as s:
            for git in gits:
                s.update(status=f"Loading module [green]{git.getName()}[/green] information")
                status = "[bright_black]Unknown[/bright_black]" if ParametersManager().offline_mode else git.getTextStatus()
                branch = git.getCurrentBranch()
                if branch is None:
                    if "not supported" in status or "Not installed" in status:
                        branch = "[bright_black]N/A[/bright_black]"
                    else:
                        branch = "[bright_black][g]? :person_shrugging:[/g][/bright_black]"
                result.append({"name": git.getName().capitalize(),
                               "status": status,
                               "current branch": branch})
        return result
