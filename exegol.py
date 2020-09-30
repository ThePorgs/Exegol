import argparse
import docker
import os

# BRANCH is either 'dev'  or 'master'
BRANCH = 'dev'

'''
TODO:
- add colored logging with the --verbose option and replace all the print('[+] Whatever')
- replace all the os.system('docker whatever') with the equivalent with the docker-py lib if possible (except those that are a PITA)
- add the 'info' positionnal arg
    - get the current status of exegol (running, with gui or not, ...)
    - ask if exegol is up to date (compare the hashes of the image from local build and dockerhub ?)
    - get info like the size of it and so on
- add the 'purge' or 'uninstall' positionnal argument to completely remove exegol (ask for confirmation)
- find out why 'stop' is so long, it wasn't before the big update

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

def get_options():
    parser = argparse.ArgumentParser(description='Exegol wrapper', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--no-default', dest='detached', action='store_true', default=True, help='help')
    parser.add_argument('action', choices=['start', 'stop', 'reset', 'install', 'update', 'info'], help='help')
    # Install
    install_update = parser.add_argument_group('Install/update options')
    mode = install_update.add_argument('--mode', dest='mode', action='store', choices=['dockerhub', 'github'], default='dockerhub', help='help')
    # start
    start = parser.add_argument_group('Start options')
    gui = start.add_argument('--x11', dest='x11', action='store_true', default=True, help='help')

    device = start.add_argument('--device', dest='device', action='store', help='help')
    privileged = start.add_argument('--privileged', dest='privileged', action='store_true', default=False, help='help')
    options = parser.parse_args()
    # Update and install do the same thing
    if options.action == 'update':
        options.action = 'install'
    return options

def container_is_running():
    if client.containers.list(filters={'name': CONTAINER_NAME}):
        print('[+] Exegol container is running')
        return True
    else:
        print('[+] Exegol container is not running')
        return False

def container_exists():
    if client.containers.list(all=True, filters={'name': CONTAINER_NAME}):
        print('[+] Exegol container exists')
        return True
    else:
        print('[+] Exegol container does not exist')
        return False

def image_exists():
    if client.images.list(IMAGE_NAME + ':' + IMAGE_TAG):
        print('[+] Exegol image exists')
        return True
    else:
        print('[+] Exegol image does not exist')
        return False

def was_running_with_gui():
    container_info = client.api.inspect_container(CONTAINER_NAME)
    for var in container_info['Config']['Env']:
        if 'DISPLAY' in var:
            print('[+] Exegol was running with GUI')
            return True
    print('[+] Exegol was not running with GUI')
    return False

def was_running_with_privileged():
    ## TODO:
    return False

def was_running_with_device():
    ## TODO:
    return False

def start(options):
    if not container_is_running():
        if container_exists():
            print('[+] Resuming Exegol from last session')
            ## TODO: tell when last session was, this can be done with docker ps
            if was_running_with_device():
                ## TODO: tell which host device was shared
                print('[+] Exegol container was created with host device (INDICATE WHICH) sharing')
            if was_running_with_privileged ():
                print('[+] Exegol container was given extended privileges')
            if was_running_with_gui():
                print('[+] Exegol container was created with display sharing')
                os.system('docker start {}'.format(CONTAINER_NAME))
                print('[+] Running xhost command to enable display sharing')
                os.system('''xhost +local:`docker inspect --format='{}' {}`'''.format('{{ .Config.Hostname }}', CONTAINER_NAME))
            else:
                os.system('docker start {}'.format(CONTAINER_NAME))
        elif image_exists():
            print('[+] Creating and starting a container')
            cmd_options = ''
            if options.x11:
                print('[+] Enabling display sharing')
                cmd_options += ' --env DISPLAY=$$DISPLAY --volume /tmp/.X11-unix:/tmp/.X11-unix --env="QT_X11_NO_MITSHM=1"'
            if options.privileged:
                print('[+] Enabling extended privileges')
                cmd_options += ' --privileged'
            if options.device:
                print('[+] Enabling host device ({}) sharing'.format(options.device))
                cmd_options += ' --device {}'.format(options.device)
            os.system('docker run {} --interactive --tty --detach --network host --volume {}:/share --name {} --hostname "{}" {}:{}'.format(cmd_options, SHARE, CONTAINER_NAME, HOSTNAME, IMAGE_NAME, IMAGE_TAG))
            if options.x11:
                print('[+] Running xhost command to enable display sharing')
                os.system('''xhost +local:`docker inspect --format='{}' {}`'''.format('{{ .Config.Hostname }}', CONTAINER_NAME))
        else:
            print('[+] Exegol image should be installed first')
    print('[+] Entering Exegol')
    os.system('docker exec -ti {} zsh'.format(CONTAINER_NAME))

def stop(options):
    if container_is_running():
        print('[+] Stopping Exegol container')
        os.system('docker stop {}'.format(CONTAINER_NAME))

def reset(options):
    if container_exists():
        if container_is_running():
            print('[+] Stopping Exegol container')
            os.system('docker stop {}'.format(CONTAINER_NAME))
        print('[+] Deleting Exegol container')
        os.system('docker rm {}'.format(CONTAINER_NAME))

def install(options):
    if options.mode == 'dockerhub':
        print('[+] Pulling Exegol image from DockerHub')
        os.system('docker pull {}:{}'.format(IMAGE_NAME, IMAGE_TAG))
    elif options.mode == 'github':
        print('[+] Pulling sources from GitHub')
        os.system('git -C {} pull origin {}'.format(EXEGOL_PATH, BRANCH))
        print('[+] Building Exegol image from sources')
        os.system('docker build --no-cache --tag {}:{} {} | tee {}/.build.log'.format(IMAGE_NAME, IMAGE_TAG, EXEGOL_PATH,EXEGOL_PATH))

def info(options):
    os.system('docker ps -a | grep {}'.format(CONTAINER_NAME))

if __name__ == '__main__':
    IMAGE_TAG = 'dev' if BRANCH == 'dev' else 'latest'
    IMAGE_NAME = 'nwodtuhs/exegol'
    HOSTNAME = 'Exegol-dev' if BRANCH == 'dev' else 'Exegol'
    CONTAINER_NAME = 'exegol-' + IMAGE_TAG
    EXEGOL_PATH = os.getcwd()
    SHARE = EXEGOL_PATH + 'shared-volume'

    client = docker.from_env()

    options = get_options()

    print('[+] Printing options: ' + str(options))
    globals()[options.action](options)
