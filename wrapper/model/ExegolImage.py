from docker.models.images import Image

from wrapper.model.SelectableInterface import SelectableInterface
from wrapper.utils.ConstantConfig import ConstantConfig
from wrapper.utils.ExeLog import logger


class ExegolImage(SelectableInterface):

    def __init__(self, name: str = "NONAME", digest: str = None, image_id: str = None, size: int = 0,
                 docker_image: Image = None):
        """Docker image default value"""
        # Init attributes
        self.__image: Image = docker_image
        self.__name = name
        # Remote image size
        self.__dl_size = ":question:" if size == 0 else self.__processSize(size)
        # Local uncompressed image's size
        self.__disk_size = ":question:"
        # Remote image ID
        self.__digest = "[bright_black]:question:[/bright_black]"
        # Local docker image ID
        self.__image_id = "[bright_black]Not installed[/bright_black]"
        # Status
        self.__is_remote = size > 0
        self.__is_install = False
        self.__is_update = False
        self.__is_discontinued = False
        # Process data
        if docker_image is not None:
            self.__initFromDockerImage()
        else:
            self.__setDigest(digest)
            self.__setImageId(image_id)
        logger.debug("└── {}\t→ ({}) {}".format(self.__name, self.getType(), self.__digest))

    def __initFromDockerImage(self):
        """Parse Docker object to setup self configuration on creation."""
        # If docker object exist, image is already installed
        self.__is_install = True
        # Set init values from docker object
        self.__name = self.__image.attrs["RepoTags"][0].split(':')[1]
        self.__setRealSize(self.__image.attrs["Size"])
        # Set local image ID
        self.__setImageId(self.__image.attrs["Id"])
        # If this image is remote, set digest ID
        self.__is_remote = len(self.__image.attrs["RepoDigests"]) > 0
        if self.__is_remote:
            self.__setDigest(self.__image.attrs["RepoDigests"][0])

    def updateCheck(self):
        """If this image can be updated, return his name, otherwise return None"""
        if self.__is_remote:
            if self.__is_update:
                logger.warning("This image is already up to date. Skipping.")
                return None
            return self.__name
        else:
            logger.error("Local images cannot be updated.")  # TODO add build mode
            return None

    def removeCheck(self):
        """If this image can be remove, return his name, otherwise return None"""
        if self.__is_install:
            return self.__name
        else:
            logger.error("This image is not installed locally. Skipping.")
            return None

    def setDockerObject(self, docker_image: Image):
        """Docker object setter. Parse object to setup self configuration."""
        self.__image = docker_image
        # When a docker image exist, image is locally installed
        self.__is_install = True
        # Set real size on disk
        self.__setRealSize(self.__image.attrs["Size"])
        # Set local image ID
        self.__setImageId(docker_image.attrs["Id"])
        # Check if local image is sync with remote digest id (check up to date status)
        digest = docker_image.attrs["RepoDigests"][0].split(":")[1]
        if self.__digest == digest:
            self.__is_update = True

    @staticmethod
    def mergeImages(remote_images, local_images):
        """Compare and merge local images and remote images.
        Return a list of ExegolImage."""
        results = []
        logger.debug("Merging remote and local images")
        for local_img in local_images:
            # Load variables
            name, tag = local_img.attrs["RepoTags"][0].split(':')
            logger.debug("- {}".format(tag))
            # Check if custom build
            if len(local_img.attrs["RepoDigests"]) == 0:
                # This image is build locally
                new_image = ExegolImage(docker_image=local_img)
                results.append(new_image)
                continue
            found = False
            # Find matching remote image
            for image in remote_images:
                if image.getName() == tag:
                    image.setDockerObject(local_img)
                    # Remove processed image from queue and add it to results
                    remote_images.remove(image)
                    results.append(image)
                    # Tag current local image as successfully processed and exit loop
                    found = True
                    break
            if not found:
                # Matching image not found
                new_image = ExegolImage(docker_image=local_img)
                new_image.__is_discontinued = True
                results.append(new_image)
        # Add remaining remote image
        results.extend(remote_images)
        return results

    @staticmethod
    def __processSize(size, precision=1):
        """Text formatter from size number to human readable size."""
        # https://stackoverflow.com/a/32009595
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        while size > 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            size = size / 1024.0  # apply the division
        return "%.*f%s" % (precision, size, suffixes[suffix_index])

    def __eq__(self, other):
        """Operation == overloading for ExegolImage object"""
        # How to compare two ExegolImage
        if type(other) is ExegolImage:
            return self.__name == other.__name and self.__digest == other.__digest
        # How to compare ExegolImage with str
        elif type(other) is str:
            return self.__name == other
        else:
            logger.error(f"Error, {type(other)} compare to ExegolImage is not implemented")
            raise NotImplementedError

    def __str__(self):
        """Default object text formatter, debug only"""
        return f"{self.__name} - {self.__disk_size} - " + \
               (f"({self.getStatus()}, {self.__dl_size})" if self.__is_remote else f"{self.getStatus()}")

    def getStatus(self):
        """Formatted text getter of image's status."""
        if not self.__is_remote:
            return "[blue]Local image[/blue]"
        elif self.__is_discontinued:
            return "[bright_black]Discontinued[/bright_black]"
        elif self.__is_update:
            return "[green]Up to date[/green]"
        elif self.__is_install:
            return "[orange3]Need update[/orange3]"
        else:
            return "[red]Not installed[/red]"

    def getType(self) -> str:
        """Image type getter"""
        return "remote" if self.__is_remote else "local"

    def __setDigest(self, digest):
        """Remote image digest setter"""
        if digest is not None:
            self.__digest = digest.split(":")[1]

    def getDigest(self) -> str:
        """Remote digest getter"""
        return self.__digest

    def __setImageId(self, image_id):
        """Local image id setter"""
        if image_id is not None:
            self.__image_id = image_id.split(":")[1][:12]

    def getId(self) -> str:
        """Local id getter"""
        return self.__image_id

    def getKey(self):
        """Universal unique key getter (from SelectableInterface)"""
        return self.getName()

    def __setRealSize(self, value):
        """On-Disk image size setter"""
        self.__disk_size = self.__processSize(value)

    def getRealSize(self):
        """On-Disk size getter"""
        return self.__disk_size

    def getDownloadSize(self):
        """Remote size getter"""
        if not self.__is_remote:
            return "local"
        return self.__dl_size

    def getSize(self):
        """Image size getter. If the image is installed, return the on-disk size, otherwise return the remote size"""
        return self.__disk_size if self.__is_install else self.__dl_size

    def isInstall(self) -> bool:
        """Installation status getter"""
        return self.__is_install

    def isLocal(self) -> bool:
        """Local type getter"""
        return not self.__is_remote

    def getName(self):
        """Image's tag name getter"""
        return self.__name

    def getFullName(self):
        """Dockerhub image's full name getter"""
        return f"{ConstantConfig.IMAGE_NAME}:{self.__name}"
