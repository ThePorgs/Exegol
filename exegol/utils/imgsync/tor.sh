#!/bin/bash
# Transparent Tor routing. Only run in the private network namespace selected by --tor.
set -Eeuo pipefail

runtime=/run/exegol/tor
state=/var/lib/exegol/tor
log=/var/log/exegol/tor.log

function tor_alive() {
  local pid comm status
  [[ -s "$runtime/pid" ]] || return 1
  read -r pid < "$runtime/pid"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [[ -r "/proc/$pid/comm" && -r "/proc/$pid/status" ]] || return 1
  read -r comm < "/proc/$pid/comm"
  status=$(awk '/^State:/ {print $2}' "/proc/$pid/status")
  [[ "$comm" == tor && "$status" != Z ]] && kill -0 "$pid" 2>/dev/null
}

function fail() {
  echo "[ERROR]Tor startup failed: $*"
  # Never remove the firewall on failure or shutdown.
  exit 1
}

function start_tor() {
  local dependency tor_uid tor_gid tor_pid attempt cap_bound
  trap 'fail "setup command failed at line $LINENO."' ERR
  for dependency in tor iptables-restore ip6tables-restore id useradd install awk grep; do
    command -v "$dependency" >/dev/null || fail "missing $dependency; use an image with tor, iptables and passwd installed."
  done
  [[ "$(id -u)" == 0 ]] || fail "root is required to set up the firewall."
  cap_bound=$(awk '/^CapBnd:/ {print $2}' /proc/self/status)
  (( (16#$cap_bound & 0x2000) == 0 )) || fail "the container must drop NET_RAW."
  [[ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" == 1 ]] || fail "IPv6 must be disabled by the container configuration."
  install -d -m 0700 "$runtime"
  rm -f "$runtime/ready" "$runtime/pid"

  # Only this account gets direct TCP access through the firewall.
  if ! id exegol-tor >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "$state" --shell /usr/sbin/nologin exegol-tor
  fi
  tor_uid=$(id -u exegol-tor)
  tor_gid=$(id -g exegol-tor)
  [[ "$tor_uid" -gt 0 ]] || fail "Tor must use an unprivileged account."

  # Install filtering before starting Tor. Allowing ESTABLISHED in OUTPUT
  # would let existing direct connections bypass the proxy.
  # Redirected packets can retain their output interface here; -o lo alone
  # would block them. Allow the Tor listeners explicitly.
  iptables-restore --wait 5 <<EOF
*filter
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
:OUTPUT DROP [0:0]
-A INPUT -i lo -j ACCEPT
-A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A OUTPUT -o lo -j ACCEPT
-A OUTPUT -d 127.0.0.1 -p tcp --dport 9040 -j ACCEPT
-A OUTPUT -d 127.0.0.1 -p udp --dport 5353 -j ACCEPT
-A OUTPUT -p tcp -m owner --uid-owner $tor_uid -j ACCEPT
COMMIT
EOF
  # Keep IPv6 blocked if its sysctl is later re-enabled.
  ip6tables-restore --wait 5 <<'EOF'
*filter
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
:OUTPUT DROP [0:0]
COMMIT
EOF
  # Replace container-local NAT, including Docker's embedded DNS rules, so DNS cannot
  # escape through Docker's resolver. DNS interception precedes the loopback exception.
  iptables-restore --wait 5 <<EOF
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
-A OUTPUT -m owner --uid-owner $tor_uid -j RETURN
-A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports 5353
-A OUTPUT -d 127.0.0.0/8 -j RETURN
-A OUTPUT -p tcp -j REDIRECT --to-ports 9040
COMMIT
EOF
  # Use Tor locally after removing Docker's DNS port mappings.
  printf 'nameserver 127.0.0.1\noptions timeout:2 attempts:2\n' > /etc/resolv.conf

  install -d -m 0700 -o "$tor_uid" -g "$tor_gid" "$state"
  install -d -m 0755 /var/log/exegol
  cat > "$runtime/torrc" <<EOF
ClientOnly 1
User exegol-tor
DataDirectory $state
SocksPort 0
TransPort 127.0.0.1:9040
DNSPort 127.0.0.1:5353
AutomapHostsOnResolve 1
VirtualAddrNetworkIPv4 10.192.0.0/10
ClientUseIPv6 0
Log notice stdout
RunAsDaemon 0
EOF
  echo '[PROGRESS]Connecting to [green]Tor[/green] (up to 300 seconds)'
  # Ignore image/user torrc defaults; start a client, never a relay or an open proxy.
  tor --defaults-torrc /dev/null -f "$runtime/torrc" > "$log" 2>&1 &
  tor_pid=$!
  echo "$tor_pid" > "$runtime/pid"
  trap 'kill "$tor_pid" 2>/dev/null || true; exit 1' TERM INT
  for ((attempt=0; attempt<300; attempt++)); do
    kill -0 "$tor_pid" 2>/dev/null || fail "daemon exited; see $log."
    if grep -q 'Bootstrapped 100%' "$log"; then
      touch "$runtime/ready"
      echo '[SUCCESS]Tor connected. TCP and DNS routing is active.'
      return 0
    fi
    sleep 1
  done
  kill "$tor_pid" 2>/dev/null || true
  fail "bootstrap timed out; check $log."
}

case "${1:-}" in
  start) start_tor ;;
  check)
    [[ -f "$runtime/ready" ]] || exit 1
    tor_alive || exit 2
    ;;
  stop)
    if tor_alive; then
      read -r pid < "$runtime/pid"
      kill "$pid"
    fi
    ;;
  *) echo 'Usage: tor.sh start|check|stop' >&2; exit 2 ;;
esac
