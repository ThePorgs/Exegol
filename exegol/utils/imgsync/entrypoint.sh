#!/bin/bash
# SIGTERM received (the container is stopping, every process must be gracefully stopped before the timeout).
trap shutdown SIGTERM

function exegol_init() {
  # Restore hosts file backup if any
  [ -f /etc/hosts.backup ] && cp -a /etc/hosts.backup /etc/hosts && rm /etc/hosts.backup
  # Setup default user shell to startup script
  usermod -s "/.exegol/spawn.sh" root > /dev/null
}

# Function specific
function load_setups() {
  # Logs are using [INFO], [VERBOSE], [WARNING], [ERROR], [SUCCESS] tags so that the wrapper can catch them and forward them to the user with the corresponding logger level
  # Load custom setups (supported setups, and user setup)
  [[ -d "/var/log/exegol" ]] || mkdir -p /var/log/exegol
  if [[ ! -f "/.exegol/.setup.lock" ]]; then
    # Execute initial setup if lock file doesn't exist
    echo >/.exegol/.setup.lock
    # Run my-resources script. Logs starting with '[EXEGOL]' will be printed to the console and reported back to the user through the wrapper.
    if [ -f /.exegol/load_supported_setups.sh ]; then
      echo "[PROGRESS]Starting [green]my-resources[/green] setup"
      /.exegol/load_supported_setups.sh | grep --line-buffered '^\[EXEGOL]' | sed -u "s/^\[EXEGOL\]\s*//g"
    else
      echo "[WARNING]Your exegol image doesn't support my-resources custom setup!"
    fi
  fi
}

function finish() {
    echo "READY"
}

function endless() {
  # Start action / endless
  finish
  # Entrypoint for the container, in order to have a process hanging, to keep the container alive
  # Alternative to running bash/zsh/whatever as entrypoint, which is longer to start and to stop and to very clean
  [[ ! -p /tmp/.entrypoint ]] && mkfifo -m 000 /tmp/.entrypoint # Create an empty fifo for sleep by read.
  read -r <> /tmp/.entrypoint  # read from /tmp/.entrypoint => endlessly wait without sub-process or need for TTY option
}

function shutdown() {
  # Shutting down the container.
  # Backup host file to restore after restart
  cp -a /etc/hosts /etc/hosts.backup
  # Sending SIGTERM to all interactive process for proper closing
  pgrep vnc && desktop-stop  # Stop webui desktop if started TODO improve desktop shutdown
  # Stop wireguard if any
  command -v wg-quick &> /dev/null && [ "$(find "/etc/wireguard/" -type f -name '*.conf' | wc -l)" -gt 0 ] && wg-quick down /etc/wireguard/* 2>/dev/null
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
  WAIT_LIST="$(pgrep -f "(.log|spawn.sh|vnc)" | grep -vE '^1$')"
  for i in $WAIT_LIST; do
    # Waiting for: $i PID process to exit
    tail --pid="$i" -f /dev/null
  done
  exit 0
}

function _resolv_docker_host() {
  # On docker desktop host, resolving the host.docker.internal before starting a VPN connection for GUI applications
  DOCKER_IP=$(getent ahostsv4 host.docker.internal | head -n1 | awk '{ print $1 }')
  if [[ "$DOCKER_IP" ]]; then
    # Add docker internal host resolution to the hosts file to preserve access to the X server
    echo "$DOCKER_IP        host.docker.internal" >>/etc/hosts
    # If the container share the host networks, no need to add a static mapping
    ip route list match "$DOCKER_IP" table all | grep -v default || ip route add "$DOCKER_IP/32" "$(ip route list | grep default | head -n1 | grep -Eo '(via [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ )?dev [a-zA-Z0-9]+')" || echo '[WARNING]Exegol cannot add a static route to resolv your host X11 server. GUI applications may not work.'
  fi
}

function ovpn() {
  [[ "$DISPLAY" == *"host.docker.internal"* ]] && _resolv_docker_host
  if ! command -v openvpn &> /dev/null
  then
      echo '[ERROR]Your exegol image does not support the VPN feature'
  else
    # Starting openvpn as a job with '&' to be able to receive SIGTERM signal and close everything properly
    echo "[PROGRESS]Starting [green]OpenVPN[/green]"
    # shellcheck disable=SC2164
    ([[ -d /.exegol/vpn/config ]] && cd /.exegol/vpn/config; openvpn --log-append /var/log/exegol/vpn.log "$@" &)
    sleep 2  # Waiting 2 seconds for the VPN to start before continuing
  fi
}

function wgconf() {
  [[ "$DISPLAY" == *"host.docker.internal"* ]] && _resolv_docker_host
  if ! command -v wg-quick &> /dev/null
  then
      echo '[ERROR]Your exegol image does not support the WireGuard VPN feature'
  else
    echo "[PROGRESS]Starting [green]WireGuard[/green] VPN"
    if ! wg-quick up "$@" &>> /var/log/exegol/vpn.log
    then
      echo '[ERROR]An error has occurred during WireGuard VPN startup. Check logs in container at path /var/log/exegol/vpn.log'
    else
      echo '[SUCCESS]WireGuard [green]VPN[/green] successfully started!'
    fi
  fi
}

function run_cmd() {
  /bin/zsh -c "autoload -Uz compinit; compinit; source ~/.zshrc; eval \"$CMD\""
}

function desktop() {
  if command -v desktop-start &> /dev/null
  then
      echo "[PROGRESS]Starting Exegol [green]desktop[/green] with [blue]${EXEGOL_DESKTOP_PROTO}[/blue]"
      ln -sf /root/.vnc /var/log/exegol/desktop
      desktop-start &>> ~/.vnc/startup.log  # Disable logging
      sleep 2  # Waiting 2 seconds for the Desktop to start before continuing
  else
      echo '[ERROR]Your exegol image does not support the Desktop features'
  fi
}

##### How "echo" works here with exegol #####
#
# Every message printed here will be displayed to the console logs of the container
# The container logs will be displayed by the wrapper to the user at startup through a progress animation (and a verbose line if -v is set)
# The logs written to ~/banner.txt will be printed to the user through the .zshrc file on each new session (until the file is removed).
# Using 'tee -a' after a command will save the output to a file AND to the console logs.
#
#############################################
echo "Starting exegol"
exegol_init

### Argument parsing

# Par each parameter
for arg in "$@"; do
 # Check if the function exist
 FUNCTION_NAME=$(echo "$arg" | cut -d ' ' -f 1)
 if declare -f "$FUNCTION_NAME" > /dev/null; then
   $arg
 else
   echo "The function '$arg' doesn't exist."
 fi
done
