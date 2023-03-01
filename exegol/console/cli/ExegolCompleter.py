from exegol.utils.DockerUtils import DockerUtils


def ContainerCompleter(prefix: str, **kwargs):
    """Function to dynamically load a container list for CLI autocompletion purpose"""
    data = [c.name for c in DockerUtils.listContainers()]
    for obj in data:
        # filter data if needed
        if prefix and not obj.startswith(prefix):
            data.remove(obj)
    return data


def ImageCompleter(prefix: str, **kwargs):
    """Function to dynamically load an image list for CLI autocompletion purpose"""
    # start = kwargs.get("prefix")
    # data = [i.getName() for i in DockerUtils.listImages()]
    # for obj in data:
    #     # filter data if needed
    #     if start and not obj.startswith(start):
    #         data.remove(obj)
    # return data
    # TODO create a fast-load image listing
    return ["full", "nightly", "ad", "web", "light", "osint"]

