![banner](https://docs.exegol.com/external/banner.png)

Exegol is a comprehensive cybersecurity environment designed by offensive security experts, for fellow hackers, with its community. It solves the common pain points of traditional security distributions by providing a modular and reliable toolkit that's made for the field.

Want to know more about the project? Go to [exegol.com](https://exegol.com)

# Getting started

How to install Exegol: [exegol.com/install](https://exegol.com/install)

The official project documentation details how Exegol is structured. Go to [docs.exegol.com](https://docs.exegol.com/).

## Tor routing

Use `--tor` when creating a container:

```bash
exegol start torlab free --tor
exegol exec --tmp --tor free 'curl https://check.torproject.org/api/ip'
```

Tor routing persists across restarts; `--tor` cannot retrofit an existing container.
It defaults to Docker bridge networking. An explicit CLI or profile network must
be `docker` or `nat` (NAT requires the corresponding Exegol subscription).
The Tor flag itself is CLI-only, not a profile setting.

Startup, commands and shells wait for Tor to bootstrap. IPv4 TCP is routed through
Tor, UDP DNS is intercepted by Tor, and other outbound UDP, ICMP and IPv6 are
blocked. The default resolver is `1.1.1.1`: UDP queries are intercepted locally;
TCP DNS reaches it through Tor. TCP DNS to loopback or private resolvers is not
supported. Firewall rules remain installed if Tor stops; restart the container
to reconnect. See `/var/log/exegol/tor.log` for bootstrap failures.

Tor mode cannot be combined with VPN, host networking, published ports, desktop,
privileged mode, or `ALL`/`NET_RAW` capabilities. Raw-packet tools will not work.
This is routing protection, not a sandbox against container root or Docker
administrators: trusted setup scripts and users retain `NET_ADMIN` and can change
the firewall or re-enable IPv6. It does not prevent applications from disclosing
identifying information through Tor.
