import docker


class DockerUtils:
    __client = docker.from_env()
    __image_name = "nwodtuhs/exegol"

    @classmethod
    def listImages(cls):
        # TODO parse images objects
        return cls.__client.images.list(cls.__image_name, filters={"dangling": False})

    @classmethod
    def listContainers(cls):
        # TODO parse containers objects
        return cls.__client.containers.list(all=True, filters={"name": "exegol-"})
