# :memo: Things to start
  Here are some things to do that I have in mind, I'll work on that asap. You can help if you feel like it!
  - enable connections through SOCKS4a/5 or HTTP proxies so that all of Exegol can be used through that proxy, simulating a advanced internal offensive system (callable with a `--proxy` or `--socks` option)
  - find a way to log commands and outputs for engagements: inspiration from https://github.com/TH3xACE/SCREEN_KILLER ?
  - Check if the following freshly installed tools work nicely: bettercap, hostapd-wpe, iproute2
  - Tools to install: arjun, apksign, cfr, dex2jar, drozer, jre8-openjdk, jtool, p7zip, ripgrep, smali, zipalign, frida, adb, dns2tcp, revsocks, chisel, ssf, darkarmor,amber, tikitorch
  - install tools for mobile applications pentest
  - install https://github.com/aircrack-ng/rtl8814au
  - install https://github.com/lexfo/rpc2socks
  - install ngrok
  - clean /tmp folder where lots of pip files are are not removed. What are they doing here ?
  - Add pygpoabuse and sharpgpoabuse
  - add chisel https://github.com/jpillora/chisel
  - improve proxychains conf ?
  - add static nmap binary install for resources
  - add JSP webshell (test all https://github.com/tennc/webshell/tree/master/jsp)
  - improve error handling (see https://github.com/ShutdownRepo/Exegol/issues/29)
  - add ssh special commands to history (socks proxy, local/remote port forwarding)
  - versioning git/dockerhub
  - add an option to mount an encrypted volume
  - update CONTRIBUTING.md
  - limits to actual packaging method
    - 2 install functions can't call the same tool installation twice. It will probably cause errors
    - install functions don't take into account the history or the aliases
    - resources and GUI-based tools don't have package installation for now
  - classify GUI tools
  - add dumpert dll and exe in windows resources
  - check hackrf support (wrapper + tools)


# Split install
  split install procedures in categories so that users can tell what "parts" to install, for example : exegol install web,osint,internal
  we can also work with docker image? Dunno, gonna have to work on this.
  we can also do things like add layers to the existing image/container like the following : exegol update osint,web
  have DockerHub build different images per metapackage, we can then docker squash or have a dockerfile build the thing nicely

# :rocket: Things to finish
  - the wiki, with videos/GIFs (https://github.com/phw/peek) ?
  - the contribution rules/info for contributors (CONTRIBUTING.md)
