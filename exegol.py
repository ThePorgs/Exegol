#!/usr/bin/env python3
## -*- coding: utf-8 -*-

import argparse
import docker
import os
import requests
import subprocess
import shutil
from tabulate import tabulate
import pandas as pd

'''
TODO LIST
- faire correspondre les noms de branche github avec le docker tag
- faire plus d'affichage de debug
- dans l'epilog, donner des exemples pour les devs et/ou faire une partie advanced usage dans le wiki, référencer le wiki dans le readme
- gérer les volumes partagés et leur nettoyage (prévoir une fonction de remove pour les containers en plus de la fonction de reset par exemple, ou intégrer une question à la fonction de reset qui va del le dossier?)
- vérifier que le help est clair (dans le help, bien expliquer que le container-tag est un identifiant unique pour le container)
- nettoyer les variables et fonctions qui ne sont plus utilisées
- remove le default suivant ~l507 + ~l534 quand l'image master sera faite : if dockertag == "": dockertag = "latest"
- revoir la gestion/montage des ressources, peut-être un container différent ? /shrug
'''

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
        "get a tmux shell:": "exegol -s tmux start",
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

    actions_help = ""
    for action in actions.keys():
        actions_help += "{}\t\t{}\n".format(action, actions[action])

    modes = {
        "release": "(default) downloads a pre-built image (from DockerHub) (faster)",
        "sources": "builds from the local sources in {} (pull from GitHub then docker build, local edits won't be overwritten)".format(
            EXEGOL_PATH
        )
    }

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
    default_start.add_argument(
        "--bind-resources",
        dest="bind_resources",
        action="store_true",
        help="mount the /opt/resources of the container in a subdirectory of host\'s {}".format(SHARED_RESOURCES)
    )
    default_start.add_argument(
        "--shell",
        "-s",
        dest="shell",
        action="store",
        choices={"zsh", "bash", "tmux"},
        default="zsh",
        help="select shell to start when entering Exegol (Default: zsh)",
    )

    # Advanced start options
    advanced_start = parser.add_argument_group(
        "{}Advanced start/stop/reset options{}".format(BLUE, END)
    )
    advanced_start.add_argument(
        "-t",
        "--container-tag",
        dest="containertag",
        action="store",
        help="Tag to use in the container name. This allows for multiple and separate containers",
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
        help="(dangerous) give extended privileges at the container creation (e.g. needed to mount things, to use wifi or bluetooth)",
    )
    advanced_start.add_argument(
        "-d",
        "--device",
        dest="device",
        action="store",
        help="add a host device at the container creation",
    )
    advanced_start.add_argument(
        "-c",
        "--custom-options",
        dest="custom_options",
        action="store",
        default="",
        help="specify custom options for the container creation",
    )

    options = parser.parse_args()

    if not options.no_default:
        options.X11 = True
        options.host_network = True
        options.bind_resources = True
    if options.action == "update":
        options.action = "install"
    return options


def container_exists(containertag):
    len_containers = len(client.containers.list(all=True, filters={"name": "exegol-" + containertag}))
    logger.debug("Containers with name {}: {}".format("exegol-" + containertag, str(len_containers)))
    if len_containers > 1:
        logger.error("Something's wrong, you shouldn't have multiple containers with the same name...")
    return bool(client.containers.list(all=True, filters={"name": "exegol-" + containertag}))


def was_created_with_gui(container):
    logger.debug("Looking for the {} in the container {}".format("'DISPLAY' environment variable", container.attrs["Name"]))
    container_info = container.attrs
    for var in container_info["Config"]["Env"]:
        if "DISPLAY" in var:
            return True
    return False


def was_created_with_privileged(container):
    logger.debug("Looking for the {} in the container {}".format("'Privileged' attribute", container.attrs["Name"]))
    return container.attrs["HostConfig"]["Privileged"]


def was_created_with_device(container):
    logger.debug("Looking for the {} in the container {}".format("'Devices' attribute", container.attrs["Name"]))
    if container.attrs["HostConfig"]["Devices"]:
        return container.attrs["HostConfig"]["Devices"][0]["PathOnHost"]
    else:
        return False


def was_created_with_host_networking(container):
    logger.debug("Looking for the {} in the container {}".format("'host' value in the 'Networks' attribute", container.attrs["Name"]))
    return ("host" in container.attrs["NetworkSettings"]["Networks"])


