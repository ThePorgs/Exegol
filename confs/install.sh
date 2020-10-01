#!/bin/bash
# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

BRANCH='dev'

RED='\033[1;31m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
NOCOLOR='\033[0m'

function colorecho () {
  echo -e "${BLUE}$@${NOCOLOR}"
}

function update() {
  colorecho "[EXEGOL] Updating, upgrading, cleaning"
  apt -y update && apt -y install apt-utils && apt -y upgrade && apt -y autoremove && apt clean
}

function fapt() {
  colorecho "[EXEGOL] Installing APT package: $@"
  apt install -y --no-install-recommends $@ || exit
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
  fapt powersploit
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
  fapt proxychains
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
  mkdir -p /share/
  mkdir -p /opt/resources/
  mkdir -p /opt/resources/windows/
  mkdir -p /opt/resources/linux/
  mkdir -p /opt/resources/mac/
}

function ohmyzsh() {
  colorecho "[EXEGOL] Installing oh-my-zsh, config, history, aliases"
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  wget -O ~/.zsh_history https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/zsh/history
  wget -O /opt/.zsh_aliases https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/zsh/aliases
  wget -O ~/.zshrc https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/zsh/zshrc
  git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions
  git clone https://github.com/zsh-users/zsh-syntax-highlighting ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting
  git clone https://github.com/zsh-users/zsh-completions ~/.oh-my-zsh/custom/plugins/zsh-completions
  echo "ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=#626262'" >> $ZSH_CUSTOM/my_patches.zsh
}

function dependencies() {
  colorecho "[EXEGOL] Installing most required dependencies"
  apt -y install python-setuptools python3-setuptools
  pip3 install wheel
  pip install wheel
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
  pip3 install -r /opt/tools/Sublist3r/requirements.txt
}

function ReconDog() {
  colorecho "[EXEGOL] Installing ReconDog"
  git -C /opt/tools/ clone https://github.com/s0md3v/ReconDog
  pip3 install -r /opt/tools/ReconDog/requirements.txt
}

function CloudFail() {
  colorecho "[EXEGOL] Installing CloudFail"
  git -C /opt/tools/ clone https://github.com/m0rtem/CloudFail
  pip3 install -r /opt/tools/CloudFail/requirements.txt
}

function OneForAll() {
  colorecho "[EXEGOL] Installing OneForAll"
  git -C /opt/tools/ clone https://github.com/shmilylty/OneForAll.git
  pip3 install -r /opt/tools/OneForAll/requirements.txt
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
  pip3 install -r requirements.txt
  python3 setup.py install
}

function SSRFmap() {
  colorecho "[EXEGOL] Installing SSRFmap"
  git -C /opt/tools/ clone https://github.com/swisskyrepo/SSRFmap
  cd /opt/tools/SSRFmap
  pip3 install -r requirements.txt
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
  pip3 install -r requirements.txt
}

function CORScanner() {
  colorecho "[EXEGOL] Installing CORScanner"
  git -C /opt/tools/ clone https://github.com/chenjj/CORScanner.git
  cd /opt/tools/CORScanner
  pip install -r requirements.txt
}

function Blazy() {
  colorecho "[EXEGOL] Installing Blazy"
  git -C /opt/tools/ clone https://github.com/UltimateHackers/Blazy
  cd /opt/tools/Blazy
  pip install -r requirements.txt
}

function XSStrike() {
  colorecho "[EXEGOL] Installing XSStrike"
  git -C /opt/tools/ clone https://github.com/s0md3v/XSStrike.git
  pip3 install fuzzywuzzy
}

function Bolt() {
  colorecho "[EXEGOL] Installing Bolt"
  git -C /opt/tools/ clone https://github.com/s0md3v/Bolt.git
}

function CrackMapExec_pip() {
  colorecho "[EXEGOL] Installing CrackMapExec"
  apt -y install libssl-dev libffi-dev python-dev build-essential python3-winrm python3-venv
  python3 -m pip install pipx
  pipx ensurepath
  pipx install crackmapexec
}

function lsassy() {
  colorecho "[EXEGOL] Installing lsassy"
  git -C /opt/tools/ clone https://github.com/Hackndo/lsassy/
  cd /opt/tools/lsassy
  python3 setup.py install
  #wget -O /opt/tools/CrackMapExec/cme/modules/lsassy3.py https://raw.githubusercontent.com/Hackndo/lsassy/master/cme/lsassy3.py
  #cd /opt/tools/CrackMapExec
  #python3 setup.py install
  pip3 install 'asn1crypto>=1.3.0'
}

function sprayhound() {
  colorecho "[EXEGOL] Installing sprayhound"
  git -C /opt/tools/ clone https://github.com/Hackndo/sprayhound
  cd /opt/tools/sprayhound
  apt -y install libsasl2-dev libldap2-dev
  pip3 install "pyasn1<0.5.0,>=0.4.6"
  python3 setup.py install
}

