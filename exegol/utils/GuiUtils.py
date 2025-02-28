import io
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from exegol.config.EnvInfo import EnvInfo
from exegol.console.ExegolPrompt import Confirm
from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ExeLog import logger, console


class GuiUtils:
    """This utility class allows determining if the current system supports the GUI
    from the information of the system (through X11 sharing)."""

    __distro_name = ""
    default_x11_path = "/tmp/.X11-unix"

    @classmethod
    def isX11GuiAvailable(cls) -> bool:
        """
        Check if the host OS can support GUI application with X11 sharing
        :return: bool
        """
        # GUI (X11 sharing) was not supported on Windows before WSLg
        if EnvInfo.isWindowsHost():
            return cls.__windowsGuiChecks()
        elif EnvInfo.isMacHost():
            return cls.__macGuiChecks()
        # Linux default is True
        return True

    @classmethod
    def isWaylandGuiAvailable(cls) -> bool:
        """
        Check if the host OS can support GUI application with WAYLAND sharing
        :return: bool
        """
        if EnvInfo.isWindowsHost():
            return False
        elif EnvInfo.isMacHost():
            return False
        return EnvInfo.isWaylandAvailable()

    @classmethod
    def getX11SocketPath(cls) -> Optional[str]:
        """
        Get the host path of the X11 socket
        :return:
        """
        if cls.__distro_name:
            # Distro name can only be set if the current host OS is Windows
            return f"\\\\wsl.localhost\\{cls.__distro_name}\\mnt\\wslg\\.X11-unix"
        elif EnvInfo.isWindowsHost():
            if EnvInfo.current_platform == "WSL":
                # Mount point from a WSL shell context
                return f"/mnt/wslg/.X11-unix"
            else:
                # From a Windows context, a WSL distro should have been supply during GUI (X11 sharing) checks
                logger.debug(f"No WSL distro have been previously found: '{cls.__distro_name}'")
                raise CancelOperation("Exegol tried to create a container with X11 sharing on a Windows host "
                                      "without having performed the availability tests before.")
        elif EnvInfo.isMacHost():
            # Docker desktop don't support UNIX socket through volume, we are using XQuartz over the network until then
            return None
        # Other distributions (Linux / Mac) have the default socket path
        return cls.default_x11_path

    @classmethod
    def getWaylandSocketPath(cls) -> Optional[Path]:
        """
        Get the host path of the Wayland socket
        :return:
        """
        wayland_dir = os.getenv("XDG_RUNTIME_DIR")
        wayland_socket = os.getenv("WAYLAND_DISPLAY")
        if wayland_dir is None or wayland_socket is None:
            return None
        return Path(wayland_dir, wayland_socket)

    @classmethod
    def getDisplayEnv(cls) -> str:
        """
        Get the current DISPLAY environment to access X11 socket
        :return:
        """
        if EnvInfo.isMacHost():
            # xquartz Mac mode
            return "host.docker.internal:0"

        # Add ENV check is case of user don't have it, which will mess up GUI (X11 sharing) if fallback does not work
        # @see https://github.com/ThePorgs/Exegol/issues/148
        if not EnvInfo.is_windows_shell:
            if os.getenv("DISPLAY") is None:
                logger.warning("The DISPLAY environment variable is not set on your host. This can prevent GUI apps to start through X11 sharing")

        # DISPLAY var is fetch from the current user environment. If it doesn't exist, using ':0'.
        return os.getenv('DISPLAY', ":0")

    @classmethod
    def getWaylandEnv(cls) -> str:
        """
        Get the current WAYLAND_DISPLAY environment to access wayland socket
        :return:
        """
        return os.getenv('WAYLAND_DISPLAY', 'wayland-0')

    # # # # # # Mac specific methods # # # # # #

    @classmethod
    def __macGuiChecks(cls) -> bool:
        """
        Procedure to check if the Mac host supports GUI (X11 sharing) with docker through XQuartz
        :return: bool
        """
        if not cls.__isXQuartzInstalled():
            logger.warning("Display sharing is [orange3]not supported[/orange3] on your mac without XQuartz installed. "
                           "You need to manually install [turquoise2]XQuartz[/turquoise2] and check the configuration 'Allow connections from network clients'.")
            return False
        logger.debug("XQuartz detected.")
        if not cls.__xquartzAllowNetworkClients():
            # Notify user to change configuration
            logger.error("XQuartz does not allow network connections. "
                         "You need to manually change the configuration to 'Allow connections from network clients'")
            # Add sys.platform check to exclude windows env (fix for mypy static code analysis)
            if sys.platform != "win32" and os.getuid() == 0:
                logger.warning("You are running exegol as [red]root[/red]! The root user cannot check in the user context whether XQuartz is properly configured or not.")
            return False

        # Check if XQuartz is started, check is dir exist and if there is at least one socket
        if not cls.__isXQuartzRunning():
            if not cls.__startXQuartz():
                logger.warning("Unable to start XQuartz service.")
                return False

        # The /tmp config is not necessary until you can use the unix socket with docker-desktop volume
        # Check if Docker Desktop is configured with /tmp in Docker Desktop > Preferences > Resources > File Sharing
        #if EnvInfo.isDockerDesktop() and not cls.__checkDockerDesktopResourcesConfig():
        #    logger.warning("Display sharing not possible, Docker Desktop configuration is incorrect. Please add /tmp in "
        #                   "[magenta]Docker Desktop > Preferences > Resources > File Sharing[/magenta]")
        #    return False
        return True

    @staticmethod
    def __checkDockerDesktopResourcesConfig() -> bool:
        """
            Check if Docker Desktop for macOS is configured correctly, allowing
            /tmp to be bind mounted into Docker containers, which is needed to
             mount /tmp/.X11-unix for display sharing.
             Return True if the configuration is correct and /tmp is part of the whitelisted resources
        """
        # Function not used for now because the X11 socket cannot be used for now with Docker Desktop
        docker_config = EnvInfo.getDockerDesktopResources()
        logger.debug(f"Docker Desktop configuration filesharingDirectories: {docker_config}")
        return '/tmp' in docker_config

    @staticmethod
    def __isXQuartzInstalled() -> bool:
        return 'xquartz' in os.getenv('DISPLAY', "").lower()

    @staticmethod
    def __xquartzAllowNetworkClients() -> bool:
        # defaults read org.xquartz.X11.plist nolisten_tcp
        conf_check = subprocess.run(["defaults", "read", "org.xquartz.X11.plist", "nolisten_tcp"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        logger.debug(f"XQuartz nolisten_tcp config: '{conf_check.stdout.strip().decode('utf-8')}'")
        return conf_check.stdout.strip() == b'0'

    @classmethod
    def __isXQuartzRunning(cls) -> bool:
        """
        Check if xquartz service is up by testing sockets
        """
        socket_path = Path(cls.default_x11_path)
        socket_x11_found = False
        if socket_path.is_dir():
            for file in socket_path.glob("*"):
                if file.is_socket():
                    socket_x11_found = True
                    break
        return socket_x11_found

    @staticmethod
    def __startXQuartz() -> bool:
        xhost_path = shutil.which("xhost")
        if not xhost_path:
            logger.error("xhost command not found, check your XQuartz installation")
            return False
        # Starting xquartz
        logger.debug("Starting XQuartz using xhost command")
        with console.status(f"Starting [green]XQuartz[/green]...", spinner_style="blue"):
            run_xhost = subprocess.run([xhost_path], shell=True,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        return run_xhost.returncode == 0

    # # # # # # Windows specific methods # # # # # #

    @classmethod
    def __windowsGuiChecks(cls) -> bool:
        """
        Procedure to check if the Windows host supports GUI (X11 sharing) with docker through WSLg
        :return: bool
        """
        logger.debug("Testing WSLg availability")
        # WSL + WSLg must be available on the Windows host for the GUI to work through X11 sharing
        if not cls.__wsl_available():
            if sys.platform != "win32" and os.getuid() == 0:
                logger.critical("You are running exegol as [red]root[/red]! The root user cannot be used to run Exegol on a Windows environment.")
            logger.error("WSL is [orange3]not available[/orange3] on your system. X11 sharing is not supported.")
            return False
        logger.debug("WSL is [green]available[/green] on the local system")
        # Only WSL2 support WSLg
        if EnvInfo.getDockerEngine() != EnvInfo.DockerEngine.WSL2:
            logger.debug(f"Docker current engine: {EnvInfo.getDockerEngine().value}")
            logger.error("Docker must be run with [orange3]WSL2[/orange3] engine in order to support X11 sharing (i.e. GUI apps).")
            return False
        logger.debug("Docker is using [green]WSL2[/green]")
        # X11 socket can only be shared from a WSL (to find WSLg mount point)
        if EnvInfo.current_platform != "WSL":
            logger.debug("Exegol is running from a Windows context (e.g. Powershell), a WSL instance must be found to share the WSLg X11 socket")
            cls.__distro_name = cls.__find_wsl_distro()
            logger.debug(f"Set WSL Distro as: '{cls.__distro_name}'")
            # If no WSL is found, propose to continue without GUI (X11 sharing)
            if not cls.__distro_name and not Confirm(
                    "Do you want to continue [orange3]without[/orange3] X11 sharing (i.e. GUI support)?", default=True):
                raise KeyboardInterrupt
        else:
            logger.debug("Using current WSL context for X11 socket sharing")
        if cls.__wslg_installed():
            logger.debug("WSLg seems to be installed.")
            return True
        elif cls.__wslg_eligible():
            logger.info("[green]WSLg[/green] is available on your system but [orange3]not installed[/orange3].")
            logger.info("Make sure, your Windows is [green]up-to-date[/green] and [green]WSLg[/green] is installed on "
                        "your host by running 'wsl --update' as [orange3]admin[/orange3].")
            return False
        logger.debug("WSLg is [orange3]not available[/orange3]")
        logger.warning("Display sharing is [orange3]not supported[/orange3] on your version of Windows. "
                       "You need to upgrade to [turquoise2]Windows 10+[/turquoise2].")
        return False

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
                logger.warning("wsl.exe seems to be unavailable on your system.")
                return False
            if name is None:
                logger.debug(f"Running: wsl.exe test -f {path}")
                ret = subprocess.run(["wsl.exe", "test", "-f", path])
            else:
                logger.debug(f"Running: wsl.exe test -d {name} -f {path}")
                ret = subprocess.run(["wsl.exe", "-d", name, "test", "-f", path])
            return ret.returncode == 0
        logger.debug("Trying to run a WSL test without Windows?")
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

        Tests the existence of WSL by searching in the default WSL first.
        However, if the default wsl is 'docker-desktop-data', the result will be false, so you have to test with docker-desktop.
        """
        if EnvInfo.isWindowsHost():
            wsl = shutil.which("wsl.exe")
            if not wsl:
                logger.debug("wsl.exe not found on the local system.")
                return False
            logger.debug("running: wsl.exe --status")
            ret = subprocess.Popen(["wsl.exe", "--status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ret.wait()
            if ret.returncode == 0:
                return True
            else:
                logger.debug(f"wsl.exe --status return code {ret.returncode}")
                logger.debug(str(ret.stdout))
                logger.debug(str(ret.stderr))
        logger.debug("WSL status command failed.. Trying a fallback check method.")
        return cls.__wsl_test("/etc/os-release", name=None) or cls.__wsl_test("/etc/os-release")

    @classmethod
    def __wslg_installed(cls) -> bool:
        """
        Check if WSLg is installed and deploy inside a WSL image by testing if the file wslg/versions.txt exist.
        :return: bool
        """
        if EnvInfo.current_platform == "WSL":
            if (Path("/mnt/host/wslg/versions.txt").is_file() or
                    Path("/mnt/wslg/versions.txt").is_file()):
                return True
            logger.debug("Unable to find WSLg locally.. Check /mnt/wslg/ or /mnt/host/wslg/")
        else:
            if (cls.__wsl_test("/mnt/host/wslg/versions.txt", name=cls.__distro_name) or
                    cls.__wsl_test("/mnt/wslg/versions.txt", name=cls.__distro_name)):
                return True
            logger.debug(f"Unable to find WSLg.. Check /mnt/wslg/ or /mnt/host/wslg/ on {cls.__distro_name}")
        logger.debug("WSLg check failed.. Trying a fallback check method.")
        return cls.__wsl_test("/mnt/host/wslg/versions.txt") or cls.__wsl_test("/mnt/wslg/versions.txt", name=None)

    @staticmethod
    def __wslg_eligible() -> bool:
        """
        Check if the current Windows version support WSLg
        :return:
        """
        if EnvInfo.current_platform == "WSL":
            # WSL is only available on Windows 10 & 11 so WSLg can be installed.
            return True
        try:
            os_version_raw, _, build_number_raw = EnvInfo.getWindowsRelease().split('.')[:3]
            os_version = int(os_version_raw)
        except ValueError:
            logger.debug(f"Impossible to find the version of windows: '{EnvInfo.getWindowsRelease()}'")
            logger.error("Exegol can't know if your [orange3]version of Windows[/orange3] can support dockerized GUIs (X11 sharing).")
            return False
        # Available for Windows 10 & 11
        if os_version >= 10:
            return True
        logger.debug(f"Current version of Windows doesn't support WSLg: {os_version_raw}.?.{build_number_raw}")
        return False

    @classmethod
    def __find_wsl_distro(cls) -> str:
        distro_name = ""
        # these distros cannot be used to load WSLg socket
        blacklisted_distro = ["docker-desktop", "docker-desktop-data"]
        logger.debug("Running: C:\\Windows\\system32\\wsl.exe -l")
        ret = subprocess.Popen(["C:\\Windows\\system32\\wsl.exe", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                            f"The '{name}' WSL distribution can be used to [green]enable X11 sharing[/green] (i.e. GUI apps) on exegol but the docker integration is [orange3]not enabled[/orange3].")
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
        logger.debug("Running: C:\\Windows\\system32\\wsl.exe --install -d Ubuntu")
        ret = subprocess.Popen(["C:\\Windows\\system32\\wsl.exe", "--install", "-d", "Ubuntu"], stderr=subprocess.PIPE)
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
            # Check if docker have default docker integration
            docker_settings = EnvInfo.getDockerDesktopSettings()
            if docker_settings is not None and docker_settings.get("EnableIntegrationWithDefaultWslDistro", docker_settings.get("enableIntegrationWithDefaultWslDistro", False)):
                logger.verbose("Set WSL Ubuntu as default to automatically enable docker integration")
                logger.debug("Running: C:\\Windows\\system32\\wsl.exe -s Ubuntu")
                # Set new WSL distribution as default to start it and enable docker integration
                ret = subprocess.Popen(["C:\\Windows\\system32\\wsl.exe", "-s", "Ubuntu"], stderr=subprocess.PIPE)
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
                logger.info("Enable WSL Docker integration for the newly created WSL in: [magenta]Docker Desktop > Settings > Resources > WSL Integration[/magenta]")
                if not Confirm("Has the WSL Ubuntu docker integration been [red]manually[/red] activated?",
                               default=True):
                    return False
            logger.success("WSL 'Ubuntu' successfully created with docker integration")
            return True
