#!/bin/bash
# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

RED='\033[1;31m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
NOCOLOR='\033[0m'

function colorecho () {
  echo -e "${BLUE}[EXEGOL] $@${NOCOLOR}"
}

function update() {
  colorecho "Updating, upgrading, cleaning"
  apt-get -y update && apt-get -y install apt-utils && apt-get -y upgrade && apt-get -y autoremove && apt-get clean
}

function fapt() {
  colorecho "Installing APT package: $@"
  apt-get install -y --no-install-recommends "$@" || exit
}

function python-pip() {
  colorecho "Installing python-pip"
  curl --insecure https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  rm get-pip.py
}

function filesystem() {
  colorecho "Preparing filesystem"
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
  colorecho "Installing oh-my-zsh, config, history, aliases"
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  cp -v /root/sources/zsh/history ~/.zsh_history
  cp -v /root/sources/zsh/aliases /opt/.zsh_aliases
  cp -v /root/sources/zsh/zshrc ~/.zshrc
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-autosuggestions
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-syntax-highlighting
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/zsh-users/zsh-completions
  git -C ~/.oh-my-zsh/custom/plugins/ clone https://github.com/agkozak/zsh-z
}

function locales() {
  colorecho "Configuring locales"
  apt-get -y install locales
  sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && locale-gen
}

function tmux() {
  colorecho "Installing tmux"
  apt -y install tmux
  cp -v /root/sources/tmux/tmux.conf ~/.tmux.conf
  touch ~/.hushlogin
}

function dependencies() {
  colorecho "Installing most required dependencies"
  apt-get -y install python-setuptools python3-setuptools
  python3 -m pip install wheel
  python -m pip install wheel
}

function Responder() {
  colorecho "Installing Responder"
  git -C /opt/tools/ clone https://github.com/lgandx/Responder
  sed -i 's/ Random/ 1122334455667788/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/AccessDenied.html/\/opt\/tools\/Responder\/files\/AccessDenied.html/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/BindShell.exe/\/opt\/tools\/Responder\/files\/BindShell.exe/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.crt/\/opt\/tools\/Responder\/certs\/responder.crt/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.key/\/opt\/tools\/Responder\/certs\/responder.key/g' /opt/tools/Responder/Responder.conf
}

function Sublist3r() {
  colorecho "Installing Sublist3r"
  git -C /opt/tools/ clone https://github.com/aboul3la/Sublist3r.git
  python3 -m pip install -r /opt/tools/Sublist3r/requirements.txt
}

function ReconDog() {
  colorecho "Installing ReconDog"
  git -C /opt/tools/ clone https://github.com/s0md3v/ReconDog
  python3 -m pip install -r /opt/tools/ReconDog/requirements.txt
}

function CloudFail() {
  colorecho "Installing CloudFail"
  git -C /opt/tools/ clone https://github.com/m0rtem/CloudFail
  python3 -m pip install -r /opt/tools/CloudFail/requirements.txt
}

function OneForAll() {
  colorecho "Installing OneForAll"
  git -C /opt/tools/ clone https://github.com/shmilylty/OneForAll.git
  python3 -m pip install -r /opt/tools/OneForAll/requirements.txt
}

function EyeWitness() {
  colorecho "Installing EyeWitness"
  git -C /opt/tools/ clone https://github.com/FortyNorthSecurity/EyeWitness
  cd /opt/tools/EyeWitness/Python/setup
  ./setup.sh
}

function wafw00f() {
  colorecho "Installing wafw00f"
  git -C /opt/tools/ clone https://github.com/EnableSecurity/wafw00f
  cd /opt/tools/wafw00f
  python setup.py install
}

function JSParser() {
  colorecho "Installing JSParser"
  git -C /opt/tools/ clone https://github.com/nahamsec/JSParser
  cd /opt/tools/JSParser
  python setup.py install
}

