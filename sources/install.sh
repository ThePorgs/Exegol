#!/bin/bash
# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

RED='\033[1;31m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
NOCOLOR='\033[0m'

function colorecho () {
  echo -e "${BLUE}$@${NOCOLOR}"
}

function update() {
  colorecho "[EXEGOL] Updating, upgrading, cleaning"
  apt-get -y update && apt-get -y install apt-utils lsb-release && apt-get -y upgrade && apt-get -y autoremove && apt-get clean
}

function fapt() {
  colorecho "[EXEGOL] Installing APT package: $@"
  apt-get install -y --no-install-recommends $@ || exit
}

function apt_packages() {
  colorecho "[EXEGOL] Installing APT packages"
  # this is easier to debug when there are dependencies issues and such. I install package by package to quickly locate errors.
  fapt aircrack-ng
  fapt crunch
  fapt curl
  fapt dirb
  fapt dirbuster
  fapt dnsenum
  fapt dnsrecon
  fapt dnsutils
  fapt dos2unix
  fapt enum4linux
  fapt exploitdb
  fapt ftp
  fapt git
  fapt hashcat
  fapt hping3
  fapt hydra
  fapt joomscan
  fapt masscan
  fapt metasploit-framework
  fapt mimikatz
  fapt nasm
  fapt ncat
  fapt netcat-traditional
  fapt nikto
  fapt nmap
  fapt patator
  fapt php
  #fapt powersploit
  fapt proxychains
  fapt python3
  fapt recon-ng
  fapt samba
  fapt samdump2
  fapt seclists
  fapt smbclient
  fapt smbmap
  fapt snmp
  fapt socat
  fapt sqlmap
  fapt sslscan
  fapt theharvester
  fapt tree
  fapt vim
  fapt nano
  fapt weevely
  fapt wfuzz
  fapt wget
  fapt whois
  fapt wordlists
  fapt seclists
  fapt wpscan
  fapt zsh
  fapt golang
  fapt ssh
  fapt iproute2
  fapt iputils-ping
  fapt python3-pip
  fapt python3-dev
  fapt sudo
  fapt tcpdump
  fapt gem
  fapt tidy
  fapt passing-the-hash
  fapt ssh-audit
  fapt whatweb
  fapt smtp-user-enum
  fapt onesixtyone
  fapt cewl
  fapt radare2
  fapt nbtscan
  fapt amap
  fapt python-dev
  fapt python2
  fapt file
  fapt dotdotpwn
  fapt xsser
  fapt rlwrap
  fapt lsof
  fapt bruteforce-luks
  fapt less
  fapt redis-tools
  fapt telnet
  fapt pst-utils
  fapt mariadb-client
  fapt fcrackzip
  fapt exiftool
  fapt tmux
  fapt man
  fapt x11-apps
  fapt hostapd-wpe
  fapt iproute2
  fapt reaver
  fapt bully
  fapt cowpatty
  DEBIAN_FRONTEND=noninteractive fapt macchanger
  DEBIAN_FRONTEND=noninteractive fapt wireshark
  DEBIAN_FRONTEND=noninteractive fapt tshark
  fapt imagemagick
  fapt mlocate
  fapt xsel
  fapt rpcbind
  fapt nfs-common
  fapt automake
  fapt autoconf
  fapt libtool
  fapt net-tools
  fapt python3-pyftpdlib
  fapt gpp-decrypt
  fapt gifsicle
  fapt padbuster
}

function python-pip() {
  colorecho "[EXEGOL] Installing python-pip"
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  rm get-pip.py
}

function filesystem() {
  colorecho "[EXEGOL] Preparing filesystem"
  mkdir -p /opt/tools/
  mkdir -p /opt/tools/bin/
  mkdir -p /data/
  mkdir -p /opt/resources/
  mkdir -p /opt/resources/windows/
  mkdir -p /opt/resources/linux/
  mkdir -p /opt/resources/mac/
  mkdir -p /opt/resources/webshells
  mkdir -p /opt/resources/webshells/PHP/
  mkdir -p /opt/resources/webshells/ASPX/
  mkdir -p /opt/resources/webshells/JSP/
  mkdir -p "/opt/resources/encrypted disks/"
}

function ohmyzsh() {
  colorecho "[EXEGOL] Installing oh-my-zsh, config, history, aliases"
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  cp /root/sources/zsh/history ~/.zsh_history
  cp /root/sources/zsh/aliases /opt/.zsh_aliases
  cp /root/sources/zsh/zshrc ~/.zshrc
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-autosuggestions
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-syntax-highlighting
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-completions
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/agkozak/zsh-z
}

function locales() {
  colorecho "[EXEGOL] Configuring locales"
  apt-get -y install locales
  sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && locale-gen
}

function tmux() {
  cp /root/sources/tmux/tmux.conf ~/.tmux.conf
  touch ~/.hushlogin
}

function dependencies() {
  colorecho "[EXEGOL] Installing most required dependencies"
  apt-get -y install python-setuptools python3-setuptools
  python3 -m pip install wheel
  python -m pip install wheel
}

function Responder() {
  colorecho "[EXEGOL] Installing Responder"
  git -C /opt/tools/ clone https://github.com/lgandx/Responder
  sed -i 's/ Random/ 1122334455667788/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/AccessDenied.html/\/opt\/tools\/Responder\/files\/AccessDenied.html/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/BindShell.exe/\/opt\/tools\/Responder\/files\/BindShell.exe/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.crt/\/opt\/tools\/Responder\/certs\/responder.crt/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.key/\/opt\/tools\/Responder\/certs\/responder.key/g' /opt/tools/Responder/Responder.conf
}

function Sublist3r() {
  colorecho "[EXEGOL] Installing Sublist3r"
  git -C /opt/tools/ clone https://github.com/aboul3la/Sublist3r.git
  python3 -m pip install -r /opt/tools/Sublist3r/requirements.txt
}

