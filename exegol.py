#!/usr/bin/env python3
## -*- coding: utf-8 -*-

import argparse
import docker
import os
import requests

# BRANCH is either 'dev'  or 'master'
BRANCH = 'dev'

'''
TODO:
- add descriptiong/epilog with argparse
- add to the 'info' positionnal arg
    - get info like the size of it and so on
- add the 'purge' or 'uninstall' positionnal argument to completely remove exegol (ask for confirmation)
- find out why 'stop' is so long, it wasn't before the big update
- manage the --no-default option, or find something else, to disabled default arguments (like display sharing).
However, this option has to NOT override other options so that we can do something like
$ python3 exegol.py --no-defaults --x11

---
OLD TRY for start() - docker exec zsh
containers = client.containers.list(filters={'name': CONTAINER_NAME})
if len(containers) != 1:
    print('There are multiple instances of ' + CONTAINER_NAME + ' running, I dont know what to do')
else:
    container = client.containers.list(filters={'name': CONTAINER_NAME})[0]
    out = container.exec_run('zsh -c echo hi', tty=True)
    print(out.output.decode())
    # Can't make an interactive shell right now, I don't know what to do
---
'''

class Logger:
    BOLD_GREEN = '\033[1;32m'
    BOLD_BLUE='\033[1;34m'
    BOLD_WHITE='\033[1;37m'
    BOLD_RED='\033[1;31m'
    BOLD_ORANGE = '\033[1;93m'
    END = '\033[0m'

    def __init__(self, verbose=False, quiet=False):
        self.verbose = verbose
        self.quiet = quiet

    def success(self, message):
        if not self.quiet:
            print('{}[+]{} {}'.format(self.BOLD_GREEN, self.END, message))

    def debug(self, message):
        if self.verbose:
            print('{}[*]{} {}'.format(self.BOLD_WHITE, self.END, message))

    def info(self, message):
        if not self.quiet:
            print('{}[*]{} {}'.format(self.BOLD_BLUE, self.END, message))

    def warning(self, message):
        if not self.quiet:
            print('{}[*]{} {}'.format(self.BOLD_ORANGE, self.END, message))

    def error(self, message):
        if not self.quiet:
            print('{}[!]{} {}'.format(self.BOLD_RED, self.END, message))

def get_options():
    description = 'Exegol wrapper'
    epilog = 'Exegol epilog'

    parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)

    actions = {
    'start': 'start and/or enter Exegol',
    'stop': 'stop Exegol in a saved state',
    'reset': 'remove the saved state, clean slate',
    'install': 'build or pull Exegol depending on the chosen install mode',
    'update': 'rebuild or pull Exegol depending on the chosen update mode',
    'info': 'print info on Exegol container and image and tell if the image is up to date',
    'uninstall': '[TODO] (danger) removes Exegol docker image'
    }

    actions_help = ''
    for action in actions.keys():
        actions_help += '{}\t\t{}\n'.format(action, actions[action])

    parser.add_argument('action', choices=actions.keys(), help=actions_help)
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False, help='show debug information')
    logging.add_argument('-q', '--quiet', dest='quiet', action='store_true', default=False, help='show no logging at all')
    install_update = parser.add_argument_group('Install/update options')
    mode = install_update.add_argument('-m', '--mode', dest='mode', action='store', choices=['dockerhub', 'github'], default='dockerhub', help='select from where to install/update Exegol')
    start = parser.add_argument_group('Start options')
    nodefault = start.add_argument('--no-default', dest='detached', action='store_true', default=True, help='[TODO] This is not coded yet, it should be used to remove default options')
    gui = start.add_argument('-X', '--X11', dest='X11', action='store_true', default=True, help='enable display sharing to run GUI-based applications (Default: True)')
    privileged = start.add_argument('-p', '--privileged', dest='privileged', action='store_true', default=False, help='give extended privileges to this container')
    device = start.add_argument('-d', '--device', dest='device', action='store', help='add a host device to the container')
    options = parser.parse_args()
    if options.action == 'update':
        options.action = 'install'
    return options


def container_is_running():
    logger.debug(client.containers.list(filters={'name': CONTAINER_NAME}))
    return bool(client.containers.list(filters={'name': CONTAINER_NAME}))

def container_exists():
    logger.debug(client.containers.list(all=True, filters={'name': CONTAINER_NAME}))
    return bool(client.containers.list(all=True, filters={'name': CONTAINER_NAME}))

def image_exists():
    logger.debug(client.images.list(IMAGE_NAME + ':' + IMAGE_TAG))
    return bool(client.images.list(IMAGE_NAME + ':' + IMAGE_TAG))

def was_running_with_gui():
    container_info = client.api.inspect_container(CONTAINER_NAME)
    for var in container_info['Config']['Env']:
        if 'DISPLAY' in var:
            return True
    return False

def was_running_with_privileged():
    ## TODO:
    return False

def was_running_with_device():
    ## TODO:
    return False

def host_exec(command):
    logger.debug('Running on host: {}'.format(command))
    os.system(command)


