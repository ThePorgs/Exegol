#!/bin/bash
# SIGTERM received (the container is stopping, every process must be gracefully stopped before the timeout).
trap shutdown SIGTERM

# Function specific
function load_setups() {
  # Load custom setups (supported setups, and user setup)
  [ -d /var/log/exegol ] || mkdir -p /var/log/exegol
  if [[ ! -f /.exegol/.setup.lock ]]; then
    # Execute initial setup if lock file doesn't exist
    echo >/.exegol/.setup.lock
    echo "Installing [green]my-resources[/green] custom setup ..."
    # Run my-resources script. Logs starting with '[exegol]' will be print to the console and report back to the user through the wrapper.
    /.exegol/load_supported_setups.sh |& tee /var/log/exegol/load_setups.log | grep -i '^\[exegol]' | sed "s/^\[exegol\]\s*//gi"
    [ -f /var/log/exegol/load_setups.log ] && echo "Compressing [green]my-resources[/green] logs" && gzip /var/log/exegol/load_setups.log
  fi
}

function endless() {
  # Start action / endless
  # Entrypoint for the container, in order to have a process hanging, to keep the container alive
  # Alternative to running bash/zsh/whatever as entrypoint, which is longer to start and to stop and to very clean
  echo "READY"
  read -u 2
}

function shutdown() {
  # Shutting down the container.
  # Sending SIGTERM to all interactive process for proper closing
  pgrep guacd && /opt/tools/bin/desktop-stop  # Stop webui desktop if started
  # shellcheck disable=SC2046
  kill $(pgrep -f -- openvpn | grep -vE '^1$') 2>/dev/null
  # shellcheck disable=SC2046
  kill $(pgrep -x -f -- zsh) 2>/dev/null
  # shellcheck disable=SC2046
  kill $(pgrep -x -f -- -zsh) 2>/dev/null
  # shellcheck disable=SC2046
  kill $(pgrep -x -f -- bash) 2>/dev/null
  # shellcheck disable=SC2046
  kill $(pgrep -x -f -- -bash) 2>/dev/null
  # Wait for every active process to exit (e.g: shell logging compression, VPN closing, WebUI)
  wait_list="$(pgrep -f "(.log|start.sh|tomcat)" | grep -vE '^1$')"
  for i in $wait_list; do
    # Waiting for: $i PID process to exit
    tail --pid="$i" -f /dev/null
  done
  exit 0
}

function resolv_docker_host() {
  # On docker desktop host, resolving the host.docker.internal before starting a VPN connection for GUI applications
  docker_ip=$(getent hosts host.docker.internal | head -n1 | awk '{ print $1 }')
  if [ "$docker_ip" ]; then
    # Add docker internal host resolution to the hosts file to preserve access to the X server
    echo "$docker_ip        host.docker.internal" >>/etc/hosts
  fi
}

# Managed features
function default() {
  load_setups
  endless
}

function ovpn() {
  load_setups
  [[ "$DISPLAY" == *"host.docker.internal"* ]] && resolv_docker_host
  # Starting openvpn as a job with '&' to be able to receive SIGTERM signal and close everything properly
  # shellcheck disable=SC2086
  echo "Starting [green]VPN[/green]"
  openvpn --log-append /var/log/exegol/vpn.log $2 &
  sleep 2  # Waiting 2 seconds for the VPN to start before continuing
  endless
}

function cmd() {
  load_setups
  # echo "Executing: ${*:2}"
  "${@:2}"
}

function compatibility() {
  # Older versions of exegol wrapper launch the container with the 'bash' command
  # This command is now interpreted by the custom entrypoint
  echo "Your version of Exegol wrapper is not up-to-date!" | tee -a ~/banner.txt
  # If the command is bash, redirect to endless. Otherwise execute the command as job to keep the shutdown procedure available
  if [ "$*" != "bash" ]; then
    echo "Executing command in backwards compatibility mode" | tee -a ~/banner.txt
    echo "$1 -c '${*:3}'"
    $1 -c "${*:3}" &
  fi
  endless
}

echo "Starting exegol"
# Default action is "default"
func_name="${1:-default}"

# Older versions of exegol wrapper launch the container with the 'bash' command
# This command is now interpreted by the custom entrypoint. Redirect execution to the raw execution for backward compatibility.
# shellcheck disable=SC2068
[ "$func_name" == "bash" ] || [ "$func_name" == "zsh" ] && compatibility $@

### How "echo" works here with exegol ###
# Every message printed here will be displayed to the console logs of the container
# The container logs will be displayed by the wrapper to the user at startup through a progress animation (and a verbose line if -v is set)
# The logs written to ~/banner.txt will be printed to the user through the .zshrc file on each new session (until the file is removed).
# Using 'tee -a' after a command will save the output to a file AND to the console logs.
##########################################

# Dynamic execution
$func_name "$@" || (
  echo "An error occurred executing the '$func_name' action. Your image version is probably out of date for this feature. Please update your image." | tee -a ~/banner.txt
  exit 1
)
