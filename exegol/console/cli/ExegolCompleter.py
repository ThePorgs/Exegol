from argparse import Namespace
from pathlib import Path
from typing import List, Tuple

from exegol.config.DataCache import DataCache
from exegol.config.UserConfig import UserConfig
from exegol.utils.NetworkUtils import NetworkUtils


# Debug : argcomplete.warn('debug message')

def _filterPrefix(data: List[str], prefix: str) -> Tuple[str, ...]:
    """Filter a list of completion options with the prefix already typed by the user"""
    if not prefix:
        return tuple(data)
    return tuple(obj for obj in data if obj.lower().startswith(prefix.lower()))


def ContainerCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Function to dynamically load a container list for CLI autocompletion purpose.
    Only the local cache is read here: the completer must be instantaneous
    and must never interact with the docker daemon."""
    try:
        data = [container.name for container in DataCache().get_containers_data().data]
    except Exception:
        # A completer must never fail, supplying no option is better than breaking the user's shell completion
        return ()
    return _filterPrefix(data, prefix)


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
    except Exception:
        data = []
    if len(data) == 0:
        # Fallback with default data if the cache is not initialized yet
        data = ["full", "nightly", "ad", "web", "light", "osint", "free"]
    return _filterPrefix(data, prefix)


def HybridContainerImageCompleter(prefix: str, parsed_args: Namespace, **kwargs) -> Tuple[str, ...]:
    """Hybrid completer for auto-complet. The selector on exec action is hybrid between image and container depending on the mode (tmp or not).
    This completer will supply the adequate data."""
    if parsed_args is None:
        return ()
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

    try:
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

        # Imported locally to keep the CLI parser light (see the shell completion fast path)
        from exegol.manager.UpdateManager import UpdateManager
        # Find profile list
        data = list(UpdateManager.listBuildProfiles(profiles_path=build_path).keys())
    except Exception:
        # A completer must never fail, supplying no option is better than breaking the user's shell completion
        return ()
    return _filterPrefix(data, prefix)


def DesktopConfigCompleter(prefix: str, **kwargs) -> Tuple[str, ...]:
    result = []
    try:
        parts = prefix.split(':')
        if len(parts) <= 1:
            # First part, suggest available protocol
            proto_options = list(UserConfig.desktop_available_proto)
            for obj in proto_options:
                if prefix is not None and obj.lower().startswith(prefix.lower()):
                    result.append(obj)
        elif len(parts) == 2:
            # Second part, autocomplet host interfaces
            addr_options = NetworkUtils.get_host_addresses()
            for obj in addr_options:
                if obj.startswith(parts[-1]):
                    result.append(parts[0] + ':' + obj)
    except Exception:
        # A completer must never fail, supplying no option is better than breaking the user's shell completion
        return ()

    return tuple(result)


def VoidCompleter(**kwargs) -> Tuple:
    """No option to auto-complet"""
    return ()
