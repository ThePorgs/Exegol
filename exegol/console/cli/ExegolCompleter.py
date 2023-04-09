from argparse import Namespace
from typing import Tuple

from exegol.utils.DockerUtils import DockerUtils


def ContainerCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Function to dynamically load a container list for CLI autocompletion purpose"""
    data = [c.name for c in DockerUtils.listContainers()]
    for obj in data:
        # filter data if needed
        if prefix and not obj.startswith(prefix):
            data.remove(obj)
    return tuple(data)


def ImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Function to dynamically load an image list for CLI autocompletion purpose"""
    # Skip image completer when container hasn't been selected first (because parameters are all optional)
    if parsed_args is not None and str(parsed_args.action) == "start" and parsed_args.containertag is None:
        return ()
    # data = [i.getName() for i in DockerUtils.listImages()]
    # TODO create a fast-load image listing (need image caching)
    data = ["full", "nightly", "ad", "web", "light", "osint"]
    for obj in data:
        # filter data if needed
        if prefix and not obj.startswith(prefix):
            data.remove(obj)
    return tuple(data)


def HybridContainerImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    # warn(parsed_args)
    if parsed_args.selector is None and parsed_args.exec is not None and len(parsed_args.exec) > 0:
        return ()
    if parsed_args.tmp:
        return ImageCompleter(prefix, parsed_args, **kwargs)
    else:
        return ContainerCompleter(prefix, parsed_args, **kwargs)


def VoidCompleter(**kwargs) -> Tuple:
    return ()
