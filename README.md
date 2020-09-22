# Exegol
  Exegol is a fully configured kali light base with many useful additional tools, resources (scripts and binaries for privesc, credential theft etc.) and some configuration (oh-my-zsh, history, aliases, colourized output for some tools). It can be used in pentest engagements, bugbounty, CTF, HackTheBox, OSCP lab & exam and so on. Exegol's original fate was to be a ready-to-hack docker in case of emergencies during engagements. It is now the environment my team and I use in day to day engagements.

  The biggest features of Exegol are:
  - [Tools](#wrench-tools): many tools that are either installed manually or with apt, pip, go etc. Some of those tools are in kali, some are not. Exegol doesn't come with ultra-famous tools only. Some tools are pre-configured and/or customized (colored output, custom NtChallengeResponse in Reponder, ...)
  - [Resources](#bulb-resources): many resources can be useful during engagements. Those resources are not referred to as "tools" since they need to be run on a pwned target, and not on the attacker machine (e.g. mimikatz, rubeus, ...).
  - [History](#scroll-history): a populated history file that allows exegol users to save time and brain space by not having to remember every tool option and argument or checking the "help" every time.
  - [Aliases](#rocket-aliases): a file containing aliases that can be handful when using manually installed tools, or doing common operations.

# :fast_forward: Install
  The install process takes time. Install it before needing it.
  1. Clone : `git clone https://github.com/ShutdownRepo/Exegol`
  2. Build : `cd Exegol && docker build --tag exegol .`
  3. Set the following aliases in your bashrc/zshrc/whateverrc.
  ```
  alias exegol-update='docker pull nwodtuhs/exegol'
  alias exegol-build='docker build --tag nwodtuhs/exegol /PATH/TO/Exegol/'
  alias exegol-run='docker run --interactive --tty --detach --network host --volume /PATH/TO/Exegol/shared-volume:/share --name exegol nwodtuhs/exegol'
  alias exegol-shell='docker exec -it exegol zsh'
  alias exegol-stop='docker stop exegol && docker rm exegol'
  ```
  4. Run the docker and get a shell : `exegol-run && exegol-shell`
  5. Stop it when you're done : `exegol-stop`

# :pushpin: Pre-requisites
  You need docker :whale:

# :mag_right: Usage
  - Update the docker : `exegol-update`
  - Run the docker : `exegol-run`
  - Get a shell when exegol is up and running (it is possible to have multiple shells) : `exegol-shell`
  - Stop exegol : `exegol-stop`

# :wrench: Tools
  The tools installed in Exegol are mostly installed from sources in order to have the latest version when deploying Exegol. Some installs are made with go, pip, apt, gem etc. You will find most of the tools in `/opt/tools`.
  - CrackMapExec (https://github.com/byt3bl33d3r/CrackMapExec)
  - Impacket (https://github.com/SecureAuthCorp/impacket)
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
  - is it possible to use Wifi and Bluetooth??
  - issues when mounting stuff
  - redo the ZeroLogon install part once clean exploits are out
  - rewrite apt_packages function
  - make a GIF and/or some visuals to present this ?
  - makefile for build, start, update etc. ?

# :loudspeaker: Credits & thanks
  Credits and thanks go to every infosec addicts that contribute and share but most specifically to [@th1b4ud](https://twitter.com/th1b4ud) for the base ["Kali Linux in 3 seconds with Docker"](https://thibaud-robin.fr/articles/docker-kali/).

# :movie_camera: Introducing Exegol (in french w/ english subs)
[![Introducing Exegol (french)](http://img.youtube.com/vi/TA3vrNpWGvg/0.jpg)](http://www.youtube.com/watch?v=TA3vrNpWGvg "Introducing Exegol (french)")
