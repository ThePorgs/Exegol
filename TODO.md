# :memo: Things to start
  Here are some things to do that I have in mind, I'll work on that asap. You can help if you feel like it!
  - enable connections through SOCKS4a/5 or HTTP proxies so that all of Exegol can be used through that proxy, simulating a advanced internal offensive system (callable with a `--proxy` or `--socks` option)
  - find a way to log commands and outputs for engagements: inspiration from https://github.com/TH3xACE/SCREEN_KILLER ?
  - Check if the following freshly installed tools work nicely: bettercap, hostapd-wpe, iproute2
  - Tools to install: cfr, drozer, jre8-openjdk, jtool, ripgrep, revsocks, ssf, darkarmor,amber, tikitorch
  - install tools for mobile applications pentest
  - install https://github.com/aircrack-ng/rtl8814au
  - install https://github.com/lexfo/rpc2socks
  - Add precompiled binaries (i.e. sharpgpoabuse, and others)
  - improve proxychains conf ?
  - add static nmap binary install for resources
  - add JSP webshell (test all https://github.com/tennc/webshell/tree/master/jsp)
  - improve error handling (see https://github.com/ShutdownRepo/Exegol/issues/29)
  - make the wrapper remove the container if it's unable to start
  - add ssh special commands to history (socks proxy, local/remote port forwarding)
  - add an option to mount an encrypted volume
  - update CONTRIBUTING.md
  - limits to actual packaging method
    - 2 install functions can't call the same tool installation twice. It will probably cause errors
    - install functions don't take into account the history or the aliases
    - resources and GUI-based tools don't have package installation for now
  - classify GUI tools
  - add dumpert dll and exe in windows resources
  - check hackrf support (wrapper + tools)
  - add: uncompyle, one_gadget
  - add kerbrute
  - replace is and is not with == and !=, danger ahead
  - populate the wiki with the --help and with GIFs
  - add manspider https://github.com/blacklanternsecurity/MANSPIDER

# Split install
  split install procedures in categories so that users can tell what "parts" to install, for example : exegol install web,osint,internal
  we can also work with docker image? Dunno, gonna have to work on this.
  we can also do things like add layers to the existing image/container like the following : exegol update osint,web
  have DockerHub build different images per metapackage, we can then docker squash or have a dockerfile build the thing nicely

# :rocket: Things to finish
  - the wiki, with videos/GIFs (https://github.com/phw/peek) ?
  - the contribution rules/info for contributors (CONTRIBUTING.md)
