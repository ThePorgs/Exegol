#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
import subprocess

import docker
import requests
from dateutil import parser
from rich.table import Table
from rich import box
from rich.console import Console

VERSION = "3.1.5"

'''
# TODO :
- faire plus d'affichage de debug
- dans l'epilog, donner des exemples pour les devs et/ou faire une partie advanced usage dans le wiki, référencer le wiki dans le readme
- vérifier que le help est clair (dans le help, bien expliquer que le container-tag est un identifiant unique pour le container)
- nettoyer les variables et fonctions qui ne sont plus utilisées
- remove le default suivant ~l507 + ~l534 quand j'aurais dockertag == branch, la stable pointe vers master là : if dockertag == "": dockertag = "stable" (rename de master et stable vers main ?)
- revoir la gestion/montage des ressources, peut-être un container différent ?
- tester un exegol -m sources install et de nommer l'image sur un nom existant, voir le comportement
- l640 corriger default_git_branch
- edit --device option so that it can be called multiple times to share multiple devices, need to adapt the info_containers
- remove the eval() calls
'''


class Logger:
    def __init__(self, verbosity=0, quiet=False):
        self.verbosity = verbosity
        self.quiet = quiet

    def debug(self, message):
        if self.verbosity == 2:
            console.print("{}[DEBUG]{} {}".format("[yellow3]", "[/yellow3]", message), highlight=False)

    def verbose(self, message):
        if self.verbosity >= 1:
            console.print("{}[VERBOSE]{} {}".format("[blue]", "[/blue]", message), highlight=False)

    def info(self, message):
        if not self.quiet:
            console.print("{}[*]{} {}".format("[bold blue]", "[/bold blue]", message), highlight=False)

    def success(self, message):
        if not self.quiet:
            console.print("{}[+]{} {}".format("[bold green]", "[/bold green]", message), highlight=False)

    def warning(self, message):
        if not self.quiet:
            console.print("{}[-]{} {}".format("[bold orange3]", "[/bold orange3]", message), highlight=False)

    def error(self, message):
        if not self.quiet:
            console.print("{}[!]{} {}".format("[bold red]", "[/bold red]", message), highlight=False)


