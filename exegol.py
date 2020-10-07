#!/usr/bin/env python3
## -*- coding: utf-8 -*-

import argparse
import docker
import os
import requests
import subprocess

# BRANCH is either 'dev' or 'master'
BRANCH = "dev"

"""
## DETAILED TODO LIST
- check if some docker calls can be done with with docker-py
- enable connections through SOCKS4a/5 or HTTP proxies so that all of Exegol can be used through that proxy, simulating a advanced internal offensive system (callable with a `--proxy` or `--socks` option)
- find a way to log commands and outputs for engagements: inspiration from https://github.com/TH3xACE/SCREEN_KILLER ?
- Check if the following freshly installed tools work nicely: bettercap, hostapd-wpe, iproute2, wifite2
- Tools to install: arjun, apksign, cfr, dex2jar, drozer, jre8-openjdk, jtool, p7zip, ripgrep, smali, zipalign, frida, adb, dns2tcp, revsocks, chisel, ssf, darkarmor,amber, tikitorch, rpc2socks
- share the /opt/resources folder to let the host easily access it : it seems to be impossible, see [this](https://github.com/moby/moby/issues/4361)
- write a wiki, with videos/GIFs ?
"""


class Logger:
    def __init__(self, verbosity=0, quiet=False):
        self.verbosity = verbosity
        self.quiet = quiet

    def debug(self, message):
        if self.verbosity == 2:
            print("{}[DEBUG]{} {}".format(YELLOW, END, message))

    def verbose(self, message):
        if self.verbosity >= 1:
            print("{}[VERBOSE]{} {}".format(BLUE, END, message))

    def info(self, message):
        if not self.quiet:
            print("{}[*]{} {}".format(BOLD_BLUE, END, message))

    def success(self, message):
        if not self.quiet:
            print("{}[+]{} {}".format(BOLD_GREEN, END, message))

    def warning(self, message):
        if not self.quiet:
            print("{}[-]{} {}".format(BOLD_ORANGE, END, message))

    def error(self, message):
        if not self.quiet:
            print("{}[!]{} {}".format(BOLD_RED, END, message))


