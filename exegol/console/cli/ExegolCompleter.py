from argparse import Namespace
from typing import List, Tuple

from argcomplete import warn

from exegol.utils.DockerUtils import DockerUtils


def ContainerCompleter(prefix: str, **kwargs) -> List[str]:
    """Function to dynamically load a container list for CLI autocompletion purpose"""
    data = [c.name for c in DockerUtils.listContainers()]
    for obj in data:
        # filter data if needed
        if prefix and not obj.startswith(prefix):
            data.remove(obj)
    return data


def ImageCompleter(prefix: str, **kwargs) -> List[str]:
    """Function to dynamically load an image list for CLI autocompletion purpose"""
    parsed_args: Namespace = kwargs.get('parsed_args')
    # Skip image completer when container hasn't been selected first (because parameters are all optional)
    if parsed_args is not None and str(parsed_args.action) == "start" and parsed_args.containertag is None:
        return []
    # data = [i.getName() for i in DockerUtils.listImages()]
    # TODO create a fast-load image listing (need image caching)
    data = ["full", "nightly", "ad", "web", "light", "osint"]
    for obj in data:
        # filter data if needed
        if prefix and not obj.startswith(prefix):
            data.remove(obj)
    return data


def HybridContainerImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> List[str]:
    if parsed_args.tmp:
        return ImageCompleter(prefix, **kwargs)
    else:
        warn("Container mode")
        return ContainerCompleter(prefix, **kwargs)


def VoidCompleter(**kwargs) -> Tuple:
    return ()