def get_options():
    description = "This Python script is a wrapper for Exegol. It can be used to easily manage Exegol on your machine."

    examples = {
        "install (↓ ~8GB max):": "exegol install",
        "check image updates:": "exegol info",
        "get a shell:\t": "exegol start",
        "get a tmux shell:": "exegol --shell tmux start",
        "use wifi/bluetooth:": "exegol --privileged start",
        "use a proxmark:": "exegol --device /dev/ttyACM0 start",
        "use a LOGITacker:": "exegol --device /dev/ttyACM0 start",
        "use an ACR122u:": "exegol --device /dev/bus/usb/ start",
        "use a Crazyradio PA:": "exegol --device /dev/bus/usb/ start",
    }

    epilog = "{}Examples:{}\n".format(GREEN, END)
    for example in examples.keys():
        epilog += "  {}\t{}\n".format(example, examples[example])

    actions = {
        "start": "automatically start, resume, create or enter an Exegol container",
        "stop": "stop an Exegol container in a saved state",
        "install": "install Exegol image (build or pull depending on the chosen install --mode)",
        "update": "update Exegol image (build or pull depending on the chosen update --mode)",
        "remove": "remove Exegol image(s) and/or container(s)",
        "info": "print info on containers and local & remote images (name, size, state, ...)",
        "version": "print current version",
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
    parser._positionals.title = "{}Required arguments{}".format("\033[1;32m", END)
    parser.add_argument("action", choices=actions.keys(), help=actions_help)
    parser.add_argument(
        "-k",
        "--insecure",
        dest="verify",
        action="store_false",
        default=True,
        required=False,
        help="Allow insecure server connections for web requests (default: False)",
    )

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
        "-s",
        "--shell",
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
        help="tag to use in the container name",
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
    advanced_start.add_argument(
        "-cwd",
        "--cwd-mount",
        dest="mount_current_dir",
        action="store_true",
        help="mount current dir to container's /workspace",
    )

    options = parser.parse_args()

    if not options.no_default:
        options.X11 = True
        options.host_network = True
        options.bind_resources = True
    options.action = options.action.replace("-", "")
    if options.action == "update":
        options.action = "install"
    return options


def container_exists(containertag):
    containers = client.containers.list(all=True, filters={"name": "exegol-" + containertag})
    for container in containers:
        if not container.name == "exegol-" + containertag:
            containers.remove(container)
    logger.debug("Containers with name {}: {}".format("exegol-" + containertag, str(len(containers))))
    if len(containers) > 1:
        logger.error("Something's wrong, you shouldn't have multiple containers with the same name...")
        exit(1)
    else:
        return bool(len(containers))


def was_created_with_gui(container):
    logger.debug(
        "Looking for the {} in the container {}".format("'DISPLAY' environment variable", container.attrs["Name"]))
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
    logger.debug("Looking for the {} in the container {}".format("'host' value in the 'Networks' attribute",
                                                                 container.attrs["Name"]))
    return ("host" in container.attrs["NetworkSettings"]["Networks"])


def container_analysis(container):
    if was_created_with_device(container):
        if options.device and options.device != was_created_with_device(container):
            logger.warning(
                "Container was created with another shared device ({}), you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account".format(
                    was_created_with_device(container)))
        else:
            logger.verbose(
                "Container was created with host device ({}) sharing".format(was_created_with_device(container)))
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
            "Container was not created with display sharing, you need to reset it and start it with the -x/--X11 "
            "option (or without --no-default) for it to be taken into account "
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
            os.mkdir(SHARED_RESOURCES)
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
    if options.mount_current_dir:
        logger.verbose("Sharing /workspace (container) ↔ {} (host)".format(os.getcwd()))
        advanced_options += " --volume {}:/workspace".format(os.getcwd())
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


# Exec command on host with output being printed with logger.debug() or logger.error()
def exec_popen(command):
    cmd = command.split()
    logger.debug("Running command on host with subprocess.Popen(): {}".format(str(cmd)))
    output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = output.communicate()
    if stdout is not None and not stdout == b"":
        for line in stdout.decode().strip().splitlines():
            logger.debug("{}(cmd stdout){}\t{}".format(BLUE, END, line))
    if stderr is not None and not stderr == b"":
        for line in stderr.decode().strip().splitlines():
            logger.error("{}(cmd stderr){}\t{}".format(RED, END, line))


def readable_size(size, precision=1):
    # https://stackoverflow.com/a/32009595
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    suffix_index = 0
    while size > 1024 and suffix_index < 4:
        suffix_index += 1  # increment the index of the suffix
        size = size / 1024.0  # apply the division
    return "%.*f%s" % (precision, size, suffixes[suffix_index])


# Exec command on host with output being printed without treatment
def exec_system(command):
    logger.debug("Running on host with os.system(): {}".format(command))
    os.system(command)


def select_containertag(local_git_branch):
    logger.info("No container tag (-t/--container-tag) supplied")

    info_containers()

    # default to local git branch or master if none
    if not local_git_branch:
        default_containertag = "master"
    else:
        default_containertag = local_git_branch

    # fetching containers
    containers = client.containers.list(all=True, filters={"name": "exegol-"})
    len_containers = len(containers)
    logger.debug("Available local containers: {}".format(len_containers))

    # default to last created container
    # TODO: need to find a way to default to the latest "used" container instead of "created"
    logger.debug("Fetching 'FinishedAt' attribute for each container")
    last_used_container_tag = ""
    if not len_containers == 0:
        finished_at = ""
        for container in containers:
            logger.debug("└── " + str(container.attrs["Name"]) + " → " + str(container.attrs["State"]["FinishedAt"]))
            this_finished_at = parser.parse(container.attrs["State"]["FinishedAt"])
            if finished_at:
                if this_finished_at >= finished_at:
                    finished_at = this_finished_at
                    last_used_container_tag = container.attrs["Name"].replace('/exegol-', '')
            else:
                last_used_container_tag = container.attrs["Name"].replace('/exegol-', '')
                finished_at = this_finished_at
        logger.debug("Last created container: {}".format(last_used_container_tag))
    if last_used_container_tag:
        default_containertag = last_used_container_tag

    # default to container that has the local dir mounted as volume
    logger.debug("Fetching volumes for each container")
    cwd_in_vol_container = ""
    if not len_containers == 0:
        for container in containers:
            volumes = []
            if container.attrs["HostConfig"]["Binds"]:
                for bind in container.attrs["HostConfig"]["Binds"]:
                    volumes.append(bind.split(":")[0])
            if container.attrs["HostConfig"]["Mounts"]:
                for mount in container.attrs["HostConfig"]["Mounts"]:
                    volumes.append(mount["VolumeOptions"]["DriverConfig"]["Options"]["device"])
            logger.debug("└── " + str(container.attrs["Name"]) + " → " + str(volumes))
            if os.getcwd() in volumes:
                cwd_in_vol_container = container.attrs["Name"].replace('/exegol-', '')
                logger.debug("Current dir is in volumes of container: {}".format(cwd_in_vol_container))
    if cwd_in_vol_container:
        default_containertag = cwd_in_vol_container

    containertags = []
    if not len_containers == 0:
        for container in containers:
            containertags.append(container.attrs["Name"].replace('/exegol-', ''))

    containertag = input(
        "{}[?]{} What container do you want to {} [default: {}]? ".format(BOLD_BLUE, END, options.action,
                                                                          default_containertag))

    if not containertag:
        options.containertag = default_containertag
    else:
        options.containertag = containertag


def start():
    global LOOP_PREVENTION
    len_images = len(client.images.list(IMAGE_NAME, filters={"dangling": False}))
    if not len_images == 0:
        if LOOP_PREVENTION == "":
            logger.success("{} Exegol images exist".format(len_images))
        if not options.containertag:
            select_containertag(LOCAL_GIT_BRANCH)
        if container_exists(options.containertag):
            if LOOP_PREVENTION == "" or LOOP_PREVENTION == "create":
                logger.success("Container exists")
            containers = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})
            for container in containers:
                if not container.name == "exegol-" + options.containertag:
                    containers.remove(container)
            container = containers[0]
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
                info_images()
                if LOCAL_GIT_BRANCH == "master":  # TODO: fix this crap when I'll have branch names that are equal to docker tags
                    default_dockertag = "stable"
                else:
                    default_dockertag = LOCAL_GIT_BRANCH
                imagetag = input(
                    "{}[?]{} What image do you want the container to create to be based upon [default: {}]? ".format(
                        BOLD_BLUE, END, default_dockertag))
                if not imagetag:
                    imagetag = default_dockertag
                if client.images.list(IMAGE_NAME + ":" + imagetag):
                    info_containers()
                    if options.containertag:
                        default_containertag = options.containertag
                    elif not container_exists(imagetag):
                        default_containertag = imagetag
                    else:
                        logger.error(f"Something's wrong. Please create a detailed issue with everything you did and are trying to do (https://github.com/ShutdownRepo/Exegol/issues)")
                        # When running start without supplying a container tag, there are multiple scenarios
                        # 1. if >= 1 container(s) exist(s), one will be chosen to start
                        # 2. else, a container is created, either using a supplied tag or using the imagetag
                        # The user shouldn't end up here.
                    client.containers.list(all=True, filters={"name": "exegol-"})
                    containertag = input(
                        "{}[?]{} What unique tag do you want to name your container with (one not in list above) [default: {}]? ".format(
                            BOLD_BLUE, END, default_containertag))
                    if containertag == "":
                        containertag = default_containertag
                    options.containertag = containertag
                    logger.info("Creating the container")
                    logger.debug("{} container based on the {} image".format("exegol-" + containertag,
                                                                             IMAGE_NAME + ":" + imagetag))
                    base_options, advanced_options = container_creation_options(options.containertag)
                    exec_popen("docker create {} {} {}:{}".format(base_options, advanced_options, IMAGE_NAME, imagetag))
                    LOOP_PREVENTION = "create"
                    start()
                else:
                    logger.warning("Image {} does not exist. You must supply a tag from the list above.".format(
                        IMAGE_NAME + ":" + imagetag))
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
    if not options.containertag:
        select_containertag(LOCAL_GIT_BRANCH)
    containers = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})
    for container in containers:
        if not container.name == "exegol-" + options.containertag:
            containers.remove(container)
    container = containers[0]
    if container.attrs["State"]["Status"] == "running":
        logger.info("Container is up")
        logger.info("Stopping container")
        exec_popen("docker stop --time 3 {}".format("exegol-" + options.containertag))
        containers = client.containers.list(all=True, filters={"name": "exegol-" + options.containertag})
        for container in containers:
            if not container.name == "exegol-" + options.containertag:
                containers.remove(container)
        container = containers[0]
        if container.attrs["State"]["Status"] == "running":
            logger.error("Container is still up, something went wrong...")
        else:
            logger.success("Container is down")
    else:
        logger.success("Container is down")


