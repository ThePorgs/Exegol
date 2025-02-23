from argparse import Namespace
from pathlib import Path
from typing import Tuple

from exegol.config.ConstantConfig import ConstantConfig
from exegol.config.DataCache import DataCache
from exegol.config.UserConfig import UserConfig
from exegol.manager.UpdateManager import UpdateManager
from exegol.utils.DockerUtils import DockerUtils


def ContainerCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Function to dynamically load a container list for CLI autocompletion purpose"""
    data = [c.name for c in DockerUtils().listContainers()]
    for obj in data:
        # filter data if needed
        if prefix and not obj.lower().startswith(prefix.lower()):
            data.remove(obj)
    return tuple(data)


def ImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Function to dynamically load an image list for CLI autocompletion purpose"""
    # Skip image completer when container hasn't been selected first (because parameters are all optional, parameters order is not working)
    if parsed_args is not None and str(parsed_args.action) == "start" and parsed_args.containertag is None:
        return ()
    try:
        if parsed_args is not None and str(parsed_args.action) == "install":
            data = [img_cache.name for img_cache in DataCache().get_images_data().data if img_cache.source == "remote"]
        else:
            data = [img_cache.name for img_cache in DataCache().get_images_data().data]
    except Exception as e:
        data = []
    if len(data) == 0:
        # Fallback with default data if the cache is not initialized yet
        data = ["full", "nightly", "ad", "web", "light", "osint"]
    for obj in data:
        # filter data if needed
        if prefix and not obj.lower().startswith(prefix.lower()):
            data.remove(obj)
    return tuple(data)


def HybridContainerImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Hybrid completer for auto-complet. The selector on exec action is hybrid between image and container depending on the mode (tmp or not).
    This completer will supply the adequate data."""
    # "exec" parameter is filled first before the selector argument
    # If "selector" is null but the selector parameter is set in the first exec slot, no longer need to supply completer options
    if parsed_args.selector is None and parsed_args.exec is not None and len(parsed_args.exec) > 0:
        return ()
    # In "tmp" mode, the user must choose an image, otherwise it's a container
    if parsed_args.tmp:
        return ImageCompleter(prefix, parsed_args, **kwargs)
    else:
        return ContainerCompleter(prefix, parsed_args, **kwargs)


def BuildProfileCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Completer function for build profile parameter. The completer must be trigger only when an image name have already been chosen."""
    # The build profile completer must be trigger only when an image name have been set by user
    if parsed_args is not None and parsed_args.imagetag is None:
        return ()

    # Handle custom build path
    if parsed_args is not None and parsed_args.build_path is not None:
        custom_build_path = Path(parsed_args.build_path).expanduser().absolute()
        # Check if we have a directory or a file to select the project directory
        if not custom_build_path.is_dir():
            custom_build_path = custom_build_path.parent
        build_path = custom_build_path
    else:
        # Default build path
        build_path = Path(UserConfig().exegol_images_path)

    # Check if directory path exist
    if not build_path.is_dir():
        return tuple()

    # Find profile list
    data = list(UpdateManager.listBuildProfiles(profiles_path=build_path).keys())
    for obj in data:
        if prefix and not obj.lower().startswith(prefix.lower()):
            data.remove(obj)
    return tuple(data)


def DesktopConfigCompleter(prefix: str, **kwargs) -> Tuple[str, ...]:
    options = list(UserConfig.desktop_available_proto)
    for obj in options:
        if prefix and not obj.lower().startswith(prefix.lower()):
            options.remove(obj)
    # TODO add interface enum
    return tuple(options)


def VoidCompleter(**kwargs) -> Tuple:
    """No option to auto-complet"""
    return ()