function Impacket() {
  colorecho "[EXEGOL] Installing Impacket scripts"
  git -C /opt/tools/ clone https://github.com/SecureAuthCorp/impacket
  cd /opt/tools/impacket/
  wget -O 0001-User-defined-password-for-LDAP-attack-addComputer.patch https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/patches/0001-User-defined-password-for-LDAP-attack-addComputer.patch
  git apply 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  pip3 install .
  wget -O /usr/share/grc/conf.ntlmrelayx https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/grc/conf.ntlmrelayx
  wget -O /usr/share/grc/conf.secretsdump https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/grc/conf.secretsdump
}

function bloodhound.py() {
  colorecho "[EXEGOL] Installing and Python ingestor for BloodHound"
  git -C /opt/tools/ clone https://github.com/fox-it/BloodHound.py
  cd /opt/tools/BloodHound.py/
  python setup.py install
}

function neo4j() {
  colorecho "[EXEGOL] Installing neo4j"
  apt -y install neo4j
  /usr/share/neo4j/bin/neo4j-admin set-initial-password exegol4thewin
  mkdir -p /usr/share/neo4j/logs/
  touch /usr/share/neo4j/logs/neo4j.log
}

function mitm6_sources() {
  colorecho "[EXEGOL] Installing mitm6 from sources"
  git -C /opt/tools/ clone https://github.com/fox-it/mitm6
  cd /opt/tools/mitm6/
  pip3 install --user -r requirements.txt
  python3 setup.py install
}

function mitm6_pip() {
  colorecho "[EXEGOL] Installing mitm6 with pip"
  pip3 install mitm6
}

function aclpwn() {
  colorecho "[EXEGOL] Installing aclpwn with pip"
  pip3 install aclpwn
  sed -i 's/neo4j.v1/neo4j/g' /usr/local/lib/python3.8/dist-packages/aclpwn/database.py
}

function IceBreaker() {
  colorecho "[EXEGOL] Installing IceBreaker"
  apt -y install lsb-release python3-libtmux python3-libnmap python3-ipython
  pip install pipenva
  git -C /opt/tools/ clone https://github.com/DanMcInerney/icebreaker
  cd /opt/tools/icebreaker/
  ./setup.sh
  pipenv --three install
}

