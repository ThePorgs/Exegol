#!/usr/bin/env python3
## -*- coding: utf-8 -*-

import argparse
import docker
import os
import requests
import subprocess

# BRANCH is either 'dev'  or 'master'
BRANCH = 'dev'

'''
## TODO LIST
- add descriptiong/epilog with argparse
- add to the 'info' positionnal arg
    - get info like the size of it and so on
- find out if CMD in dockerfile is why 'stop' is so long, it wasn't before the big update
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
    'remove': '[TODO] (danger) removes Exegol docker image'
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
    nodefault = start.add_argument('--no-default', dest='nodefault', action='store_true', default=False, help='Removes default options (e.g. -X/--X11)')
    gui = start.add_argument('-X', '--X11', dest='X11', action='store_true', help='enable display sharing to run GUI-based applications (Default: True)')
    privileged = start.add_argument('-p', '--privileged', dest='privileged', action='store_true', default=False, help='give extended privileges to this container')
    device = start.add_argument('-d', '--device', dest='device', action='store', help='add a host device to the container')
    options = parser.parse_args()
    if not options.nodefault:
        options.X11 = True
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
    return client.api.inspect_container(CONTAINER_NAME)['HostConfig']['Privileged']

def was_running_with_device():
    ## TODO: what happens if there are multiple devices
    if client.api.inspect_container(CONTAINER_NAME)['HostConfig']['Devices']:
        return client.api.inspect_container(CONTAINER_NAME)['HostConfig']['Devices'][0]['PathOnHost']
    else:
        return False

def exec_popen(command):
    logger.debug('Running on host with subprocess.Popen(): {}'.format(str(command.replace('  ', ' ').split(' '))))
    output = subprocess.Popen(command.replace('  ', ' ').split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = output.communicate()
    if not stdout == None and not stdout == b'':
        for line in stdout.decode().strip().split('\n'):
            logger.debug('(cmd stdout)\t{}'.format(line))
    if not stderr == None and not stderr == b'':
        for line in stderr.decode().strip().split('\n'):
            logger.error('(cmd stderr)\t{}'.format(logger.BOLD_RED + line + logger.END))

def exec_system(command):
    logger.debug('Running on host with os.system(): {}'.format(command))
    os.system(command)


def start():
    if not container_is_running():
        logger.warning('Exegol container is down')
        if container_exists():
            logger.success('Exegol container exists')
            logger.info('Restarting the container')
            ## TODO: tell when last session was, this can be done with docker ps
            if was_running_with_device():
                logger.warning('Exegol container was created with host device ({}) sharing'.format(was_running_with_device()))
            if was_running_with_privileged ():
                logger.warning('Exegol container was given extended privileges')
            if was_running_with_gui():
                logger.info('Exegol container was created with display sharing')
                exec_popen('docker start {}'.format(CONTAINER_NAME))
                logger.info('Running xhost command to enable display sharing')
                exec_popen('xhost +local:{}'.format(client.api.inspect_container(CONTAINER_NAME)['Config']['Hostname']))
            else:
                exec_popen('docker start {}'.format(CONTAINER_NAME))
            if container_is_running():
                logger.success('Exegol container is up again')
            else:
                logger.warning('Exegol container is down')
                logger.error('Something went wrong...')
        elif image_exists():
            logger.warning('Exegol container does not exist')
            logger.info('Exegol image exists')
            logger.info('Creating and starting a container')
            cmd_options = ''
            if options.X11:
                logger.info('Enabling display sharing')
                cmd_options += ' --env DISPLAY={} --volume /tmp/.X11-unix:/tmp/.X11-unix --env="QT_X11_NO_MITSHM=1"'.format(os.getenv('DISPLAY'))
            if options.privileged:
                logger.warning('Enabling extended privileges')
                cmd_options += ' --privileged'
            if options.device:
                logger.debug('Enabling host device ({}) sharing'.format(options.device))
                cmd_options += ' --device {}'.format(options.device)
            exec_popen('docker run {} --interactive --tty --detach --network host --volume {}:/share --name {} --hostname "{}" {}:{}'.format(cmd_options, SHARE, CONTAINER_NAME, HOSTNAME, IMAGE_NAME, IMAGE_TAG))
            if options.X11:
                logger.info('Running xhost command to enable display sharing')
                exec_popen('xhost +local:{}'.format(client.api.inspect_container(CONTAINER_NAME)['Config']['Hostname']))
        else:
            logger.warning('Exegol image does not exist, you must install it first')
            pass
    else:
        logger.success('Exegol container is up')
        if options.privileged and not was_running_with_privileged():
            logger.warning('Exegol container was not given extended privileges at its creation, you need to reset it and start it with the -p/--privileged option for it to be taken into account')
        if options.X11 and not was_running_with_gui():
            logger.warning('Exegol container was not created with display sharing, you need to reset it and start it with the -X/--X11 option for it to be taken into account')
        if options.device and not was_running_with_device():
            logger.warning('Exegol container was created with no device sharing, you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account')
        if options.device and was_running_with_device() and option.device != was_running_with_device():
            logger.warning('Exegol container was created with another shared device ({}), you need to reset it and start it with the -d/--device option, and the name of the device, for it to be taken into account'.format(was_running_with_device()))
            print('error')
    if container_is_running():
        logger.info('Entering Exegol')
        exec_system('docker exec -ti {} zsh'.format(CONTAINER_NAME))

def stop():
    if container_is_running():
        logger.info('Exegol container is up')
        logger.info('Stopping Exegol container')
        exec_popen('docker stop --time 1 {}'.format(CONTAINER_NAME))
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
        exec_popen('docker rm {}'.format(CONTAINER_NAME))
        if container_exists():
            logger.error('Something went wrong...')
        else:
            logger.success('Exegol container does not exist anymore')
    else:
        logger.success('Exegol container does not exist')

def install():
    if options.mode == 'dockerhub':
        logger.info('Pulling Exegol image from DockerHub')
        exec_system('docker pull {}:{}'.format(IMAGE_NAME, IMAGE_TAG))
    elif options.mode == 'github':
        logger.info('Pulling sources from GitHub')
        exec_system('git -C {} pull origin {}'.format(EXEGOL_PATH, BRANCH))
        logger.info('Building Exegol image from sources')
        exec_system('docker build --no-cache --tag {}:{} {} | tee {}/.build.log'.format(IMAGE_NAME, IMAGE_TAG, EXEGOL_PATH,EXEGOL_PATH))

def remove():
    if image_exists():
        logger.info('Exegol image exists')
        logger.warning('About to remove docker Image {}'.format(IMAGE_NAME + ':' + IMAGE_TAG))
        confirmation = input('{}[?]{} Are you sure you want to do this? [y/N] '.format(logger.BOLD_ORANGE, logger.END))
        if confirmation == 'y' or confirmation == 'yes' or confirmation == 'Y':
            logger.info('Deletion confirmed, removing {}'.format(IMAGE_NAME + ':' + IMAGE_TAG))
            exec_popen('docker image rm {}'.format(IMAGE_NAME + ':' + IMAGE_TAG))
            if image_exists():
                logger.error('Exegol image is still here, something is wrong...')
            else:
                logger.success('Exegol image has been successfully removed')
        else:
            logger.info('Canceled')
    else:
        logger.success('Exegol image does not exist')

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
        local_image_hash = client.images.list(IMAGE_NAME + ':' + IMAGE_TAG)[0].attrs['Id']
        ## TODO: Handle multiple images ?
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
            logger.info('Exegol image is up to date ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
            logger.warning('Exegol image is not up to date, you should update it')
    else:
        logger.info('Exegol image exists ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
        if container_exists():
            logger.info('Exegol container exists ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        else:
            logger.info('Exegol container exists ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
        if container_is_running():
            logger.info('Exegol container is running ? {}'.format(logger.BOLD_GREEN + 'OK' + logger.END))
        else:
            logger.info('Exegol container is running ? {}'.format(logger.BOLD_ORANGE + 'KO' + logger.END))
        logger.warning('Exegol image does not exist, you should install it')

if __name__ == '__main__':
    IMAGE_TAG = 'dev' if BRANCH == 'dev' else 'latest'
    IMAGE_NAME = 'nwodtuhs/exegol'
    HOSTNAME = 'Exegol-dev' if BRANCH == 'dev' else 'Exegol'
    CONTAINER_NAME = 'exegol-' + IMAGE_TAG
    EXEGOL_PATH = os.path.dirname(os.path.realpath(__file__))
    SHARE = EXEGOL_PATH + '/shared-volume'

    client = docker.from_env()
    options = get_options()
    logger = Logger(options.verbose, options.quiet)

    logger.debug('Options: ' + str(options))

    globals()[options.action]()
