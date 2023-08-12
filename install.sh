#!/bin/sh

# Environment status
if [ -r /etc/os-release ]; then
	. /etc/os-release
fi

check_dependencies() {
    while [ $# -gt 0 ]; do
        command -v "$1" > /dev/null 2>&1 || (echo "Missing $1" && exit 1)
    shift
    done

}

check_docker_right() {
    docker ps 1>/dev/null || (echo "Docker execution error for ${USER}" && exit 1)
}

cloning_repos() {
    git clone "https://github.com/ThePorgs/Exegol"
}

install_python_requirements() {
    if [ $ID = "debian" ] && [ $VERSION_ID -ge "12" ]; then
    python3 -m pip install --requirement "Exegol/requirements.txt" --break-system-packages
    else
    python3 -m pip install --requirement "Exegol/requirements.txt"
    fi
}

add_exegol_path() {
    cd Exegol && sudo ln -s "$(pwd)/exegol.py" "/usr/local/bin/exegol"
}

while [ $# -gt 0 ]; do
    case $1 in
        -v|--verbose)
            set -x
        ;;
    esac
shift
done

check_dependencies "git" "python3" "docker" "sudo"
check_docker_right
cloning_repos
install_python_requirements
add_exegol_path

### Run Exegol install 
exegol install