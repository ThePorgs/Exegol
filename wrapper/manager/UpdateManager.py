from wrapper.manager.GitManager import GitManager
from wrapper.utils.DockerUtils import DockerUtils
from wrapper.utils.ExeLog import logger


class UpdateManager:
    def __init__(self, build=False):
        self.__build = build
        self.__git = GitManager()

    def updateImage(self, tag=None):
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
            raise NotImplementedError

    def updateGit(self, branch=None):
        # Check if pending change -> cancel
        if not self.__git.safeCheck():
            logger.error("Aborting git update.")
            return
        # List & Select git branch
        logger.info(self.__git.listBranch())
        # TODO select git branch (need TUI)
        # Checkout new branch
        if branch is not None:
            self.__git.checkout(branch)
        # git pull
        self.__git.update()

    def __buildSource(self):
        # Ask to update git ?
        # Choose tag name
        # Docker Build
        pass
