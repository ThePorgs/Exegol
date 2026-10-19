#!/bin/bash
# SIGTERM received (the container is stopping, every process must be gracefully stopped before the timeout).
trap shutdown SIGTERM

function exegol_init() {
  # Restore hosts file backup if any
  [ -f /etc/hosts.backup ] && cp -a /etc/hosts.backup /etc/hosts && rm /etc/hosts.backup
  # Setup default user shell to startup script
  usermod -s "/.exegol/spawn.sh" root > /dev/null
  # Patch zsh.d directory for older images (before 3.1.12) // TODO remove in 2027
  grep 'test -d /etc/zsh.d' /etc/zsh/zshrc > /dev/null || echo "test -d /etc/zsh.d && source /etc/zsh.d/*" >> /etc/zsh/zshrc
  grep 'test -d /etc/bash.d' /etc/bash.bashrc > /dev/null || echo "test -d /etc/bash.d && source /etc/bash.d/*" >> /etc/bash.bashrc
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
  # These four lines matched NOTHING. `-x` with `-f` demands the FULL COMMAND
  # LINE be exactly "zsh"; the interactive Exegol shell's is "/usr/bin/zsh", so
  # no interactive shell was ever asked to exit. It went unnoticed while the wait
  # below fell through immediately -- tearing down the PID namespace killed the
  # shell anyway -- and became visible when Sentinel's recorder made that wait
  # block: the container then only stopped on Docker's SIGKILL timeout.
  #
  # ONE PATTERN FOR BOTH SHELLS, AND THE OPTIONAL PREFIX FORBIDS SPACES.
  # `[^ ]*/` is what keeps this to interactive shells: a shell given ARGUMENTS
  # has spaces in its command
  # line and cannot match, so this one call reaches `zsh`, `-zsh`, `/usr/bin/zsh`,
  # `bash`, `-bash` and `/bin/bash`, while leaving alone every shell that is running
  # something -- `bash /root/.pyenv/libexec/pyenv exec python3 …
  # sentinel_runner.py` (the runners have their own line below and must not be
  # killed twice, still less mid-copy), `/bin/bash /.exegol/spawn.sh`, and this
  # entrypoint itself. A `.*/` prefix would match across the spaces and take all
  # three with it.
  #
  # PID 1 is excluded anyway: this entrypoint IS bash, and one grep is cheaper
  # than trusting that it will always be started with an argument.
  # shellcheck disable=SC2046
  kill $(pgrep -x -f -- '(-|[^ ]*/)?(bash|zsh)' | grep -vE '^1$') 2>/dev/null
  # shellcheck disable=SC2046
  kill $(pgrep -f -- /.exegol/sentinel/sentinel_runner.py) 2>/dev/null
  # Wait for every active process to exit (e.g: shell logging compression, VPN closing, WebUI)
  #
  # NOT ".log", which also matches Sentinel's session recorder --
  #   script -qef -c /bin/zsh /tmp/.sentinel/session_<name>_<pid>.log
  # -- a process present in EVERY Sentinel container, with or without --log. PID
  # 1 blocked on `tail --pid=<recorder>` and never reached `exit 0`. The recorder
  # needs no waiting on: it exits with the shell killed above, and spawn.sh --
  # which IS waited on here -- owns the session file through its EXIT trap.
  # Scoped to the shell-logging recordings this wait was written for.
  WAIT_LIST="$(pgrep -f "(/workspace/logs|spawn.sh|vnc)" | grep -vE '^1$')"
  for i in $WAIT_LIST; do
    # Waiting for: $i PID process to exit.
    # BOUNDED: one process that never exits must not hold the whole shutdown for
    # the operator's entire `--time`. spawn.sh's own cleanup already waits up to
    # 60s for an in-flight capture, so this sits just above it.
    timeout 60 tail --pid="$i" -f /dev/null
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
    # If the creds file's optional 3rd line holds the encrypted private key's
    # passphrase, OpenVPN can't read it from --auth-user-pass (that only reads
    # the first two lines), so it's split into its own --askpass file.
    CREDS_FILE="/.exegol/vpn/auth/creds.txt"
    if [[ -f "$CREDS_FILE" ]]; then
      KEY_PASS="$(sed -n '3p' "$CREDS_FILE" | tr -d '\r')"
      if [[ -n "$KEY_PASS" ]]; then
        ASKPASS_FILE="/.exegol/vpn/auth/askpass.txt"
        printf '%s\n' "$KEY_PASS" > "$ASKPASS_FILE"
        chmod 600 "$ASKPASS_FILE"
        set -- "$@" --askpass "$ASKPASS_FILE"
      fi
    fi
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
