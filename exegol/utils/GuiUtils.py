import io
import os
import shutil
import subprocess
import time
from typing import Optional

from exegol.console.ExegolPrompt import Confirm
from exegol.utils.EnvInfo import EnvInfo
from exegol.utils.ExeLog import logger, console


class GuiUtils:
    """This utility class allows determining if the current system supports the GUI
    from the information of the system."""

    __distro_name = ""

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
                logger.error("WSL is [orange3]not available[/orange3] on your system. GUI is not supported.")
                return False
            # Only WSL2 support WSLg
            if EnvInfo.getDockerEngine() != "wsl2":
                logger.error("Docker must be run with [orange3]WSL2[/orange3] engine in order to support GUI applications.")
                return False
            logger.debug("WSL is [green]available[/green] and docker is using WSL2")
            if cls.__wslg_installed():
                # X11 GUI socket can only be shared from a WSL (to find WSLg mount point)
                if EnvInfo.current_platform != "WSL":
                    cls.__distro_name = cls.__find_wsl_distro()
                    # If no WSL is found, propose to continue without GUI
                    if not cls.__distro_name and not Confirm(
                            "Do you want to continue [orange3]without[/orange3] GUI support ?", default=True):
                        raise KeyboardInterrupt
                return True
            elif cls.__wslg_eligible():
                logger.info("[green]WSLg[/green] is available on your system but [orange3]not installed[/orange3].")
                logger.info("Make sure, [green]WSLg[/green] is installed on your Windows by running 'wsl --update' as [orange3]admin[/orange3].")
                return True
            logger.debug("WSLg is [orange3]not available[/orange3]")
            logger.warning(
                "Display sharing is [orange3]not supported[/orange3] on your version of Windows. You need to upgrade to [turquoise2]Windows 11[/turquoise2].")
            return False
        # TODO check mac compatibility (default: same as linux)
        return True

    @classmethod
    def getX11SocketPath(cls) -> str:
        """
        Get the host path of the X11 socket
        :return:
        """
        if cls.__distro_name:
            return f"\\\\wsl.localhost\\{cls.__distro_name}\\mnt\\wslg\\.X11-unix"
        return "/tmp/.X11-unix"

    @classmethod
    def getDisplayEnv(cls) -> str:
        """
        Get the current DISPLAY env to access X11 socket
        :return:
        """
        return os.getenv('DISPLAY', ":0")

    @staticmethod
    def __wsl_test(path, name: Optional[str] = "docker-desktop") -> bool:
        """
        Check presence of a file in the WSL docker-desktop image.
        the targeted WSL image can be changed with 'name' parameter.
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
    def __check_wsl_docker_integration(cls, distrib_name) -> bool:
        """
        Check the presence of the docker binary in the supplied WSL distribution.
        This test allows checking if docker integration is enabled.
        """
        return cls.__wsl_test("/usr/bin/docker", distrib_name)

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
        try:
            os_version_raw, _, build_number_raw = EnvInfo.getWindowsRelease().split('.')[:3]
        except ValueError:
            logger.debug(f"Impossible to find the version of windows: '{EnvInfo.getWindowsRelease()}'")
            logger.error("Exegol can't know if your [orange3]version of Windows[/orange3] can support dockerized GUIs.")
            return False
        # Available from Windows 10 Build 21364
        # Available from Windows 11 Build 22000
        os_version = int(os_version_raw)
        build_number = int(build_number_raw)
        if os_version == 10 and build_number >= 21364:
            return True
        elif os_version > 10:
            return True
        return False

    @classmethod
    def __find_wsl_distro(cls) -> str:
        distro_name = ""
        # these distros cannot be used to load WSLg socket
        blacklisted_distro = ["docker-desktop", "docker-desktop-data"]
        ret = subprocess.Popen(["C:\Windows\system32\wsl.exe", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Wait for WSL process to end
        ret.wait()
        if ret.returncode == 0:
            skip_header = True
            # parse distribs
            logger.debug("Found WSL distribution:")
            assert ret.stdout is not None
            for line in io.TextIOWrapper(ret.stdout, encoding="utf-16le"):
                # Skip WSL text header
                if skip_header:
                    skip_header = False
                    continue
                # Remove newline
                line = line.strip()
                # Skip if line is empty
                if not line:
                    continue
                # Remove default text message
                name = line.split()[0]
                logger.debug(f"- {name}")
                # Skip blacklisted WSL
                if name not in blacklisted_distro:
                    eligible = True
                    # Test if the current WSL has docker integration activated
                    while not cls.__check_wsl_docker_integration(name):
                        eligible = False
                        logger.warning(
                            f"The '{name}' WSL distribution could be used to [green]enable the GUI[/green] on exegol but the docker integration is [orange3]not enabled[/orange3].")
                        if not Confirm(
                                f"Do you want to [red]manually[/red] enable docker integration for WSL '{name}'?",
                                default=True):
                            break
                        eligible = True
                    if eligible:
                        distro_name = name
                        break
            if distro_name:
                logger.verbose(f"Wsl '{distro_name}' distribution found, the WSLg service can be mounted in exegol.")
            else:
                logger.warning(
                    "No WSL distribution was found on your machine. At least one distribution must be available to allow Exegol to use WSLg.")
                if Confirm("Do you want Exegol to install one automatically (Ubuntu)?", default=True):
                    if cls.__create_default_wsl():
                        distro_name = "Ubuntu"
        else:
            assert ret.stderr is not None
            logger.error(
                f"Error while loading existing wsl distributions. {ret.stderr.read().decode('utf-16le')} (code: {ret.returncode})")
        return distro_name

    @classmethod
    def __create_default_wsl(cls) -> bool:
        logger.info("Creating Ubuntu WSL distribution. Please wait.")
        ret = subprocess.Popen(["C:\Windows\system32\wsl.exe", "--install", "-d", "Ubuntu"], stderr=subprocess.PIPE)
        ret.wait()
        logger.info("Please follow installation instructions on the new window.")
        if ret.returncode != 0:
            assert ret.stderr is not None
            logger.error(
                f"Error while install WSL Ubuntu: {ret.stderr.read().decode('utf-16le')} (code: {ret.returncode})")
            return False
        else:
            while not Confirm("Is the installation of Ubuntu [green]finished[/green]?", default=True):
                pass
            logger.verbose("Set WSL Ubuntu as default to enable docker integration")
            # Set new WSL distribution as default to start it and enable docker integration
            ret = subprocess.Popen(["C:\Windows\system32\wsl.exe", "-s", "Ubuntu"], stderr=subprocess.PIPE)
            ret.wait()
            # Wait for the docker integration (10 try, 1 sec apart)
            with console.status("Waiting for the activation of the docker integration", spinner_style="blue"):
                for _ in range(10):
                    if cls.__check_wsl_docker_integration("Ubuntu"):
                        break
                    time.sleep(1)
            while not cls.__check_wsl_docker_integration("Ubuntu"):
                logger.error("The newly created WSL could not get the docker integration automatically. "
                             "It has to be activated [red]manually[/red]")
                if not Confirm("Has the WSL Ubuntu docker integration been [red]manually[/red] activated?",
                               default=True):
                    return False
            logger.success("WSL 'Ubuntu' successfully created with docker integration")
            return True
