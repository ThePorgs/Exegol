import io
import tarfile
from typing import Optional

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger


class ImageScriptSync:

    @staticmethod
    def getCurrentStartVersion() -> str:
        """Find the current version of the spawn.sh script."""
        with open(ConstantConfig.spawn_context_path_obj, 'r') as file:
            for line in file.readlines():
                if line.startswith('# Spawn Version:'):
                    return line.split(':')[-1].strip()
        logger.critical(f"The spawn.sh version cannot be found, check your exegol setup! {ConstantConfig.spawn_context_path_obj}")
        raise RuntimeError

    @staticmethod
    def getImageSyncTarData(include_entrypoint: bool = False, include_spawn: bool = False) -> Optional[bytes]:
        """The purpose of this class is to generate and overwrite scripts like the entrypoint or spawn.sh inside exegol containers
        to integrate the latest features, whatever the version of the image."""

        # Create tar file
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w|') as entry_tar:

            # Load entrypoint data
            if include_entrypoint:
                entrypoint_script_path = ConstantConfig.entrypoint_context_path_obj
                logger.debug(f"Entrypoint script path: {str(entrypoint_script_path)}")
                if not entrypoint_script_path.is_file():
                    logger.critical("Unable to find the entrypoint script! Your Exegol installation is probably broken...")
                    return None
                with open(entrypoint_script_path, 'rb') as f:
                    raw = f.read()
                    data = io.BytesIO(initial_bytes=raw)

                # Import file to tar object
                info = tarfile.TarInfo(name="/.exegol/entrypoint.sh")
                info.size = len(raw)
                info.mode = 0o500
                entry_tar.addfile(info, fileobj=data)

            # Load start data
            if include_spawn:
                spawn_script_path = ConstantConfig.spawn_context_path_obj
                logger.debug(f"Spawn script path: {str(spawn_script_path)}")
                if not spawn_script_path.is_file():
                    logger.error("Unable to find the spawn script! Your Exegol installation is probably broken...")
                    return None
                with open(spawn_script_path, 'rb') as f:
                    raw = f.read()
                    data = io.BytesIO(initial_bytes=raw)

                # Import file to tar object
                info = tarfile.TarInfo(name="/.exegol/spawn.sh")
                info.size = len(raw)
                info.mode = 0o500
                entry_tar.addfile(info, fileobj=data)
        return stream.getvalue()
