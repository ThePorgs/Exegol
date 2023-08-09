import io
import tarfile

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


def getImageSyncTarData():
    """The purpose of this class is to generate and overwrite scripts like the entrypoint or start.sh inside exegol containers
    to integrate the latest features, whatever the version of the image."""

    entrypoint_script_path = ConstantConfig.entrypoint_context_path_obj
    logger.debug(f"Entrypoint script path: {str(entrypoint_script_path)}")
    start_script_path = ConstantConfig.start_context_path_obj
    logger.debug(f"Start script path: {str(start_script_path)}")
    if not entrypoint_script_path.is_file() or not start_script_path.is_file():
        logger.error("Unable to find the entrypoint or start script! Your Exegol installation is probably broken...")
        return None
    # Create tar file
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as entry_tar:
        # Load entrypoint data
        with open(entrypoint_script_path, 'rb') as f:
            raw = f.read()
            data = io.BytesIO(initial_bytes=raw)

        # Import file to tar object
        info = tarfile.TarInfo(name="/.exegol/entrypoint.sh")
        info.size = len(raw)
        info.mode = 0o500
        entry_tar.addfile(info, fileobj=data)

        # Load start data
        with open(start_script_path, 'rb') as f:
            raw = f.read()
            data = io.BytesIO(initial_bytes=raw)

        # Import file to tar object
        info = tarfile.TarInfo(name="/.exegol/start.sh")
        info.size = len(raw)
        info.mode = 0o500
        entry_tar.addfile(info, fileobj=data)
    return stream.getvalue()
