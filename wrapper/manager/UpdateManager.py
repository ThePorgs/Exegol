from typing import Optional, Dict

from rich.prompt import Confirm, Prompt

from wrapper.console.TUI import ExegolTUI
from wrapper.model.ExegolImage import ExegolImage
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger
from wrapper.utils.GitUtils import GitUtils


class UpdateManager:
    __git = None

    @classmethod
    def __getGit(cls) -> GitUtils:
        """GetUtils local singleton getter"""
        if cls.__git is None:
            cls.__git = GitUtils()
        return cls.__git

    @classmethod
    def updateImage(cls, tag: Optional[str] = None) -> Optional[ExegolImage]:
        """User procedure to build/pull docker image"""
        # List Images
        images = DockerUtils.listImages()
        selected_image: ExegolImage = None
        # Select image
        if tag is None:
            # Interactive selection
            selected_image = ExegolTUI.selectFromTable(images)
        else:
            # Find image by name
            for img in images:
                if img.getName() == tag:
                    selected_image = img
                    break

        if selected_image is not None:
            # Update
            DockerUtils.updateImage(selected_image)
        else:
            # Install / build image
            logger.warning(f"There is no image with the name: {tag}")
            # Ask confirm to build ?
            if Confirm.ask("[blue][?][/blue] Do you want to build locally a custom image?",
                           choices=["y", "N"],
                           show_default=False,
                           default=False):
                build_name = cls.buildSource(tag)
                return DockerUtils.getImage(build_name)
            return None
        return selected_image

    @classmethod
    def updateGit(cls):
        """User procedure to update local git repository"""
        # Check if pending change -> cancel
        if not cls.__getGit().safeCheck():
            logger.error("Aborting git update.")
            return
        # List & Select git branch
        selected_branch = ExegolTUI.selectFromList(cls.__getGit().listBranch(),
                                                   subject="a git branch",
                                                   title="Branch",
                                                   default=cls.__getGit().getCurrentBranch())
        # Checkout new branch
        if selected_branch is not None and selected_branch != cls.__getGit().getCurrentBranch():
            cls.__getGit().checkout(selected_branch)
        # git pull
        cls.__getGit().update()

    @classmethod
    def buildSource(cls, build_name: Optional[str] = None) -> str:
        """build user process :
        Ask user is he want to update the git source (to get new& updated build profiles),
        User choice a build name (if not supplied)
        User select a build profile
        Start docker image building
        Return the name of the built image"""
        # Ask to update git
        if not cls.__getGit().isUpToDate() and Confirm.ask(
                "[blue][?][/blue] Do you want to update git (in order to update local build profiles)?",
                choices=["Y", "n"],
                show_default=False,
                default=True):
            cls.updateGit()
        # Choose tag name
        blacklisted_build_name = ["stable"]
        while build_name is None or build_name in blacklisted_build_name:
            if build_name is not None:
                logger.error("This name is reserved and cannot be used for local build. Please choose another one.")
            build_name = Prompt.ask("[blue][?][/blue] Choice a name for your build",
                                    default="local")
        # Choose dockerfile
        build_profile = ExegolTUI.selectFromList(cls.__listBuildProfiles(),
                                                 subject="a build profile",
                                                 title="Profile",
                                                 default="stable")
        # Docker Build
        DockerUtils.buildImage(build_name, build_profile)
        return build_name

    @classmethod
    def __listBuildProfiles(cls) -> Dict:
        """List every build profiles available locally
        Return a dict of options {"key = profile name": "value = dockerfile full name"}"""
        # Default stable profile
        profiles = {"stable": "Dockerfile"}
        # List file *.dockerfile is the build context directory
        docker_files = list(ConstantConfig.build_context_path_obj.glob("*.dockerfile"))
        for file in docker_files:
            # Convert every file to the dict format
            filename = file.name
            profile_name = filename.replace(".dockerfile", "")
            profiles[profile_name] = filename
        logger.debug(f"List docker build profiles : {profiles}")
        return profiles
