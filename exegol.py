import argparse
import subprocess

BRANCH = 'dev'
IMAGE_TAG = 'dev' if BRANCH == 'dev' else 'latest'
IMAGE_NAME = 'nwodtuhs/exegol'
HOSTNAME = 'Exegol-' + TAG

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
    if IMAGE_NAME + ':' + IMAGE_TAG in subprocess.check_output(['docker', 'ps']).decode():
        return True
    else:
        return False

def start(options):
    if is_running():
        print('is_running')
        #TODO

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
    print(options)
    globals()[options.action](options)