def remove_container():
    if not options.containertag:
        select_containertag(LOCAL_GIT_BRANCH)
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
    logger.info("Cleaning unused host directories (resources and empty data)")
    if os.path.isdir(SHARED_RESOURCES):
        logger.verbose("Host directory {} exists. Removing it...".format(SHARED_RESOURCES))
        try:
            shutil.rmtree(SHARED_RESOURCES)
        except PermissionError:
            logger.warning("I don't have the rights to remove {}".format(SHARED_RESOURCES))
        except:
            logger.error("Something else went wrong")
    if os.path.isdir(SHARED_DATA_VOLUMES + "/" + options.containertag):
        if len(os.listdir(SHARED_DATA_VOLUMES + "/" + options.containertag)) == 0:
            logger.verbose("Host directory {} exists and is empty. Removing...".format(
                SHARED_DATA_VOLUMES + "/" + options.containertag))
            try:
                shutil.rmtree(SHARED_DATA_VOLUMES + "/" + options.containertag)
            except PermissionError:
                logger.warning("I don't have the rights to remove {} (do it yourself)".format(
                    SHARED_DATA_VOLUMES + "/" + options.containertag))
            except:
                logger.error("Something else went wrong")


def install():
    info_images()
    if options.mode == "release":
        if LOCAL_GIT_BRANCH == "master":  # TODO: fix this crap when I'll have branch names that are equal to docker tags
            default_dockertag = "stable"
        else:
            default_dockertag = LOCAL_GIT_BRANCH
        dockertag = input(
            "{}[?]{} What remote image (tag) do you want to install/update [default: {}]? ".format(BOLD_BLUE, END,
                                                                                                   default_dockertag))
        if dockertag == "":
            dockertag = default_dockertag
        logger.debug("Fetching DockerHub images tags")
        remote_image_tags = []
        remote_images_request = requests.get(url="https://hub.docker.com/v2/repositories/{}/tags".format(IMAGE_NAME), verify=options.verify)
        for image in \
                eval(
                    remote_images_request.text.replace("true", "True").replace("false", "False").replace("null", '""'))[
                    "results"]:
            remote_image_tags.append(image["name"])
        if dockertag not in remote_image_tags:
            logger.warning("The supplied tag doesn't exist. You must use one from the previous list")
        else:
            logger.info("Pulling sources from GitHub (local changes won't be overwritten)")
            exec_system("git -C {} pull origin {}".format(EXEGOL_PATH, LOCAL_GIT_BRANCH))
            logger.info("Pulling {} from DockerHub".format(IMAGE_NAME + ":" + dockertag))
            exec_system("docker pull {}:{}".format(IMAGE_NAME, dockertag))
    elif options.mode == "sources":
        logger.debug("Fetching available GitHub branches")
        branches_request = requests.get(url="https://api.github.com/repos/ShutdownRepo/Exegol/branches", verify=options.verify)
        branches = eval(branches_request.text.replace("true", "True").replace("false", "False").replace("null", '""'))
        logger.info("Available GitHub branches")
        for branch in branches:
            logger.info(" •  {}".format(branch["name"]))
        default_branch = LOCAL_GIT_BRANCH
        branch = input(
            "{}[?]{} What branch do you want the code to be based upon [default: {}]? ".format(BOLD_BLUE, END,
                                                                                                   default_branch))
        if branch == "":
            branch = default_branch
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
                default_imagetag = "stable"
            else:
                default_imagetag = branch
            imagetag = input(
                "{}[?]{} What tag do you want to give to your Exegol image [default: {}]? ".format(BOLD_BLUE, END,
                                                                                                   default_imagetag))
            if not imagetag:
                imagetag = default_imagetag
            logger.info("Building Exegol image {} from sources".format(IMAGE_NAME + ":" + imagetag))
            exec_system(
                "docker build --no-cache --tag {}:{} {} | tee {}/.build.log".format(
                    IMAGE_NAME, imagetag, EXEGOL_PATH, EXEGOL_PATH
                )
            )


