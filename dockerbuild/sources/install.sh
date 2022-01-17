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
  colorecho "Installing apt-get package: $@"
  apt-get install -y --no-install-recommends "$@" || exit
}

function python-pip() {
  colorecho "Installing python-pip (for Python2.7)"
  curl --insecure https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py
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
  apt-get -y install tmux
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
  fapt gcc-mingw-w64-x86-64
  x86_64-w64-mingw32-gcc /opt/tools/Responder/tools/MultiRelay/bin/Runas.c -o /opt/tools/Responder/tools/MultiRelay/bin/Runas.exe -municode -lwtsapi32 -luserenv
  x86_64-w64-mingw32-gcc /opt/tools/Responder/tools/MultiRelay/bin/Syssvc.c -o /opt/tools/Responder/tools/MultiRelay/bin/Syssvc.exe -municode
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

function githubemail() {
  colorecho "Installing github-email"
  npm install --global github-email
}

function onionsearch() {
  colorecho "Installing onionsearch"
  git -C /opt/tools/ clone https://github.com/megadose/onionsearch
  cd /opt/tools/onionsearch
  python3 setup.py install
  rm -rf /opt/tools/onionsearch
}

function photon() {
  colorecho "Installing photon"
  git -C /opt/tools/ clone https://github.com/s0md3v/photon
  python3 -m pip install -r /opt/tools/photon/requirements.txt
}


function WikiLeaker() {
  colorecho "Installing WikiLeaker"
  git -C /opt/tools/ clone https://github.com/jocephus/WikiLeaker.git
  python3 -m pip install -r /opt/tools/WikiLeaker/requirements.txt
}


function OSRFramework() {
  colorecho "Installing OSRFramework"
  python3 -m pip install osrframework
}

function sn0int() {
  colorecho "Installing sn0int"
  apt-get install debian- -y
  gpg -a --export --keyring /usr/share/keyrings/debian-maintainers.gpg git@rxv.cc | apt-key add -
  apt-key adv --keyserver keyserver.ubuntu.com --refresh-keys git@rxv.cc
  echo deb http://apt.vulns.sexy stable main > /etc/apt/sources.list.d/apt-vulns-sexy.list
  apt-get update -y
  apt-get install sn0int -y
  apt-get install --fix-broken -y
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

function install_odat() {
  odat_latest=$(curl -L -s https://github.com/quentinhardy/odat/releases/latest | grep tar.gz | cut -d '"' -f 2 | head -1)
  wget "https://github.com/$odat_latest" -O /tmp/odat_latest.tar.gz
  mkdir -p /opt/tools/odat
  tar xvf /tmp/odat_latest.tar.gz -C /opt/tools/odat --strip=2
  mv /opt/tools/odat/odat* /opt/tools/odat/odat
  echo -e '#!/bin/sh\n(cd /opt/tools/odat/ && ./odat $@)' > /usr/local/bin/odat
  chmod +x /usr/local/bin/odat
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

function install_XSpear() {
  colorecho "Installing XSpear"
  gem install XSpear
}

function install_pass_station() {
  colorecho "Installing Pass Station"
  gem install pass-station
}

function evilwinrm() {
  colorecho "Installing evil-winrm"
  gem install evil-winrm
}

function Bolt() {
  colorecho "Installing Bolt"
  git -C /opt/tools/ clone https://github.com/s0md3v/Bolt.git
}

function install_crackmapexec() {
  colorecho "Installing CrackMapExec"
  apt-get -y install libssl-dev libffi-dev python-dev build-essential python3-winrm python3-venv
  git -C /opt/tools/ clone --recursive https://github.com/byt3bl33d3r/CrackMapExec
  cd /opt/tools/CrackMapExec
  python3 -m pipx install .
  # this is for having the ability to check the source code when working with modules and so on
  #git -C /opt/tools/ clone https://github.com/byt3bl33d3r/CrackMapExec
#  apt-get -y install crackmapexec
}

function install_lsassy() {
  colorecho "Installing lsassy"
  git -C /opt/tools/ clone https://github.com/Hackndo/lsassy/
  cd /opt/tools/lsassy
  git checkout 3.0.0
  git pull origin 3.0.0
  python3 setup.py install
  # python3 -m pip install 'asn1crypto>=1.3.0'
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
  # User-defined password for LDAP attack addComputer
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1063.patch | git apply --verbose
  # rcbd.py in examples
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1108.patch | git apply --verbose
  # Shadow Credentials in ntlmrelayx.py
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1132.patch | git apply --verbose
  # AD CS in ntlmrelayx.py
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1101.patch | git apply --verbose
  # Return server time in case of clock skew with KDC
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1133.patch | git apply --verbose
  # Improved searchFilter for GetUserSPNs
  curl --location https://github.com/SecureAuthCorp/impacket/pull/1135.patch | git apply --verbose
  python3 -m pip install .
  cp -v /root/sources/grc/conf.ntlmrelayx /usr/share/grc/conf.ntlmrelayx
  cp -v /root/sources/grc/conf.secretsdump /usr/share/grc/conf.secretsdump
  cp -v /root/sources/grc/conf.getgpppassword /usr/share/grc/conf.getgpppassword
  cp -v /root/sources/grc/conf.rbcd /usr/share/grc/conf.rbcd
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
  colorecho "Installing cypheroth"
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
  cd /usr/lib/x86_64-linux-gnu/
  ln -s -f libc.a liblibc.a
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

function install_routersploit() {
  colorecho "Installing RouterSploit"
  git -C /opt/tools/ clone https://www.github.com/threat9/routersploit
  cd /opt/tools/routersploit
  python3 -m pip install -r requirements.txt
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
  python -m pip install pycryptodomex
  wget -O /opt/tools/dementor/dementor.py https://gist.githubusercontent.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc/raw/7c7f09ea46eff4ede636f69c00c6dfef0541cd14/dementor.py
}

function assetfinder() {
  colorecho "Installing assetfinder"
  go get -u -v github.com/tomnomnom/assetfinder
}

function install_subfinder() {
  colorecho "Installing subfinder"
  go get -u -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder
}

function install_gobuster() {
  colorecho "Installing gobuster"
  go get -u -v github.com/OJ/gobuster
}

function install_kiterunner() {
  colorecho "Installing kiterunner (kr)"
  git -C /opt/tools/ clone https://github.com/assetnote/kiterunner.git
  cd /opt/tools/kiterunner
  wget https://wordlists-cdn.assetnote.io/data/kiterunner/routes-large.kite.tar.gz
  wget https://wordlists-cdn.assetnote.io/data/kiterunner/routes-small.kite.tar.gz
  make build
  ln -s $(pwd)/dist/kr /opt/tools/bin/kr
}

function install_dirsearch() {
  colorecho "Installing dirsearch"
  git -C /opt/tools/ clone https://github.com/maurosoria/dirsearch
  cd /opt/tools/dirsearch/
  python3 -m pip install .
}

function install_cmsmap() {
  colorecho "Installing CMSmap"
  git -C /opt/tools/ clone https://github.com/Dionach/CMSmap.git
  cd /opt/tools/CMSmap/
  python3 -m pip install .
  cmsmap -U PC
}

function install_tomcatwardeployer() {
  colorecho "Installing tomcatWarDeployer"
  git -C /opt/tools/ clone https://github.com/mgeeky/tomcatWarDeployer.git
  cd /opt/tools/tomcatWarDeployer/
  python -m pip install -r requirements.txt
}

function install_clusterd() {
  colorecho "Installing clusterd"
  git -C /opt/tools/ clone https://github.com/hatRiot/clusterd.git
  cd /opt/tools/clusterd/
  python -m pip install -r requirements.txt
  echo -e '#!/bin/sh\n(cd /opt/tools/clusterd/ && python clusterd.py $@)' > /usr/local/bin/clusterd
  chmod +x /usr/local/bin/clusterd
}

function install_moodlescan() {
  colorecho "Installing moodlescan"
  git -C /opt/tools/ clone https://github.com/inc0d3/moodlescan.git
  cd /opt/tools/moodlescan/
  python3 -m pip install -r requirements.txt
  /opt/tools/moodlescan/moodlescan.py -a
}

function install_arjun() {
  colorecho "Installing arjun"
  python3 -m pip install arjun
}

function amass() {
  colorecho "Installing amass"
  go get -v -u github.com/OWASP/Amass/v3/...
}

function install_ffuf() {
  colorecho "Installing ffuf"
  go get -v -u github.com/ffuf/ffuf
}

function install_waybackurls() {
  colorecho "Installing waybackurls"
  go get -v -u github.com/tomnomnom/waybackurls
}

function install_gitrob(){
  colorecho "Installing gitrob"
  go get -v -u github.com/michenriksen/gitrob
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

function install_proxychains() {
  colorecho "Installing proxychains"
  git -C /opt/tools/ clone https://github.com/rofl0r/proxychains-ng
  cd /opt/tools/proxychains-ng/
  ./configure --prefix=/usr --sysconfdir=/etc
  make
  make install
  make install-config
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

function install_autorecon() {
  colorecho "Installing autorecon"
  git -C /opt/tools/ clone https://github.com/Tib3rius/AutoRecon
  cd /opt/tools/AutoRecon/
  python3 -m pip install -r requirements.txt
}

function install_simplyemail() {
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

function install_angr() {
  colorecho "Installing angr"
  python -m pip install angr
  python3 -m pip install angr
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
  python3 setup.py install
}

function uberfile() {
  colorecho "Installing uberfile"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/uberfile
  cd /opt/tools/uberfile/
  python3 setup.py install
}

function kadimus() {
  colorecho "Installing kadimus"
  apt-get -y install libcurl4-openssl-dev libpcre3-dev libssh-dev
  git -C /opt/tools/ clone https://github.com/P0cL4bs/Kadimus
  cd /opt/tools/Kadimus
  make
}

function install_testssl() {
  colorecho "Installing testssl"
  apt-get -y install bsdmainutils
  git -C /opt/tools/ clone --depth 1 https://github.com/drwetter/testssl.sh.git
}

function bat() {
  colorecho "Installing bat"
  version=$(curl -s https://api.github.com/repos/sharkdp/bat/releases/latest | grep "tag_name" | cut -d 'v' -f2 | cut -d '"' -f1)
  wget https://github.com/sharkdp/bat/releases/download/v$version/bat_$version\_amd64.deb
  fapt -f ./bat_$version\_amd64.deb
  rm bat_$version\_amd64.deb
}

function mdcat() {
  colorecho "Installing mdcat"
  version=$(curl -s https://api.github.com/repos/lunaryorn/mdcat/releases/latest | grep "tag_name" | cut -d '"' -f4)
  wget https://github.com/lunaryorn/mdcat/releases/download/$version/$version-x86_64-unknown-linux-musl.tar.gz
  tar xvfz $version-x86_64-unknown-linux-musl.tar.gz
  mv $version-x86_64-unknown-linux-musl/mdcat /opt/tools/bin
  rm -r $version-x86_64-unknown-linux-musl.tar.gz $version-x86_64-unknown-linux-musl
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
  python -m pip install dnstool==1.15.0
  git -C /opt/tools/ clone https://github.com/dirkjanm/krbrelayx
}

function hakrawler() {
  colorecho "Installing hakrawler"
  go get -u -v github.com/hakluke/hakrawler
}

function install_jwt_tool() {
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

function install_git-dumper() {
  colorecho "Installing git-dumper"
  git -C /opt/tools/ clone https://github.com/arthaud/git-dumper
  cd /opt/tools/git-dumper
  python3 -m pip install -r requirements.txt
}

function install_gittools() {
  colorecho "Installing GitTools"
  git -C /opt/tools/ clone https://github.com/internetwache/GitTools.git
}

function gopherus() {
  colorecho "Installing gopherus"
  git -C /opt/tools/ clone https://github.com/tarunkant/Gopherus
  cd /opt/tools/Gopherus
  ./install.sh
}

function install_ysoserial() {
  colorecho "Installing ysoserial"
  mkdir /opt/tools/ysoserial/
  wget -O /opt/tools/ysoserial/ysoserial.jar "https://jitpack.io/com/github/frohoff/ysoserial/master-SNAPSHOT/ysoserial-master-SNAPSHOT.jar"
}

function ysoserial_net() {
  colorecho "Downloading ysoserial"
  url=$(curl -s https://github.com/pwntester/ysoserial.net/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')
  tag=${url##*/}
  prefix=${tag:1}
  wget -O /tmp/ysoserial_net.zip "$url/ysoserial-$prefix.zip"
  unzip -d /opt/resources/windows/ /tmp/ysoserial_net.zip
  mv /opt/resources/windows/Release/ /opt/resources/windows/ysoserial.net
  rm /tmp/ysoserial_net.zip
}

function phpggc(){
  colorecho "Installing phpggc"
  git -C /opt/tools clone https://github.com/ambionics/phpggc.git
}

function symfony_exploits(){
  colorecho "Installing symfony-exploits"
  git -C /opt/tools clone https://github.com/ambionics/symfony-exploits
}

function install_john() {
  colorecho "Installing john the ripper"
  fapt qtbase5-dev
  git -C /opt/tools/ clone https://github.com/openwall/john
  cd /opt/tools/john/src && ./configure && make
}

function install_nth() {
  colorecho "Installing Name-That-Hash"
  python3 -m pip install name-that-hash
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

function install_proxmark3() {
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

function nishang() {
  colorecho "Downloading Nishang"
  git -C /opt/resources/windows/ clone https://github.com/samratashok/nishang.git
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
  git -C /opt/resources/windows/ clone https://github.com/Kevin-Robertson/Inveigh
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
  # Add LaZagne Forensic? https://github.com/AlessandroZ/LaZagneForensic
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
  cd /opt/tools/arsenal
  python3 -m pip install -r requirements.txt
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
  /root/go/bin/bettercap -eval "caplets.update; ui.update; q"
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
  git apply --verbose undefined-symbol-aesni-key.patch
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

function buster() {
  colorecho "Installing buster"
  git -C /opt/tools/ clone https://github.com/sham00n/buster.git
  cd /opt/tools/buster
  python3 setup.py install
}

function pwnedornot() {
  colorecho "Installing pwnedornot"
  git -C /opt/tools/ clone https://github.com/thewhiteh4t/pwnedOrNot
}
function ghunt() {
  colorecho "Installing ghunt"
  apt-get update
  apt-get install -y curl unzip gnupg
  curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
  echo "deb [arch=amd64]  http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
  apt-get update
  apt-get install -y google-chrome-stable
  rm -rf /var/lib/apt/lists/*
  git -C /opt/tools/ clone https://github.com/mxrch/GHunt
  cd /opt/tools/GHunt
  python3 -m pip install -r requirements.txt
  python3 download_chromedriver.py
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
  wget -P /tmp/ "https://ghidra-sre.org/ghidra_9.2.3_PUBLIC_20210325.zip"
  unzip /tmp/ghidra_9.2.3_PUBLIC_20210325.zip -d /opt/tools
  rm /tmp/ghidra_9.2.3_PUBLIC_20210325.zip
}

function burp() {
  colorecho "Installing Burp"
  burp_version=$(curl -s "https://portswigger.net/burp/releases#community" | grep -P -o "\d{4}-\d-\d" | head -1 | tr - .)
  wget "https://portswigger.net/burp/releases/download?product=community&version=$burp_version&type=Linux" -O /tmp/burp.sh
  chmod +x "/tmp/burp.sh"
  /tmp/burp.sh -q
  # FIXME: find a way to install in /opt/tools?
  # FIXME: set up the dark theme right away?
  # FIXME: add burp certificate to embedded firefox and chrome?
}

function bitleaker() {
  colorecho "Downloading bitleaker for BitLocker TPM attacks"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/bitleaker
}

function napper() {
  colorecho "Download napper for TPM vuln scanning"
  git -C "/opt/resources/encrypted disks/" clone https://github.com/kkamagui/napper-for-tpm
}

function linkedin2username() {
  colorecho "Installing linkedin2username"
  git -C /opt/tools/ clone https://github.com/initstring/linkedin2username
  cd /opt/tools/linkedin2username
  python3 -m python -m pip install -r requirements.txt
}

function toutatis() {
  colorecho "Installing toutatis"
  git -C /opt/tools/ clone https://github.com/megadose/toutatis
  cd /opt/tools/toutatis
  python3 setup.py install
}

function carbon14() {
  colorecho "Installing Carbon14"
  git -C /opt/tools/ clone https://github.com/Lazza/Carbon14
  cd /opt/tools/Carbon14
  python3 -m pip install -r requirements.txt
}

function youtubedl() {
  colorecho "Installing youtube-dl"
  python3 -m pip install youtube-dl
}

function ipinfo() {
  colorecho "Installing ipinfo"
  sudo npm install ipinfo-cli --global
}

function constellation() {
  colorecho "Installing constellation"
  cd /opt/tools/
  wget https://github.com/constellation-app/constellation/releases/download/v2.1.1/constellation-linux-v2.1.1.tar.gz
  tar xvf constellation-linux-v2.1.1.tar.gz
  rm constellation-linux-v2.1.1.tar.gz
}


function holehe() {
  colorecho "Installing holehe"
  python3 -m pip install holehe
}

function twint() {
  colorecho "Installing twint"
  python3 -m pip install twint
}

function tiktokscraper() {
  colorecho "Installing tiktok-scraper"
  npm i -g tiktok-scraper
}

function h8mail() {
  colorecho "Installing h8mail"
  python3 -m pip install h8mail
}


function phoneinfoga() {
  colorecho "Installing phoneinfoga"
  curl -sSL https://raw.githubusercontent.com/sundowndev/PhoneInfoga/master/support/scripts/install | bash
  sudo mv ./phoneinfoga /opt/tools/bin
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

function install_trilium_packaged() {
  colorecho "Installing Trilium (packaged)"
  url=$(curl -s https://github.com/zadam/trilium/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')
  tag=${url##*/v}
  wget -O /opt/tools/trilium.tar.xz $url/trilium-linux-x64-server-$tag.tar.xz
  tar -xvf /opt/tools/trilium.tar.xz -C /opt/tools/
  mv /opt/tools/trilium-linux-x64-server /opt/tools/trilium
  rm /opt/tools/trilium.tar.xz
  mkdir -p /root/.local/share/trilium-data
  cp -v /root/sources/trilium/* /root/.local/share/trilium-data
}

function install_trilium_sources() {
  colorecho "Installing Trilium (packaged)"
  git -C /opt/tools/ clone https://github.com/zadam/trilium
  cd /opt/tools/trilium
  npm install
  mkdir -p /root/.local/share/trilium-data
  cp -v /root/sources/trilium/* /root/.local/share/trilium-data
}

function install_trilium_sources() {
  colorecho "Installing Trilium (building from sources)"
  apt-get -y install libpng16-16 libpng-dev pkg-config autoconf libtool build-essential nasm libx11-dev libxkbfile-dev
  git -C /opt/tools/ clone -b stable https://github.com/zadam/trilium.git
  cd /opt/tools/trilium
  npm install
  mkdir -p /root/.local/share/trilium-data
  cp -v /root/sources/trilium/* /root/.local/share/trilium-data
}

function ntlmv1-multi() {
  colorecho "Installing ntlmv1 multi tool"
  git -C /opt/tools clone https://github.com/evilmog/ntlmv1-multi
}

function install_droopescan() {
  colorecho "Installing droopescan"
  git -C /opt/tools clone https://github.com/droope/droopescan.git
  cd /opt/tools/droopescan
  python3 -m pip install -r requirements.txt
  python3 setup.py install
}

function install_drupwn() {
  colorecho "Installing drupwn"
  git -C /opt/tools clone https://github.com/immunIT/drupwn.git
  cd /opt/tools/drupwn
  python3 setup.py install
}

function kubectl(){
  colorecho "Installing kubectl"
  mkdir -p /opt/tools/kubectl
  cd /opt/tools/kubectl
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
}

function awscli(){
  colorecho "Installing aws cli"
  cd /tmp
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip awscliv2.zip
  ./aws/install -i /opt/tools/aws-cli -b /usr/local/bin
  rm -rf aws
  rm awscliv2.zip
}

function install_scout() {
  colorecho "Installing ScoutSuite"
  python3 -m pip install scoutsuite
}

function jdwp_shellifier(){
  colorecho "Installing jdwp_shellifier"
  git -C /opt/tools/ clone https://github.com/IOActive/jdwp-shellifier.git
}

function maigret_pip() {
  colorecho "Installing maigret"
  pip3 install maigret
}

function amber() {
  colorecho "Installing amber"
  # TODO: this fails and needs a fix
  go get -u -v github.com/EgeBalci/amber
}

function hashonymize() {
  colorecho "Installing hashonymizer"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/hashonymize
  cd /opt/tools/hashonymize
  python3 setup.py install
}

function install_theHarvester() {
  colorecho "Installing theHarvester"
  python3 -m pip install censys
  apt-get -y install theharvester
}

function install_pcsc() {
  colorecho "Installing tools for PC/SC (smartcard)"
  apt-get install -y pcsc-tools pcscd libpcsclite-dev libpcsclite1
}

function install_libnfc() {
  colorecho "Installing libnfc"
  apt-get install -y libnfc-dev libnfc-bin
  cd /opt/tools/
  wget http://dl.bintray.com/nfc-tools/sources/libnfc-1.7.1.tar.bz2
  tar xjf libnfc-1.7.1.tar.bz2
  cd libnfc-1.7.1
  ./configure --with-drivers=all
  make
  make install
  ldconfig
  cd ../
  rm libnfc-1.7.1.tar.bz2
}

function install_mfoc() {
  colorecho "Installing mfoc"
  git -C /opt/tools/ clone https://github.com/nfc-tools/mfoc
  cd /opt/tools/mfoc
  autoreconf -vis
  ./configure
  make
  make install
}

function install_mfcuk() {
  colorecho "Installing mfcuk"
  apt-get install -y mfcuk
}

function install_libnfc-crypto1-crack() {
  colorecho "Installing libnfc_crypto1_crack"
  git -C /opt/tools/ clone https://github.com/aczid/crypto1_bs
  cd /opt/tools/crypto1_bs
  wget https://github.com/droidnewbie2/acr122uNFC/raw/master/crapto1-v3.3.tar.xz
  wget https://github.com/droidnewbie2/acr122uNFC/raw/master/craptev1-v1.1.tar.xz
  xz -d craptev1-v1.1.tar.xz crapto1-v3.3.tar.xz
  tar xvf craptev1-v1.1.tar
  tar xvf crapto1-v3.3.tar --one-top-level
  make CFLAGS=-"-std=gnu99 -O3 -march=native -Wl,--allow-multiple-definition"
  cp libnfc_crypto1_crack /opt/tools/bin
}

function install_mfdread() {
  colorecho "Installing mfdread"
  pip3 install bitstring
  git -C /opt/tools/ clone https://github.com/zhovner/mfdread
}

function install_mousejack() {
  colorecho "Installing mousejack"
  apt-get -y install sdcc binutils python git
  python-pip
  git -C /opt/tools/ clone https://github.com/BastilleResearch/mousejack
  cd /opt/tools/mousejack
  git submodule init
  git submodule update
  cd nrf-research-firmware
  make
}

function install_jackit() {
  colorecho "Installing jackit"
  git -C /opt/tools/ clone https://github.com/insecurityofthings/jackit
  cd /opt/tools/jackit
  pip install -e .
}

function install_gosecretsdump() {
  colorecho "Installing gosecretsdump"
  git -C /opt/tools/ clone https://github.com/c-sto/gosecretsdump
  go get -u -v github.com/C-Sto/gosecretsdump
}

function install_hackrf() {
  colorecho "Installing HackRF tools"
  apt-get -y install hackrf
}

function install_gqrx() {
  colorecho "Installing gqrx"
  apt-get -y install gqrx-sdr
}

function install_sipvicious() {
  colorecho "Installing SIPVicious"
  git -C /opt/tools/ clone https://github.com/enablesecurity/sipvicious.git
  cd /opt/tools/sipvicious/
  python3 setup.py install
}

function install_httpmethods() {
  colorecho "Installing httpmethods"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/httpmethods
  cd /opt/tools/httpmethods
  python3 setup.py install
}

function install_adidnsdump() {
  colorecho "Installing adidnsdump"
  git -C /opt/tools/ clone https://github.com/dirkjanm/adidnsdump
  cd /opt/tools/adidnsdump/
  python3 -m pip install .
}

function install_powermad() {
  colorecho "Downloading Powermad for resources"
  git -C /opt/resources/windows/ clone https://github.com/Kevin-Robertson/Powermad
}

function install_snaffler() {
  colorecho "Downloading Snaffler for resources"
  url=$(curl -s https://github.com/SnaffCon/Snaffler/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')
  mkdir -p /opt/resources/windows/Snaffler
  wget -O /opt/resources/windows/Snaffler.zip $url/Snaffler.zip
  unzip -d /opt/resources/windows/Snaffler /opt/resources/windows/Snaffler.zip
  rm -v /opt/resources/windows/Snaffler.zip
}

function install_dnschef() {
    colorecho "Installing DNSChef"
    git -C /opt/tools/ clone https://github.com/iphelix/dnschef
}

function install_h2csmuggler() {
  colorecho "Installing h2csmuggler"
  git -C /opt/tools/ clone https://github.com/BishopFox/h2csmuggler
  python3 -m pip install h2
}

function install_byp4xx() {
  colorecho "Installing byp4xx"
  git -C /opt/tools/ clone https://github.com/lobuhi/byp4xx
}

function install_pipx() {
  colorecho "Installing pipx"
  python3 -m pip install pipx
  pipx ensurepath
}

function install_peepdf() {
  colorecho "Installing peepdf"
  fapt libjpeg-dev
  python3 -m pip install peepdf
}

function install_volatility() {
  colorecho "Installing volatility"
  apt-get -y install pcregrep libpcre++-dev python-dev yara
  git -C /opt/tools/ clone https://github.com/volatilityfoundation/volatility
  cd /opt/tools/volatility
  python -m pip install pycrypto distorm3 pillow openpyxl ujson
  python setup.py install
  # https://github.com/volatilityfoundation/volatility/issues/535#issuecomment-407571161
  ln -s /usr/local/lib/python2.7/dist-packages/usr/lib/libyara.so /usr/lib/libyara.so
}

function install_zsteg() {
  colorecho "Installing zsteg"
  gem install zsteg
}

function install_stegolsb() {
  colorecho "Installing stegolsb"
  python3 -m pip install stego-lsb
}

function install_whatportis() {
  colorecho "Installing whatportis"
  python3 -m pip install whatportis
  echo y | whatportis --update
}

function install_ultimate_vimrc() {
    colorecho "Installing The Ultimate vimrc"
    git clone --depth=1 https://github.com/amix/vimrc.git ~/.vim_runtime
    sh ~/.vim_runtime/install_awesome_vimrc.sh
}

function install_ngrok() {
  colorecho "Installing ngrok"
  wget -O /tmp/ngrok.zip https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
  unzip -d /opt/tools/bin/ /tmp/ngrok.zip
}

function install_chisel() {
  colorecho "Installing chisel"
  go get -v github.com/jpillora/chisel
  #FIXME: add windows pre-compiled binaries in /opt/ressources/windows?
}

function install_sshuttle() {
  colorecho "Installing sshtuttle"
  git -C /opt/tools/ clone https://github.com/sshuttle/sshuttle.git
  cd /opt/tools/sshuttle
  python3 setup.py install
}

function install_pygpoabuse() {
  colorecho "Installing pyGPOabuse"
  git -C /opt/tools/ clone https://github.com/Hackndo/pyGPOAbuse
}

function install_rsactftool() {
  colorecho "Installing RsaCtfTool"
  git -C /opt/tools/ clone https://github.com/Ganapati/RsaCtfTool
  cd /opt/tools/RsaCtfTool
  apt-get -y install libgmp3-dev libmpc-dev
  python3 -m pip install -r requirements.txt
}

function install_feroxbuster() {
  colorecho "Installing feroxbuster"
  # cd /tmp
  # curl -sLO https://github.com/epi052/feroxbuster/releases/latest/download/feroxbuster_amd64.deb.zip
  # unzip feroxbuster_amd64.deb.zip
  # rm feroxbuster_amd64.deb.zip
  # apt-get -y install -f ./feroxbuster_*_.deb
  # rm feroxbuster*.deb
  apt-get -y install feroxbuster
}

function install_bloodhound-import() {
  colorecho "Installing bloodhound-import"
  python3 -m pip install bloodhound-import
}

function install_bloodhound-quickwin() {
  colorecho "Installing bloodhound-quickwin"
  python3 -m pip install py2neo pandas prettytable
  git -C /opt/tools/ clone https://github.com/kaluche/bloodhound-quickwin
}

function install_ldapsearch-ad() {
  colorecho "Installing ldapsearch-ad"
  python3 -m pip install -r requirements.txt
  git -C /opt/tools/ clone https://github.com/yaap7/ldapsearch-ad
}

function install_ntlm-scanner() {
  colorecho "Installing ntlm-scanner"
  git -C /opt/tools/ clone https://github.com/preempt/ntlm-scanner
}

function install_rustscan() {
  colorecho "Installing RustScan"
  mkdir /opt/tools/rustscan/
  wget -qO- https://api.github.com/repos/RustScan/RustScan/releases/latest | grep "browser_download_url.*amd64.deb" | cut -d: -f2,3 | tr -d \" | wget -qO /opt/tools/rustscan/rustscan.deb -i-
  dpkg -i /opt/tools/rustscan/rustscan.deb
  wget https://gist.github.com/snovvcrash/c7f8223cc27154555496a9cbb4650681/raw/a76a2c658370d8b823a8a38a860e4d88051b417e/rustscan-ports-top1000.toml -O /root/.rustscan.toml
}

function install_divideandscan() {
  colorecho "Installing DivideAndScan"
  git -C /opt/tools/ clone https://github.com/snovvcrash/DivideAndScan
  cd /opt/tools/DivideAndScan
  python3 -m pip install .
}

function install_trid() {
  colorecho "Installing trid"
  mkdir /opt/tools/trid/
  cd /opt/tools/trid
  wget https://mark0.net/download/tridupdate.zip
  wget https://mark0.net/download/triddefs.zip
  wget https://mark0.net/download/trid_linux_64.zip
  unzip trid_linux_64.zip
  unzip triddefs.zip
  unzip tridupdate.zip
  rm tridupdate.zip triddefs.zip trid_linux_64.zip
  chmod +x trid
  python3 tridupdate.py
}

function install_pcredz() {
  colorecho "Installing PCredz"
  fapt python3-pip libpcap-dev
  python3 -m pip install Cython python-libpcap
  git -C /opt/tools/ clone https://github.com/lgandx/PCredz
}

function install_smartbrute() {
  colorecho "Installing smartbrute"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/smartbrute
  cd /opt/tools/smartbrute
  python3 -m pip install -r requirements.txt
  python3 -m pip install --force rich
}

function install_frida() {
  colorecho "Installing frida"
  python3 -m pip install frida-tools
}

function install_androguard() {
  colorecho "Installing androguard"
  python3 -m pip install androguard
}

function install_petitpotam() {
  colorecho "Installing PetitPotam"
  git -C /opt/tools/ clone https://github.com/topotam/PetitPotam
}

function install_PKINITtools() {
  colorecho "Installing PKINITtools"
  git -C /opt/tools/ clone https://github.com/dirkjanm/PKINITtools
}

function install_pywhisker() {
  colorecho "Installing pyWhisker"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/pywhisker
  cd /opt/tools/pywhisker
  python3 -m pip install -r requirements.txt
}

function install_targetedKerberoast() {
  colorecho "Installing targetedKerberoast"
  git -C /opt/tools/ clone https://github.com/ShutdownRepo/targetedKerberoast
  cd /opt/tools/targetedKerberoast
  python3 -m pip install -r requirements.txt
}

function install_manspider() {
  colorecho "Installing MANSPIDER"
  git -C /opt/tools/ clone https://github.com/blacklanternsecurity/MANSPIDER
  fapt antiword
  python3 -m pip install man-spider
}

function install_pywsus() {
  colorecho "Installing pywsus"
  git -C /opt/tools/ clone https://github.com/GoSecure/pywsus
  cd /opt/tools/pywsus
  python3 -m pip install -r requirements.txt
}

function install_base() {
  update || exit
  fapt man                        # Most important
  fapt git                        # Git client
  fapt lsb-release
  fapt pciutils
  fapt zip
  fapt unzip
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
  fapt jq                         # jq is a lightweight and flexible command-line JSON processor
  python-pip                      # Pip
  fapt python3-pip                # Pip
  filesystem
  locales
  tmux                            # Tmux
  fapt zsh                        # Awesome shell
  ohmyzsh                         # Awesome shell
  dependencies
  grc
  fapt golang                     # Golang language
  fapt gem                        # Install ruby packages
  fapt automake                   # Automake
  fapt autoconf                   # Autoconf
  fapt make
  fapt gcc
  fapt g++
  fapt file                       # Detect type of file with magic number
  fapt lsof                       # Linux utility
  fapt less                       # Linux utility
  fapt x11-apps                   # Linux utility
  fapt net-tools                  # Linux utility
  fapt vim                        # Text editor
  install_ultimate_vimrc          # Make vim usable OOFB
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
  fapt sshpass                    # SSHpass (wrapper for using SSH with password on the CLI)
  fapt telnet                     # Telnet client
  fapt nfs-common                 # NFS client
  fapt snmp                       # TODO: comment this
  fzf                             # File fuzzer
  fapt ncat                       # Socket manager
  fapt netcat-traditional         # Socket manager
  fapt socat                      # Socket manager
  #gf_install                      # wrapper around grep
  fapt rdate                      # tool for querying the current time from a network server
  fapt putty                      # GUI-based SSH, Telnet and Rlogin client
  fapt screen                     # CLI-based PuTT-like
  fapt npm                        # Node Package Manager
  fapt p7zip-full                 # 7zip
  fapt p7zip-rar                  # 7zip rar module
  fapt rar                        # rar
  fapt unrar                      # unrar
  fapt xz-utils                   # xz (de)compression
  fapt xsltproc                   # apply XSLT stylesheets to XML documents (Nmap reports)
  fapt openvpn                    # OpenVPN client
  install_pipx
}

# Package dedicated to most used offensive tools
function install_most_used_tools() {
  fapt exploitdb                  # Exploitdb downloaded locally
  fapt metasploit-framework       # Offensive framework
  fapt nmap                       # Port scanner
  fapt seclists                   # Awesome wordlists
  install_subfinder               # Subdomain bruteforcer
  install_autorecon               # External recon tool
  install_gitrob                  # Senstive files reconnaissance in github
  install_waybackurls             # Website history
  install_theHarvester            # Gather emails, subdomains, hosts, employee names, open ports and banners
  install_simplyemail             # Gather emails
  install_gobuster                # Web fuzzer (pretty good for several extensions)
  install_ffuf                    # Web fuzzer (little favorites)
  fapt wfuzz                      # Web fuzzer (second favorites)
  fapt nikto                      # Web scanner
  fapt sqlmap                     # SQL injection scanner
  fapt hydra                      # Login scanner
  fapt joomscan                   # Joomla scanner
  fapt wpscan                     # Wordpress scanner
  install_droopescan              # Drupal scanner
  install_drupwn                  # Drupal scanner
  install_testssl                 # SSL/TLS scanner
  fapt sslscan                    # SSL/TLS scanner
  fapt weevely                    # Awesome secure and light PHP webshell
  CloudFail                       # Cloudflare misconfiguration detector
  EyeWitness                      # Website screenshoter
  wafw00f                         # Waf detector
  install_jwt_tool                # Toolkit for validating, forging, scanning and tampering JWTs
  install_gittools                # Dump a git repository from a website
  install_ysoserial               # Deserialization payloads
  Responder                       # LLMNR, NBT-NS and MDNS poisoner
  install_crackmapexec            # Network scanner
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
#  install_trilium_packaged       # notes taking tool
  install_trilium_sources         # notes taking tool
  fapt exiftool                   # Meta information reader/writer
  fapt imagemagick                # Copy, modify, and distribute image
  install_ngrok                   # expose a local development server to the Internet
  install_whatportis              # Search default port number
  fapt ascii                      # The ascii table in the shell
}

# Package dedicated to the installation of wordlists and tools like wl generators
function install_wordlists_tools() {
  fapt crunch                     # Wordlist generator
  fapt seclists                   # Awesome wordlists
  fapt wordlists                  # Others wordlists (not the best)
  fapt cewl                       # Wordlist generator
  fapt cupp                       # User password profiler
  install_pass_station            # Default credentials database
}

# Package dedicated to offline cracking/bruteforcing tools
function install_cracking_tools() {
  fapt hashcat                    # Password cracker
  install_john                    # Password cracker
  fapt fcrackzip                  # Zip cracker
  fapt pdfcrack                   # PDF cracker
  fapt bruteforce-luks            # Find the password of a LUKS encrypted volume
  install_nth                     # Name-That-Hash, the hash identifier tool
}

# Package dedicated to osint, recon and passive tools
function install_osint_tools() {
  #Picture And Videos
  youtubedl                       # Command-line program to download videos from YouTube.com and other video sites
  apt-get update
  fapt exiftool                   # For read exif information
  fapt exifprobe                  # Probe and report structure and metadata content of camera image files
  #Subdomain
  Sublist3r                       # Fast subdomains enumeration tool
  assetfinder                     # Find domains and subdomains potentially related to a given domain
  install_subfinder               # Subfinder is a subdomain discovery tool that discovers valid subdomains for websites
  fapt amass                      # OWASP Amass tool suite is used to build a network map of the target
  findomain                       # Findomain Monitoring Service use OWASP Amass, Sublist3r, Assetfinder and Subfinder
  #DNS
  fapt dnsenum                    # DNSEnum is a command-line tool that automatically identifies basic DNS records
  fapt dnsrecon                   # DNS Enumeration Script
  #Email
  holehe                          # Check if the mail is used on different sites
  install_simplyemail             # Gather emails
  install_theHarvester            # Gather emails, subdomains, hosts, employee names, open ports and banners
  h8mail                          # Email OSINT & Password breach hunting tool
  infoga                          # Gathering email accounts informations
  buster                          # An advanced tool for email reconnaissance
  pwnedornot                      # OSINT Tool for Finding Passwords of Compromised Email Addresses
  ghunt                           # Investigate Google Accounts with emails
  #Phone
  phoneinfoga                     # Advanced information gathering & OSINT framework for phone numbers
  #Social Network
  maigret_pip                     # Search pseudos and information about users on many platforms
  linkedin2username               # Generate username lists for companies on LinkedIn
  toutatis                        # Toutatis is a tool that allows you to extract information from instagrams accounts
  tiktokscraper                   # TikTok Scraper. Download video posts, collect user/trend/hashtag/music feed metadata, sign URL and etc
  #Website
  install_waybackurls             # Website history
  carbon14                        # OSINT tool for estimating when a web page was written
  WikiLeaker                      # A WikiLeaks scraper
  photon                          # Incredibly fast crawler designed for OSINT.
  CloudFail                       # Utilize misconfigured DNS and old database records to find hidden IP's behind the CloudFlare network
  #Ip
  ipinfo                          # Get information about an IP address using command line with ipinfo.io
  #Data visualization
  constellation                   # A graph-focused data visualisation and interactive analysis application.
  #Framework
  apt-get update
  fapt maltego                    # Maltego is a software used for open-source intelligence and forensics
  fapt spiderfoot                 # SpiderFoot automates OSINT collection
  fapt finalrecon                 # A fast and simple python script for web reconnaissance
  fapt recon-ng                   # External recon tool
  # TODO : http://apt.vulns.sexy make apt update print a warning, and the repo has a weird name, we need to fix this in order to not alarm users
  # sn0int                          # Semi-automatic OSINT framework and package manager
  OSRFramework                    # OSRFramework, the Open Sources Research Framework
  #Dark
  apt-get update
  fapt tor                        # Tor proxy
  fapt torbrowser-launcher        # Tor browser
  onionsearch                     # OnionSearch is a script that scrapes urls on different .onion search engines.
  #Github
  githubemail                     # Retrieve a GitHub user's email even if it's not public
  #Other
  apt-get update
  fapt whois                      # See information about a specific domain name or IP address
  ReconDog                        # Informations gathering tool
  JSParser                        # Parse JS files
  gron                            # JSON parser
}

# Package dedicated to applicative and active web pentest tools
function install_web_tools() {
  install_gobuster                # Web fuzzer (pretty good for several extensions)
  install_kiterunner              # Web fuzzer (fast and pretty good for api bruteforce)
  amass                           # Web fuzzer
  install_ffuf                    # Web fuzzer (little favorites)
  fapt dirb                       # Web fuzzer
  fapt dirbuster                  # Web fuzzer
  fapt wfuzz                      # Web fuzzer (second favorites)
  install_dirsearch               # Web fuzzer
  fapt nikto                      # Web scanner
  fapt sqlmap                     # SQL injection scanner
  SSRFmap                         # SSRF scanner
  gopherus                        # SSRF helper
  NoSQLMap                        # NoSQL scanner
  XSStrike                        # XSS scanner
  install_XSpear                  # XSS scanner
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
  install_droopescan              # Drupal scanner
  install_drupwn                  # Drupal scanner
  install_cmsmap                  # CMS scanner (Joomla, Wordpress, Drupal)
  install_moodlescan              # Moodle scanner
  install_testssl                 # SSL/TLS scanner
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
  install_jwt_tool                # Toolkit for validating, forging, scanning and tampering JWTs
  jwt_cracker                     # JWT cracker and bruteforcer
  wuzz                            # Burp cli
  install_git-dumper              # Dump a git repository from a website
  install_gittools                # Dump a git repository from a website
  fapt padbuster
  install_ysoserial               # Deserialization payloads
  fapt whatweb                    # Recognises web technologies including content management
  phpggc                          # php deserialization payloads
  symfony_exploits                #  symfony secret fragments exploit
  jdwp_shellifier                 # exploit java debug
  install_httpmethods             # Tool for HTTP methods enum & verb tampering
  install_h2csmuggler             # Tool for HTTP2 smuggling
  install_byp4xx                  # Tool to automate 40x errors bypass attempts
  install_feroxbuster             # ffuf but with multithreaded recursion
  install_tomcatwardeployer       # Apache Tomcat auto WAR deployment & pwning tool
  install_clusterd                # Axis2/JBoss/ColdFusion/Glassfish/Weblogic/Railo scanner
  install_arjun                   # HTTP Parameter Discovery
}

# Package dedicated to command & control frameworks
function install_c2_tools() {
  Empire                          # Exploit framework
  fapt metasploit-framework       # Offensive framework
  install_routersploit            # Exploitation Framework for Embedded Devices
  # TODO: add Silentrinity
  # TODO: add starkiller
  # TODO: add beef-xss
}

# Package dedicated to specific services tools apart from HTTP/HTTPS (e.g. SSH, and so on)
install_services_tools() {
  fapt ssh-audit                  # SSH server audit
  fapt hydra                      # Login scanner
  memcached-cli                   # TODO: comment this
  fapt mariadb-client             # Mariadb client
  fapt redis-tools                # Redis protocol
  install_odat                    # Oracle Database Attacking Tool
}

# Package dedicated to internal Active Directory tools
function install_ad_tools() {
  Responder                       # LLMNR, NBT-NS and MDNS poisoner
  install_crackmapexec            # Network scanner
  sprayhound                      # Password spraying tool
  install_smartbrute              # Password spraying tool
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
  install_lsassy                  # Credentials extracter
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
  hashonymize                     # Anonymize NTDS, ASREProast, Kerberoast hashes for remote cracking
  install_gosecretsdump           # secretsdump in Go for heavy files
  install_adidnsdump              # enumerate DNS records in Domain or Forest DNS zones
  install_powermad                # MachineAccountQuota and DNS exploit tools
  install_snaffler                # Shares enumeration and looting
  install_pygpoabuse              # TODO : comment this
  install_bloodhound-import       # Python script to import BH data to a neo4j db
  install_bloodhound-quickwin     # Python script to find quickwins from BH data in a neo4j db
  install_ldapsearch-ad           # Python script to find quickwins from basic ldap enum
  install_ntlm-scanner            # Python script to check public vulns on DCs
  install_petitpotam              # Python script to coerce auth through MS-EFSR abuse
  install_PKINITtools             # Python scripts to use kerberos PKINIT to obtain TGT
  install_pywhisker               # Python script to manipulate msDS-KeyCredentialLink
  install_manspider               # Snaffler-like in Python
  install_targetedKerberoast
  install_pcredz
  install_pywsus

}

# Package dedicated to mobile apps pentest tools
function install_mobile_tools() {
  fapt android-tools-adb
  fapt smali
  fapt dex2jar
  fapt zipalign
  fapt apksigner
  fapt apktool
  install_frida
  install_androguard              # Reverse engineering and analysis of Android applications
}

# Package dedicated to VOIP/SIP pentest tools
function install_voip_tools() {
  install_sipvicious              # Set of tools for auditing SIP based VOIP systems
  #TODO: SIPp?
}

# Package dedicated to RFID/NCF pentest tools
function install_rfid_tools() {
  fapt git
  fapt libusb-dev
  fapt autoconf
  fapt nfct
  install_pcsc
  install_libnfc                  # NFC library
  install_mfoc                    # Tool for nested attack on Mifare Classic
  install_mfcuk                   # Tool for Darkside attack on Mifare Classic
  install_libnfc-crypto1-crack    # tool for hardnested attack on Mifare Classic
  install_mfdread                 # Tool to pretty print Mifare 1k/4k dumps
  install_proxmark3               # Proxmark3 scripts
}

# Package dedicated to IoT tools
function install_iot_tools() {
  fapt avrdude
  fapt minicom
}

# Package dedicated to SDR
function install_sdr_tools() {
  install_mousejack               # tools for mousejacking
  install_jackit                  # tools for mousejacking
  install_hackrf                  # tools for hackrf
  install_gqrx                    # spectrum analyzer for SDR
  fapt rtl-433                    # decode radio transmissions from devices on the ISM bands
  # TODO : ubertooth, ...
}

# Package dedicated to network pentest tools
function install_network_tools() {
  install_proxychains                     # Network tool
  DEBIAN_FRONTEND=noninteractive fapt wireshark # Wireshark packet sniffer
  DEBIAN_FRONTEND=noninteractive fapt tshark    # Tshark packet sniffer
  # wireshark_sources             # Install Wireshark from sources
  fapt hping3                     # Discovery tool
  fapt masscan                    # Port scanner
  fapt nmap                       # Port scanner
  install_autorecon               # External recon tool
  # Sn1per                        # Vulnerability scanner
  fapt iproute2                   # Firewall rules
  fapt tcpdump                    # Capture TCP traffic
  install_dnschef                 # Python DNS server
  install_rustscan                # Fast port scanner
  install_divideandscan           # Python project to automate port scanning routine
  fapt iptables                   # iptables for the win
  fapt traceroute                 # ping ping
  install_chisel                  # Fast TCP/UDP tunnel over HTTP
  install_sshuttle                # Transparent proxy over SSH
  fapt dns2tcp                    # TCP tunnel over DNS
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
  fapt binwalk                    # Tool to find embedded files
  fapt foremost                   # Alternative to binwalk
  install_volatility              # Memory analysis tool
  install_trid                    # filetype detection tool
  install_peepdf                  # PDF analysis
}

# Package dedicated to steganography tools
function install_steganography_tools() {
  install_zsteg                   # Detect stegano-hidden data in PNG & BMP
  fapt stegosuite
  fapt steghide
  install_stegolsb                # (including wavsteg)
}

# Package dedicated to cloud tools
function install_cloud_tools() {
  kubectl
  awscli
  install_scout                   # Multi-Cloud Security Auditing Tool
}

# Package dedicated to reverse engineering tools
function install_reverse_tools() {
  pwntools                        # CTF framework and exploit development library
  pwndbg                          # Advanced Gnu Debugger
  angr                            # Binary analysis
  checksec_py                     # Check security on binaries
  fapt nasm                       # Netwide Assembler
  fapt radare2                    # Awesome debugger
  fapt wabt                       # The WebAssembly Binary Toolkit
  fapt ltrace
  fapt strace
}

# Package dedicated to attack crypto
function install_crypto_tools() {
  install_rsactftool              # attack rsa
}

# Package dedicated to GUI-based apps
function install_GUI_tools() {
  bloodhound
  bloodhound_old_v3
  bloodhound_old_v2
  fapt freerdp2-x11
  fapt rdesktop
  ghidra
  fapt xtightvncviewer
  fapt jd-gui                     # Java decompiler
  burp
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
  nishang
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
  rm -rfv /tmp/*
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
      echo "A successful build will output the following last line:"
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
