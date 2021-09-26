from wrapper.utils.ExeLog import logger


class ExegolImage:

    def __init__(self, name="NONAME", digest=None, image_id=None, size=0, docker_image=None, is_local=False):
        # Init attributes
        self.__image = docker_image
        self.__name = name
        self.__size = "[bright_black]N/A[/bright_black]" if size == 0 else self.__processSize(size)
        self.__real_size = "[bright_black]N/A[/bright_black]"
        self.__digest = "[bright_black]Unknown digest[/bright_black]"
        self.__id = "[bright_black]Unknown ID[/bright_black]"
        self.__is_remote = not is_local
        self.__is_install = False
        self.__is_update = False
        self.__is_discontinued = False
        # Process data
        self.__setDigest(digest)
        self.__setImageId(image_id)
        if docker_image is not None:
            self.__initFromDockerImage()
        logger.debug("└── {}\t→ ({}) {}".format(self.__name, self.getType(), self.__digest))

    def __initFromDockerImage(self):
        # If docker object exist, image is already installed
        self.__is_install = True
        # Set init values from docker object
        self.__name = self.__image.attrs["RepoTags"][0].split(':')[1]
        self.__setRealSize(self.__image.attrs["Size"])
        # Set local image ID
        self.__setImageId(self.__image.attrs["Id"])
        # If this image is remote, set digest ID
        if self.__is_remote:
            self.__setDigest(self.__image.attrs["RepoDigests"][0].split(":")[1])

    def setDockerObject(self, docker_image):
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
    def __processSize(size, precision=1):
        # https://stackoverflow.com/a/32009595
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        while size > 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            size = size / 1024.0  # apply the division
        return "%.*f%s" % (precision, size, suffixes[suffix_index])

    @staticmethod
    def mergeImages(remote_images, local_images):
        results = []
        logger.debug("Merging remote and local images")
        for local_img in local_images:
            # Load variables
            name, tag = local_img.attrs["RepoTags"][0].split(':')
            logger.debug("- {}".format(tag))
            # Check if custom build
            if len(local_img.attrs["RepoDigests"]) == 0:
                # This image is build locally
                new_image = ExegolImage(docker_image=local_img, is_local=True)
                results.append(new_image)
                continue
            found = False
            # Find matching remote image
            for image in remote_images:
                if image.getName() == tag:
                    image.setDockerObject(local_img)
                    remote_images.remove(image)
                    results.append(image)
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

    def __eq__(self, other):
        # Don't compare image's digest when using == (update check if separate)
        return self.__name == other.__name and self.__image == other.__image

    def __str__(self):
        return f"{self.__name} - {self.__real_size} - " + (
            f"({self.getStatus()}, {self.__size})" if self.__is_remote else f"{self.getStatus()}")

    def getStatus(self):
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

    def getType(self):
        return "remote" if self.__is_remote else "local"

    def __setDigest(self, digest):
        if digest is not None:
            self.__digest = digest.split(":")[1]
        else:
            self.__digest = "[bright_black]Unknown digest[/bright_black]"

    def __setImageId(self, image_id):
        if image_id is not None:
            self.__id = image_id.split(":")[1][:12]
        else:
            self.__id = "[bright_black]Unknown ID[/bright_black]"

    def getDigest(self):
        return self.__digest

    def __setRealSize(self, value):
        self.__real_size = self.__processSize(value)

    def getRealSize(self):
        return self.__real_size

    def isInstall(self) -> bool:
        return self.__is_install

    def getName(self):
        return self.__name

    def update(self):
        if self.__is_remote:
            if self.__is_update:
                logger.warning("This image is already up to date. Skipping.")
                return None
            return self.__name
        else:
            logger.error("Local images cannot be updated.")  # TODO add build mode
            return None

    def remove(self):
        raise NotImplemented
