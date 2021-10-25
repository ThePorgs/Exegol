from wrapper.manager.GitManager import GitManager
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger


class UpdateManager:
    __git = GitManager()

    @staticmethod
    def updateImage(tag=None):
        """User procedure to build/pull docker image"""
        # List Images
        images = DockerUtils.listImages()
        selected_image = None
        # Select image
        if tag is None:
            logger.info(images)
            # Interactive selection
            # TODO select image (need TUI)
            selected_image = images[0]
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
            # Ask confirm to build ?
            raise NotImplementedError

    @classmethod
    def updateGit(cls, branch=None):
        """User procedure to update local git repository"""
        # Check if pending change -> cancel
        if not cls.__git.safeCheck():
            logger.error("Aborting git update.")
            return
        # List & Select git branch
        logger.info(cls.__git.listBranch())
        # TODO select git branch (need TUI)
        # Checkout new branch
        if branch is not None:
            cls.__git.checkout(branch)
        # git pull
        cls.__git.update()

    @staticmethod
    def buildSource():  # TODO
        # Ask to update git ?
        # Choose tag name
        # Docker Build
        DockerUtils.buildImage("local")
