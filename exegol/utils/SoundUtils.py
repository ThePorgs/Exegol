import io
import os
from pathlib import Path
from typing import Optional

from exegol.console.ExegolPrompt import Confirm
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, console


class SoundUtils:
    """This utility class allows determining if the current system supports the sound sharing
    from the information of the system."""

    @classmethod
    def isPulseAudioAvailable(cls) -> bool:
        """
        Check if the host OS has PulseAudio installed
        :return: bool
        """
        if "XDG_RUNTIME_DIR" in os.environ:
            return Path(f"{os.getenv('XDG_RUNTIME_DIR')}/pulse/native").exists()
        else:
            return Path(f"/run/user/{os.getuid()}/pulse/native").exists()

    @classmethod
    def getPulseAudioSocketPath(cls) -> str:
        """
        Get the host path of the Pulse Audio socket
        :return:
        """
        # todo : find the path for windows/WSL
        if "XDG_RUNTIME_DIR" in os.environ:
            return f"{os.getenv('XDG_RUNTIME_DIR')}/pulse/native"
        else:
            return f"/run/user/{os.getuid()}/pulse/native"

    @classmethod
    def getPulseAudioCookiePath(cls) -> str:
        """
        Get the host path of the Pulse Audio cookie
        :return:
        """
        # todo : find the path for windows/WSL
        # return f"{os.getenv('HOME')}/.config/pulse/cookie"
        return str(Path().home() / ".config/pulse/cookie")
