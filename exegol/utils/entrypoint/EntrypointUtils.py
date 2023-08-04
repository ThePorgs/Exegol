import io
import tarfile

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


def getEntrypointTarData():
    """The purpose of this class is to generate and overwrite the entrypoint script of exegol containers
    to integrate the latest features, whatever the version of the image."""

    # Load entrypoint data
    script_path = ConstantConfig.entrypoint_context_path_obj
    logger.debug(f"Entrypoint path: {str(script_path)}")
    if not script_path.is_file():
        logger.error("Unable to find the entrypoint script! Your Exegol installation is probably broken...")
        return None
    with open(script_path, 'rb') as f:
        raw = f.read()
        data = io.BytesIO(initial_bytes=raw)

    # Create tar file
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as entry_tar:
        # Import file to tar object
        info = tarfile.TarInfo(name="/.exegol/entrypoint.sh")
        info.size = len(raw)
        info.mode = 0o500
        entry_tar.addfile(info, fileobj=data)
    return stream.getvalue()
