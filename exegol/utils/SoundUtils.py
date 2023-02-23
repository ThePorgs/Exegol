import io
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from exegol.console.ExegolPrompt import Confirm
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, console


class SoundUtils:
    """This utility class allows determining if the current system supports the sound sharing
    from the information of the system."""

    __distro_name = ""

    @classmethod
    def isPulseAudioAvailable(cls) -> bool:
        """
        Check if the host OS has PulseAudio installed
        :return: bool
        """
        assert os.getenv("XDG_RUNTIME_DIR")
        return Path(f"{os.getenv('XDG_RUNTIME_DIR')}/pulse/native").exists()

    @classmethod
    def getPulseAudioSocketPath(cls) -> Path:
        """
        Get the host path of the Pulse Audio socket
        :return:
        """
        # todo : find the path for windows/WSL
        assert os.getenv("XDG_RUNTIME_DIR")
        return f"{os.getenv('XDG_RUNTIME_DIR')}/pulse/native"

    @classmethod
    def getPulseAudioCookiePath(cls) -> str:
        """
        Get the host path of the Pulse Audio cookie
        :return:
        """
        # todo : find the path for windows/WSL
        return f"{os.getenv('HOME')}/.config/pulse/cookie"
        #return Path().home() / "/.config/pulse/cookie"