def container_analysis(container):
    if was_created_with_device(container):
        if options.device and options.device != was_created_with_device(container):
            logger.warning("Container was created with another shared device ({}), you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account".format(was_created_with_device()))
        else:
            logger.verbose("Container was created with host device ({}) sharing".format(was_created_with_device(container)))
    elif options.device:
        logger.warning(
            "Container was created with no device sharing, you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account"
        )

    if was_created_with_privileged(container):
        logger.warning("Container was given extended privileges at its creation")
    elif options.privileged:
        logger.warning(
            "Container was not given extended privileges at its creation, you need to reset it and start it with the -p/--privileged option for it to be taken into account"
        )

    if was_created_with_host_networking(container):
        logger.verbose("Container was created with host networking")
    elif options.host_network:
        logger.warning(
            "Container was not created with host networking, you need to reset it and start it with the --host-network (or without --no-default) option for it to be taken into account"
        )

    if was_created_with_gui(container):
        logger.verbose("Container was created with display sharing")
    elif options.X11:
        logger.warning(
            "Container was not created with display sharing, you need to reset it and start it with the -x/--X11 option (or without --no-default) for it to be taken into account"
        )


def container_creation_options(containertag):
    base_options = ""
    advanced_options = ""
    if options.X11:
        logger.verbose("Enabling display sharing")
        advanced_options += " --env DISPLAY=unix{}".format(os.getenv("DISPLAY"))
        advanced_options += " --volume /tmp/.X11-unix:/tmp/.X11-unix"
        advanced_options += ' --env="QT_X11_NO_MITSHM=1"'
    if options.host_network:
        logger.verbose("Enabling host networking")
        advanced_options += " --network host"
    if options.bind_resources:
        # TODO: find a solution for this, if two containers have differents resources, when I boot container A and B, B's resources will be overwriten with A's
        logger.verbose("Sharing /opt/resources (container) ↔ {} (host)".format(SHARED_RESOURCES))
        if not os.path.isdir(SHARED_RESOURCES):
            logger.debug("Host directory {} doesn\'t exist. Creating it...".format(SHARED_RESOURCES))
            os.mkdir(SHARED_RESOURCES )
        advanced_options += ' --mount '
        advanced_options += 'type=volume,'
        advanced_options += 'dst=/opt/resources,'
        advanced_options += 'volume-driver=local,'
        advanced_options += 'volume-opt=type=none,'
        advanced_options += 'volume-opt=o=bind,'
        advanced_options += 'volume-opt=device={}'.format(SHARED_RESOURCES)
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
    base_options += " --volume {}:/data".format(SHARED_DATA_VOLUMES + "/" + containertag)
    base_options += " --name {}".format("exegol-" + containertag)
    base_options += " --hostname {}".format("exegol-" + containertag)
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
    len_images = len(client.images.list(IMAGE_NAME))
    if not len_images == 0:
        if LOOP_PREVENTION == "":
            logger.success("{} Exegol images exist".format(len_images))
        if container_exists(options.containertag):
            if LOOP_PREVENTION == "" or LOOP_PREVENTION == "create":
                logger.success("Container exists")
            container = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})[0]
            if container.attrs["State"]["Status"] == "running":
                if LOOP_PREVENTION == "exec":
                    logger.debug("Loop prevention triggered")
                    logger.error("Something went wrong...")
                else:
                    logger.success("Container is up")
                    container_analysis(container)
                    if was_created_with_gui(container):
                        logger.info("Running xhost command for display sharing")
                        exec_popen(
                            "xhost +local:{}".format(
                                client.api.inspect_container("exegol-" + options.containertag)["Config"][
                                    "Hostname"
                                ]
                            )
                        )
                    logger.info("Entering Exegol")
                    exec_system("docker exec -ti {} {}".format("exegol-" + options.containertag, options.shell))
                    LOOP_PREVENTION = "exec"
            else:
                if LOOP_PREVENTION == "start":
                    logger.debug("Loop prevention triggered")
                    logger.error("Something went wrong...")
                else:
                    logger.warning("Container is down")
                    logger.info("Starting the container")
                    exec_popen("docker start {}".format("exegol-" + options.containertag))
                    LOOP_PREVENTION = "start"
                    start()
        else:
            if LOOP_PREVENTION == "create":
                logger.debug("Loop prevention triggered")
                logger.error("Something went wrong...")
            else:
                logger.warning("Container does not exist")
                logger.info("Available local images: {}".format(len_images))
                info_images()
                imagetag = input("{}[?]{} What image do you want the container to create to be based upon (give tag)? ".format(BOLD_BLUE, END))
                if client.images.list(IMAGE_NAME + ":" + imagetag):
                    len_containers = len(client.containers.list(all=True, filters={"name": "exegol-"}))
                    logger.info("Available local containers: {}".format(len_containers))
                    info_containers()
                    if not container_exists(imagetag):
                        default_containertag = imagetag
                    else:
                        default_containertag = options.containertag
                    client.containers.list(all=True, filters={"name": "exegol-"})
                    containertag = input("{}[?]{} What unique tag do you want to name your container with (one not in list above) [default: {}]? ".format(BOLD_BLUE, END, default_containertag))
                    if containertag == "":
                        containertag = imagetag
                    options.containertag = containertag
                    logger.info("Creating the container")
                    logger.debug("{} container based on the {} image".format("exegol-" + containertag, IMAGE_NAME + ":" + imagetag))
                    base_options, advanced_options = container_creation_options(options.containertag)
                    exec_popen("docker create {} {} {}:{}".format(base_options, advanced_options, IMAGE_NAME, imagetag))
                    LOOP_PREVENTION = "create"
                    start()
                else:
                    logger.warning("Image {} does not exist. You must supply a tag from the list above.".format(IMAGE_NAME + ":" + imagetag))
    else:
        if LOOP_PREVENTION == "install":
            logger.debug("Loop prevention triggered")
            logger.error("Something went wrong...")
        else:
            logger.warning("Exegol image does not exist, you must install it first")
            confirmation = input(
                "{}[?]{} Do you wish to install it now (↓ ~6GB)? [y/N] ".format(
                    BOLD_ORANGE, END
                )
            )
            if confirmation == "y" or confirmation == "yes" or confirmation == "Y":
                install()
                LOOP_PREVENTION = "install"
                start()