def get_options():

    description = "This Python script is a wrapper for Exegol. It can be used to easily manage Exegol on your machine."

    examples = {
        "install (↓ ~6GB):": "exegol install",
        "get a shell:\t": "exegol start",
        "use wifi/bluetooth:": "exegol --privileged start",
        "use a proxmark:": "exegol --device /dev/ttyACM0 start",
        "check image updates:": "exegol info",
    }

    epilog = "{}Examples:{}\n".format(GREEN, END)
    for example in examples.keys():
        epilog += "  {}\t{}\n".format(example, examples[example])

    actions = {
        "start": "automatically start, resume, or enter Exegol",
        "stop": "stop Exegol in a saved state",
        "reset": "remove the saved state, clean slate (removes the container, not the image)",
        "install": "install Exegol image (build or pull depending on the chosen install --mode)",
        "update": "update Exegol image (build or pull depending on the chosen update --mode)",
        "info": "print info on Exegol container/image (up to date, size, state, ...)",
        "remove": "remove Exegol image",
    }

    modes = {
        "release": "(default) downloads a pre-built image (from DockerHub) (faster)",
        "sources": "builds from the sources in {} (the sources will first be updated from GitHub but local edits won't be overwritten)".format(
            EXEGOL_PATH
        ),
    }

    actions_help = ""
    for action in actions.keys():
        actions_help += "{}\t\t{}\n".format(action, actions[action])

    modes_help = ""
    for mode in modes.keys():
        modes_help += "{}\t\t{}\n".format(mode, modes[mode])

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Required arguments
    parser._positionals.title = "{}Required arguments{}".format(BOLD_GREEN, END)
    parser.add_argument("action", choices=actions.keys(), help=actions_help)

    # Optional arguments
    parser._optionals.title = "{}Optional arguments{}".format(BLUE, END)
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument(
        "-v",
        "--verbose",
        dest="verbosity",
        action="count",
        default=0,
        help="verbosity level (-v for verbose, -vv for debug)",
    )
    logging.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        default=False,
        help="show no information at all",
    )

    # Install/update options
    install_update = parser.add_argument_group(
        "{}Install/update options{}".format(BLUE, END)
    )
    install_update.add_argument(
        "-m",
        "--mode",
        dest="mode",
        action="store",
        choices=modes.keys(),
        default="release",
        help=modes_help,
    )

    # Default start options
    default_start = parser.add_argument_group(
        "{}Default start options{}".format(BLUE, END),
        description='The following options are enabled by default. They can all be disabled with the advanced option "--no-default". They can then be enabled back separately, for example "exegol --no-default --X11 start"',
    )
    default_start.add_argument(
        "-x",
        "--X11",
        dest="X11",
        action="store_true",
        help="enable display sharing to run GUI-based applications",
    )
    default_start.add_argument(
        "--host-network",
        dest="host_network",
        action="store_true",
        help="let the container share the host's networking namespace (the container shares the same interfaces and has the same adresses, needed for mitm6)",
    )

    # Advanced start options
    advanced_start = parser.add_argument_group(
        "{}Advanced start options{}".format(BLUE, END)
    )
    advanced_start.add_argument(
        "--no-default",
        dest="no_default",
        action="store_true",
        default=False,
        help="disable the default start options (e.g. --X11, --host-network)",
    )
    advanced_start.add_argument(
        "--privileged",
        dest="privileged",
        action="store_true",
        default=False,
        help="(dangerous) give extended privileges to this container (e.g. needed to mount things, to use wifi or bluetooth)",
    )
    advanced_start.add_argument(
        "-d",
        "--device",
        dest="device",
        action="store",
        help="add a host device to the container",
    )
    advanced_start.add_argument(
        "-c",
        "--custom-options",
        dest="custom_options",
        action="store",
        default="",
        help="specify custom options for the container creation (docker run)",
    )

    options = parser.parse_args()

    if not options.no_default:
        options.X11 = True
        options.host_network = True
    if options.action == "update":
        options.action = "install"
    return options


def image_exists():
    logger.debug("Images with name {}: {}".format(IMAGE_NAME + ":" + IMAGE_TAG, str(client.images.list(IMAGE_NAME + ":" + IMAGE_TAG))))
    return bool(client.images.list(IMAGE_NAME + ":" + IMAGE_TAG))


def container_is_running():
    logger.debug("Running containers with name {}: {}".format(CONTAINER_NAME, str(client.containers.list(filters={"name": CONTAINER_NAME}))))
    return bool(client.containers.list(filters={"name": CONTAINER_NAME}))


def container_exists():
    logger.debug("Containers with name {}: {}".format(CONTAINER_NAME, str(client.containers.list(all=True, filters={"name": CONTAINER_NAME}))))
    return bool(client.containers.list(all=True, filters={"name": CONTAINER_NAME}))


def was_created_with_gui():
    logger.debug("Looking for the {} in the container {}".format("DISPLAY environment variable", CONTAINER_NAME))
    container_info = client.api.inspect_container(CONTAINER_NAME)
    for var in container_info["Config"]["Env"]:
        if "DISPLAY" in var:
            return True
    return False


def was_created_with_privileged():
    logger.debug("Looking for the {} in the container {}".format("Privileged attribute", CONTAINER_NAME))
    return client.api.inspect_container(CONTAINER_NAME)["HostConfig"]["Privileged"]


def was_created_with_device():
    logger.debug("Looking for the {} in the container {}".format("Devices attribute", CONTAINER_NAME))
    if client.api.inspect_container(CONTAINER_NAME)["HostConfig"]["Devices"]:
        return client.api.inspect_container(CONTAINER_NAME)["HostConfig"]["Devices"][0]["PathOnHost"]
    else:
        return False