function LinkFinder() {
  colorecho "Installing LinkFinder"
  git -C /opt/tools/ clone https://github.com/GerbenJavado/LinkFinder.git
  cd /opt/tools/LinkFinder
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function SSRFmap() {
  colorecho "Installing SSRFmap"
  git -C /opt/tools/ clone https://github.com/swisskyrepo/SSRFmap
  cd /opt/tools/SSRFmap
  python3 -m pip install -r requirements.txt
}

function NoSQLMap() {
  colorecho "Installing NoSQLMap"
  git -C /opt/tools clone https://github.com/codingo/NoSQLMap.git
  cd /opt/tools/NoSQLMap
  python setup.py install
}

function fuxploider() {
  colorecho "Installing fuxploider"
  git -C /opt/tools/ clone https://github.com/almandin/fuxploider.git
  cd /opt/tools/fuxploider
  python3 -m pip install -r requirements.txt
}

function CORScanner() {
  colorecho "Installing CORScanner"
  git -C /opt/tools/ clone https://github.com/chenjj/CORScanner.git
  cd /opt/tools/CORScanner
  python -m pip install -r requirements.txt
}

function Blazy() {
  colorecho "Installing Blazy"
  git -C /opt/tools/ clone https://github.com/UltimateHackers/Blazy
  cd /opt/tools/Blazy
  python -m pip install -r requirements.txt
}

function XSStrike() {
  colorecho "Installing XSStrike"
  git -C /opt/tools/ clone https://github.com/s0md3v/XSStrike.git
  python3 -m pip install fuzzywuzzy
}

function Bolt() {
  colorecho "Installing Bolt"
  git -C /opt/tools/ clone https://github.com/s0md3v/Bolt.git
}

function CrackMapExec_pip() {
  colorecho "Installing CrackMapExec"
  apt-get -y install libssl-dev libffi-dev python-dev build-essential python3-winrm python3-venv
  python3 -m pip install pipx
  pipx ensurepath
  pipx install crackmapexec
  # this is for having the ability to check the source code when working with modules and so on
  git -C /opt/tools/ clone https://github.com/byt3bl33d3r/CrackMapExec
  crackmapexec smb # this is for initializing everything TODO : need to check it works
}

function lsassy() {
  colorecho "Installing lsassy"
  git -C /opt/tools/ clone https://github.com/Hackndo/lsassy/
  cd /opt/tools/lsassy
  python3 setup.py install
  #wget -O /opt/tools/CrackMapExec/cme/modules/lsassy3.py https://raw.githubusercontent.com/Hackndo/lsassy/master/cme/lsassy3.py
  #cd /opt/tools/CrackMapExec
  #python3 setup.py install
  python3 -m pip install 'asn1crypto>=1.3.0'
}

function sprayhound() {
  colorecho "Installing sprayhound"
  git -C /opt/tools/ clone https://github.com/Hackndo/sprayhound
  cd /opt/tools/sprayhound
  apt-get -y install libsasl2-dev libldap2-dev
  python3 -m pip install "pyasn1<0.5.0,>=0.4.6"
  python3 setup.py install
}

function Impacket() {
  colorecho "Installing Impacket scripts"
  git -C /opt/tools/ clone https://github.com/SecureAuthCorp/impacket
  cd /opt/tools/impacket/
  cp -v /root/sources/patches/0001-User-defined-password-for-LDAP-attack-addComputer.patch 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  git apply 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  python3 -m pip install .
  cp -v /root/sources/grc/conf.ntlmrelayx /usr/share/grc/conf.ntlmrelayx
  cp -v /root/sources/grc/conf.secretsdump /usr/share/grc/conf.secretsdump
}

function bloodhound.py() {
  colorecho "Installing and Python ingestor for BloodHound"
  git -C /opt/tools/ clone https://github.com/fox-it/BloodHound.py
  cd /opt/tools/BloodHound.py/
  python setup.py install
}

function neo4j_install() {
  colorecho "Installing neo4j"
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
  coloecho "Installing cypheroth"
  git -C /opt/tools/ clone https://github.com/seajaysec/cypheroth/
}

function mitm6_sources() {
  colorecho "Installing mitm6 from sources"
  git -C /opt/tools/ clone https://github.com/fox-it/mitm6
  cd /opt/tools/mitm6/
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function mitm6_pip() {
  colorecho "Installing mitm6 with pip"
  python3 -m pip install service_identity
  python3 -m pip install mitm6
}

function aclpwn() {
  colorecho "Installing aclpwn with pip"
  python3 -m pip install aclpwn
  sed -i 's/neo4j.v1/neo4j/g' /usr/local/lib/python3.8/dist-packages/aclpwn/database.py
}

function IceBreaker() {
  colorecho "Installing IceBreaker"
  apt-get -y install lsb-release python3-libtmux python3-libnmap python3-ipython
  python -m pip install pipenva
  git -C /opt/tools/ clone https://github.com/DanMcInerney/icebreaker
  cd /opt/tools/icebreaker/
  ./setup.sh
  pipenv --three install
}

function Empire() {
  colorecho "Installing Empire"
  export STAGING_KEY=$(echo exegol4thewin | md5sum | cut -d ' ' -f1)
  python -m pip install pefile
  git -C /opt/tools/ clone https://github.com/BC-SECURITY/Empire
  cd /opt/tools/Empire/setup
  ./install.sh
}

function Sn1per() {
  colorecho "Installing Sn1per"
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
  colorecho "Installing dementor"
  mkdir /opt/tools/dementor
  python -m pip install pycrypto
  wget -O /opt/tools/dementor/dementor.py https://gist.githubusercontent.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc/raw/7c7f09ea46eff4ede636f69c00c6dfef0541cd14/dementor.py
}

function subjack() {
  colorecho "Installing subjack"
  go get -u -v github.com/haccer/subjack
}

function assetfinder() {
  colorecho "Installing assetfinder"
  go get -u -v github.com/tomnomnom/assetfinder
}

function subfinder() {
  colorecho "Installing subfinder"
  go get -u -v github.com/projectdiscovery/subfinder/cmd/subfinder
}

function gobuster() {
  colorecho "Installing gobuster"
  go get -u -v github.com/OJ/gobuster
}

function amass() {
  colorecho "Installing amass"
  go get -v -u github.com/OWASP/Amass/v3/...
}

function ffuf() {
  colorecho "Installing ffuf"
  go get -v -u github.com/ffuf/ffuf
}

function gitrob() {
  colorecho "Installing gitrob"
  go get -v -u github.com/michenriksen/gitrob
}

function shhgit() {
  colorecho "Installing shhgit"
  go get -v -u github.com/eth0izzle/shhgit
}

function waybackurls() {
  colorecho "Installing waybackurls"
  go get -v -u github.com/tomnomnom/waybackurls
}

function subover() {
  colorecho "Installing SubOver"
  go get -v -u github.com/Ice3man543/SubOver
}

function subzy() {
  colorecho "Installing subzy"
  go get -u -v github.com/lukasikic/subzy
  go install -v github.com/lukasikic/subzy
}

function gron() {
  colorecho "Installing gron"
  go get -u -v github.com/tomnomnom/gron
}

function timing_attack() {
  colorecho "Installing timing_attack"
  gem install timing_attack
}

function updog() {
  colorecho "Installing updog"
  python3 -m pip install updog
}

function findomain() {
  colorecho "Installing findomain"
  wget -O /opt/tools/bin/findomain https://github.com/Edu4rdSHL/findomain/releases/latest/download/findomain-linux
  chmod +x /opt/tools/bin/findomain
}

function proxychains() {
  colorecho "Installing proxychains"
  fapt proxychains
  cp -v /root/sources/proxychains/proxychains.conf /etc/proxychains.conf
}

function grc() {
  colorecho "Installing and configuring grc"
  apt-get -y install grc
  cp -v /root/sources/grc/grc.conf /etc/grc.conf
}

function pykek() {
  colorecho "Installing Python Kernel Exploit Kit (pykek) for MS14-068"
  git -C /opt/tools/ clone https://github.com/preempt/pykek
}

function autorecon() {
  colorecho "Installing autorecon"
  git -C /opt/tools/ clone https://github.com/Tib3rius/AutoRecon
  cd /opt/tools/AutoRecon/
  python3 -m pip install -r requirements.txt
}

function simplyemail() {
  colorecho "Installing SimplyEmail"
  git -C /opt/tools/ clone https://github.com/SimplySecurity/SimplyEmail.git
  cd /opt/tools/SimplyEmail/
  sudo bash setup/setup.sh
}

function privexchange() {
  colorecho "Installing privexchange"
  git -C /opt/tools/ clone https://github.com/dirkjanm/PrivExchange
}

function LNKUp() {
  colorecho "Installing LNKUp"
  git -C /opt/tools/ clone https://github.com/Plazmaz/LNKUp
  cd /opt/tools/LNKUp
  python -m pip install -r requirements.txt
}

function pwntools() {
  colorecho "Installing pwntools"
  python -m pip install pwntools
  python3 -m pip install pwntools
}

function pwndbg() {
  colorecho "Installing pwndbg"
  apt-get -y install python3.8 python3.8-dev
  git -C /opt/tools/ clone https://github.com/pwndbg/pwndbg
  cd /opt/tools/pwndbg
  ./setup.sh
  echo 'set disassembly-flavor intel' >> ~/.gdbinit
}

function darkarmour() {
  colorecho "Installing darkarmour"
  git -C /opt/tools/ clone https://github.com/bats3c/darkarmour
  cd /opt/tools/darkarmour
  apt-get -y install mingw-w64-tools mingw-w64-common g++-mingw-w64 gcc-mingw-w64 upx-ucl osslsigncode
}

function powershell() {
  colorecho "Installing powershell"
  apt-get -y install powershell
  mv /opt/microsoft /opt/tools/microsoft
  rm /usr/bin/pwsh
  ln -s /opt/tools/microsoft/powershell/7/pwsh /usr/bin/pwsh
}

function fzf() {
  colorecho "Installing fzf"
  git -C /opt/tools/ clone --depth 1 https://github.com/junegunn/fzf.git
  cd /opt/tools/fzf
  ./install --all
}

function shellerator() {
  colorecho "Installing shellerator"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/shellerator
  cd /opt/tools/shellerator
  python3 -m pip install -r requirements.txt
}

function uberfile() {
  colorecho "Installing uberfile"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/uberfile
  cd /opt/tools/uberfile/
  python3 -m pip install -r requirements.txt
}

function kadimus() {
  colorecho "Installing kadimus"
  apt-get -y install libcurl4-openssl-dev libpcre3-dev libssh-dev
  git -C /opt/tools/ clone https://github.com/P0cL4bs/Kadimus
  cd /opt/tools/Kadimus
  make
}

function testssl() {
  colorecho "Installing testssl"
  apt-get -y install testssl.sh bsdmainutils
}

function bat() {
  colorecho "Installing bat"
  wget https://github.com/sharkdp/bat/releases/download/v0.13.0/bat_0.13.0_amd64.deb
  fapt -f ./bat_0.13.0_amd64.deb
  rm bat_0.13.0_amd64.deb
}

function mdcat() {
  colorecho "Installing mdcat"
  wget https://github.com/lunaryorn/mdcat/releases/download/mdcat-0.16.0/mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  tar xvfz mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  mv mdcat-0.16.0-x86_64-unknown-linux-musl/mdcat /opt/tools/bin
  rm -r mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz mdcat-0.16.0-x86_64-unknown-linux-musl
  chown root:root /opt/tools/bin/mdcat
}

function xsrfprobe() {
  colorecho "Installing XSRFProbe"
  git -C /opt/tools/ clone https://github.com/0xInfection/XSRFProbe
  cd /opt/tools/XSRFProbe
  python3 setup.py install
}

function krbrelayx() {
  colorecho "Installing krbrelayx"
  git -C /opt/tools/ clone https://github.com/dirkjanm/krbrelayx
}

function hakrawler() {
  colorecho "Installing hakrawler"
  go get -u -v github.com/hakluke/hakrawler
}

function jwt_tool() {
  colorecho "Installing JWT tool"
  git -C /opt/tools/ clone https://github.com/ticarpi/jwt_tool
  python3 -m pip install pycryptodomex
}

function jwt_cracker() {
  colorecho "Installing JWT cracker"
  apt-get -y install npm
  npm install --global jwt-cracker
}

function wuzz() {
  colorecho "Installing wuzz"
  go get -u -v github.com/asciimoo/wuzz
}

function gf_install() {
  colorecho "Installing gf"
  mkdir ~/.gf
  go get -u -v github.com/tomnomnom/gf
  echo 'source $GOPATH/src/github.com/tomnomnom/gf/gf-completion.zsh' | tee -a ~/.zshrc
  cp -rv ~/go/src/github.com/tomnomnom/gf/examples/* ~/.gf
  # TODO: fix this when building : cp: cannot stat '/root/go/src/github.com/tomnomnom/gf/examples/*': No such file or directory
  gf -save redirect -HanrE 'url=|rt=|cgi-bin/redirect.cgi|continue=|dest=|destination=|go=|out=|redir=|redirect_uri=|redirect_url=|return=|return_path=|returnTo=|rurl=|target=|view=|from_url=|load_url=|file_url=|page_url=|file_name=|page=|folder=|folder_url=|login_url=|img_url=|return_url=|return_to=|next=|redirect=|redirect_to=|logout=|checkout=|checkout_url=|goto=|next_page=|file=|load_file='
}

function rockyou() {
  colorecho "Decompressing rockyou.txt"
  gunzip -d /usr/share/wordlists/rockyou.txt.gz
}

function rbcd-attack() {
  colorecho "Installing rbcd-attack"
  git -C /opt/tools/ clone https://github.com/tothi/rbcd-attack
}

function rbcd-permissions() {
  colorecho "Installing rbcd_permissions (alternative to rbcd-attack)"
  git -C /opt/tools/ clone https://github.com/NinjaStyle82/rbcd_permissions
}

function evilwinrm() {
  colorecho "Installing evil-winrm"
  gem install evil-winrm
}

function pypykatz() {
  colorecho "Installing pypykatz"
  python3 -m pip install pypykatz
}

function enyx() {
  colorecho "Installing enyx"
  git -C /opt/tools/ clone https://github.com/trickster0/Enyx
}

function enum4linux-ng() {
  colorecho "Installing enum4linux-ng"
  git -C /opt/tools/ clone https://github.com/cddmp/enum4linux-ng
}

function git-dumper() {
  colorecho "Installing git-dumper"
  git -C /opt/tools/ clone https://github.com/arthaud/git-dumper
  cd /opt/tools/git-dumper
  python3 -m pip install -r requirements.txt
}

function gittools() {
  colorecho "Installing GitTools"
  git -C /opt/tools/ clone https://github.com/internetwache/GitTools.git
}

function gopherus() {
  colorecho "Installing gopherus"
  git -C /opt/tools/ clone https://github.com/tarunkant/Gopherus
  cd /opt/tools/Gopherus
  ./install.sh
}

function ysoserial() {
  colorecho "Installing ysoserial"
  mkdir /opt/tools/ysoserial/
  wget -O /opt/tools/ysoserial/ysoserial.jar "https://jitpack.io/com/github/frohoff/ysoserial/master-SNAPSHOT/ysoserial-master-SNAPSHOT.jar"
}

function ysoserial_net() {
  colorecho "Downloading ysoserial"
  url=$(curl -s https://github.com/pwntester/ysoserial.net/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')
  tag=${url##*/}
  prefix=${tag:1}
  mkdir /opt/resources/windows/ysoserial.net
  wget -O /opt/resources/windows/ysoserial.net/ysoserial.zip "$url/ysoserial-$prefix.zip"
  unzip -d /opt/resources/windows/ysoserial.net /opt/tools/ysoserial.net/ysoserial.zip
  rm /opt/resources/windows/ysoserial.net/ysoserial.zip
}

function john() {
  colorecho "Installing john the ripper"
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
  colorecho "Installing memcached-cli"
  npm install -g memcached-cli
}

function zerologon() {
  colorecho "Pulling CVE-2020-1472 exploit and scan scripts"
  git -C /opt/tools/ clone https://github.com/SecuraBV/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-scan
  git -C /opt/tools/ clone https://github.com/dirkjanm/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-exploit
}

function proxmark3() {
  colorecho "Installing proxmark3 client"
  colorecho "Compiling proxmark client for generic usage with PLATFORM=PM3OTHER (read https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/md/Use_of_Proxmark/4_Advanced-compilation-parameters.md#platform)"
  colorecho "It can be compiled again for RDV4.0 with 'make clean && make all && make install' from /opt/tools/proxmak3/"
  apt-get -y install --no-install-recommends git ca-certificates build-essential pkg-config libreadline-dev gcc-arm-none-eabi libnewlib-dev qtbase5-dev libbz2-dev libbluetooth-dev
  git -C /opt/tools/ clone https://github.com/RfidResearchGroup/proxmark3.git
  cd /opt/tools/proxmark3
  make clean
  make all PLATFORM=PM3OTHER
  make install PLATFORM=PM3OTHER
}

function checksec_py() {
  colorecho "Installing checksec.py"
  python3 -m pip install checksec.py
}

function sysinternals() {
  colorecho "Downloading SysinternalsSuite"
  wget -O /opt/resources/windows/sysinternals.zip "https://download.sysinternals.com/files/SysinternalsSuite.zip"
  unzip -d /opt/resources/windows/sysinternals /opt/resources/windows/sysinternals.zip
  rm /opt/resources/windows/sysinternals.zip
}

function winenum() {
  colorecho "Downloading WinEnum"
  git -C /opt/resources/windows/ clone https://github.com/mattiareggiani/WinEnum
}

function pspy() {
  colorecho "Downloading pspy"
  mkdir -p /opt/resources/linux/pspy
  wget -O /opt/resources/linux/pspy/pspy32 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32"
  wget -O /opt/resources/linux/pspy/pspy64 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64"
  wget -O /opt/resources/linux/pspy/pspy32s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32s"
  wget -O /opt/resources/linux/pspy/pspy64s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64s"
}

function peass() {
  colorecho "Downloading PEAS Suite"
  git -C /opt/resources/ clone https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite
  cp -v /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x64/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x64.exe
  cp -v /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x86/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x86.exe
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/linPEAS /opt/resources/linux
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/winPEAS /opt/resources/windows
  rm -r /opt/resources/privilege-escalation-awesome-scripts-suite
}

function linux_smart_enumeration() {
  colorecho "Downloading Linux Smart Enumeration"
  wget -O /opt/resources/linux/lse.sh "https://github.com/diego-treitos/linux-smart-enumeration/raw/master/lse.sh"
}

function linenum() {
  colorecho "Downloading LinEnum"
  wget -O /opt/resources/linux/LinEnum.sh "https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh"
}

function linux_exploit_suggester() {
  colorecho "Downloading Linux Exploit Suggester"
  wget -O /opt/resources/linux/les.sh "https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh"
}

function mimikatz() {
  colorecho "Downloading mimikatz"
  wget -O /opt/resources/windows/mimikatz.zip "$(curl -s https://github.com/gentilkiwi/mimikatz/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/mimikatz_trunk.zip"
  unzip -d /opt/resources/windows/mimikatz /opt/resources/windows/mimikatz.zip
}

function mailsniper() {
  colorecho "Downloading MailSniper"
  git -C /opt/resources/windows/ clone https://github.com/dafthack/MailSniper
}

function powersploit() {
  colorecho "Downloading PowerSploit"
  git -C /opt/resources/windows/ clone https://github.com/PowerShellMafia/PowerSploit
}

function privesccheck() {
  colorecho "Downloading PrivescCheck"
  git -C /opt/resources/windows/ clone https://github.com/itm4n/PrivescCheck
}

function rubeus() {
  colorecho "Downloading Rubeus"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_3.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_4.5.exe"
}

function inveigh() {
  colorecho "Downloading Inveigh"
  git -C /opt/resources/windows https://github.com/Kevin-Robertson/Inveigh
}

function sharphound() {
  colorecho "Downloading SharpHound"
  wget -P /opt/resources/windows/ "https://raw.githubusercontent.com/BloodHoundAD/BloodHound/master/Collectors/SharpHound.exe"
  wget -P /opt/resources/windows/ "https://raw.githubusercontent.com/BloodHoundAD/BloodHound/master/Collectors/SharpHound.ps1"
}

function azurehound() {
  colorecho "Downloading AzureHound"
  wget -P /opt/resources/windows/ "https://raw.githubusercontent.com/BloodHoundAD/BloodHound/master/Collectors/AzureHound.ps1"
}

function juicypotato() {
  colorecho "Downloading JuicyPotato"
  wget -P /opt/resources/windows/ "$(curl -s https://github.com/ohpe/juicy-potato/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/JuicyPotato.exe"
}

function impacket_windows() {
  colorecho "Downloading Impacket examples for Windows"
  git -C /opt/resources/windows/ clone https://github.com/maaaaz/impacket-examples-windows
}

function webshells() {
  colorecho "Downloading webshells"
  git -C /opt/resources/webshells/PHP/ clone https://github.com/mIcHyAmRaNe/wso-webshell
  # Setting password to exegol4thewin
  sed -i 's/fa769dac7a0a94ee47d8ebe021eaba9e/0fc3bcf177377d328c77b2b51b7f3c9b/g' /opt/resources/webshells/PHP/wso-webshell/wso.php
  echo 'exegol4thewin' > /opt/resources/webshells/PHP/wso-webshell/password.txt
  git -C /opt/resources/webshells/PHP/ clone https://github.com/flozz/p0wny-shell
  wget -O /opt/resources/webshells/ASPX/webshell.aspx "https://raw.githubusercontent.com/xl7dev/WebShell/master/Aspx/ASPX%20Shell.aspx"
}

function nc() {
  colorecho "Downloading nc for Windows"
  cp -v /usr/bin/nc.traditional /opt/resources/linux/nc
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/nc.exe"
}

function http-put-server() {
  colorecho "Downloading http-put-server for Python3"
  wget -O /opt/resources/linux/http-put-server.py https://gist.githubusercontent.com/mildred/67d22d7289ae8f16cae7/raw/214c213c9415da18a471d1ed04660022cce059ef/server.py
}

function spoolsample() {
  colorecho "Downloading SpoolSample"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample_v4.5_x64..exe"
}

function diaghub() {
  colorecho "Downloading DiagHub"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/diaghub.exe"
}

function lazagne() {
  colorecho "Downloading LaZagne"
  git -C /tmp/ clone https://github.com/AlessandroZ/LaZagne
  mv /tmp/LaZagne/Linux /opt/resources/linux/LaZagne
  mv /tmp/LaZagne/Mac /opt/resources/mac/LaZagne
  mv /tmp/LaZagne/Windows /opt/resources/widnows/LaZagne
  wget -P /opt/resources/windows/LaZagne/ "$(curl -s https://github.com/AlessandroZ/LaZagne/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/lazagne.exe"
  rm -r /tmp/LaZagne
}

function sublinacl() {
  colorecho "Downloading Sublinacl"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/sublinacl.exe"
}

function powersploit() {
  colorecho "Downloading PowerSploit"
  git -C /opt/resources/windows/ clone https://github.com/PowerShellMafia/PowerSploit
}

function mimipenguin() {
  colorecho "Downloading mimipenguin"
  git -C /opt/resources/linux/ clone https://github.com/huntergregal/mimipenguin
}

function mimipy() {
  colorecho "Downloading mimipy"
  git -C /opt/resources/linux/ clone https://github.com/n1nj4sec/mimipy
}

function plink() {
  colorecho "Downloading plink"
  wget -O /opt/resources/windows/plink32.exe "https://the.earth.li/~sgtatham/putty/latest/w32/plink.exe"
  wget -O /opt/resources/windows/plink64.exe "https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe"
}

function deepce() {
  colorecho "Downloading deepce"
  wget -O /opt/resources/linux/deepce "https://github.com/stealthcopter/deepce/raw/master/deepce.sh"
}

function arsenal() {
  echo "Installing Arsenal"
  git -C /opt/tools/ clone https://github.com/Orange-Cyberdefense/arsenal
}

function bloodhound() {
  echo "Installing BloodHound from sources"
  git -C /opt/tools/ clone https://github.com/BloodHoundAD/BloodHound/
  mv /opt/tools/BloodHound /opt/tools/BloodHound4
  npm install -g electron-packager
  cd /opt/tools/BloodHound4
  npm install
  npm run linuxbuild
  mkdir -p ~/.config/bloodhound
  cp -v /root/sources/bloodhound/config.json ~/.config/bloodhound/config.json
  cp -v /root/sources/bloodhound/customqueries.json ~/.config/bloodhound/customqueries.json
}

function bloodhound_old_v3() {
  echo "Installing Bloodhound v3 (just-in-case)"
  fapt libxss1
  wget -P /tmp/ "https://github.com/BloodHoundAD/BloodHound/releases/download/3.0.5/BloodHound-linux-x64.zip"
  unzip /tmp/BloodHound-linux-x64.zip -d /opt/tools/
  mv /opt/tools/BloodHound-linux-x64 /opt/tools/BloodHound3
  rm /tmp/BloodHound-linux-x64.zip
}

function bloodhound_old_v2() {
  echo "Installing BloodHound v2 (for older databases/collections)"
  wget -P /tmp/ https://github.com/BloodHoundAD/BloodHound/releases/download/2.2.1/BloodHound-linux-x64.zip
  unzip /tmp/BloodHound-linux-x64.zip -d /opt/tools/
  mv /opt/tools/BloodHound-linux-x64 /opt/tools/BloodHound2
  rm /tmp/BloodHound-linux-x64.zip
}

function bettercap_install() {
  colorecho "Installing Bettercap"
  apt-get -y install libpcap-dev libusb-1.0-0-dev libnetfilter-queue-dev
  go get -u -v github.com/bettercap/bettercap
  bettercap -eval "caplets.update; ui.update; q"
  sed -i 's/set api.rest.username user/set api.rest.username bettercap/g' /usr/local/share/bettercap/caplets/http-ui.cap
  sed -i 's/set api.rest.password pass/set api.rest.password exegol4thewin/g' /usr/local/share/bettercap/caplets/http-ui.cap
  sed -i 's/set api.rest.username user/set api.rest.username bettercap/g' /usr/local/share/bettercap/caplets/https-ui.cap
  sed -i 's/set api.rest.password pass/set api.rest.password exegol4thewin/g' /usr/local/share/bettercap/caplets/https-ui.cap
}

function hcxtools() {
  colorecho "Installing hcxtools"
  git -C /opt/tools/ clone https://github.com/ZerBea/hcxtools
  cd /opt/tools/hcxtools/
  make
  make install
}

function hcxdumptool() {
  colorecho "Installing hcxdumptool"
  apt-get -y install libcurl4-openssl-dev libssl-dev
  git -C /opt/tools/ clone https://github.com/ZerBea/hcxdumptool
  cd /opt/tools/hcxdumptool
  make
  make install
  ln -s /usr/local/bin/hcxpcapngtool /usr/local/bin/hcxpcaptool
}

function pyrit() {
  colorecho "Installing pyrit"
  git -C /opt/tools clone https://github.com/JPaulMora/Pyrit
  cd /opt/tools/Pyrit
  python -m pip install psycopg2-binary scapy
  #https://github.com/JPaulMora/Pyrit/issues/591
  cp -v /root/sources/patches/undefined-symbol-aesni-key.patch undefined-symbol-aesni-key.patch
  git apply undefined-symbol-aesni-key.patch
  python setup.py clean
  python setup.py build
  python setup.py install
}

function wifite2() {
  colorecho "Installing wifite2"
  git -C /opt/tools/ clone https://github.com/derv82/wifite2.git
  cd /opt/tools/wifite2/
  python3 setup.py install
}

function wireshark_sources() {
  colorecho "Installing tshark, wireshark"
  apt-get -y install cmake libgcrypt20-dev libglib2.0-dev libpcap-dev qtbase5-dev libssh-dev libsystemd-dev qtmultimedia5-dev libqt5svg5-dev qttools5-dev libc-ares-dev flex bison byacc
  wget -O /tmp/wireshark.tar.xz https://www.wireshark.org/download/src/wireshark-latest.tar.xz
  cd /tmp/
  tar -xvf /tmp/wireshark.tar.xz
  cd "$(find . -maxdepth 1 -type d -name 'wireshark*')"
  cmake .
  make
  make install
  cd /tmp/
  rm -r "$(find . -maxdepth 1 -type d -name 'wireshark*')"
  wireshark.tar.xz
}

function infoga() {
  colorecho "Installing infoga"
  git -C /opt/tools/ clone https://github.com/m4ll0k/Infoga.git
  find /opt/tools/Infoga/ -type f -print0 | xargs -0 dos2unix
  cd /opt/tools/Infoga
  python setup.py install
}

function oaburl_py() {
  colorecho "Downloading oaburl.py"
  mkdir /opt/tools/OABUrl
  wget -O /opt/tools/OABUrl/oaburl.py "https://gist.githubusercontent.com/snovvcrash/4e76aaf2a8750922f546eed81aa51438/raw/96ec2f68a905eed4d519d9734e62edba96fd15ff/oaburl.py"
  chmod +x /opt/tools/OABUrl/oaburl.py
}

function libmspack() {
  colorecho "Installing libmspack"
  git -C /opt/tools/ clone https://github.com/kyz/libmspack.git
  cd /opt/tools/libmspack/libmspack
  ./rebuild.sh
  ./configure
  make
}

function peas_offensive() {
  colorecho "Installing PEAS-Offensive"
  git -C /opt/tools/ clone https://github.com/snovvcrash/peas.git peas-offensive
  python3 -m pip install pipenv
  cd /opt/tools/peas-offensive
  pipenv --python 2.7 install -r requirements.txt
}

function ruler() {
  colorecho "Downloading ruler and form templates"
  mkdir -p /opt/tools/ruler/templates
  wget -O /opt/tools/ruler/ruler "$(curl -s https://github.com/sensepost/ruler/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/ruler-linux64"
  chmod +x /opt/tools/ruler/ruler
  wget -O /opt/tools/ruler/templates/formdeletetemplate.bin "https://github.com/sensepost/ruler/raw/master/templates/formdeletetemplate.bin"
  wget -O /opt/tools/ruler/templates/formtemplate.bin "https://github.com/sensepost/ruler/raw/master/templates/formtemplate.bin"
  wget -O /opt/tools/ruler/templates/img0.bin "https://github.com/sensepost/ruler/raw/master/templates/img0.bin"
  wget -O /opt/tools/ruler/templates/img1.bin "https://github.com/sensepost/ruler/raw/master/templates/img1.bin"
}

function ghidra() {
  colorecho "Installing Ghidra"
  apt-get -y install openjdk-14-jdk
  wget -P /tmp/ "https://ghidra-sre.org/ghidra_9.1.2_PUBLIC_20200212.zip"
  unzip /tmp/ghidra_9.1.2_PUBLIC_20200212.zip -d /opt/tools
  rm /tmp/ghidra_9.1.2_PUBLIC_20200212.zip
}

function bitleaker() {
  colorecho "Downloading bitleaker for BitLocker TPM attacks"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/bitleaker
}

function napper() {
  colorecho "Download napper for TPM vuln scanning"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/napper-for-tpm
}

function sherlock() {
  colorecho "Installing sherlock"
  git -C /opt/tools/ clone https://github.com/sherlock-project/sherlock
  cd /opt/tools/sherlock
  python3 -m python -m pip install -r requirements.txt
}

function holehe() {
  colorecho "Installing holehe"
  python3 -m pip install holehe
}

function windapsearch-go() {
  colorecho "Installing Go windapsearch"
  wget -O /opt/tools/bin/windapsearch "$(curl -s https://github.com/ropnop/go-windapsearch/releases/latest/ | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/windapsearch-linux-amd64"
  chmod +x /opt/tools/bin/windapsearch
}

function icmpdoor() {
  colorecho "Installing icmptools"
  git -C /opt/tools/ clone https://github.com/krabelize/icmpdoor
  mkdir -p /opt/resources/windows/icmptools/
  cp -v /opt/tools/icmpdoor/binaries/x86_64-linux/* /opt/resources/windows/icmptools/
  mkdir -p /opt/resources/linux/icmptools/
  cp -v /opt/tools/icmpdoor/binaries/x86_64-linux/* /opt/resources/linux/icmptools/
}

function trilium() {
  colorecho "Installing Trilium"
  apt -y install libpng16-16 libpng-dev pkg-config autoconf libtool build-essential nasm libx11-dev libxkbfile-dev
  git -C /opt/tools/ clone -b stable https://github.com/zadam/trilium.git
  cd /opt/tools/trilium
  npm install
  mkdir /root/.local/share/trilium-data
  cp -v /root/sources/trilium/* /root/.local/share/trilium-data
}

function ntlmv1-multi() {
  colorecho "Installing ntlmv1 multi tool"
  git -C /opt/tools clone https://github.com/evilmog/ntlmv1-multi
}

function droopescan() {
  colorecho "Installing droopescan"
  git -C /opt/tools clone https://github.com/droope/droopescan.git
  cd /opt/tools/droopescan
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function simplyemail() {
  colorecho "Installing SimplyEmail"
  git -C /opt/tools/ clone https://github.com/SimplySecurity/SimplyEmail.git
  cd /opt/tools/SimplyEmail/
  bash setup/setup.sh
}

function maigret_pip() {
  colorecho "Installing maigret"
  pip3 install maigret
}

function amber() {
  colorecho "Installing amber"
  go get -u -v github.com/EgeBalci/amber
}

function install_base() {
  update || exit
  fapt man                        # Most important
  fapt git                        # Git client
  fapt lsb-release
  fapt pciutils
  fapt kmod
  fapt gifsicle
  fapt sudo                       # Sudo
  fapt curl                       # HTTP handler
  fapt wget                       # Wget
  fapt python3-pyftpdlib          # FTP server python library
  fapt php                        # Php language
  fapt python2                    # Python 2 language
  fapt python3                    # Python 3 language
  fapt python-dev                 # Python 2 language (dev version)
  fapt python3-dev                # Python 3 language (dev version)
  python-pip                      # Pip
  fapt python3-pip                # Pip
  filesystem
  locales
  fapt zsh                        # Awesome shell
  ohmyzsh                         # Awesome shell
  tmux                            # Tmux
  dependencies
  grc
  fapt golang                     # Golang language
  fapt gem                        # Install ruby packages
  fapt automake                   # Automake
  fapt autoconf                   # Autoconf
  fapt file                       # Detect type of file with magic number
  fapt lsof                       # Linux utility
  fapt less                       # Linux utility
  fapt x11-apps                   # Linux utility
  fapt net-tools                  # Linux utility
  fapt vim                        # Text editor
  fapt nano                       # Text editor (not the best)
  fapt iputils-ping               # Ping binary
  arsenal                         # Cheatsheets tool
  mdcat                           # cat markdown files
  bat                             # Beautiful cat
  fapt tidy                       # TODO: comment this
  fapt amap                       # TODO: comment this
  fapt mlocate                    # TODO: comment this
  fapt xsel                       # TODO: comment this
  fapt libtool                    # TODO: comment this
  fapt dnsutils                   # DNS utilities like dig and nslookup
  fapt dos2unix                   # Convert encoded dos script
  DEBIAN_FRONTEND=noninteractive fapt macchanger  # Macchanger
  fapt samba                      # Samba
  fapt ftp                        # FTP client
  fapt ssh                        # SSH client
  fapt telnet                     # Telnet client
  fapt nfs-common                 # NFS client
  fapt snmp                       # TODO: comment this
  fzf                             # File fuzzer
  fapt ncat                       # Socket manager
  fapt netcat-traditional         # Socket manager
  fapt socat                      # Socket manager
  #gf_install                      # wrapper around grep
}

# Package dedicated to most used offensive tools
function install_most_used_tools() {
  fapt exploitdb                  # Exploitdb downloaded locally
  fapt metasploit-framework       # Offensive framework
  fapt nmap                       # Port scanner
  john                            # Password cracker
  fapt seclists                   # Awesome wordlists
  subfinder                       # Subdomain bruteforcer
  autorecon                       # External recon tool
  gitrob                          # Senstive files reconnaissance in github
  waybackurls                     # Website history
  fapt theharvester               # Gather emails, subdomains, hosts, employee names, open ports and banners 
  simplyemail                     # Gather emails
  gobuster                        # Web fuzzer (pretty good for several extensions)
  ffuf                            # Web fuzzer (little favorites)
  fapt wfuzz                      # Web fuzzer (second favorites)
  fapt nikto                      # Web scanner
  fapt sqlmap                     # SQL injection scanner
  fapt hydra                      # Login scanner
  fapt joomscan                   # Joomla scanner
  fapt wpscan                     # Wordpress scanner
  droopescan                      # Drupal scanner
  testssl                         # SSL/TLS scanner
  fapt sslscan                    # SSL/TLS scanner
  fapt weevely                    # Awesome secure and light PHP webshell
  CloudFail                       # Cloudflare misconfiguration detector
  EyeWitness                      # Website screenshoter
  wafw00f                         # Waf detector
  jwt_tool                        # Toolkit for validating, forging, scanning and tampering JWTs
  gittools                        # Dump a git repository from a website
  ysoserial                       # Deserialization payloads
  Responder                       # LLMNR, NBT-NS and MDNS poisoner
  CrackMapExec_pip                # Network scanner
  Impacket                        # Network protocols scripts
  fapt enum4linux                 # Hosts enumeration
  fapt mimikatz                   # AD vulnerability exploiter
  fapt smbclient                  # Small dynamic library that allows iOS apps to access SMB/CIFS file servers
  fapt smbmap                     # Allows users to enumerate samba share drives across an entire domain
}

# Package dedicated to offensive miscellaneous tools
function install_misc_tools() {
  fapt exploitdb                  # Exploitdb downloaded locally
  fapt rlwrap                     # Reverse shell utility
  shellerator                     # Reverse shell generator
  uberfile                        # file uploader/downloader commands generator
  trilium                         # notes taking tool
  fapt exiftool                   # Meta information reader/writer
  fapt imagemagick                # Copy, modify, and distribute image
}

# Package dedicated to the installation of wordlists and tools like wl generators
function install_wordlists_tools() {
  fapt crunch                     # Wordlist generator
  fapt seclists                   # Awesome wordlists
  fapt wordlists                  # Others wordlists (not the best)
  fapt cewl                       # Wordlist generator
}

# Package dedicated to offline cracking/bruteforcing tools
function install_cracking_tools() {
  fapt hashcat                    # Password cracker
  john                            # Password cracker
  fapt fcrackzip                  # Zip cracker
  fapt bruteforce-luks            # Find the password of a LUKS encrypted volume
}

# Package dedicated to osint, recon and passive tools
function install_osint_tools() {
  Sublist3r                       # Subdomain bruteforcer
  subjack                         # Subdomain bruteforcer
  assetfinder                     # Subdomain bruteforcer
  subfinder                       # Subdomain bruteforcer
  subover                         # Subdomain bruteforcer
  subzy                           # Subdomain bruteforcer
  findomain                       # Subdomain bruteforcer
  fapt dnsenum                    # Subdomain bruteforcer
  fapt dnsrecon                   # Subdomain bruteforcer
  fapt recon-ng                   # External recon tool
  fapt whois                      # See information about a specific domain name or IP address
  ReconDog                        # Informations gathering tool
  JSParser                        # Parse JS files
  gitrob                          # Senstive files reconnaissance in github
  shhgit                          # Senstive files reconnaissance in github
  waybackurls                     # Website history
  gron                            # JSON parser
  infoga                          # Gathering email accounts informations
  sherlock                        # Hunt down social media accounts by username across social networks
  holehe                          # Check if the mail is used on different sites
  fapt theharvester               # Gather emails, subdomains, hosts, employee names, open ports and banners 
  simplyemail                     # Gather emails
  maigret_pip                     # Search pseudos and information about users on many platforms
}

# Package dedicated to applicative and active web pentest tools
function install_web_tools() {
  gobuster                        # Web fuzzer (pretty good for several extensions)
  amass                           # Web fuzzer
  ffuf                            # Web fuzzer (little favorites)
  fapt dirb                       # Web fuzzer
  fapt dirbuster                  # Web fuzzer
  fapt wfuzz                      # Web fuzzer (second favorites)
  fapt nikto                      # Web scanner
  fapt sqlmap                     # SQL injection scanner
  SSRFmap                         # SSRF scanner
  gopherus                        # SSRF helper
  NoSQLMap                        # NoSQL scanner
  XSStrike                        # XSS scanner
  fapt xsser                      # XSS scanner
  xsrfprobe                       # CSRF scanner
  Bolt                            # CSRF scanner
  fapt dotdotpwn                  # LFI scanner
  kadimus                         # LFI scanner
  fuxploider                      # File upload scanner
  Blazy                           # Login scanner
  fapt patator                    # Login scanner
  fapt joomscan                   # Joomla scanner
  fapt wpscan                     # Wordpress scanner
  droopescan                      # Drupal scanner
  testssl                         # SSL/TLS scanner
  fapt sslscan                    # SSL/TLS scanner
  fapt weevely                    # Awesome secure and light PHP webshell
  CloudFail                       # Cloudflare misconfiguration detector
  EyeWitness                      # Website screenshoter
  OneForAll                       # TODO: comment this
  wafw00f                         # Waf detector
  CORScanner                      # CORS misconfiguration detector
  hakrawler                       # Web endpoint discovery
  LinkFinder                      # Discovers endpoint JS files
  timing_attack                   # Cryptocraphic timing attack
  updog                           # New HTTPServer
  jwt_tool                        # Toolkit for validating, forging, scanning and tampering JWTs
  jwt_cracker                     # JWT cracker and bruteforcer
  wuzz                            # Burp cli
  git-dumper                      # Dump a git repository from a website
  gittools                        # Dump a git repository from a website
  fapt padbuster
  ysoserial                       # Deserialization payloads
  fapt whatweb                    # Recognises web technologies including content management
}

# Package dedicated to command & control frameworks
function install_c2_tools() {
  Empire                          # Exploit framework
  fapt metasploit-framework       # Offensive framework
  # TODO: add Silentrinity
  # TODO: add starkiller
}

# Package dedicated to specific services tools apart from HTTP/HTTPS (e.g. SSH, and so on)
install_services_tools() {
  fapt ssh-audit                  # SSH server audit
  fapt hydra                      # Login scanner
  memcached-cli                   # TODO: comment this
  fapt mariadb-client             # Mariadb client
  fapt redis-tools                # Redis protocol
}

# Package dedicated to internal Active Directory tools
function install_ad_tools() {
  Responder                       # LLMNR, NBT-NS and MDNS poisoner
  CrackMapExec_pip                # Network scanner
  sprayhound                      # Password spraying tool
  bloodhound.py                   # AD cartographer
  neo4j_install                   # Bloodhound dependency
  cypheroth                       # Bloodhound dependency
  # mitm6_sources                 # Install mitm6 from sources
  mitm6_pip                       # DNS server misconfiguration exploiter
  aclpwn                          # ACL exploiter
  # IceBreaker                    # TODO: comment this
  dementor                        # SpoolService exploiter
  Impacket                        # Network protocols scripts
  pykek                           # AD vulnerability exploiter
  lsassy                          # Credentials extracter
  privexchange                    # Exchange exploiter
  ruler                           # Exchange exploiter
  darkarmour                      # Windows AV evasion
  amber                           # AV evasion
  powershell                      # Windows Powershell for Linux
  krbrelayx                       # Kerberos unconstrained delegation abuse toolkit
  rbcd-attack                     # Kerberos Resource-Based Constrained Delegation Attack
  rbcd-permissions                # Kerberos Resource-Based Constrained Delegation Attack
  evilwinrm                       # WinRM shell
  pypykatz                        # Mimikatz implementation in pure Python
  enyx                            # Hosts discovery
  fapt enum4linux                 # Hosts enumeration
  enum4linux-ng                   # Hosts enumeration
  zerologon                       # Exploit for zerologon cve-2020-1472
  libmspack                       # Library for some loosely related Microsoft compression format
  peas_offensive                  # Library and command line application for running commands on Microsoft Exchange
  windapsearch-go                 # Active Directory Domain enumeration through LDAP queries
  oaburl_py                       # Send request to the MS Exchange Autodiscover service
  LNKUp
  fapt mimikatz                   # AD vulnerability exploiter
  fapt samdump2                   # Dumps Windows 2k/NT/XP/Vista password hashes
  fapt smbclient                  # Small dynamic library that allows iOS apps to access SMB/CIFS file servers
  fapt smbmap                     # Allows users to enumerate samba share drives across an entire domain
  fapt passing-the-hash           # Pass the hash attack
  fapt smtp-user-enum             # SMTP user enumeration via VRFY, EXPN and RCPT
  fapt onesixtyone                # SNMP scanning
  fapt nbtscan                    # NetBIOS scanning tool
  fapt rpcbind                    # RPC scanning
  fapt gpp-decrypt                # Decrypt a given GPP encrypted string
  ntlmv1-multi                    # NTLMv1 multi tools: modifies NTLMv1/NTLMv1-ESS/MSCHAPv2
}

# Package dedicated to mobile apps pentest tools
function install_mobile_tools() {
  continue
  # TODO
}

# Package dedicated to RFID pentest tools
function install_rfid_tools() {
  proxmark3                       # Proxmark3 scripts
  # TODO
}

function install_sdr_tools() {
  continue
  # TODO
}

# Package dedicated to network pentest tools
function install_network_tools() {
  proxychains                     # Network tool
  DEBIAN_FRONTEND=noninteractive fapt wireshark # Wireshark packet sniffer
  DEBIAN_FRONTEND=noninteractive fapt tshark    # Tshark packet sniffer
  # wireshark_sources             # Install Wireshark from sources
  fapt hping3                     # Discovery tool
  fapt masscan                    # Port scanner
  fapt nmap                       # Port scanner
  autorecon                       # External recon tool
  # Sn1per                        # Vulnerability scanner
  fapt iproute2                   # Firewall rules
  fapt tcpdump                    # Capture TCP traffic
}

# Package dedicated to wifi pentest tools
function install_wifi_tools() {
  pyrit                           # Databases of pre-computed WPA/WPA2-PSK authentication phase
  wifite2                         # Retrieving password of a wireless access point (router)
  fapt aircrack-ng                # WiFi security auditing tools suite
  fapt hostapd-wpe                # Modified hostapd to facilitate AP impersonation attacks
  fapt reaver                     # Brute force attack against Wifi Protected Setup
  fapt bully                      # WPS brute force attack
  fapt cowpatty                   # WPA2-PSK Cracking
  bettercap_install               # MiTM tool
  hcxtools                        # Tools for PMKID and other wifi attacks
  hcxdumptool                     # Small tool to capture packets from wlan devices
}

# Package dedicated to forensic tools
function install_forensic_tools() {
  fapt pst-utils                  # Reads a PST and prints the tree structure to the console
  # TODO: add volatility
}

# Package dedicated to steganography tools
function install_steganography_tools() {
  continue
  # TODO
}

# Package dedicated to reverse engineering tools
function install_reverse_tools() {
  pwntools                        # CTF framework and exploit development library
  pwndbg                          # Advanced Gnu Debugger
  checksec_py                     # Check security on binaries
  fapt nasm                       # Netwide Assembler
  fapt radare2                    # Awesome debugger
}

# Package dedicated to GUI-based apps
function install_GUI_tools() {
  bloodhound
  bloodhound_old_v3
  bloodhound_old_v2
  fapt freerdp2-x11
  ghidra
}

# Package dedicated to the download of resources
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
  azurehound
  icmpdoor
}

# Function used to clean up post-install files
function install_clean() {
  colorecho "Cleaning..."
  # TODO: clean /tmp and other dirs
  # rm -r /tmp/*
  # rm /usr/local/bin/bloodhound-python
  # rm /tmp/gobuster.7z
  # rm -r /tmp/gobuster-linux-amd64
}

# Entry point for the installation
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
      "$@"
    fi
  else
    echo "'$1' is not a known function name" >&2
    exit 1
  fi
fi
