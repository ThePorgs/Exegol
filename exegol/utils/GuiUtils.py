import os
import shutil
import subprocess

from exegol.console.ExegolPrompt import Confirm
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger


# Windows environment detection class
class GuiUtils:

    @staticmethod
    def __wsl_test(path, name="docker-desktop") -> bool:
        """
        Check presence of a file in the WSL docker-desktop image.
        the targeted WSL image can be change with 'name' parameter.
        If name is None, the default WSL image will be use.
        """
        if EnvInfo.isWindowsHost():
            wsl = shutil.which("wsl.exe")
            if not wsl:
                return False
            if name is None:
                ret = subprocess.run(["wsl.exe", "test", "-f", path])
            else:
                ret = subprocess.run(["wsl.exe", "-d", name, "test", "-f", path])
            return ret.returncode == 0
        return False

    @classmethod
    def __wsl_available(cls) -> bool:
        """
        heuristic to detect if Windows Subsystem for Linux is available.

        Uses presence of /etc/os-release in the WSL image to say Linux is there.
        This is a de facto file standard across Linux distros.
        """
        return cls.__wsl_test("/etc/os-release", name=None)

    @classmethod
    def __wslg_installed(cls) -> bool:
        """
        Check if WSLg is installed and deploy inside a WSL image by testing if the file wslg/versions.txt exist.
        :return: bool
        """
        return cls.__wsl_test("/mnt/host/wslg/versions.txt") or cls.__wsl_test("/mnt/wslg/versions.txt", name=None)

    @staticmethod
    def __wslg_eligible() -> bool:
        """
        Check if the current Windows version support WSLg
        :return:
        """
        # Windows build release not available on  WSL env
        if EnvInfo.is_linux_shell:
            logger.error("Exegol running from a linux terminal can't know "
                         "if your version of Windows can support dockerized GUIs.")
            return False
        else:
            os_version, _, build_number = EnvInfo.windows_release.split('.')[:3]
            os_version = int(os_version)
            build_number = int(build_number)
            # Available from Windows 10 Build 21364
            # Available from Windows 11 Build 22000
            return os_version >= 10 and build_number >= 21364

    @classmethod
    def isGuiAvailable(cls) -> bool:
        """
        Check if the host OS can support GUI application with X11 sharing
        :return: bool
        """
        # GUI was not supported on Windows before WSLg
        if EnvInfo.isWindowsHost():
            logger.debug("Testing WSLg availability")
            # WSL + WSLg must be available on the Windows host for the GUI to work
            if not cls.__wsl_available():
                logger.error("WSL is not available on your system. GUI is not supported.")
                return False
            # Only WSL2 support WSLg
            if EnvInfo.getDockerEngine() != "wsl2":
                logger.error("Docker must be run with WSL2 engine in order to support GUI applications.")
                return False
            logger.debug("WSL is available and docker is using WSL2")
            if cls.__wslg_installed():
                # X11 GUI socket can only be shared from a WSL with docker integration context
                if EnvInfo.current_platform != "WSL":
                    # TODO find a bypass to create a GUI container from windows context
                    logger.error(
                        "WSLg is installed but a GUI container can only be created from a WSL context with docker integration (for now).")
                    if not Confirm("Do you want to continue without GUI support ?", default=True):
                        raise KeyboardInterrupt
                    return False
                return True
            elif cls.__wslg_eligible():
                logger.info("WSLg is available on your system but not installed.")
                logger.info("Make sure, WSLg is installed on your Windows by running 'wsl --update' as admin.")
                return True
            logger.debug("WSLg is not available")
            logger.warning(
                "Display sharing is not supported on your version of Windows. You need to upgrade to [turquoise2]Windows 11[/turquoise2].")
            return False
        # TODO check mac compatibility
        return True

    @classmethod
    def getX11SocketPath(cls) -> str:
        """
        Get the host path of the X11 socket
        :return:
        """
        # TODO check WSLg mount from Windows/WSL
        return "/tmp/.X11-unix"

    @classmethod
    def getDisplayEnv(cls) -> str:
        """
        Get the current DISPLAY env to access X11 socket
        :return:
        """
        # TODO check WSLg display env
        return os.getenv('DISPLAY')