function ReconDog() {
  colorecho "[EXEGOL] Installing ReconDog"
  git -C /opt/tools/ clone https://github.com/s0md3v/ReconDog
  python3 -m pip install -r /opt/tools/ReconDog/requirements.txt
}

function CloudFail() {
  colorecho "[EXEGOL] Installing CloudFail"
  git -C /opt/tools/ clone https://github.com/m0rtem/CloudFail
  python3 -m pip install -r /opt/tools/CloudFail/requirements.txt
}

function OneForAll() {
  colorecho "[EXEGOL] Installing OneForAll"
  git -C /opt/tools/ clone https://github.com/shmilylty/OneForAll.git
  python3 -m pip install -r /opt/tools/OneForAll/requirements.txt
}

function EyeWitness() {
  colorecho "[EXEGOL] Installing EyeWitness"
  git -C /opt/tools/ clone https://github.com/FortyNorthSecurity/EyeWitness
  cd /opt/tools/EyeWitness/setup
  ./setup.sh
}

function wafw00f() {
  colorecho "[EXEGOL] Installing wafw00f"
  git -C /opt/tools/ clone https://github.com/EnableSecurity/wafw00f
  cd /opt/tools/wafw00f
  python setup.py install
}

function JSParser() {
  colorecho "[EXEGOL] Installing JSParser"
  git -C /opt/tools/ clone https://github.com/nahamsec/JSParser
  cd /opt/tools/JSParser
  python setup.py install
}

