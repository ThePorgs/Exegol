#!/usr/bin/env bash
set -e

log() {
    echo -e "\e[1;34m[INFO]\e[0m $1"
}

warn() {
    echo -e "\e[1;33m[WARN]\e[0m $1"
}

error() {
    echo -e "\e[1;31m[ERROR]\e[0m $1"
    exit 1
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO=$ID
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        DISTRO="darwin"
    else
        error "Cannot detect Linux distribution."
    fi
}

install_apt() {
    log "Installing dependencies using 'apt'"
    sudo apt update
    sudo apt install -y git python3 pipx
}

install_dnf() {
    log "Installing dependencies using 'dnf'..."
    sudo dnf -y check-update || true
    sudo dnf -y install git python3 pipx
}

install_pacman() {
    log "Installing dependencies using 'pacman'..."
    sudo pacman -Syu --noconfirm
    sudo pacman -S --noconfirm git python-pipx
}

install_void() {
    log "Installing dependencies for Void..."
    sudo xbps-install -Syuy xbps
    sudo xbps-install -Syuy git python3 python3-pipx
}

install_brew() {
    log "Installing dependencies using 'brew'..."
    brew install git python pipx
}

install_nixos() {
    warn "Automatic install on NixOS is not recommended."
    warn "Use nix-shell or add packages to configuration.nix."
}

install_gentoo() {
    log "Installing dependencies using 'emerge'..."
    sudo emerge --ask dev-vcs/git
    sudo emerge --ask dev-lang/python
    sudo emerge --ask dev-python/pip
}

install_generic() {
    warn "Unknown distro. Attempting generic install..."
    if command -v apt >/dev/null; then
        install_apt
    elif command -v dnf >/dev/null; then
        install_dnf
    elif command -v pacman >/dev/null; then
        install_pacman
    else
        error "Could not determine package manager."
    fi
}

install_docker() {
    if command -v docker >/dev/null; then
        log "Docker already installed."
        return
    elif command -v orbstack >/dev/null; then
        log "Orbstack already installed."
        return
    fi

    case "$DISTRO" in
        arch|manjaro|cachyos)
            log "Installing Docker using 'pacman'..."
            sudo pacman -Syu --noconfirm docker
            ;;
        void)
            log "Installing Docker using 'xbps'..."
            sudo xbps-install -S docker
            ;;
        gentoo)
            log "Installing Docker using 'emerge'..."
            sudo emerge --ask --verbose app-containers/docker app-containers/docker-cli
            /usr/share/docker/contrib/check-config.sh

            if command -v systemctl; then
                sudo systemctl start docker.service
                sudo systemctl enable docker.service
            else
                rc-update add docker default
                rc-service docker start
                rc-update add registry default
                rc-service registry start
            fi
            ;;
        darwin)
            log "Installing Orbstack..."
            brew install orbstack
            ;;
        *)
            log "Installing Docker using official script..."
            if command -v curl >/dev/null; then
                curl -fsSL "https://get.docker.com/" | sh
            elif command -v wget >/dev/null; then
                wget -O - -q "https://get.docker.com/" | sh
            else
                error "Either 'wget' or 'curl' are required to install Exegol."
            fi
            ;;
    esac
}

start_docker() {
    case "$DISTRO" in
        void)
            sudo sv up docker

            # configure docker to start at boot
            sudo ln -s /etc/sv/docker /var/service/
            ;;
        *)
            if command -v systemctl >/dev/null; then
                sudo systemctl start docker
                sudo systemctl enable --now docker
            fi
            ;;
    esac
}

install_graphical_support() {
    case "$DISTRO" in
        arch|manjaro|cachyos)
            sudo pacman -S xorg-xhost
            xhost +si:localuser:root
            warn "You may need to enable X11 inside container by issuing this command inside containers: 'export DISPLAY=:0'"
            ;;
        void)
            sudo xbps-install -Syuy xhost
            xhost +si:localuser:root
            warn "You will need to enable X11 inside container by issuing this command inside containers: 'export DISPLAY=:0'"
            ;;
        gentoo)
            sudo emerge --ask x11-apps/xhost
            xhost +local:
            warn "You will need to enable X11 inside container by issuing this command inside containers: 'export DISPLAY=:0'"
            ;;
        darwin)
            log "Installing Xquartz..."
            brew install --cask xquartz
            ;;
        *)
            return
            ;;
    esac
}

setup_pipx() {
    log "Ensuring pipx path..."
    pipx ensurepath || true
}

install_exegol_wrapper() {
    log "Installing Exegol wrapper with pipx..."
    pipx install exegol --force
}

configure_alias() {
    # The '-E' argument is not available in 'sudo-rs': https://github.com/trifectatechfoundation/sudo-rs/issues/1299
    if command -v sudo.ws >/dev/null; then
        local alias_line="alias exegol='sudo.ws -E \$HOME/.local/bin/exegol'"
    else
        local alias_line="alias exegol='sudo -E \$HOME/.local/bin/exegol'"
    fi

    declare -a config_files=("$HOME/.config/fish/config.fish" "$HOME/.bashrc" "$HOME/.zshrc")

    for config_file in "${config_files[@]}"
    do
        if ! grep -q "alias exegol=" "$config_file" 2>/dev/null; then
            if [[ -f "$config_file" ]]; then
                log "Adding exegol alias to $config_file"
                echo "$alias_line" >> "$config_file"
            fi
        fi
    done
}

install_dependencies() {
    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop)
            install_apt
            ;;
        fedora)
            install_dnf
            ;;
        arch|manjaro|cachyos)
            install_pacman
            ;;
        void)
            install_void
            ;;
        nixos)
            install_nixos
            ;;
        gentoo)
            install_gentoo
            ;;
        darwin)
            install_brew
            ;;
        *)
            install_generic
            ;;
    esac
}

install_autocomplete() {
    log "Installing Exegol wrapper arguments autocomplete..."

    pipx install argcomplete --force

    declare -a config_files=("$HOME/.bashrc" "$HOME/.zshrc")

    for config_file in "${config_files[@]}"
    do
        if ! grep -q "register-python-argcomplete --no-defaults exegol" "$config_file" 2>/dev/null; then
            log "Adding exegol alias to $config_file"

            echo 'eval "$(register-python-argcomplete --no-defaults exegol)"' >> "$config_file"
        fi
    done

    echo "autoload -U compinit && compinit" >> "$HOME/.zshrc"
}

main() {
    detect_distro

    log "Detected distro: $DISTRO"

    install_dependencies

    install_docker
    start_docker
    install_graphical_support

    setup_pipx
    install_exegol_wrapper
    configure_alias

    install_autocomplete

    log "Installation complete."
    log "Restart your shell"
    log "Then install your first image with: exegol install"
}

main "$@"
