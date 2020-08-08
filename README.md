# Exegol
  Exegol is a fully configured kali light base with many useful additional tools, resources (scripts and binaries for privesc, credential theft etc.) and some configuration (oh-my-zsh, history, aliases, colourized output for some tools). It can be used in pentest engagements, bugbounty, CTF, HackTheBox, OSCP lab & exam and so on. Exegol's original fate was to be a ready-to-hack docker in case of emergencies during engagements. It is now an environnement my team and I use in day to day engagements.

  The biggest features of Exegol are:
  - [Tools](#wrench-tools): many tools that are either installed manually or with apt, pip, go etc. Some of those tools are in kali, some are not. Exegol doesn't come with ultra-famous tools only. Some tools are pre-configured and/or customized (colored output, custom NtChallengeResponse in Reponder, ...)
  - [Resources](#bulb-resources): many resources can be useful during engagements. Those resources are not referred to as "tools" since they need to be run on a pwned target, and not on the attacker machine (e.g. mimikatz, rubeus, ...).
  - [History](#scroll-history): a populated history file that allows exegol users to save time and brain space by not having to remember every tool option and argument or checking the "help" every time.
  - [Aliases](#rocket-aliases): a file containing aliases that can be handful when using manually installed tools, or doing common operations.

  ![Screenshot Empire/DeathStar/mitm6/Responder/ntlmrelayx](https://i.imgur.com/PBThtlx.png)

# :fast_forward: Quick start
  **:construction: Docker Hub builds are failing right now (see [issue #11](https://github.com/ShutdownRepo/Exegol/issues/11)). For now, ignore this part and refer to [installation from GitHub](#install-from-github) and [usage](#usage)**
  The project is on Docker Hub, you don't need to clone this git.
  :warning: Don't run the `install.sh` script on your host. It is meant to run on the docker build.
  1. First set the following aliases in your bashrc/zshrc/whateverrc.
  ```
  alias exegol-update='docker pull nwodtuhs/exegol'
  alias exegol-build='docker build --tag nwodtuhs/exegol /PATH/TO/Exegol/'
  alias exegol-run='docker run --interactive --tty --detach --network host --volume /PATH/TO/Exegol/shared-volume:/share --name exegol nwodtuhs/exegol'
  alias exegol-shell='docker exec -it exegol zsh'
  alias exegol-stop='docker stop exegol && docker rm exegol'
  ```
  2. Then pull : `docker pull nwodtuhs/exegol`
  3. Then run the docker and get a shell : `exegol-run && exegol-shell`
  4. Stop it when you're done : `exegol-stop`

# :pushpin: Pre-requisites
  Docker is needed here if you want to run Exegol in a docker (intended). You can also use the `install.sh` in order to deploy Exegol elsewhere but I don't guarantee it'll work. (That being said I don't guarantee anything bro)

  Need a quick install of docker & docker-compose? Check this out (intended for kali users but I guess it could work on any other Debian based system)
  ```
  sudo apt-get install apt-transport-https ca-certificates curl gnupg-agent software-properties-common
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
  echo 'deb [arch=amd64] https://download.docker.com/linux/debian buster stable' | sudo tee /etc/apt/sources.list.d/docker.list
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io
  sudo curl -L "https://github.com/docker/compose/releases/download/1.25.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
  sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
  sudo curl -L https://raw.githubusercontent.com/docker/compose/1.25.3/contrib/completion/bash/docker-compose -o /etc/bash_completion.d/docker-compose
  sudo groupadd docker
  sudo usermod -aG docker $USER
  ```

# :whale: Install (from Docker Hub)
  **:construction: Docker Hub builds are failing right now (see [issue #11](/issues/11))**
  It can be long, pull exegol before needing it.
  ```
  docker pull nwodtuhs/exegol
  ```

# :octocat: Install (from GitHub)
  The build can be long, build exegol before needing it.
  :warning: Don't run the `install.sh` script on your host. It is meant to run on the docker build.
  ```
  git clone https://github.com/ShutdownRepo/Exegol
  cd Exegol
  docker build --tag exegol .
  ```

# :mag_right: Usage
  I personnaly use these aliases to go fast ([very fast](https://www.youtube.com/watch?v=KsBjVvxBj84))
  ```
  alias exegol-update='docker pull nwodtuhs/exegol'
  alias exegol-build='docker build --tag nwodtuhs/exegol /PATH/TO/Exegol/'
  alias exegol-run='docker run --interactive --tty --detach --network host --volume /PATH/TO/Exegol/shared-volume:/share --name exegol nwodtuhs/exegol'
  alias exegol-shell='docker exec -it exegol zsh'
  alias exegol-stop='docker stop exegol && docker rm exegol'
  ```
  - Update the docker : `exegol-update`
  - Run the docker : `exegol-run`
  - Get a shell when exegol is up and running (it is possible to pop multiple shells) : `exegol-shell`
  - Stop exegol : `exegol-stop`

# :wrench: Tools
  The tools installed in Exegol are mostly installed from sources in order to have the latest version when deploying Exegol. Some of the tools can be found in a complete kali install though. Some installs are made with go, pip, apt, gem etc. The installs are not perfect but hey, it works! You will find most of the tools in `/opt/tools`.
  Some of the tools:
  - Responder (https://github.com/lgandx/Responder)
  - CrackMapExec (https://github.com/byt3bl33d3r/CrackMapExec)
  - lsassy (https://github.com/Hackndo/lsassy)
  - sprayhound (https://github.com/Hackndo/sprayhound)
  - Impacket (https://github.com/SecureAuthCorp/impacket)
  - BloodHound.py (https://github.com/fox-it/BloodHound.py)
  - mitm6 (https://github.com/fox-it/mitm6)
  - dementor (https://gist.github.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc)
  - aclwpn (https://github.com/fox-it/aclpwn.py)
  - icebreaker (https://github.com/DanMcInerney/icebreaker)
  - Powershell Empire (https://github.com/BC-SECURITY/Empire)
  - DeathStar (https://github.com/byt3bl33d3r/DeathStar)
  - AutoRecon (https://github.com/Tib3rius/AutoRecon)
  - Sn1per (https://github.com/1N3/Sn1per)
  - Sublist3r (https://github.com/aboul3la/Sublist3r)
  - ReconDog (https://github.com/s0md3v/ReconDog)
  - CloudFail (https://github.com/m0rtem/CloudFail)
  - OneForAll (https://github.com/shmilylty/OneForAll)
  - EyeWitness (https://github.com/FortyNorthSecurity/EyeWitness)
  - wafw00f (https://github.com/EnableSecurity/wafw00f)
  - JSParser (https://github.com/nahamsec/JSParser)
  - LinkFinder (https://github.com/GerbenJavado/LinkFinder)
  - SSRFmap (https://github.com/swisskyrepo/SSRFmap)
  - fuxploider (https://github.com/almandin/fuxploider)
  - CORScanner (https://github.com/chenjj/CORScanner)
  - Blazy (https://github.com/UltimateHackers/Blazy)
  - XSStrike (https://github.com/UltimateHackers/Blazy)
  - Bolt (https://github.com/s0md3v/Bolt)
  - subjack (https://github.com/haccer/subjack)
  - assetfinder (https://github.com/tomnomnom/assetfinder)
  - subfinder (https://github.com/projectdiscovery/subfinder/cmd/subfinder)
  - gobuster (https://github.com/OJ/gobuster)
  - amass (https://github.com/OWASP/Amass)
  - ffuf (https://github.com/ffuf/ffuf)
  - gitrob (https://github.com/michenriksen/gitrob)
  - shhgit (https://github.com/eth0izzle/shhgit)
  - waybackurls (https://github.com/tomnomnom/waybackurls)
  - subzy (https://github.com/lukasikic/subzy)
  - findomain (https://github.com/Edu4rdSHL/findomain)
  - timing attack (https://github.com/ffleming/timing_attack)
  - updog (https://github.com/sc0tfree/updog)
  - grc (https://github.com/garabik/grc)
  - gron (https://github.com/tomnomnom/gron)
  - pwndbg (https://github.com/pwndbg/pwndbg)
  - darkarmour (https://github.com/bats3c/darkarmour)
  - bat (https://github.com/sharkdp/bat)
  - shellerator (https://github.com/ShutdownRepo/shellerator)
  - mdcat (https://github.com/lunaryorn/mdcat)
  - kadimus (https://github.com/P0cL4bs/Kadimus)
  - XSRFProbe (https://github.com/0xInfection/XSRFProbe)
  - NoSQLMap (https://github.com/codingo/NoSQLMap)
  - krbrelayx (https://github.com/dirkjanm/krbrelayx)
  - hakrawler (https://github.com/hakluke/hakrawler)
  - JWT tool (https://github.com/ticarpi/jwt_tool)
  - JWT cracker (https://github.com/lmammino/jwt-cracker)
  - gf (https://github.com/tomnomnom/gf)
  - wuzz (https://github.com/asciimoo/wuzz)
  - rbcd-attack (https://github.com/tothi/rbcd-attack)
  - evil-winrm (https://github.com/Hackplayers/evil-winrm)
  - pypykatz (https://github.com/skelsec/pypykatz)
  - enyx (https://github.com/trickster0/Enyx)

# :bulb: Resources
  In addition to the many tools pre-installed and configured for some, you will find many useful pre-fetched resources like scripts and binaries in `/opt/resources`. There some pre-EoP enumeration scripts (EoP: Escalation of Privileges) and other useful binaries like Rubeus or mimikatz.
  - LinEnum (https://github.com/rebootuser/LinEnum)
  - WinEnum (https://github.com/mattiareggiani/WinEnum)
  - Linux Smart Enumeration (lse.sh) (https://github.com/diego-treitos/linux-smart-enumeration)
  - Linux Exploit Suggester (les.sh) (https://github.com/mzet-/linux-exploit-suggester)
  - mimikatz (https://github.com/gentilkiwi/mimikatz)
  - linPEAS & winPEAS (https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite)
  - pspy (https://github.com/DominicBreuker/pspy)
  - sysinternals (https://docs.microsoft.com/en-us/sysinternals/downloads/)
  - PowerSploit (https://github.com/PowerShellMafia/PowerSploit)
  - PrivescCheck (https://github.com/itm4n/PrivescCheck)
  - Inveigh (https://github.com/Kevin-Robertson/Inveigh)
  - Rubeus (https://github.com/GhostPack/Rubeus) ([pre-compiled binary](https://github.com/r3motecontrol/Ghostpack-CompiledBinaries))
  - LaZagne (https://github.com/AlessandroZ/LaZagne)
  - SpoolSample (https://github.com/leechristensen/SpoolSample/)
  - PowerSploit (https://github.com/PowerShellMafia/PowerSploit)
  - mimipenguin (https://github.com/huntergregal/mimipenguin)
  - mimipy (https://github.com/n1nj4sec/mimipy)

# :scroll: History
  Another useful feature is the populated history. When I hack, I often rely on my history. I don't have to remember command line options, syntax and such. This history is filled with commands that I used in engagements, bugbounties, ctf, oscp and so on. Of course, the values are placeholders that need to be changed with the appropriate ones in your context.

# :rocket: Aliases
  Since many tools are manually installed in `/opt/tools/`, aliases could be heplful to use these without having to change directory manually.
  Other aliases are set to save time while hacking (`http-server`, `php-server`, `urlencode`,`ipa`, ...).

# :memo: To-Do List
  Here are some things to add/correct that I have in mind, I'll work on that asap
  - is it possible to use Wifi and Bluetooth??
  - history : ffuf with extensions
  - replace impacket install with original repo and manually add commit
  - Issue with dementor and grc, output is not printed unless the process has ended...
  - create a wiki instead of this really long readme?

# :loudspeaker: Credits & thanks
  Credits and thanks go to every infosec addicts that contribute and share but most specifically to [@th1b4ud](https://twitter.com/th1b4ud) for the base ["Kali Linux in 3 seconds with Docker"](https://thibaud-robin.fr/articles/docker-kali/).

# :movie_camera: Introducing Exegol (in french w/ english subs)
[![Introducing Exegol (french)](http://img.youtube.com/vi/TA3vrNpWGvg/0.jpg)](http://www.youtube.com/watch?v=TA3vrNpWGvg "Introducing Exegol (french)")