def was_created_with_host_networking():
    logger.debug("Looking for the {} in the container {}".format("'host' value in the Networks attribute", CONTAINER_NAME))
    return ("host" in client.api.inspect_container(CONTAINER_NAME)["NetworkSettings"]["Networks"])


def container_analysis():
    if was_created_with_device():
        if options.device and options.device != was_created_with_device():
            logger.warning("Exegol container was created with another shared device ({}), you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account".format(was_created_with_device()))
        else:
            logger.verbose("Exegol container was created with host device ({}) sharing".format(was_created_with_device()))
    elif options.device:
        logger.warning(
            "Exegol container was created with no device sharing, you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account"
        )

    if was_created_with_privileged():
        logger.warning("Exegol container was given extended privileges at its creation")
    elif options.privileged:
        logger.warning(
            "Exegol container was not given extended privileges at its creation, you need to reset it and start it with the -p/--privileged option for it to be taken into account"
        )

    if was_created_with_host_networking():
        logger.verbose("Exegol container was created with host networking")
    elif options.host_network:
        logger.warning(
            "Exegol container was not created with host networking, you need to reset it and start it with the --host-network (or without --no-default) option for it to be taken into account"
        )

    if was_created_with_gui():
        logger.verbose("Exegol container was created with display sharing")
    elif options.X11:
        logger.warning(
            "Exegol container was not created with display sharing, you need to reset it and start it with the -x/--X11 option (or without --no-default) for it to be taken into account"
        )


def container_creation_options():
    base_options = ""
    advanced_options = ""
    if options.X11:
        logger.verbose("Enabling display sharing")
        advanced_options += " --env DISPLAY={}".format(os.getenv("DISPLAY"))
        advanced_options += " --volume /tmp/.X11-unix:/tmp/.X11-unix"
        advanced_options += ' --env="QT_X11_NO_MITSHM=1"'
    if options.host_network:
        logger.verbose("Enabling host networking")
        advanced_options += " --network host"
    if options.privileged:
        logger.warning("Enabling extended privileges")
        advanced_options += " --privileged"
    if options.device:
        logger.verbose("Enabling host device ({}) sharing".format(options.device))
        advanced_options += " --device {}".format(options.device)
    if options.custom_options:
        logger.verbose("Specifying custom options: {}".format(options.custom_options))
        advanced_options += " " + options.custom_options
    base_options += " --interactive"
    base_options += " --tty"
    # base_options += ' --detach'
    base_options += " --volume {}:/share".format(SHARE_PATH)
    base_options += " --name {}".format(CONTAINER_NAME)
    base_options += " --hostname {}".format(HOSTNAME)
    return base_options, advanced_options


def exec_popen(command):
    cmd = command.split()
    logger.debug("Running command on host with subprocess.Popen(): {}".format(str(cmd)))
    output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = output.communicate()
    if not stdout == None and not stdout == b"":
        for line in stdout.decode().strip().splitlines():
            logger.debug("{}(cmd stdout){}\t{}".format(BLUE, END, line))
    if not stderr == None and not stderr == b"":
        for line in stderr.decode().strip().splitlines():
            logger.error("{}(cmd stderr){}\t{}".format(RED, END, line))


def exec_system(command):
    logger.debug("Running on host with os.system(): {}".format(command))
    os.system(command)


def info_container():
    if container_exists():
        logger.info("Container exists ? {}".format(OK))
        if was_created_with_gui():
            logger.info("├── display sharing ? {}".format(OK))
        else:
            logger.info("├── display sharing ? {}".format(KO))
        if was_created_with_device():
            logger.info("├── host device sharing ? {}".format(OK))
        else:
            logger.info("├── host device sharing ? {}".format(KO))
        if was_created_with_privileged():
            logger.info("├── extended privileged (dangerous) ? {}".format(OK))
        else:
            logger.info("├── extended privileged (dangerous) ? {}".format(KO))
        if was_created_with_host_networking():
            logger.info("└── host networking ? {}".format(OK))
        else:
            logger.info("└── host networking ? {}".format(KO))
    else:
        logger.info("Container exists ? {}".format(KO))
    if container_is_running():
        logger.info("Container is running ? {}".format(OK))
    else:
        logger.info("Container is running ? {}".format(KO))