def stop():
    container = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})[0]
    if container.attrs["State"]["Status"] == "running":
        logger.info("Container is up")
        logger.info("Stopping container")
        exec_popen("docker stop --time 3 {}".format("exegol-" + options.containertag))
        container = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})[0]
        if container.attrs["State"]["Status"] == "running":
            logger.error("Container is still up, something went wrong...")
        else:
            logger.success("Container is down")
    else:
        logger.success("Container is down")

def reset():
    if container_exists(options.containertag):
        logger.info("Container exists")
        stop()
        logger.info("Deleting container")
        exec_popen("docker rm {}".format("exegol-" + options.containertag))
        if container_exists(options.containertag):
            logger.error("Something went wrong...")
        else:
            logger.success("Container does not exist anymore")
    else:
        logger.success("Container does not exist")
    if os.path.isdir(SHARED_RESOURCES):
        logger.debug("Host directory {} exists. Removing it...".format(SHARED_RESOURCES))
        shutil.rmtree(SHARED_RESOURCES, ignore_errors=True)


def install():
    len_images = len(client.images.list(IMAGE_NAME))
    logger.info("Available local images: {}".format(len_images))
    info_images()
    if options.mode == "release":
        logger.debug("Fetching DockerHub image tags")
        logger.debug("Obtaining token for DockerHub API queries")
        token_request = requests.get(
            url="https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io".format(
                IMAGE_NAME
            )
        )
        token = eval(token_request.text)["token"]
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
            "Authorization": "Bearer {}".format(token),
        }
        remote_image_request = requests.get(
            url="https://registry.hub.docker.com/v2/{}/tags/list".format(
                IMAGE_NAME
            ),
            headers=headers,
        )
        remote_image_tags = eval(remote_image_request.text)["tags"]
        logger.info("Available DockerHub remote images (tags)")
        for tag in remote_image_tags:
            logger.info(" •  {}".format(tag))
        print()
        dockertag = input("{}[?]{} What image (tag) do you want to install/update [default: latest]? ".format(BOLD_BLUE, END))
        if dockertag == "":
            dockertag = "latest"
        if dockertag not in remote_image_tags:
            logger.warning("The supplied tag doesn't exist. You must use one from the previous list")
        else:
            logger.info("Pulling {} from DockerHub".format(IMAGE_NAME + ":" + dockertag))
            exec_system("docker pull {}:{}".format(IMAGE_NAME, dockertag))
    elif options.mode == "sources":
        logger.debug("Fetching available GitHub branches")
        branches_request = requests.get(url="https://api.github.com/repos/ShutdownRepo/Exegol/branches")
        branches = eval(branches_request.text.replace("true", "True").replace("false", "False"))
        logger.info("Available GitHub branches")
        for branch in branches:
            logger.info(" •  {}".format(branch["name"]))
        branch = input("{}[?]{} What branch do you want the code to be based upon [default: master]? ".format(BOLD_BLUE, END))
        if branch == "":
            branch = "master"
        branch_in_branches = False
        for b in branches:
            if branch == b["name"]:
                branch_in_branches = True
        if not branch_in_branches:
            logger.warning("The supplied branch doesn't exist. You must use one from the previous list")
        else:
            logger.info("Pulling sources from GitHub (local changes won't be overwritten)")
            # TODO: not sure the following cmd is needed : exec_system("git -C {} checkout {}".format(EXEGOL_PATH, branch))
            exec_system("git -C {} pull origin {}".format(EXEGOL_PATH, branch))
            if branch == "master":
                default_imagetag = "latest"
            else:
                default_imagetag = branch
            imagetag = input("{}[?]{} What tag do you want to give to your Exegol image [default: {}]? ".format(BOLD_BLUE, END, default_imagetag))
            logger.info("Building Exegol image {} from sources".format(IMAGE_NAME + ":" + imagetag))
            exec_system(
                "docker build --no-cache --tag {}:{} {} | tee {}/.build.log".format(
                    IMAGE_NAME, imagetag, EXEGOL_PATH, EXEGOL_PATH
                )
            )