def remove_image():
    len_images = len(client.images.list(IMAGE_NAME, filters={"dangling": False}))
    logger.info("Available local images: {}".format(len_images))
    if not len_images == 0:
        info_images()
        imagetag = input("{}[?]{} What image do you want to remove (give tag)? ".format(BOLD_BLUE, END))
        if not client.images.list(IMAGE_NAME + ":" + imagetag):
            logger.warning("Image {} does not exist. You must supply a tag from the list above.".format(
                IMAGE_NAME + ":" + imagetag))
        else:
            logger.warning(
                "About to remove docker Image {}".format(IMAGE_NAME + ":" + imagetag)
            )
            confirmation = input(
                "{}[?]{} Are you sure you want to do this? [y/N] ".format(BOLD_ORANGE, END)
            )
            if confirmation == "y" or confirmation == "yes" or confirmation == "Y":
                logger.info("Deletion confirmed, proceeding")
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


def remove():
    # TODO: this needs to be improved to have the possibility to remove files, networks and so on related to Exegol,
    #  and improve for simultaneous multiple removals
    to_remove = input("{}[?]{} Do you want to remove container(s) or image(s) [C/i]? ".format(BOLD_BLUE, END))
    if to_remove.lower() == "c" or not to_remove:
        remove_container()
    elif to_remove.lower() == "i":
        remove_image()
    else:
        logger.warning("Invalid choice")