def readable_size(size, precision=1):
    # https://stackoverflow.com/a/32009595
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1  # increment the index of the suffix
        size = size / 1024.0  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


def start():
    global LOOP_PREVENTION
    if image_exists():
        if LOOP_PREVENTION == "":
            logger.success("Exegol image exists")
        if container_exists():
            if LOOP_PREVENTION == "" or LOOP_PREVENTION == "create":
                logger.success("Exegol container exists")
            if container_is_running():
                if LOOP_PREVENTION == "exec":
                    logger.error("Loop prevention triggered. Something went wrong...")
                else:
                    logger.success("Exegol container is up")
                    container_analysis()
                    if was_created_with_gui():
                        logger.info("Running xhost command for display sharing")
                        exec_popen(
                            "xhost +local:{}".format(
                                client.api.inspect_container(CONTAINER_NAME)["Config"][
                                    "Hostname"
                                ]
                            )
                        )
                    logger.info("Entering Exegol")
                    exec_system("docker exec -ti {} zsh".format(CONTAINER_NAME))
                    LOOP_PREVENTION = "exec"
            else:
                if LOOP_PREVENTION == "start":
                    logger.error("Loop prevention triggered. Something went wrong...")
                else:
                    logger.warning("Exegol container is down")
                    logger.info("Starting the container")
                    exec_popen("docker start {}".format(CONTAINER_NAME))
                    LOOP_PREVENTION = "start"
                    start()
        else:
            if LOOP_PREVENTION == "create":
                logger.error("Loop prevention triggered. Something went wrong...")
            else:
                logger.warning("Exegol container does not exist")
                logger.info("Creating the container")
                base_options, advanced_options = container_creation_options()
                exec_popen(
                    "docker create {} {} {}:{}".format(
                        base_options, advanced_options, IMAGE_NAME, IMAGE_TAG
                    )
                )
                LOOP_PREVENTION = "create"
                start()
    else:
        if LOOP_PREVENTION == "install":
            logger.error("Loop prevention triggered. Something went wrong...")
        else:
            logger.warning("Exegol image does not exist, you must install it first")
            confirmation = input(
                "{}[?]{} Do you wish to install it now (↓ ~6GB)? [y/N] ".format(
                    BOLD_ORANGE, END
                )
            )
            if confirmation == "y" or confirmation == "yes" or confirmation == "Y":
                logger.success(
                    "Installation confirmed, proceeding"
                )
                install()
                LOOP_PREVENTION = "install"
                start()


def stop():
    if container_is_running():
        logger.info("Exegol container is up")
        logger.info("Stopping Exegol container")
        exec_popen("docker stop --time 3 {}".format(CONTAINER_NAME))
        if container_is_running():
            logger.error("Exegol container is up, something went wrong...")
        else:
            logger.success("Exegol container is down")
    else:
        logger.success("Exegol container is down")


def reset():
    if container_exists():
        logger.info("Exegol container exists")
        stop()
        logger.info("Deleting Exegol container")
        exec_popen("docker rm {}".format(CONTAINER_NAME))
        if container_exists():
            logger.error("Something went wrong...")
        else:
            logger.success("Exegol container does not exist anymore")
    else:
        logger.success("Exegol container does not exist")


def install():
    if options.mode == "release":
        logger.info("Pulling Exegol image from DockerHub")
        exec_system("docker pull {}:{}".format(IMAGE_NAME, IMAGE_TAG))
    elif options.mode == "sources":
        logger.info("Pulling sources from GitHub")
        exec_system("git -C {} pull origin {}".format(EXEGOL_PATH, BRANCH))
        logger.info("Building Exegol image from sources")
        exec_system(
            "docker build --no-cache --tag {}:{} {} | tee {}/.build.log".format(
                IMAGE_NAME, IMAGE_TAG, EXEGOL_PATH, EXEGOL_PATH
            )
        )


