#!/bin/sh

# Environment status
if [ -r /etc/os-release ]; then
	. /etc/os-release
fi

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
        local command_package="$1"
        if [ "$1" = "python3-pip" ] || [ "$1" = "py3-pip" ]; then
            command_package="pip"
        fi
        if ! [ "$(command -v "$command_package")" ]; then
            echo "Missing $1"
            if [ "$FIX_INSTALL" = True ]; then
                echo "$PACKAGE_MANAGER_INSTALL"
                if [ "$PACKAGE_MANAGER" = "apt" ]; then
                    sudo $PACKAGE_MANAGER_UPDATE
                fi
                sudo $PACKAGE_MANAGER_INSTALL "$1" 
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

check_dependencies "git" "python3" "docker" "sudo"
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
install_python_requirements
add_exegol_path

### Run Exegol install 
exegol install