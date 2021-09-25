from wrapper.utils.ExeLog import logger


class ExegolImage:

    def __init__(self, name="NONAME", digest=None, size=0, docker_image=None, image_type="remote"):
        self.__image = docker_image
        self.__name = name
        self.__size = "[bright_black]N/A[/bright_black]" if size == 0 else self.__processSize(size)
        self.__real_size = "[bright_black]N/A[/bright_black]"
        self.__digest = "[bright_black]Unknown ID[/bright_black]"
        self.__short_id = "?"
        if digest is not None:
            self.__setDigest(digest)
        self.__type = image_type
        self.__is_install = False
        self.__is_update = False
        self.__is_discontinued = False
        if docker_image is not None:
            self.__initFromDockerImage()
        logger.debug("└── {}\t→ ({}) {}".format(self.__name, self.__type, self.__digest))

    def __initFromDockerImage(self):
        self.__is_install = True
        self.__name = self.__image.attrs["RepoTags"][0].split(':')[1]
        self.__setRealSize(self.__image.attrs["Size"])
        self.__setDigest(self.__image.attrs["Id"])

    def setDockerObject(self, docker_image):
        self.__image = docker_image
        self.__is_install = True
        digest = docker_image.attrs["Id"].replace("sha256:", "")
        if self.__digest == digest:
            self.__is_update = True
        self.__setRealSize(self.__image.attrs["Size"])

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
                new_image = ExegolImage(docker_image=local_img, image_type="local")
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
            f"{self.getStatus()}" if self.__type != "remote" else f"({self.getStatus()}, {self.__size})")

    def getStatus(self):
        if self.__type == "local":
            return "[blue]Local image[/blue]"
        elif self.__is_discontinued:
            return "[bright_black]Discontinued[/bright_black]"
        elif self.__is_update:
            return "[green]Up to date[/green]"
        elif self.__is_install:
            return "[orange3]Need update[/orange3]"
        else:
            return "[red]Not installed[/red]"

    def __setDigest(self, digest):
        self.__digest = digest.split(":")[1]
        self.__short_id = self.__digest[:12]

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
        raise NotImplemented

    def remove(self):
        raise NotImplemented
