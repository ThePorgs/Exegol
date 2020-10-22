# :memo: Things to start
  Here are some things to do that I have in mind, I'll work on that asap. You can help if you feel like it!
  - check if some docker calls can be done with with docker-py
  - enable connections through SOCKS4a/5 or HTTP proxies so that all of Exegol can be used through that proxy, simulating a advanced internal offensive system (callable with a `--proxy` or `--socks` option)
  - find a way to log commands and outputs for engagements: inspiration from https://github.com/TH3xACE/SCREEN_KILLER ?
  - Check if the following freshly installed tools work nicely: bettercap, hostapd-wpe, iproute2
  - Tools to install: arjun, apksign, cfr, dex2jar, drozer, jre8-openjdk, jtool, p7zip, ripgrep, smali, zipalign, frida, adb, dns2tcp, revsocks, chisel, ssf, darkarmor,amber, tikitorch
  - install tools for mobile applications pentest
  - exegol.py : check the docker service is running
  - exegol.py : check the running user is in the docker group, if not, ask the run with privileges (sudo)
  - install https://github.com/aircrack-ng/rtl8814au
  - install https://github.com/lexfo/rpc2socks
  - install ngrok
  - install https://github.com/ambionics/symfony-exploits
  - install https://github.com/ambionics/phpggc
  - install Trilium for local note taking
  - Add pygpoabuse and sharpgpoabuse
  - neo4j password change is not taken into account since I switched neo4j from official repos

# Split install
  split install procedures in categories so that users can tell what "parts" to install, for example : exegol install web,osint,internal
  we can also work with docker image? Dunno, gonna have to work on this.
  we can also do things like add layers to the existing image/container like the following : exegol update osint,web
  have DockerHub build different images per metapackage, we can then docker squash or have a dockerfile build the thing nicely

# :rocket: Things to finish
  - the wiki, with videos/GIFs (https://github.com/phw/peek) ?
  - the contribution rules/info for contributors (CONTRIBUTING.md)
