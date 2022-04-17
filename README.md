# Exegol

<p align="center">
  <img alt="DockerHub build type" src="https://img.shields.io/docker/cloud/automated/nwodtuhs/exegol">
  <img alt="DockerHub build state" src="https://img.shields.io/docker/cloud/build/nwodtuhs/exegol">
  <img alt="image size" src="https://img.shields.io/docker/image-size/nwodtuhs/exegol/nightly">
  <img alt="GitHub code size in bytes" src="https://img.shields.io/github/languages/code-size/ShutdownRepo/Exegol">
  <img alt="Python" src="https://img.shields.io/badge/Python-3-success">
  <br>
  <img alt="current version" src="https://img.shields.io/badge/version-3.1.12.dev-blueviolet">
  <img alt="latest commit on master" src="https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/master?label=latest%20release">
  <img alt="latest commit on dev" src="https://img.shields.io/github/last-commit/ShutdownRepo/Exegol/dev?label=latest%20commit%20%28in%20dev%20branch%29">
  <br></br>
  <a href="https://twitter.com/intent/follow?screen_name=_nwodtuhs" title="Follow"><img src="https://img.shields.io/twitter/follow/_nwodtuhs?label=Shutdown&style=social"></a>
  <br><br>
</p>

**:bulb: TL;DR: Exegol is a community-driven hacking environment, powerful and yet simple enough to be used by anyone in day to day engagements.**

## Wrapper & images
Exegol is two things in one. Try it, and you'll stop using your old, unstable, risky environment like Kali Linux.
- **a python wrapper** making everyone's life easier. It handles all docker and git operations so you don't have to and allows for l33t hacking following best-practices. No more messed up history, libraries, and workspaces. **Now's the time to have a clean environment** with one container per engagement without effort. Exegol handles multiple images and multiple containers.
    - Want to test a new tool without risking messing up your environment? Exegol is here, pop up a new container in 5 seconds and try the tool without risk or effort
    - Like the idea of using docker containers without effort but don't want to sacrifice GUI tools like BloodHound and Burp? Exegol is here, new containers are created with X11 sharing by default allowing for GUI tools to work.
    - Like the idea of using docker containers but want to use USB accessories, Wi-Fi, host's network interfaces, etc.? Exegol handles all that flawlessly
    - Want to stop pentesting your clients with the same environment everytime, interconnecting everything and risking being a weak link? Exegol is here, pop multiple containers without breaking a sweat and lead by example!
- a set of pre-built **docker images** and dockerfiles that include a neat choice of tools, awesome resources, custom configs and many more.
    - Fed up with the instability and poor choice of tools of Kali Linux ? Exegol is here, trying to correct all this by being community-driven. Want some not-so-famous tool to be added? Open an issue and let's talk do it!
    - Tired of always having to open `man` or print the help for every tool because the syntax varies? Exegol includes a command history allowing you to just replace the placeholders with your values, saving you precious time
    - Want to improve productivity? Exegol includes all sorts of custom configs and tweaks with ease of use and productivity in mind (colored output for Impacket, custom shortcuts and aliases, custom tool configs, ...).
    - Want to build your own docker images locally? It's absolutely possibe and the wrapper will help in the quest.
    - Tired of always having to search github for your favorite privesc enumeration script? Exegol includes a set of resources, shared with all exegol containers and your host, including LinPEAS, WinPEAS, LinEnum, PrivescCheck, SysinternalsSuite, mimikatz, Rubeus and many more.
    