def info_images():
    images = []
    logger.info("Available images")
    remote_images = {}
    logger.debug("Fetching remote image tags, digests and sizes")
    try:
        remote_images_request = requests.get(url="https://hub.docker.com/v2/repositories/{}/tags".format(IMAGE_NAME), timeout=(5, 10), verify=options.verify)
        remote_images_list = json.loads(remote_images_request.text)
        for image in remote_images_list["results"]:
            tag = image["name"]
            digest = image["images"][0]["digest"]
            compressed_size = readable_size(image["full_size"])
            logger.debug("└── {} → {}...".format(tag, digest[:32]))
            remote_images[digest] = {"tag": tag, "compressed_size": compressed_size}
        notinstalled_remote_images = remote_images
        logger.debug("Fetching local image tags, digests (and other attributes)")
        local_images_list = client.images.list(IMAGE_NAME, filters={"dangling": False})
        for image in local_images_list:
            id = image.attrs["Id"].split(":")[1][:12]
            if not image.attrs["RepoTags"]:
                # TODO: investigate this, print those images as "layers"
                #  these are layers for other images
                real_size = readable_size(image.attrs["Size"])
                digest = image.attrs["Id"].replace("sha256:", "")
                images.append([id, "<none>", real_size, "local layer"])
            else:
                name, tag = image.attrs["RepoTags"][0].split(':')
                real_size = readable_size(image.attrs["Size"])

                if image.attrs["RepoDigests"]:  # If true, the image was pulled instead of built
                    digest = image.attrs["RepoDigests"][0].replace("{}@".format(IMAGE_NAME), "")

                    logger.debug("└── {} → {}...".format(tag, digest[:32]))
                    if digest in remote_images.keys():
                        images.append([id, tag, real_size, "remote ({}, {})".format("[green]up to date[/green]",
                                                                                    remote_images[digest][
                                                                                        "compressed_size"])])
                        notinstalled_remote_images.pop(digest)
                    else:
                        for key in remote_images:
                            if remote_images[key]["tag"] == tag:
                                remote_digest = key
                                break
                            else:  # This means the image was pulled but it doesn't exist anymore on DockerHub
                                remote_digest = ""
                        if remote_digest:
                            compressed_size = remote_images[remote_digest]["compressed_size"]
                            images.append([id, tag, real_size,
                                           "remote ({}, {})".format("[orange3]deprecated[/orange3]", compressed_size)])
                            notinstalled_remote_images.pop(remote_digest)
                        else:
                            images.append([id, tag, real_size, "remote ({})".format("[bright_black]discontinued["
                                                                                    "/bright_black]")])
                else:
                    images.append([id, tag, real_size, "local image"])
        for uninstalled_remote_image in notinstalled_remote_images.items():
            tag = uninstalled_remote_image[1]["tag"]
            compressed_size = uninstalled_remote_image[1]["compressed_size"]
            id = uninstalled_remote_image[0].split(":")[1][:12]
            images.append([id, tag, "[bright_black]N/A[/bright_black]",
                           "remote ({}, {})".format("[yellow3]not installed[/yellow3]", compressed_size)])
        images = sorted(images, key=lambda k: k[1])
        if options.verbosity == 0:
            table = Table(show_header=True, header_style="bold blue", border_style="blue", box=box.SIMPLE)
            table.add_column("Image tag")
            table.add_column("Real size")
            table.add_column("Type")
            for image in images:
                if image[1] != "<none>":
                    table.add_row(image[1], image[2], image[3])
        elif options.verbosity >= 1:
            table = Table(show_header=True, header_style="bold blue", border_style="grey35", box=box.SQUARE)
            table.add_column("Id")
            table.add_column("Image tag")
            table.add_column("Real size")
            table.add_column("Type")
            for image in images:
                table.add_row(image[0], image[1], image[2], image[3])
        console.print(table)
        print()
    except requests.exceptions.ConnectionError as err:
        logger.warning("Connection Error: you probably have no internet, skipping online queries")
        logger.warning(f"Error: {err}")