def remove():
    len_images = len(client.images.list(IMAGE_NAME))
    logger.info("Available local images: {}".format(len_images))
    if not len_images == 0:
        info_images()
        imagetag = input("{}[?]{} What image do you want to remove (give tag)? ".format(BOLD_BLUE, END))
        if not client.images.list(IMAGE_NAME + ":" + imagetag):
            logger.warning("Image {} does not exist. You must supply a tag from the list above.".format(IMAGE_NAME + ":" + imagetag))
        else:
            logger.warning(
                "About to remove docker Image {}".format(IMAGE_NAME + ":" + imagetag)
            )
            confirmation = input(
                "{}[?]{} Are you sure you want to do this? [y/N] ".format(BOLD_ORANGE, END)
            )
            if confirmation == "y" or confirmation == "yes" or confirmation == "Y":
                logger.info("Deletion confirmed, proceeding")
                reset()
                logger.info("Deleting image {}".format(IMAGE_NAME + ":" + imagetag))
                exec_system("docker image rm {}".format(IMAGE_NAME + ":" + imagetag))
                if client.images.list(IMAGE_NAME + ":" + imagetag):
                    logger.error("Exegol image is still here, something is wrong...")
                else:
                    logger.success("Exegol image has been successfully removed")
            else:
                logger.info("Deletion canceled")
    else:
        logger.info("No Exegol image here, ya messin with me?")


def info_images():
    images = []
    images.append(["IMAGE TAG", "SIZE", "TYPE", "UP TO DATE"])
    logger.debug("Obtaining token for DockerHub API queries")
    token_request = requests.get(
    url="https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io".format(
    IMAGE_NAME
    )
    )
    token = eval(token_request.text)["token"]
    for image in client.images.list(IMAGE_NAME):
        name, tag = image.attrs["RepoTags"][0].split(':')
        if image.attrs["RepoDigests"]:
            mode = "release"
            logger.debug("Fetching local image digest for image {}".format(IMAGE_NAME + ":" + tag))
            local_image_hash = image.attrs["Id"]
            logger.debug("└── {}...".format(local_image_hash[:32]))
            logger.debug("Fetching remote image digest for image {}".format(name + ":" + tag))
            headers = {
                "Accept": "application/vnd.docker.distribution.manifest.v2+json",
                "Authorization": "Bearer {}".format(token),
            }
            remote_image_request = requests.get(
                url="https://registry.hub.docker.com/v2/{}/manifests/{}".format(
                    name, tag
                ),
                headers=headers,
            )
            remote_image_hash = eval(remote_image_request.text)["config"]["digest"]
            logger.debug("└── {}...".format(remote_image_hash[:32]))
            if local_image_hash == remote_image_hash:
                uptodate = BOLD_GREEN + "yes" + END
            else:
                uptodate = BOLD_ORANGE + "no" + END
        else:
            mode = "sources"
            uptodate = ""
        size = readable_size(image.attrs["Size"])
        images.append([tag, size, mode, uptodate])

    df = pd.DataFrame(images[1:], columns=images[0])
    print(tabulate(df, headers='keys', tablefmt='psql', showindex="never"))
    print()


