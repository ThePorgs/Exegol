# Exegol

  ![last commit on master](https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/master?label=latest%20release) ![last commit on dev](https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/dev?label=last%20commit%20%28dev%29)

  ![Python](https://img.shields.io/badge/Python-3-success) ![DockerHub build type](https://img.shields.io/docker/cloud/automated/nwodtuhs/exegol) ![DockerHub build state](https://img.shields.io/docker/cloud/build/nwodtuhs/exegol) ![image size](https://img.shields.io/docker/image-size/nwodtuhs/exegol/latest)

  [![Twitter](https://img.shields.io/twitter/follow/_nwodtuhs?label=Shutdown&style=social)](https://twitter.com/intent/follow?screen_name=_nwodtuhs)

  Exegol is a fully configured docker with many useful additional tools, resources (scripts and binaries for privesc, credential theft etc.) and some configuration (oh-my-zsh, history, aliases, colorized output for some tools). It can be used in pentest engagements, bugbounty, CTF, HackTheBox, OSCP lab & exam and so on. Exegol's original fate was to be a ready-to-hack docker in case of emergencies during engagements.

  The main features of Exegol are:
  - [Tools](#wrench-tools): many tools that are either installed manually or with apt, pip, go etc. Some of those tools are in kali, some are not. Exegol doesn't come with only ultra-famous tools, you will find ones that the community loves to use, even if it's in dev/new/not famous. Some tools are pre-configured and/or customized (colored output, custom NtChallengeResponse in Responder, custom queries in BloodHound, ...)
  - [Resources](#bulb-resources): many resources can be useful during engagements. Those resources are not referred to as "tools" since they need to be run on a pwned target, and not on the attacker machine (e.g. mimikatz, rubeus, ...).
  - [History](#scroll-history): a populated history file that allows exegol users to save time and brain space by not having to remember every tool option and argument or checking the "help" every time.
  - [Aliases](#rocket-aliases): a file containing aliases that can be handful when using manually installed tools, or doing common operations.
  - [Usage](#mag_right-usage) : a powerful Python3 wrapper used to manage Exegol container and image very easily (handles operations of `docker pull`, `docker build`, `docker run`, `docker start`, `docker ps`, `docker inspect` and so on).

  :bulb: **TL;DR** Exegol is a community-driven environment, powerful and yet simple enough to be used in day to day engagements by anyone.

# :fast_forward: Install
  The install process takes time. Install it before needing it.
  1. Install the python requirements to use the wrapper : `pip install -r requirements.txt`
  2. (optional) Set the following alias in you zshrc/bashrc/whateverrc : `alias exegol='python3 /PATH/TO/Exegol/exegol.py'`
  3. Install : `exegol install`

# :mag_right: Usage
  1. Start : `exegol start`
  2. Stop : `exegol stop`
  3. Reset the container state : `exegol reset`
  4. Get help on advanced usage : `exegol --help`

# :closed_lock_with_key: Credentials
  Some tools are pre-configured with the following credentials
  | Element | User | Password |
  | ------- | ---- | -------- |
  | wso-webshell (PHP) | | exegol4thewin |
  | neo4j database | neo4j | exegol4thewin |
  | bettercap ui | bettercap | exegol4thewin |

# :pushpin: Pre-requisites
  You need docker :whale:, make, and 15GB of free storage (*What did you expect? A fully featured pentesting environment for less than 2GB? If you've got ideas I'm all ears*).

# :wrench: Tools
  The tools installed in Exegol are mostly installed from sources in order to have the latest version when deploying Exegol. Some installs are made with go, pip, apt, gem etc. You will find most of the tools in `/opt/tools`.
  - CrackMapExec (https://github.com/byt3bl33d3r/CrackMapExec)
  - Impacket (https://github.com/SecureAuthCorp/impacket)
  - BloodHound (https://github.com/BloodHoundAD/BloodHound)
  - BloodHound.py (https://github.com/fox-it/BloodHound.py)
  - Powershell Empire (https://github.com/BC-SECURITY/Empire)
  - ffuf (https://github.com/ffuf/ffuf)
  - updog (https://github.com/sc0tfree/updog)
  - shellerator (https://github.com/ShutdownRepo/shellerator)
  - krbrelayx (https://github.com/dirkjanm/krbrelayx)
  - [and many others...](https://github.com/ShutdownRepo/Exegol/blob/master/README_long.md#wrench-tools)

# :bulb: Resources
  In addition to the many tools pre-installed and configured for some, you will find many useful pre-fetched resources like scripts and binaries in `/opt/resources`. There some pre-EoP enumeration scripts (EoP: Escalation of Privileges) and other useful binaries like Rubeus or mimikatz.
  - Linux Smart Enumeration (lse.sh) (https://github.com/diego-treitos/linux-smart-enumeration)
  - mimikatz (https://github.com/gentilkiwi/mimikatz)
  - linPEAS & winPEAS (https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite)
  - pspy (https://github.com/DominicBreuker/pspy)
  - sysinternals (https://docs.microsoft.com/en-us/sysinternals/downloads/)
  - PowerSploit (https://github.com/PowerShellMafia/PowerSploit)
  - Rubeus (https://github.com/GhostPack/Rubeus) ([pre-compiled binary](https://github.com/r3motecontrol/Ghostpack-CompiledBinaries))
  - [and many others...](https://github.com/ShutdownRepo/Exegol/blob/master/README_long.md#bulb-resources)

# :scroll: History
  When I hack, I often rely on my history. I don't have to remember command line options, syntax and such. This history is filled with commands that I used in engagements, bugbounties, ctf, oscp and so on. Of course, the values are placeholders that need to be changed with the appropriate ones in your context.

# :rocket: Aliases
  Since many tools are manually installed in `/opt/tools/`, aliases could be heplful to use these without having to change directory manually.
  Other aliases are set to save time while hacking (`http-server`, `php-server`, `urlencode`,`ipa`, ...).

# :memo: To-Do List
  Here are some things to add/correct that I have in mind, I'll work on that asap
  - redo the ZeroLogon install part once clean exploits are out
  - make a GIF and/or some visuals to present this ?
  - find a way to log commands and outputs for engagements
  - Check if the following freshly installed tools work nicely: bettercap, hostapd-wpe, iproute2, wifite2
  - Tools to install: arjun, apksign, cfr, dex2jar, drozer, jre8-openjdk, jtool, p7zip, ripgrep, smali, zipalign, frida, adb
  - share the /opt/resources folder to let the host easily access it : it seems to be impossible, see [this](https://github.com/moby/moby/issues/4361)
  - manual install of msf to move it to /opt/tools/ : I think it was Sn1per install, I commented out this tool for now, it's heavy and I don't use it, I may enable it again if people want me to
  - move the long readme to a wiki and document some things

# :loudspeaker: Credits & thanks
  Credits and thanks go to every infosec addicts that contribute and share but most specifically to [@th1b4ud](https://twitter.com/th1b4ud) for the base ["Kali Linux in 3 seconds with Docker"](https://thibaud-robin.fr/articles/docker-kali/).

# :movie_camera: Introducing Exegol (in french w/ english subs)
[![Introducing Exegol (french)](http://img.youtube.com/vi/TA3vrNpWGvg/0.jpg)](http://www.youtube.com/watch?v=TA3vrNpWGvg "Introducing Exegol (french)")