def remove():
    if image_exists():
        logger.info("Exegol image exists")
        logger.warning(
            "About to remove docker Image {}".format(IMAGE_NAME + ":" + IMAGE_TAG)
        )
        confirmation = input(
            "{}[?]{} Are you sure you want to do this? [y/N] ".format(BOLD_ORANGE, END)
        )
        if confirmation == "y" or confirmation == "yes" or confirmation == "Y":
            logger.info(
                "Deletion confirmed, removing {}".format(IMAGE_NAME + ":" + IMAGE_TAG)
            )
            reset()
            logger.info("Removing image {}".format(IMAGE_NAME + ":" + IMAGE_TAG))
            exec_popen("docker image rm {}".format(IMAGE_NAME + ":" + IMAGE_TAG))
            if image_exists():
                logger.error("Exegol image is still here, something is wrong...")
            else:
                logger.success("Exegol image has been successfully removed")
        else:
            logger.info("Deletion canceled")
    else:
        logger.success("Exegol image does not exist")


def info():
    if image_exists():
        logger.info("Image exists ? {}".format(OK))
        image_size = readable_size(
            client.images.list(IMAGE_NAME + ":" + IMAGE_TAG)[0].attrs["Size"]
        )
        logger.info("└── Image size: {}".format(BOLD_BLUE + image_size + END))
        info_container()
        logger.debug("Fetching local image digest")
        local_image_hash = client.images.list(IMAGE_NAME + ":" + IMAGE_TAG)[0].attrs[
            "Id"
        ]
        ## TODO: Handle multiple images ?
        logger.debug("Local image digest: {}...".format(local_image_hash[:32]))
        logger.debug("Fetching remote image digest")
        logger.debug("Fetching docker token first")
        token_request = requests.get(
            url="https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io".format(
                IMAGE_NAME
            )
        )
        token = eval(token_request.text)["token"]
        logger.debug("Token: {}...".format(token[:32]))
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            "Authorization": "Bearer {}".format(token),
        }
        remote_image_request = requests.get(
            url="https://registry.hub.docker.com/v2/{}/manifests/{}".format(
                IMAGE_NAME, IMAGE_TAG
            ),
            headers=headers,
        )
        remote_image_hash = eval(remote_image_request.text)["config"]["digest"]
        logger.debug("Remote image digest: {}...".format(remote_image_hash[:32]))
        logger.debug("Comparing digests")
        if local_image_hash == remote_image_hash:
            logger.info("Image is up to date ? {}".format(OK))
        else:
            logger.info("Image is up to date ? {}".format(KO))
            logger.warning("Exegol image is not up to date, you should update it")
    else:
        logger.info("Image exists ? {}".format(KO))
        info_container()
        logger.warning("Exegol image does not exist, you should install it")


if __name__ == "__main__":
    BOLD_GREEN = "\033[1;32m"
    BOLD_BLUE = "\033[1;34m"
    BOLD_WHITE = "\033[1;37m"
    BOLD_RED = "\033[1;31m"
    BOLD_ORANGE = "\033[1;93m"
    END = "\033[0m"
    BLUE = "\033[0;34m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    RED = "\033[0;31m"

    OK = BOLD_GREEN + "OK" + END
    KO = BOLD_ORANGE + "KO" + END

    IMAGE_TAG = "dev" if BRANCH == "dev" else "latest"
    IMAGE_NAME = "nwodtuhs/exegol"
    HOSTNAME = "Exegol-dev" if BRANCH == "dev" else "Exegol"
    CONTAINER_NAME = "exegol-" + IMAGE_TAG
    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))
    SHARE_PATH = EXEGOL_PATH + "/shared-volume"
    RESOURCES_PATH = EXEGOL_PATH + "/resources-volume"

    LOOP_PREVENTION = ""

    client = docker.from_env()
    options = get_options()
    logger = Logger(options.verbosity, options.quiet)

    globals()[options.action]()