def info_containers():
    containers = []
    # TODO: move the host networking, shared display and such in a column "attributes" with values like 1100, 1101 and so on and explain that attributes=host net,shared display, ... this is fore pretty printing, I'm not sure I'll do this though, I like precision
    containers.append(["CONTAINER TAG", "STATE", "IMAGE (repo:image tag)", "HOST NETWORKING", "DISPLAY SHARING", "DEVICE SHARING", "PRIVILEGED"])
    for container in client.containers.list(all=True, filters={"name": "exegol-"}):
        tag = container.attrs["Name"].replace('/exegol-', '')
        state = container.attrs["State"]["Status"]
        if state == "running":
            state = BOLD_GREEN + state + END
        image = container.attrs["Config"]["Image"]
        display_sharing = "✓" if was_created_with_gui(container) else ""
        device_sharing = "✓" if was_created_with_device(container) else ""
        privileged = "✓" if was_created_with_privileged(container) else ""
        host_networking = "✓" if was_created_with_host_networking(container) else ""
        containers.append([tag, state, image, host_networking, display_sharing, device_sharing, privileged])

    df = pd.DataFrame(containers[1:], columns=containers[0])
    print(tabulate(df, headers='keys', tablefmt='psql', showindex="never"))
    print()

def test():
    c = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})
    print(c)

def info():
    len_images = len(client.images.list(IMAGE_NAME))
    logger.info("Available local images: {}".format(len_images))
    info_images()
    len_containers = len(client.containers.list(all=True, filters={"name": "exegol-"}))
    logger.info("Available local containers: {}".format(len_containers))
    info_containers()
    if len_images == 0:
        logger.warning("Exegol image does not exist, you should install it")
    elif len_containers == 0:
        logger.warning("You have at least one Exegol image lying aroung,you might as well use it ;)")


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

    IMAGE_NAME = "nwodtuhs/exegol"
    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))
    SHARED_DATA_VOLUMES = EXEGOL_PATH + "/shared-data-volumes"
    SHARED_RESOURCES = EXEGOL_PATH + "/shared-resources"

    client = docker.from_env()
    options = get_options()
    logger = Logger(options.verbosity, options.quiet)

    if not options.containertag:
        logger.debug("No container tag (-t/--container-tag) supplied")

        # get working git branch
        branch = subprocess.Popen(f"git -C {EXEGOL_PATH} symbolic-ref --short -q HEAD".split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].decode("utf-8").strip()
        if not branch:
            branch = "master"
        default_containertag = branch

        # get last used container
        containers = client.containers.list(all=True, filters={"name": "exegol-"})
        len_containers = len(containers)
        logger.debug("Available local containers: {}".format(len_containers))
        if not len_containers == 0:
            at = containers[0].attrs["State"]["FinishedAt"]
            finished_at = ""
            for container in containers:
                if finished_at:
                    this_finished_at = dateutil.parser.parse(container.attrs["State"]["FinishedAt"])
                    if this_finished_at >= finished_at:
                        finished_at = this_finished_at
                        last_used_container_tag = container.attrs["Name"].replace('/exegol-', '')
                else:
                    last_used_container_tag = container.attrs["Name"].replace('/exegol-', '')
            logger.debug("Last used container: {}".format(last_used_container_tag))
            default_containertag = last_used_container_tag

        logger.debug("Defaulting to the last used container, or working git branch if none, or 'master' if none")
        logger.debug("Container tag set to {}".format(branch))
        options.containertag = branch
    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))

    LOOP_PREVENTION = ""

    globals()[options.action]()