function LinkFinder() {
  colorecho "[EXEGOL] Installing LinkFinder"
  git -C /opt/tools/ clone https://github.com/GerbenJavado/LinkFinder.git
  cd /opt/tools/LinkFinder
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function SSRFmap() {
  colorecho "[EXEGOL] Installing SSRFmap"
  git -C /opt/tools/ clone https://github.com/swisskyrepo/SSRFmap
  cd /opt/tools/SSRFmap
  python3 -m pip install -r requirements.txt
}

function NoSQLMap() {
  colorecho "[EXEGOL] Installing NoSQLMap"
  git -C /opt/tools clone https://github.com/codingo/NoSQLMap.git
  cd /opt/tools/NoSQLMap
  python setup.py install
}

function fuxploider() {
  colorecho "[EXEGOL] Installing fuxploider"
  git -C /opt/tools/ clone https://github.com/almandin/fuxploider.git
  cd /opt/tools/fuxploider
  python3 -m pip install -r requirements.txt
}

function CORScanner() {
  colorecho "[EXEGOL] Installing CORScanner"
  git -C /opt/tools/ clone https://github.com/chenjj/CORScanner.git
  cd /opt/tools/CORScanner
  python -m pip install -r requirements.txt
}

function Blazy() {
  colorecho "[EXEGOL] Installing Blazy"
  git -C /opt/tools/ clone https://github.com/UltimateHackers/Blazy
  cd /opt/tools/Blazy
  python -m pip install -r requirements.txt
}

function XSStrike() {
  colorecho "[EXEGOL] Installing XSStrike"
  git -C /opt/tools/ clone https://github.com/s0md3v/XSStrike.git
  python3 -m pip install fuzzywuzzy
}

function Bolt() {
  colorecho "[EXEGOL] Installing Bolt"
  git -C /opt/tools/ clone https://github.com/s0md3v/Bolt.git
}

function CrackMapExec_pip() {
  colorecho "[EXEGOL] Installing CrackMapExec"
  apt-get -y install libssl-dev libffi-dev python-dev build-essential python3-winrm python3-venv
  python3 -m pip install pipx
  pipx ensurepath
  pipx install crackmapexec
  crackmapexec
}

function lsassy() {
  colorecho "[EXEGOL] Installing lsassy"
  git -C /opt/tools/ clone https://github.com/Hackndo/lsassy/
  cd /opt/tools/lsassy
  python3 setup.py install
  #wget -O /opt/tools/CrackMapExec/cme/modules/lsassy3.py https://raw.githubusercontent.com/Hackndo/lsassy/master/cme/lsassy3.py
  #cd /opt/tools/CrackMapExec
  #python3 setup.py install
  python3 -m pip install 'asn1crypto>=1.3.0'
}

function sprayhound() {
  colorecho "[EXEGOL] Installing sprayhound"
  git -C /opt/tools/ clone https://github.com/Hackndo/sprayhound
  cd /opt/tools/sprayhound
  apt-get -y install libsasl2-dev libldap2-dev
  python3 -m pip install "pyasn1<0.5.0,>=0.4.6"
  python3 setup.py install
}

function Impacket() {
  colorecho "[EXEGOL] Installing Impacket scripts"
  git -C /opt/tools/ clone https://github.com/SecureAuthCorp/impacket
  cd /opt/tools/impacket/
  cp /root/sources/patches/0001-User-defined-password-for-LDAP-attack-addComputer.patch 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  git apply 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  python3 -m pip install .
  cp /root/sources/grc/conf.ntlmrelayx /usr/share/grc/conf.ntlmrelayx
  cp /root/sources/grc/conf.secretsdump /usr/share/grc/conf.secretsdump
}

function bloodhound.py() {
  colorecho "[EXEGOL] Installing and Python ingestor for BloodHound"
  git -C /opt/tools/ clone https://github.com/fox-it/BloodHound.py
  cd /opt/tools/BloodHound.py/
  python setup.py install
}

function neo4j_install() {
  colorecho "[EXEGOL] Installing neo4j"
  wget -O - https://debian.neo4j.com/neotechnology.gpg.key | apt-key add -
  echo 'deb https://debian.neo4j.com stable latest' | tee /etc/apt/sources.list.d/neo4j.list
  apt-get update
  apt-get -y install --no-install-recommends gnupg libgtk2.0-bin libcanberra-gtk-module libx11-xcb1 libva-glx2 libgl1-mesa-glx libgl1-mesa-dri libgconf-2-4 libasound2 libxss1
  apt-get -y install neo4j
  #mkdir /usr/share/neo4j/conf
  neo4j-admin set-initial-password exegol4thewin
  mkdir -p /usr/share/neo4j/logs/
  touch /usr/share/neo4j/logs/neo4j.log
}

function cypheroth() {
  coloecho "[EXEGOL] Installing cypheroth"
  git -C /opt/tools/ clone https://github.com/seajaysec/cypheroth/
}

function mitm6_sources() {
  colorecho "[EXEGOL] Installing mitm6 from sources"
  git -C /opt/tools/ clone https://github.com/fox-it/mitm6
  cd /opt/tools/mitm6/
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function mitm6_pip() {
  colorecho "[EXEGOL] Installing mitm6 with pip"
  python3 -m pip install service_identity
  python3 -m pip install mitm6
}

function aclpwn() {
  colorecho "[EXEGOL] Installing aclpwn with pip"
  python3 -m pip install aclpwn
  sed -i 's/neo4j.v1/neo4j/g' /usr/local/lib/python3.8/dist-packages/aclpwn/database.py
}

function IceBreaker() {
  colorecho "[EXEGOL] Installing IceBreaker"
  apt-get -y install lsb-release python3-libtmux python3-libnmap python3-ipython
  python -m pip install pipenva
  git -C /opt/tools/ clone https://github.com/DanMcInerney/icebreaker
  cd /opt/tools/icebreaker/
  ./setup.sh
  pipenv --three install
}

function Empire() {
  colorecho "[EXEGOL] Installing Empire"
  export STAGING_KEY=$(echo exegol4thewin | md5sum | cut -d ' ' -f1)
  python -m pip install pefile
  git -C /opt/tools/ clone https://github.com/BC-SECURITY/Empire
  cd /opt/tools/Empire/setup
  ./install.sh
}

function DeathStar() {
  colorecho "[EXEGOL] Installing DeathStar"
  git -C /opt/tools/ clone https://github.com/byt3bl33d3r/DeathStar
  cd /opt/tools/DeathStar
  python3 -m pip install -r requirements.txt
}

function Sn1per() {
  colorecho "[EXEGOL] Installing Sn1per"
  git -C /opt/tools/ clone https://github.com/1N3/Sn1per
  sed -i 's/read answer/echo no answer to give/' /opt/tools/Sn1per/install.sh
  sed -i 's/cp/cp -v/g' /opt/tools/Sn1per/install.sh
  sed -i 's/mkdir/mkdir -v/g' /opt/tools/Sn1per/install.sh
  sed -i 's/rm/rm -v/g' /opt/tools/Sn1per/install.sh
  sed -i 's/mv/mv -v/g' /opt/tools/Sn1per/install.sh
  sed -i 's/wget/wget -v/g' /opt/tools/Sn1per/install.sh
  sed -i 's/2> \/dev\/null//g' /opt/tools/Sn1per/install.sh
  cd /opt/tools/Sn1per/
  bash install.sh
}

function dementor() {
  colorecho "[EXEGOL] Installing dementor"
  mkdir /opt/tools/dementor
  python -m pip install pycrypto
  wget -O /opt/tools/dementor/dementor.py https://gist.githubusercontent.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc/raw/7c7f09ea46eff4ede636f69c00c6dfef0541cd14/dementor.py
}

function subjack() {
  colorecho "[EXEGOL] Installing subjack"
  go get -u -v github.com/haccer/subjack
}

function assetfinder() {
  colorecho "[EXEGOL] Installing assetfinder"
  go get -u -v github.com/tomnomnom/assetfinder
}

function subfinder() {
  colorecho "[EXEGOL] Installing subfinder"
  go get -u -v github.com/projectdiscovery/subfinder/cmd/subfinder
}

function gobuster() {
  colorecho "[EXEGOL] Installing gobuster"
  go get -u -v github.com/OJ/gobuster
}

function amass() {
  colorecho "[EXEGOL] Installing amass"
  go get -v -u github.com/OWASP/Amass/v3/...
}

function ffuf() {
  colorecho "[EXEGOL] Installing ffuf"
  go get -v -u github.com/ffuf/ffuf
}

function gitrob() {
  colorecho "[EXEGOL] Installing gitrob"
  go get -v -u github.com/michenriksen/gitrob
}

function shhgit() {
  colorecho "[EXEGOL] Installing shhgit"
  go get -v -u github.com/eth0izzle/shhgit
}

function waybackurls() {
  colorecho "[EXEGOL] Installing waybackurls"
  go get -v -u github.com/tomnomnom/waybackurls
}

function subover() {
  colorecho "[EXEGOL] Installing SubOver"
  go get -v -u github.com/Ice3man543/SubOver
}

function subzy() {
  colorecho "[EXEGOL] Installing subzy"
  go get -u -v github.com/lukasikic/subzy
  go install -v github.com/lukasikic/subzy
}

function gron() {
  colorecho "[EXEGOL] Installing gron"
  go get -u -v github.com/tomnomnom/gron
}

function timing_attack() {
  colorecho "[EXEGOL] Installing timing_attack"
  gem install timing_attack
}

function updog() {
  colorecho "[EXEGOL] Installing updog"
  python3 -m pip install updog
}

function findomain() {
  colorecho "[EXEGOL] Installing findomain"
  wget -O /opt/tools/bin/findomain https://github.com/Edu4rdSHL/findomain/releases/latest/download/findomain-linux
  chmod +x /opt/tools/bin/findomain
}

function proxychains() {
  colorecho "[EXEGOL] Editing /etc/proxychains.conf for ntlmrelayx.py"
  cp /root/sources/proxychains/proxychains.conf /etc/proxychains.conf
}

function grc() {
  colorecho "[EXEGOL] Installing and configuring grc"
  apt-get -y install grc
  cp /root/sources/grc/grc.conf /etc/grc.conf
}

function pykek() {
  colorecho "[EXEGOL] Installing Python Kernel Exploit Kit (pykek) for MS14-068"
  git -C /opt/tools/ clone https://github.com/preempt/pykek
}

function autorecon() {
  colorecho "[EXEGOL] Installing autorecon"
  git -C /opt/tools/ clone https://github.com/Tib3rius/AutoRecon
  cd /opt/tools/AutoRecon/
  python3 -m pip install -r requirements.txt
}

function privexchange() {
  colorecho "[EXEGOL] Installing privexchange"
  git -C /opt/tools/ clone https://github.com/dirkjanm/PrivExchange
}

function LNKUp() {
  colorecho "[EXEGOL] Installing LNKUp"
  git -C /opt/tools/ clone https://github.com/Plazmaz/LNKUp
  cd /opt/tools/LNKUp
  python -m pip install -r requirements.txt
}

function pwntools() {
  colorecho "[EXEGOL] Installing pwntools"
  python -m pip install pwntools
  python3 -m pip install pwntools
}

function pwndbg() {
  colorecho "[EXEGOL] Installing pwndbg"
  apt-get -y install python3.8 python3.8-dev
  git -C /opt/tools/ clone https://github.com/pwndbg/pwndbg
  cd /opt/tools/pwndbg
  ./setup.sh
  echo 'set disassembly-flavor intel' >> ~/.gdbinit
}

function darkarmour() {
  colorecho "[EXEGOL] Installing darkarmour"
  git -C /opt/tools/ clone https://github.com/bats3c/darkarmour
  cd /opt/tools/darkarmour
  apt-get -y install mingw-w64-tools mingw-w64-common g++-mingw-w64 gcc-mingw-w64 upx-ucl osslsigncode
}

function powershell() {
  colorecho "[EXEGOL] Installing powershell"
  apt-get -y install powershell
  mv /opt/microsoft /opt/tools/microsoft
  rm /usr/bin/pwsh
  ln -s /opt/tools/microsoft/powershell/7/pwsh /usr/bin/pwsh
}

function fzf() {
  colorecho "[EXEGOL] Installing fzf"
  git -C /opt/tools/ clone --depth 1 https://github.com/junegunn/fzf.git
  cd /opt/tools/fzf
  ./install --all
}

function shellerator() {
  colorecho "[EXEGOL] Installing shellerator"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/shellerator
  cd /opt/tools/shellerator
  python3 -m pip install -r requirements.txt
}

function uberfile() {
  colorecho "[EXEGOL] Installing uberfile"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/uberfile
  cd /opt/tools/uberfile/
  python3 -m pip install -r requirements.txt
}

function kadimus() {
  colorecho "[EXEGOL] Installing kadimus"
  apt-get -y install libcurl4-openssl-dev libpcre3-dev libssh-dev
  git -C /opt/tools/ clone https://github.com/P0cL4bs/Kadimus
  cd /opt/tools/Kadimus
  make
}

function testssl() {
  colorecho "[EXEGOL] Installing testssl"
  apt-get -y install testssl.sh bsdmainutils
}

function bat() {
  colorecho "[EXEGOL] Installing bat"
  wget https://github.com/sharkdp/bat/releases/download/v0.13.0/bat_0.13.0_amd64.deb
  fapt -f ./bat_0.13.0_amd64.deb
  rm bat_0.13.0_amd64.deb
}

function mdcat() {
  colorecho "[EXEGOL] Installing mdcat"
  wget https://github.com/lunaryorn/mdcat/releases/download/mdcat-0.16.0/mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  tar xvfz mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  mv mdcat-0.16.0-x86_64-unknown-linux-musl/mdcat /opt/tools/bin
  rm -r mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz mdcat-0.16.0-x86_64-unknown-linux-musl
  chown root:root /opt/tools/bin/mdcat
}

function xsrfprobe() {
  colorecho "[EXEGOL] Installing XSRFProbe"
  git -C /opt/tools/ clone https://github.com/0xInfection/XSRFProbe
  cd /opt/tools/XSRFProbe
  python3 setup.py install
}

function krbrelayx() {
  colorecho "[EXEGOL] Installing krbrelayx"
  git -C /opt/tools/ clone https://github.com/dirkjanm/krbrelayx
}

function hakrawler() {
  colorecho "[EXEGOL] Installing hakrawler"
  go get -u -v github.com/hakluke/hakrawler
}

function jwt_tool() {
  colorecho "[EXEGOL] Installing JWT tool"
  git -C /opt/tools/ clone https://github.com/ticarpi/jwt_tool
  python3 -m pip install pycryptodomex
}

function jwt_cracker() {
  colorecho "[EXEGOL] Installing JWT cracker"
  apt-get -y install npm
  npm install --global jwt-cracker
}

function wuzz() {
  colorecho "[EXEGOL] Installing wuzz"
  go get -u -v github.com/asciimoo/wuzz
}

function gf_install() {
  colorecho "[EXEGOL] Installing gf"
  mkdir ~/.gf
  go get -u -v github.com/tomnomnom/gf
  echo 'source $GOPATH/src/github.com/tomnomnom/gf/gf-completion.zsh' >> ~/.zshrc
  cp -rv ~/go/src/github.com/tomnomnom/gf/examples/* ~/.gf
  gf -save redirect -HanrE 'url=|rt=|cgi-bin/redirect.cgi|continue=|dest=|destination=|go=|out=|redir=|redirect_uri=|redirect_url=|return=|return_path=|returnTo=|rurl=|target=|view=|from_url=|load_url=|file_url=|page_url=|file_name=|page=|folder=|folder_url=|login_url=|img_url=|return_url=|return_to=|next=|redirect=|redirect_to=|logout=|checkout=|checkout_url=|goto=|next_page=|file=|load_file='
}

function rockyou() {
  colorecho "[EXEGOL] Decompressing rockyou.txt"
  gunzip -d /usr/share/wordlists/rockyou.txt.gz
}

function rbcd-attack() {
  colorecho "[EXEGOL] Installing rbcd-attack"
  git -C /opt/tools/ clone https://github.com/tothi/rbcd-attack
}

function evilwinrm() {
  colorecho "[EXEGOL] Installing evil-winrm"
  gem install evil-winrm
}

function pypykatz() {
  colorecho "[EXEGOL] Installing pypykatz"
  python3 -m pip install pypykatz
}

function enyx() {
  colorecho "[EXEGOL] Installing enyx"
  git -C /opt/tools/ clone https://github.com/trickster0/Enyx
}

function enum4linux-ng() {
  colorecho "[EXEGOL] Installing enum4linux-ng"
  git -C /opt/tools/ clone https://github.com/cddmp/enum4linux-ng
}

function git-dumper() {
  colorecho "[EXEGOL] Installing git-dumper"
  git -C /opt/tools/ clone https://github.com/arthaud/git-dumper
  cd /opt/tools/git-dumper
  python3 -m pip install -r requirements.txt
}

function gittools(){
  colorecho "[EXEGOL] Installing GitTools"
  git -C /opt/tools/ clone https://github.com/internetwache/GitTools.git
}

function gopherus() {
  colorecho "[EXEGOL] Installing gopherus"
  git -C /opt/tools/ clone https://github.com/tarunkant/Gopherus
  cd /opt/tools/Gopherus
  ./install.sh
}

function ysoserial() {
  colorecho "[EXEGOL] Installing ysoserial"
  mkdir /opt/tools/ysoserial/
  wget -O /opt/tools/ysoserial/ysoserial.jar "https://jitpack.io/com/github/frohoff/ysoserial/master-SNAPSHOT/ysoserial-master-SNAPSHOT.jar"
}

function ysoserial_net() {
  colorecho "[EXEGOL] Downloading ysoserial"
  url=$(curl -s https://github.com/pwntester/ysoserial.net/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')
  tag=${url##*/}
  prefix=${tag:1}
  mkdir /opt/resources/windows/ysoserial.net
  wget -O /opt/resources/windows/ysoserial.net/ysoserial.zip "$url/ysoserial-$prefix.zip"
  unzip -d /opt/resources/windows/ysoserial.net /opt/tools/ysoserial.net/ysoserial.zip
  rm /opt/resources/windows/ysoserial.net/ysoserial.zip
}

function john() {
  colorecho "[EXEGOL] Installing john the ripper"
  fapt qtbase5-dev
  git -C /opt/tools/ clone https://github.com/openwall/john
  cd /opt/tools/john/src
  ./configure --disable-openmp
  make -s clean && make -sj4
  mv ../run/john ../run/john-non-omp
  ./configure CPPFLAGS='-DOMP_FALLBACK -DOMP_FALLBACK_BINARY="\"john-non-omp\""'
  make -s clean && make -sj4
  sudo make shell-completion
}

function memcached-cli() {
  colorecho "[EXEGOL] Installing memcached-cli"
  npm install -g memcached-cli
}

function zerologon() {
  colorecho "[EXEGOL] Pulling CVE-2020-1472 exploit and scan scripts"
  git -C /opt/tools/ clone https://github.com/SecuraBV/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-scan
  git -C /opt/tools/ clone https://github.com/dirkjanm/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-exploit
}

function proxmark3() {
  colorecho "[EXEGOL] Installing proxmark3 client"
  colorecho "[EXEGOL] Compiling proxmark client for generic usage with PLATFORM=PM3OTHER (read https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/md/Use_of_Proxmark/4_Advanced-compilation-parameters.md#platform)"
  colorecho "[EXEGOL] It can be compiled again for RDV4.0 with 'make clean && make all && make install' from /opt/tools/proxmak3/"
  apt-get -y install --no-install-recommends git ca-certificates build-essential pkg-config libreadline-dev gcc-arm-none-eabi libnewlib-dev qtbase5-dev libbz2-dev libbluetooth-dev
  git -C /opt/tools/ clone https://github.com/RfidResearchGroup/proxmark3.git
  cd /opt/tools/proxmark3
  make clean
  make all PLATFORM=PM3OTHER
  make install PLATFORM=PM3OTHER
}

function checksec_py() {
  colorecho "[EXEGOL] Installing checksec.py"
  python3 -m pip install checksec.py
}

function sysinternals() {
  colorecho "[EXEGOL] Downloading SysinternalsSuite"
  wget -O /opt/resources/windows/sysinternals.zip "https://download.sysinternals.com/files/SysinternalsSuite.zip"
  unzip -d /opt/resources/windows/sysinternals /opt/resources/windows/sysinternals.zip
  rm /opt/resources/windows/sysinternals.zip
}

function winenum() {
  colorecho "[EXEGOL] Downloading WinEnum"
  git -C /opt/resources/windows/ clone https://github.com/mattiareggiani/WinEnum
}

function pspy() {
  colorecho "[EXEGOL] Downloading pspy"
  mkdir -p /opt/resources/linux/pspy
  wget -O /opt/resources/linux/pspy/pspy32 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32"
  wget -O /opt/resources/linux/pspy/pspy64 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64"
  wget -O /opt/resources/linux/pspy/pspy32s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32s"
  wget -O /opt/resources/linux/pspy/pspy64s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64s"
}

function peass() {
  colorecho "[EXEGOL] Downloading PEAS Suite"
  git -C /opt/resources/ clone https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite
  cp /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x64/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x64.exe
  cp /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x86/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x86.exe
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/linPEAS /opt/resources/linux
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/winPEAS /opt/resources/windows
  rm -r /opt/resources/privilege-escalation-awesome-scripts-suite
}

function linux_smart_enumeration() {
  colorecho "[EXEGOL] Downloading Linux Smart Enumeration"
  wget -O /opt/resources/linux/lse.sh "https://github.com/diego-treitos/linux-smart-enumeration/raw/master/lse.sh"
}

function linenum() {
  colorecho "[EXEGOL] Downloading LinEnum"
  wget -O /opt/resources/linux/LinEnum.sh "https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh"
}

function linux_exploit_suggester() {
  colorecho "[EXEGOL] Downloading Linux Exploit Suggester"
  wget -O /opt/resources/linux/les.sh "https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh"
}

function mimikatz() {
  colorecho "[EXEGOL] Downloading mimikatz"
  wget -O /opt/resources/windows/mimikatz.zip "$(curl -s https://github.com/gentilkiwi/mimikatz/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/mimikatz_trunk.zip"
  unzip -d /opt/resources/windows/mimikatz /opt/resources/windows/mimikatz.zip
}

function mailsniper() {
  colorecho "[EXEGOL] Downloading MailSniper"
  git -C /opt/resources/windows/ clone https://github.com/dafthack/MailSniper
}

function powersploit() {
  colorecho "[EXEGOL] Downloading PowerSploit"
  git -C /opt/resources/windows/ clone https://github.com/PowerShellMafia/PowerSploit
}

function privesccheck() {
  colorecho "[EXEGOL] Downloading PrivescCheck"
  git -C /opt/resources/windows/ clone https://github.com/itm4n/PrivescCheck
}

function rubeus() {
  colorecho "[EXEGOL] Downloading Rubeus"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_3.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_4.5.exe"
}

function inveigh() {
  colorecho "[EXEGOL] Downloading Inveigh"
  git -C /opt/resources/windows https://github.com/Kevin-Robertson/Inveigh
}

function sharphound() {
  colorecho "[EXEGOL] Downloading SharpHound"
  mkdir /opt/resources/windows/SharpHound
  wget -P /opt/resources/windows/SharpHound/ "https://github.com/BloodHoundAD/BloodHound/raw/master/Ingestors/SharpHound.exe"
  wget -P /opt/resources/windows/SharpHound/ "https://github.com/BloodHoundAD/BloodHound/raw/master/Ingestors/SharpHound.ps1"
}

function juicypotato() {
  colorecho "[EXEGOL] Downloading JuicyPotato"
  wget -P /opt/resources/windows/ "$(curl -s https://github.com/ohpe/juicy-potato/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/JuicyPotato.exe"
}

function impacket_windows() {
  colorecho "[EXEGOL] Downloading Impacket examples for Windows"
  git -C /opt/resources/windows/ clone https://github.com/maaaaz/impacket-examples-windows
}

function webshells() {
  colorecho "[EXEGOL] Downloading webshells"
  git -C /opt/resources/webshells/PHP/ clone https://github.com/mIcHyAmRaNe/wso-webshell
  # Setting password to exegol4thewin
  sed -i 's/fa769dac7a0a94ee47d8ebe021eaba9e/0fc3bcf177377d328c77b2b51b7f3c9b/g' /opt/resources/webshells/PHP/wso-webshell/wso.php
  echo 'exegol4thewin' > /opt/resources/webshells/PHP/wso-webshell/password.txt
  git -C /opt/resources/webshells/PHP/ clone https://github.com/flozz/p0wny-shell
  wget -O /opt/resources/webshells/ASPX/webshell.aspx "https://raw.githubusercontent.com/xl7dev/WebShell/master/Aspx/ASPX%20Shell.aspx"
}

function nc() {
  colorecho "[EXEGOL] Downloading nc for Windows"
  cp /usr/bin/nc.traditional /opt/resources/linux/nc
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/nc.exe"
}

function http-put-server() {
  colorecho "[EXEGOL] Downloading http-put-server for Python3"
  wget -O /opt/resources/linux/http-put-server.py https://gist.githubusercontent.com/mildred/67d22d7289ae8f16cae7/raw/214c213c9415da18a471d1ed04660022cce059ef/server.py
}

function spoolsample() {
  colorecho "[EXEGOL] Downloading SpoolSample"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample_v4.5_x64..exe"
}

function diaghub() {
  colorecho "[EXEGOL] Downloading DiagHub"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/diaghub.exe"
}

function lazagne() {
  colorecho "[EXEGOL] Downloading LaZagne"
  git -C /tmp/ clone https://github.com/AlessandroZ/LaZagne
  mv /tmp/LaZagne/Linux /opt/resources/linux/LaZagne
  mv /tmp/LaZagne/Mac /opt/resources/mac/LaZagne
  mv /tmp/LaZagne/Windows /opt/resources/widnows/LaZagne
  wget -P /opt/resources/windows/LaZagne/ "$(curl -s https://github.com/AlessandroZ/LaZagne/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/lazagne.exe"
  rm -r /tmp/LaZagne
}

function sublinacl() {
  colorecho "[EXEGOL] Downloading Sublinacl"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/sublinacl.exe"
}

function powersploit() {
  colorecho "[EXEGOL] Downloading PowerSploit"
  git -C /opt/resources/windows/ clone https://github.com/PowerShellMafia/PowerSploit
}

function mimipenguin() {
  colorecho "[EXEGOL] Downloading mimipenguin"
  git -C /opt/resources/linux/ clone https://github.com/huntergregal/mimipenguin
}

function mimipy() {
  colorecho "[EXEGOL] Downloading mimipy"
  git -C /opt/resources/linux/ clone https://github.com/n1nj4sec/mimipy
}

function plink() {
  colorecho "[EXEGOL] Downloading plink"
  wget -O /opt/resources/windows/plink32.exe "https://the.earth.li/~sgtatham/putty/latest/w32/plink.exe"
  wget -O /opt/resources/windows/plink64.exe "https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe"
}

function deepce() {
  colorecho "[EXEGOL] Downloading deepce"
  wget -O /opt/resources/linux/deepce "https://github.com/stealthcopter/deepce/raw/master/deepce.sh"
}

function arsenal() {
  echo "[EXEGOL] Installing Arsenal"
  git -C /opt/tools/ clone https://github.com/Orange-Cyberdefense/arsenal
}

function bloodhound() {
  echo "[EXEGOL] Installing Bloodhound from latest release"
  fapt libxss1
  wget -P /tmp/ "$(curl -s https://github.com/BloodHoundAD/BloodHound/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/BloodHound-linux-x64.zip"
  unzip /tmp/BloodHound-linux-x64.zip -d /opt/tools/
  mv /opt/tools/BloodHound-linux-x64 /opt/tools/BloodHound3
  rm /tmp/BloodHound-linux-x64.zip
  mkdir -p ~/.config/bloodhound
  cp /root/sources/bloodhound/config.json ~/.config/bloodhound/config.json
  cp /root/sources/bloodhound/customqueries.json ~/.config/bloodhound/customqueries.json
}

function bloodhound_old_v2() {
  echo "[EXEGOL] Installing BloodHound v2 (for older databases/collections)"
  wget -P /tmp/ https://github.com/BloodHoundAD/BloodHound/releases/download/2.2.1/BloodHound-linux-x64.zip
  unzip /tmp/BloodHound-linux-x64.zip -d /opt/tools/
  mv /opt/tools/BloodHound-linux-x64 /opt/tools/BloodHound2
  rm /tmp/BloodHound-linux-x64.zip
}

function bettercap_install(){
  colorecho "[EXEGOL] Installing Bettercap"
  apt-get -y install libpcap-dev libusb-1.0-0-dev libnetfilter-queue-dev
  go get -u -v github.com/bettercap/bettercap
  bettercap -eval "caplets.update; ui.update; q"
  sed -i 's/set api.rest.username user/set api.rest.username bettercap/g' /usr/local/share/bettercap/caplets/http-ui.cap
  sed -i 's/set api.rest.password pass/set api.rest.password exegol4thewin/g' /usr/local/share/bettercap/caplets/http-ui.cap
  sed -i 's/set api.rest.username user/set api.rest.username bettercap/g' /usr/local/share/bettercap/caplets/https-ui.cap
  sed -i 's/set api.rest.password pass/set api.rest.password exegol4thewin/g' /usr/local/share/bettercap/caplets/https-ui.cap
}

function hcxtools() {
  colorecho "[EXEGOL] Installing hcxtools"
  git -C /opt/tools/ clone https://github.com/ZerBea/hcxtools
  cd /opt/tools/hcxtools/
  make
  make install
}

function hcxdumptool() {
  colorecho "[EXEGOL] Installing hcxdumptool"
  apt-get -y install libcurl4-openssl-dev libssl-dev
  git -C /opt/tools/ clone https://github.com/ZerBea/hcxdumptool
  cd /opt/tools/hcxdumptool
  make
  make install
  ln -s /usr/local/bin/hcxpcapngtool /usr/local/bin/hcxpcaptool
}

function pyrit() {
  colorecho "[EXEGOL] Installing pyrit"
  git -C /opt/tools clone https://github.com/JPaulMora/Pyrit
  cd /opt/tools/Pyrit
  python -m pip install psycopg2-binary scapy
  #https://github.com/JPaulMora/Pyrit/issues/591
  cp /root/sources/patches/undefined-symbol-aesni-key.patch undefined-symbol-aesni-key.patch
  git apply undefined-symbol-aesni-key.patch
  python setup.py clean
  python setup.py build
  python setup.py install
}

function wifite2() {
  colorecho "[EXEGOL] Installing wifite2"
  git -C /opt/tools/ clone https://github.com/derv82/wifite2.git
  cd /opt/tools/wifite2/
  python3 setup.py install
}

function wireshark_sources() {
  colorecho "[EXEGOL] Installing tshark, wireshark"
  apt-get -y install cmake libgcrypt20-dev libglib2.0-dev libpcap-dev qtbase5-dev libssh-dev libsystemd-dev qtmultimedia5-dev libqt5svg5-dev qttools5-dev libc-ares-dev flex bison byacc
  wget -O /tmp/wireshark.tar.xz https://www.wireshark.org/download/src/wireshark-latest.tar.xz
  cd /tmp/
  tar -xvf /tmp/wireshark.tar.xz
  cd $(find . -maxdepth 1 -type d -name 'wireshark*')
  cmake .
  make
  make install
  cd /tmp/
  rm -r $(find . -maxdepth 1 -type d -name 'wireshark*')
  wireshark.tar.xz
}

function infoga() {
  colorecho "[EXEGOL] Installing infoga"
  git -C /opt/tools/ clone https://github.com/m4ll0k/Infoga.git
  find /opt/tools/Infoga/ -type f -print0 | xargs -0 dos2unix
  cd /opt/tools/Infoga
  python setup.py install
}

function oaburl_py() {
  colorecho "[EXEGOL] Downloading oaburl.py"
  mkdir /opt/tools/OABUrl
  wget -O /opt/tools/OABUrl/oaburl.py "https://gist.githubusercontent.com/snovvcrash/4e76aaf2a8750922f546eed81aa51438/raw/96ec2f68a905eed4d519d9734e62edba96fd15ff/oaburl.py"
  chmod +x /opt/tools/OABUrl/oaburl.py
}

function libmspack() {
  colorecho "[EXEGOL] Installing libmspack"
  git -C /opt/tools/ clone https://github.com/kyz/libmspack.git
  cd /opt/tools/libmspack/libmspack
  ./rebuild.sh
  ./configure
  make
}

function peas_offensive() {
  colorecho "[EXEGOL] Installing PEAS-Offensive"
  git -C /opt/tools/ clone https://github.com/snovvcrash/peas.git peas-offensive
  python3 -m pip install pipenv
  cd /opt/tools/peas-offensive
  pipenv --python 2.7 install -r requirements.txt
}

function ruler() {
  colorecho "[EXEGOL] Downloading ruler and form templates"
  mkdir -p /opt/tools/ruler/templates
  wget -O /opt/tools/ruler/ruler "$(curl -s https://github.com/sensepost/ruler/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/ruler-linux64"
  chmod +x /opt/tools/ruler/ruler
  wget -O /opt/tools/ruler/templates/formdeletetemplate.bin "https://github.com/sensepost/ruler/raw/master/templates/formdeletetemplate.bin"
  wget -O /opt/tools/ruler/templates/formtemplate.bin "https://github.com/sensepost/ruler/raw/master/templates/formtemplate.bin"
  wget -O /opt/tools/ruler/templates/img0.bin "https://github.com/sensepost/ruler/raw/master/templates/img0.bin"
  wget -O /opt/tools/ruler/templates/img1.bin "https://github.com/sensepost/ruler/raw/master/templates/img1.bin"
}

function ghidra() {
  colorecho "[EXEGOL] Installing Ghidra"
  apt-get -y install openjdk-14-jdk
  wget -P /tmp/ "https://ghidra-sre.org/ghidra_9.1.2_PUBLIC_20200212.zip"
  unzip /tmp/ghidra_9.1.2_PUBLIC_20200212.zip -d /opt/tools
  rm /tmp/ghidra_9.1.2_PUBLIC_20200212.zip
}

function bitleaker() {
  colorecho "[EXEGOL] Downloading bitleaker for BitLocker TPM attacks"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/bitleaker
}

function napper() {
  colorecho "[EXEGOL] Download napper for TPM vuln scanning"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/napper-for-tpm
}

function sherlock() {
  colorecho "[EXEGOL] Installing sherlock"
  git -C /opt/tools/ clone https://github.com/sherlock-project/sherlock
  cd /opt/tools/sherlock
  python3 -m python -m pip install -r requirements.txt
}

function holehe() {
  colorecho "[EXEGOL] Installing holehe"
  python3 -m pip install holehe
}

function windapsearch-go() {
  colorecho "[EXEGOL] Installing Go windapsearch"
  wget -O /opt/tools/bin/windapsearch "$(curl -s https://github.com/ropnop/go-windapsearch/releases/latest/ | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/windapsearch-linux-amd64"
  chmod +x /opt/tools/bin/windapsearch
}

function icmptools() {
  colorecho "[EXEGOL] Installing icmptools"
  git -C /opt/tools/ clone https://github.com/krabelize/icmpdoor
  mkdir /opt/resources/windows/icmptools/ && cp -v /opt/tools/icmpdoor/binaries/x86_64-linux/* /opt/resources/windows/icmptools/
  mkdir /opt/resources/linux/icmptools/ && cp -v /opt/tools/icmpdoor/binaries/x86_64-linux/* /opt/resources/linux/icmptools/
}

function install_base() {
  update || exit
  apt_packages || exit
  python-pip
  filesystem
  locales
  ohmyzsh
  tmux
}

function install_tools() {
  dependencies
  grc
  Responder
  Sublist3r
  ReconDog
  CloudFail
  OneForAll
  EyeWitness
  wafw00f
  #JSParser
  LinkFinder
  SSRFmap
  NoSQLMap
  fuxploider
  CORScanner
  Blazy
  XSStrike
  Bolt
  CrackMapExec_pip
  sprayhound
  bloodhound.py
  neo4j_install
  cypheroth
  #mitm6_sources
  mitm6_pip
  aclpwn
  #IceBreaker
  Empire
  DeathStar
  #Sn1per
  dementor
  Impacket
  proxychains
  pykek
  lsassy
  subjack
  assetfinder
  subfinder
  gobuster
  amass
  ffuf
  gitrob
  shhgit
  waybackurls
  subover
  subzy
  gron
  timing_attack
  updog
  findomain
  autorecon
  privexchange
  pwntools
  pwndbg
  darkarmour
  powershell
  fzf
  shellerator
  kadimus
  testssl
  bat
  mdcat
  xsrfprobe
  krbrelayx
  hakrawler
  jwt_tool
  jwt_cracker
  wuzz
  gf_install
  rbcd-attack
  evilwinrm
  pypykatz
  enyx
  enum4linux-ng
  git-dumper
  gittools
  gopherus
  ysoserial
  john
  memcached-cli
  zerologon
  arsenal
  proxmark3
  #wireshark_sources
  bettercap_install
  hcxtools
  hcxdumptool
  pyrit
  wifite2
  infoga
  oaburl_py
  libmspack
  peas_offensive
  ruler
  checksec_py
  sherlock
  holehe
  windapsearch-go
  uberfile
}

function install_tools_gui() {
  bloodhound
  bloodhound_old_v2
  fapt freerdp2-x11
  ghidra
}

function install_resources() {
  sysinternals
  winenum
  pspy
  peass
  linux_smart_enumeration
  linenum
  linux_exploit_suggester
  mimikatz
  powersploit
  privesccheck
  rubeus
  inveigh
  sharphound
  juicypotato
  impacket_windows
  nc
  spoolsample
  diaghub
  lazagne
  sublinacl
  mimipenguin
  mimipy
  plink
  deepce
  rockyou
  webshells
  mailsniper
  ysoserial_net
  bitleaker
  napper
  http-put-server
}

function install_clean() {
  colorecho "[EXEGOL] Cleaning..."
  # I don't want this, I don't know yet what tools installs it, this should be a temporary fix
  rm /usr/local/bin/bloodhound-python
  #rm /tmp/gobuster.7z
  #rm -r /tmp/gobuster-linux-amd64
}

if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}"
  echo "You must be a root user" 2>&1
  echo -e "${NOCOLOR}"
  exit 1
else
  if declare -f "$1" > /dev/null
  then
    if [[ -f '/.dockerenv' ]]; then
      echo -e "${GREEN}"
      echo "This script is running in docker, as it should :)"
      echo "If you see things in red, don't panic, it's usually not errors, just badly handled colors"
      echo -e "${NOCOLOR}${BLUE}"
      echo "A successful build whill output the following last line:"
      echo "  Successfully tagged nwodtuhs/exegol:latest"
      echo -e "${NOCOLOR}"
      sleep 2
      "$@"
    else
      echo -e "${RED}"
      echo "[!] Careful : this script is supposed to be run inside a docker/VM, do not run this on your host unless you know what you are doing and have done backups. You are warned :)"
      echo "[*] Sleeping 30 seconds, just in case... You can still stop this"
      echo -e "${NOCOLOR}"
      sleep 30
      install_base
      install_tools
      install_tools_gui
      install_resources
      install_clean
    fi
  else
    echo "'$1' is not a known function name" >&2
    exit 1
  fi
fi
