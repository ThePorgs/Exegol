#!/bin/sh

# Environment status
if [ -r /etc/os-release ]; then
	. /etc/os-release
fi

if ! [ "$(command -v "sudo")" ]; then
    SUDO=""
else
    SUDO="sudo"
fi

if [ -z "$lsb_dist" ]; then
    if command -v brew >/dev/null 2>&1; then
        PACKAGE_MANAGER="brew"
        PACKAGE_MANAGER_INSTALL="brew install -y"
    else
        echo "Homebrew isn't install."
        echo "For install Exegol, pls refert to: https://exegol.readthedocs.io/en/latest/getting-started/install.html"
        exit 1
    fi
else
    case $ID in
        debian|ubuntu)
            PACKAGE_MANAGER="apt"
            PACKAGE_MANAGER_INSTALL="apt install -y"
            PACKAGE_MANAGER_UPDATE="apt update"
        ;;
        fedora)
            PACKAGE_MANAGER="dnf"
            PACKAGE_MANAGER_INSTALL="dnf install -y"
        ;;
        alpine)
            PACKAGE_MANAGER="apk"
            PACKAGE_MANAGER_INSTALL="apk add"
        ;;
        *)
            echo "Installer not support this version."
            echo "For install Exegol, pls refert to: https://exegol.readthedocs.io/en/latest/getting-started/install.html"
            exit 1
        ;;

    esac
fi

usage() {
    echo "Exegol installer script"
    echo "USAGE: ./install.sh [OPTION]"
    echo "OPTION:"
    echo "-v                verbose output"
    echo "--fix-install     download missing dependencies"
    echo "--help            print this help"
}

check_dependencies() {
    MISSING_DEPENDENCIES=0
    while [ $# -gt 0 ]; do
        if ! [ "$(command -v "$1")" ]; then
            echo "Missing $1"
            if [ "$FIX_INSTALL" = True ]; then
                echo "$PACKAGE_MANAGER_INSTALL"
                if [ "$PACKAGE_MANAGER" = "apt" ]; then
                    $PACKAGE_MANAGER_UPDATE
                fi
                $SUDO $PACKAGE_MANAGER_INSTALL "$1" 
            else
                MISSING_DEPENDENCIES=$( expr "$MISSING_DEPENDENCIES" + 1 )
            fi
        fi
    shift
    done

}

check_docker_right() {
    docker ps 1>/dev/null || (echo "Docker execution error for ${USER}" && exit 1)
}

cloning_repos() {
    exegol_dir=$(find . -name 'Exegol' -type d 2>/dev/null)
    if [ -z "$exegol_dir" ]; then
        git clone "https://github.com/ThePorgs/Exegol"
    else
        printf "Exegol already install here:\n\t%s\n", "$exegol_dir"
    fi
}

activate_venv() {
    python3 -m venv Exegol/ || echo "Error: cannot create venv"
    . Exegol/bin/activate
}

install_python_requirements() {
    python3 -m pip install --requirement "Exegol/requirements.txt"
}

add_exegol_path() {
    cd Exegol && sudo ln -s "$(pwd)/exegol.py" "/usr/local/bin/exegol"
}

while [ $# -gt 0 ]; do
    case $1 in
        -v|--verbose)
            set -x
        ;;
        --fix-install)
            FIX_INSTALL=True
        ;;
        --help)
            usage
            exit 0
        ;;
    esac
shift
done

check_dependencies "git" "python3" "python3-venv" "docker" "sudo"

if [ "$ID" = "alpine" ]; then
    check_dependencies "py3-pip"
else
    check_dependencies "python3-pip"
fi

if [ "$MISSING_DEPENDENCIES" -ge 1 ]; then
    echo "For fix missing package, add --fix-install"
    exit 1
fi
check_docker_right
cloning_repos
activate_venv
install_python_requirements
add_exegol_path

### Run Exegol install 
exegol install