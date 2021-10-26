from rich.prompt import Confirm, Prompt

from wrapper.console.TUI import ExegolTUI
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger
from wrapper.utils.GitUtils import GitUtils


class UpdateManager:
    __git = None

    @classmethod
    def __getGit(cls):
        if cls.__git is None:
            cls.__git = GitUtils()
        return cls.__git

    @classmethod
    def updateImage(cls, tag=None):
        """User procedure to build/pull docker image"""
        # List Images
        images = DockerUtils.listImages()
        selected_image = None
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
                cls.buildSource(tag)

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
    def buildSource(cls, build_name=None):
        # Ask to update git
        if Confirm.ask("[blue][?][/blue] Do you want to update git?",
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

    @classmethod
    def __listBuildProfiles(cls):
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
