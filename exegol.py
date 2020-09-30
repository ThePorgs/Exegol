import argparse
import docker

BRANCH = 'dev'

IMAGE_TAG = 'dev' if BRANCH == 'dev' else 'latest'
IMAGE_NAME = 'nwodtuhs/exegol'
HOSTNAME = 'Exegol-' + IMAGE_TAG
CONTAINER_NAME = 'exegol-' + IMAGE_TAG

client = docker.from_env()

'''
def start():
    if docker_not_running:
        if docker_image_exists:
            if was_running_with_gui:
                docker_start(options)
                xhost()
            else:
                docker_start(options)
        elif wants_gui:
            docker_run()
            xhost()
        else:
            docker_run()
    docker_exec()

def stop():
    if docker_is_running:
        docker_stop()

def reset():
    if docker_is_running:
        docker_stop()
        docker_rm()
    elif docker_image_exists:
        docker_rm()
'''

'''
Include a status positionnal arg : status / version or info ??
- get the current status of exegol (running, with gui or not, ...)
- ask if exegol is up to date (compare the hashes of the image from local build and dockerhub ?)
- get info like the size of it and so on
'''

def get_options():
    parser = argparse.ArgumentParser(description='Exegol wrapper', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--no-default', dest='detached', action='store_true', default=True, help='help')
    parser.add_argument('action', choices=['start', 'stop', 'reset', 'install', 'update'], help='help')
    # Install
    install_update = parser.add_argument_group('Install/update options')
    mode = install_update.add_argument('--mode', dest='mode', action='store', choices=['dockerhub', 'github'], default='dockerhub', help='help')
    # start
    start = parser.add_argument_group('Start options')
    gui = start.add_argument('--x11', dest='x11', action='store_true', default=True, help='help')
    device = start.add_argument('--device', dest='device', action='store', help='help')
    privileged = start.add_argument('--privileged', dest='privileged', action='store_true', default=False, help='help')
    options = parser.parse_args()
    return options

def is_running():
    if client.containers.list(filters={'name': CONTAINER_NAME}):
        return True
    else:
        False

def image_exists():
    if client.images.list(IMAGE_NAME + ':' + IMAGE_TAG):
        return True
    else:
        return False

def was_running_with_gui():
    container_info = client.api.inspect_container(CONTAINER_NAME)
    for var in container_info['Config']['Env']:
        if 'DISPLAY' in var:
            return True
    return False

def start(options):
    if not is_running():
        print('[+] Exegol is not running')
        if image_exists():
            print('[+] Exegol exists')
            if was_running_with_gui():
                print('[+] Exegol was running with GUI')
                #TODO
    else:
        print('[+] Exegol is running')
        containers = client.containers.list(filters={'name': CONTAINER_NAME})
        if len(containers) != 1:
            print('There are multiple instances of ' + CONTAINER_NAME + ' running, I dont know what to do')
        else:
            container = client.containers.list(filters={'name': CONTAINER_NAME})[0]
            out = container.exec_run('zsh -c echo hi', tty=True)
            print(out.output.decode())
            # Can't make an interactive shell right now, I don't know what to do

def stop(options):
    print('stop')
    #TODO

def install(options):
    print('install')
    #TODO

def update(options):
    print('update')
    #TODO

def reset(options):
    print('reset')
    #TODO

if __name__ == '__main__':
    options = get_options()
    print('[+] Printing options: ', end='')
    print(options)
    globals()[options.action](options)