Exegol was built with pentest engagements in mind, but it can also be used in CTFs, Bug Bounties, HackTheBox, OSCP, and so on.
- [:wrench: Tools](#wrench-tools): many tools that are either installed manually or with apt, pip, go etc. Some of those tools are in kali, some are not. Exegol doesn't come with only ultra-famous tools, you will find ones that the community loves to use, even if it's in dev/new/not famous. Some tools are pre-configured and/or customized (colored output, custom NtChallengeResponse in Responder, custom queries in BloodHound, ...)
- [:bulb: Resources](#bulb-resources): many resources can be useful during engagements. Those resources are not referred to as "tools" since they need to be run on a pwned target, and not on the attacker machine (e.g. mimikatz, rubeus, ...).
- [:scroll: History](#scroll-history): a populated history file that allows exegol users to save time and brain space by not having to remember every tool option and argument or checking the "help" every time.
- [:rocket: Aliases](#rocket-aliases): a file containing aliases that can be handful when using manually installed tools, or doing common operations.
- [:mag_right: Usage](#mag_right-usage) : a powerful Python3 wrapper used to manage Exegol container and image very easily (handles every docker operations).

Below is an example of a Zerologon attack operated with Exegol.
**TODO**

Below is an example of a [ACE abuse/RBCD attack](https://www.thehacker.recipes/active-directory-domain-services/movement/abusing-aces) operated with Exegol
**TODO**

# :fast_forward: Quick start

> Keep in mind that the wrapper is one thing, but in order to use Exegol, at least one Exegol docker image must be installed.
> Installing the wrapper and running it will do the next steps (which can be a bit lengthy)

## Installation using pip

Exegol's wrapper can be installed from pip repository. That's the entrypoint of the project, you'll be able to do all the rest from there.
```
python3 -m pip install exegol
```
Remember that pip install binaries in `~/.local/bin`, which then must be in the `PATH`.

## Installation from sources
Exegol's wrapper can also be installed from sources. The wrapper then knows how to self-update.
```
git clone https://github.com/ShutdownRepo/Exegol
cd Exegol
python3 -m pip install --user --requirement requirements.txt
```

The wrapper can then be added to the `PATH`.
```
sudo ln -s $(pwd)/exegol.py /usr/local/bin/exegol
```

## Exegol images

It is possible to install an exegol image using the wrapper with the following command: `exegol install <image_name>`

| Image name | Description                                                                                        |
|------------|----------------------------------------------------------------------------------------------------|
| full       | Includes all the tools supported by Exegol (warning: this is the heaviest image)                   |
| nightly    | (for developers and advanced users) contains the latest updates. This image can be unstable!       |
| ad         | Includes tools for Active Directory / internal pentesting only.                                    |
| web        | Includes tools for Web pentesting only.                                                            |
| light      | Includes the lightest and most used tools for various purposes.                                    |
| osint      | Includes tools for OSINT.                                                                          |

# :mag_right: Usage
Below are some examples of usage. For more examples, run the following command: `exegol <action> -h` (action: install/start/stop/etc.).

- Install an Exegol image : `exegol install`
- Create/start/enter a container : `exegol start`
- Show info on containers and images : `exegol info`
- Stop a container : `exegol stop`
- Remove a container : `exegol remove`
- Uninstall an image : `exegol uninstall`
- Get help and advanced usage : `exegol --help`

:warning: remember that Exegol uses Docker images and containers. Understanding the difference is essential to understand Exegol.
- **image**: think of it as an immutable template. They cannot be executed as-is and serve as input for containers. It's not possible to open a shell in an image.
- **container**: a container rests upon an image. A container is created for a certain image at a certain time. It's possible to open a shell in a container. Careful though, once a container is created, updating the image it was created upon won't have any impact on the container. In order to enjoy the new things, a new container must be created upon that updated image.

**TODO: usage GIF**

By default, Exegol will create containers with display sharing allowing GUI-based programs to run, with network host sharing, and a few others things.
Below is an example of a GUI app running in an Exegol container.

**TODO: example with BloodHound and Burp?**

# :closed_lock_with_key: Credentials
Some tools are pre-configured with the following credentials

| Element | User | Password |
| ------- | ---- | -------- |
| neo4j database | neo4j | exegol4thewin |
| bettercap ui | bettercap | exegol4thewin |
| trilium | trilium | exegol4thewin |
| wso-webshell (PHP) | | exegol4thewin |

# :pushpin: Pre-requisites
You need python3 and docker :whale:, and at least 20GB of free storage.
You also need python libraries listed in [requirements.txt](./requirements.txt).

# :wrench: Tools
The tools installed in [Exegol-images](https://github.com/ShutdownRepo/Exegol-images) are mostly installed from sources in order to have the latest version when deploying Exegol. Some installs are made with go, pip, apt, gem etc. You will find most of the tools in `/opt/tools`.
- Impacket (https://github.com/SecureAuthCorp/impacket)
- BloodHound (https://github.com/BloodHoundAD/BloodHound)
- Ghidra (https://ghidra-sre.org/)
- ffuf (https://github.com/ffuf/ffuf)
- Burp (https://portswigger.net/burp)
- [and many others...](https://github.com/ShutdownRepo/Exegol/wiki/Tools)

# :bulb: Resources
In addition to the many tools pre-installed and configured for some, you will find many useful pre-fetched resources ([Exegol-resources](https://github.com/ShutdownRepo/Exegol-resources)) like scripts and binaries in `/opt/resources`. There some pre-EoP enumeration scripts (EoP: Escalation of Privileges) and other useful binaries like Rubeus or mimikatz.
- mimikatz (https://github.com/gentilkiwi/mimikatz)
- linPEAS & winPEAS (https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite)
- Linux Smart Enumeration (lse.sh) (https://github.com/diego-treitos/linux-smart-enumeration)
- sysinternals (https://docs.microsoft.com/en-us/sysinternals/downloads/)
- PowerSploit (https://github.com/PowerShellMafia/PowerSploit)
- [and many others...](https://github.com/ShutdownRepo/Exegol/wiki/Resources)

# :scroll: History
When I hack, I often rely on my history. I don't have to remember command line options, syntax and such. This history is filled with commands that I used in engagements, bugbounties, ctf, oscp and so on. Of course, the values are placeholders that need to be changed with the appropriate ones in your context.
The history is easily usable with [oh-my-zsh](https://github.com/ohmyzsh/ohmyzsh), [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions), and [fzf](https://github.com/junegunn/fzf)

# :rocket: Aliases
Since many tools are manually installed in `/opt/tools/`, aliases could be heplful to use these without having to change directory manually.
Other aliases are set to save time while hacking (`http-server`, `php-server`, `urlencode`,`ipa`, ...).

# :loudspeaker: Credits & thanks
Credits and thanks go to every infosec addicts that contribute and share but most specifically to 
- [@th1b4ud](https://twitter.com/th1b4ud) for the base ["Kali Linux in 3 seconds with Docker"](https://thibaud-robin.fr/articles/docker-kali/).
- [dramelac_](https://twitter.com/dramelac_) for working on [Exegol](https://github.com/ShutdownRepo/Exegol) (the wrapper)
- LamaBzh for working on [Exegol-images](https://github.com/ShutdownRepo/Exegol-images)

# :movie_camera: Introducing Exegol (in french w/ english subs)
<p align="center">
  <a href="http://www.youtube.com/watch?v=TA3vrNpWGvg" title="Video"><img src="http://img.youtube.com/vi/TA3vrNpWGvg/0.jpg">
</p>