def info_containers():
    len_containers = len(client.containers.list(all=True, filters={"name": "exegol-"}))
    logger.info("Available local containers: {}".format(len_containers))
    containers = []
    for container in client.containers.list(all=True, filters={"name": "exegol-"}):
        id = container.attrs["Id"][:12]
        tag = container.attrs["Name"].replace('/exegol-', '')
        state = container.attrs["State"]["Status"]
        if state == "running":
            state = "[green]" + state + "[/green]"
        image = container.attrs["Config"]["Image"]
        logger.debug("Fetching details on containers creation")
        details = []
        if was_created_with_gui(container):
            details.append("--X11")
        if was_created_with_host_networking(container):
            details.append("--host-network")
        if was_created_with_device(container):
            details.append("--device {}".format(was_created_with_device(container)))
        if was_created_with_privileged(container):
            details.append("[orange3]--privileged[/orange3]")
        details = " ".join(details)
        logger.debug("Fetching volumes for each container")
        volumes = ""
        if container.attrs["HostConfig"]["Binds"]:
            for bind in container.attrs["HostConfig"]["Binds"]:
                volumes += bind.replace(":", " ↔ ") + "\n"
        if container.attrs["HostConfig"]["Mounts"]:
            for mount in container.attrs["HostConfig"]["Mounts"]:
                volumes += mount["VolumeOptions"]["DriverConfig"]["Options"]["device"]
                volumes += " ↔ "
                volumes += mount["Target"]
                volumes += "\n"
        containers.append([id, tag, state, image, details, volumes])

    if options.verbosity == 0:
        table = Table(show_header=True, header_style="bold blue", border_style="blue", box=box.SIMPLE)
        table.add_column("Container tag")
        table.add_column("State")
        table.add_column("Image (repo/image:tag)")
        table.add_column("Creation details")
        for container in containers:
            table.add_row(container[1], container[2], container[3], container[4])
    elif options.verbosity >= 1:
        table = Table(show_header=True, header_style="bold blue", border_style="grey35", box=box.SQUARE)
        table.add_column("Id")
        table.add_column("Container tag")
        table.add_column("State")
        table.add_column("Image (repo/image:tag)")
        table.add_column("Creation details")
        table.add_column("Binds & mounts")
        for container in containers:
            table.add_row(container[0], container[1], container[2], container[3], container[4], container[5])
    console.print(table)
    print()


def info():
    info_images()
    info_containers()

def version():
   logger.info(f"You are running version {VERSION}")

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

    IMAGE_NAME = "nwodtuhs/exegol"
    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))
    SHARED_DATA_VOLUMES = EXEGOL_PATH + "/shared-data-volumes"
    SHARED_RESOURCES = EXEGOL_PATH + "/shared-resources"

    options = get_options()
    logger = Logger(options.verbosity, options.quiet)
    console = Console()

    if not options.verify:
        requests.packages.urllib3.disable_warnings()
        logger.verbose("Disabling warnings of insecure connection for invalid certificates")
        requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
        logger.debug("Allowing the use of deprecated and weak cipher methods")
        try:
            requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
        except AttributeError:
            pass

    try:
        client = docker.from_env()
    except docker.errors.DockerException as e:
        if "ConnectionRefusedError" in str(e):
            logger.error("Connection to docker service API refused (your docker service is probably down)")
        elif "PermissionError" in str(e):
            logger.error("Connection to docker service API not allowed (you probably need higher privileges to run "
                         "docker, try to use sudo or to add your user to the 'docker' group)")
        else:
            logger.error(f"Some error occurred while calling the docker service API: {e}")
        exit(0)
    except Exception as e:
        logger.error(f"Some error occurred while calling the docker service API: {e}")

    # get working git branch
    LOCAL_GIT_BRANCH = \
        subprocess.Popen(f"git -C {EXEGOL_PATH} symbolic-ref --short -q HEAD".split(), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).communicate()[0].decode("utf-8").strip()
    if not LOCAL_GIT_BRANCH:
        logger.debug("No local git branch or error when fetching it, defaulting to 'master'")
        LOCAL_GIT_BRANCH = "master"
    else:
        logger.debug("Local git branch: {}".format(LOCAL_GIT_BRANCH))

    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))

    LOOP_PREVENTION = ""
    globals()[options.action]()