def start():
    if not container_is_running():
        logger.warning('Exegol container is down')
        if container_exists():
            logger.success('Exegol container exists')
            logger.info('Restarting the container')
            ## TODO: tell when last session was, this can be done with docker ps
            if was_running_with_device():
                ## TODO: tell which host device was shared
                logger.debug('Exegol container was created with host device (INDICATE WHICH) sharing')
            if was_running_with_privileged ():
                logger.warning('Exegol container was given extended privileges')
            if was_running_with_gui():
                logger.info('Exegol container was created with display sharing')
                host_exec('docker start {}'.format(CONTAINER_NAME))
                logger.info('Running xhost command to enable display sharing')
                host_exec('''xhost +local:`docker inspect --format='{}' {}`'''.format('{{ .Config.Hostname }}', CONTAINER_NAME))
            else:
                host_exec('docker start {}'.format(CONTAINER_NAME))
            if container_is_running():
                logger.success('Exegol container is up again')
            else:
                logger.warning('Exegol container is down')
                logger.error('Something went wrong...')
        elif image_exists():
            logger.warning('Exegol container does not exist')
            logger.info('Creating and starting a container')
            cmd_options = ''
            if options.x11:
                logger.info('Enabling display sharing')
                cmd_options += ' --env DISPLAY=$DISPLAY --volume /tmp/.X11-unix:/tmp/.X11-unix --env="QT_X11_NO_MITSHM=1"'
            if options.privileged:
                logger.warning('Enabling extended privileges')
                cmd_options += ' --privileged'
            if options.device:
                logger.debug('Enabling host device ({}) sharing'.format(options.device))
                cmd_options += ' --device {}'.format(options.device)
            host_exec('docker run {} --interactive --tty --detach --network host --volume {}:/share --name {} --hostname "{}" {}:{}'.format(cmd_options, SHARE, CONTAINER_NAME, HOSTNAME, IMAGE_NAME, IMAGE_TAG))
            if options.x11:
                logger.info('Running xhost command to enable display sharing')
                host_exec('''xhost +local:`docker inspect --format='{}' {}`'''.format('{{ .Config.Hostname }}', CONTAINER_NAME))
        else:
            logger.warning('Exegol image does not exist, you must install it first')
    else:
        logger.success('Exegol container is up')
    logger.info('Entering Exegol')
    host_exec('docker exec -ti {} zsh'.format(CONTAINER_NAME))

def stop():
    if container_is_running():
        logger.info('Exegol container is up')
        logger.info('Stopping Exegol container')
        host_exec('docker stop {}'.format(CONTAINER_NAME))
        if container_is_running():
            logger.error('Exegol container is up, something went wrong...')
        else:
            logger.success('Exegol container is down')
    else:
        logger.success('Exegol container is down')

def reset():
    if container_exists():
        logger.info('Exegol container exists')
        stop()
        logger.info('Deleting Exegol container')
        host_exec('docker rm {}'.format(CONTAINER_NAME))
        if container_exists():
            logger.error('Something went wrong...')
        else:
            logger.success('Exegol container does not exist anymore')
    else:
        logger.success('Exegol container does not exist')

def install():
    if options.mode == 'dockerhub':
        logger.info('Pulling Exegol image from DockerHub')
        host_exec('docker pull {}:{}'.format(IMAGE_NAME, IMAGE_TAG))
    elif options.mode == 'github':
        logger.info('Pulling sources from GitHub')
        host_exec('git -C {} pull origin {}'.format(EXEGOL_PATH, BRANCH))
        logger.info('Building Exegol image from sources')
        host_exec('docker build --no-cache --tag {}:{} {} | tee {}/.build.log'.format(IMAGE_NAME, IMAGE_TAG, EXEGOL_PATH,EXEGOL_PATH))

def uninstall():
    logger.error('Not coded yet')
    ## TODO:

def info():
    if image_exists():
        logger.info('Exegol image exists ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        if container_exists():
            logger.info('Exegol container exists ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        else:
            logger.info('Exegol container exists ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
        if container_is_running():
            logger.info('Exegol container is running ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        else:
            logger.info('Exegol container is running ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
        logger.debug('Fetching local image digest')
        container_info = client.api.inspect_container(CONTAINER_NAME)
        local_image_hash = container_info['Image']
        logger.debug('Local image digest: {}...'.format(local_image_hash[:32]))
        logger.debug('Fetching remote image digest')
        logger.debug('Fetching docker token first')
        token_request = requests.get(url='https://auth.docker.io/token?scope=repository:{}:pull&service=registry.docker.io'.format(IMAGE_NAME))
        token = eval(token_request.text)['token']
        logger.debug('Token: {}...'.format(token[:32]))
        headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json', 'Authorization': 'Bearer {}'.format(token)}
        remote_image_request = requests.get(url='https://registry.hub.docker.com/v2/{}/manifests/{}'.format(IMAGE_NAME, IMAGE_TAG), headers=headers)
        remote_image_hash = eval(remote_image_request.text)['config']['digest']
        logger.debug('Remote image digest: {}...'.format(remote_image_hash[:32]))
        logger.debug('Comparing digests')
        if local_image_hash == remote_image_hash:
            logger.info('Exegol image is up to date ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        else:
            logger.info('Exegol image is up to date ? {}'.format(logger.BOLD_RED + 'KO' + logger.END))
            logger.warning('Exegol image is not up to date, you should update it')
            ## TODO: add info to the user to tell what command to run and such
    else:
        logger.info('Exegol image exists ? {}'.format(logger.BOLD_RED + 'KO' + logger.END))
        logger.warning('Exegol image does not exist, you should install it')

if __name__ == '__main__':
    IMAGE_TAG = 'dev' if BRANCH == 'dev' else 'latest'
    IMAGE_NAME = 'nwodtuhs/exegol'
    HOSTNAME = 'Exegol-dev' if BRANCH == 'dev' else 'Exegol'
    CONTAINER_NAME = 'exegol-' + IMAGE_TAG
    EXEGOL_PATH = os.getcwd()
    SHARE = EXEGOL_PATH + 'shared-volume'

    client = docker.from_env()
    options = get_options()
    logger = Logger(options.verbose, options.quiet)

    logger.debug('Options: ' + str(options))

    globals()[options.action]()