function Empire() {
  colorecho "[EXEGOL] Installing Empire"
  export STAGING_KEY='123Soleil'
  pip install pefile
  git -C /opt/tools/ clone https://github.com/BC-SECURITY/Empire
  sed -i.bak 's/System.Security.Cryptography.HMACSHA256/System.Security.Cryptography.HMACSHA1/g' data/agent/stagers/*.ps1
  sed -i.bak 's/System.Security.Cryptography.HMACSHA256/System.Security.Cryptography.HMACSHA1/g' data/agent/agent.ps1
  sed -i.bak 's/hashlib.sha256/hashlib.sha1/g' lib/common/*.py
  sed -i.bak 's/hashlib.sha256/hashlib.sha1/g' data/agent/stagers/*.py
  cd /opt/tools/Empire/setup
  ./install.sh
}

function DeathStar() {
  colorecho "[EXEGOL] Installing DeathStar"
  git -C /opt/tools/ clone https://github.com/byt3bl33d3r/DeathStar
  cd /opt/tools/DeathStar
  pip3 install -r requirements.txt
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
  pip install pycrypto
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
  pip3 install updog
}

function findomain() {
  colorecho "[EXEGOL] Installing findomain"
  wget -O /opt/tools/bin/findomain https://github.com/Edu4rdSHL/findomain/releases/latest/download/findomain-linux
  chmod +x /opt/tools/bin/findomain
}

function proxychains() {
  colorecho "[EXEGOL] Editing /etc/proxychains.conf for ntlmrelayx.py"
  sed -i 's/9050/1080/g' /etc/proxychains.conf
}

function grc() {
  colorecho "[EXEGOL] Installing and configuring grc"
  apt -y install grc
  wget -O /etc/grc.conf https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/grc/grc.conf
}

function pykek() {
  colorecho "[EXEGOL] Installing Python Kernel Exploit Kit (pykek) for MS14-068"
  git -C /opt/tools/ clone https://github.com/preempt/pykek
}

function autorecon() {
  colorecho "[EXEGOL] Installing autorecon"
  git -C /opt/tools/ clone https://github.com/Tib3rius/AutoRecon
  cd /opt/tools/AutoRecon/
  pip3 install -r requirements.txt
}

function privexchange() {
  colorecho "[EXEGOL] Installing privexchange"
  git -C /opt/tools/ clone https://github.com/dirkjanm/PrivExchange
}

function LNKUp() {
  colorecho "[EXEGOL] Installing LNKUp"
  git -C /opt/tools/ clone https://github.com/Plazmaz/LNKUp
  cd /opt/tools/LNKUp
  pip install -r requirements.txt
}

function pwntools() {
  colorecho "[EXEGOL] Installing pwntools"
  pip install pwntools
  pip3 install pwntools
}

function pwndbg() {
  colorecho "[EXEGOL] Installing pwndbg"
  apt -y install python3.8 python3.8-dev
  git -C /opt/tools/ clone https://github.com/pwndbg/pwndbg
  cd /opt/tools/pwndbg
  ./setup.sh
  echo 'set disassembly-flavor intel' >> ~/.gdbinit
}

function darkarmour() {
  colorecho "[EXEGOL] Installing darkarmour"
  git -C /opt/tools/ clone https://github.com/bats3c/darkarmour
  cd /opt/tools/darkarmour
  apt -y install mingw-w64-tools mingw-w64-common g++-mingw-w64 gcc-mingw-w64 upx-ucl osslsigncode
}

function powershell() {
  colorecho "[EXEGOL] Installing powershell"
  apt -y install powershell
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
  git -C /opt/tools clone https://github.com/ShutdownRepo/shellerator
  cd /opt/tools/shellerator
  pip3 install -r requirements.txt
}

function kadimus() {
  colorecho "[EXEGOL] Installing kadimus"
  apt -y install libcurl4-openssl-dev libpcre3-dev libssh-dev
  git -C /opt/tools/ clone https://github.com/P0cL4bs/Kadimus
  cd /opt/tools/Kadimus
  make
}

function testssl() {
  colorecho "[EXEGOL] Installing testssl"
  apt -y install testssl.sh bsdmainutils
}

function bat() {
  colorecho "[EXEGOL] Installing bat"
  wget https://github.com/sharkdp/bat/releases/download/v0.13.0/bat_0.13.0_amd64.deb
  apt install -f ./bat_0.13.0_amd64.deb
  rm bat_0.13.0_amd64.deb
}

function mdcat() {
  colorecho "[EXEGOL] Installing mdcat"
  wget https://github.com/lunaryorn/mdcat/releases/download/mdcat-0.16.0/mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  tar xvfz mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  mv mdcat-0.16.0-x86_64-unknown-linux-musl/mdcat /opt/tools/bin
  rm -r mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz mdcat-0.16.0-x86_64-unknown-linux-musl
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
  pip3 install pycryptodomex
}

function jwt_cracker() {
  colorecho "[EXEGOL] Installing JWT cracker"
  apt -y install npm
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
  pip3 install pypykatz
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
  pip3 install -r requirements.txt
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

function john() {
  colorecho "[EXEGOL] Installing john the ripper"
  apt install qtbase5-dev
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
  apt -y install --no-install-recommends git ca-certificates build-essential pkg-config libreadline-dev gcc-arm-none-eabi libnewlib-dev qtbase5-dev libbz2-dev libbluetooth-dev
  git -C /opt/tools/ clone https://github.com/RfidResearchGroup/proxmark3.git
  cd /opt/tools/proxmark3
  make clean
  make all PLATFORM=PM3OTHER
  make install PLATFORM=PM3OTHER
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

function powersploit() {
  colorecho "[EXEGOL] Downloading PowerSploit"
  git -C /opt/resources/windows/ https://github.com/PowerShellMafia/PowerSploit
}

function privesccheck() {
  colorecho "[EXEGOL] Downloading PrivescCheck"
  git -C /opt/resources/windows/ https://github.com/itm4n/PrivescCheck
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
  mkdir -p /opt/resources/webshells/
  mkdir -p /opt/resources/webshells/PHP/
  mkdir -p /opt/resources/webshells/ASPX/
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

function bloodhound(){
  echo "[EXEGOL] Installing Bloodhound from latest release"
  wget -P /tmp/ "$(curl -s https://github.com/BloodHoundAD/BloodHound/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/BloodHound-linux-x64.zip"
  unzip /tmp/BloodHound-linux-x64.zip -d /opt/tools/
  mv /opt/tools/BloodHound-linux-x64 /opt/tools/BloodHound
  rm /tmp/BloodHound-linux-x64.zip
  mkdir -p ~/.config/bloodhound
  wget -O ~/.config/bloodhound/config.json https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/bloodhound/config.json
  wget -O ~/.config/bloodhound/customqueries.json https://raw.githubusercontent.com/ShutdownRepo/Exegol/$BRANCH/confs/bloodhound/customqueries.json
}

function install_base() {
  update || exit
  apt_packages || exit
  python-pip
  filesystem
  ohmyzsh
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
  neo4j
  #mitm6_sources
  mitm6_pip
  aclpwn
  IceBreaker
  Empire
  DeathStar
  Sn1per
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
}

function install_tools_gui() {
  bloodhound
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
  powersploit
  mimipenguin
  mimipy
  plink
  deepce
  rockyou
  webshells
}

function install_clean() {
  colorecho "[EXEGOL] Cleaning..."
  rm /tmp/gobuster.7z
  rm -r /tmp/gobuster-linux-amd64
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
