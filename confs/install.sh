#!/bin/bash
# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

function update() {
  echo "[EXEGOL] Updating, upgrading, cleaning"
  apt -y update && apt -y install apt-utils && apt -y upgrade && apt -y autoremove && apt clean
}

function apt_packages() {
  echo "[EXEGOL] Installing APT packages"
  apt install -y --no-install-recommends aircrack-ng crunch curl dirb dirbuster dnsenum dnsrecon dnsutils dos2unix enum4linux exploitdb ftp git hashcat hping3 hydra joomscan masscan metasploit-framework mimikatz nasm ncat netcat-traditional nikto nmap patator php powersploit proxychains python3 recon-ng samba samdump2 seclists smbclient smbmap snmp socat sqlmap sslscan theharvester tree vim nano weevely wfuzz wget whois wordlists seclists wpscan zsh golang ssh iproute2 iputils-ping python3-pip python3-dev sudo tcpdump gem tidy passing-the-hash proxychains ssh-audit whatweb smtp-user-enum onesixtyone cewl radare2 nbtscan amap python-dev python2 file dotdotpwn xsser rlwrap lsof bruteforce-luks less redis-tools telnet pst-utils mariadb-client fcrackzip
}

function python-pip() {
  echo "[EXEGOL] Installing python-pip"
  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  rm get-pip.py
}

function filesystem() {
  echo "[EXEGOL] Preparing filesystem"
  mkdir -p /opt/tools/ /opt/tools/bin/ /share/
}

function ohmyzsh() {
  echo "[EXEGOL] Installing oh-my-zsh, config, history, aliases"
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  sed -i 's/robbyrussell/gentoo/g' ~/.zshrc
  sed -i 's/plugins=(git)/plugins=(git sudo docker docker-compose)/g' ~/.zshrc
  echo '' >> ~/.zshrc
  echo 'TIME_="%{$fg[white]%}[%{$fg[red]%}%D %T%{$fg[white]%}]%{$reset_color%}"' >> ~/.zshrc
  echo 'PROMPT="$TIME_%{$FX[bold]$FG[013]%} Exegol %{$fg_bold[blue]%}%(!.%1~.%c) $(prompt_char)%{$reset_color%} "' >> ~/.zshrc
  echo '' >> ~/.zshrc
  echo 'export GOPATH=$HOME/go' >> ~/.zshrc
  echo 'export GO111MODULE=on' >> ~/.zshrc
  echo 'export JOHN=/opt/tools/john/run' >> ~/.zshrc
  echo 'export PATH=/opt/tools/bin:$JOHN:$GOPATH/bin:$PATH' >> ~/.zshrc
  wget -O ~/.zsh_history https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/zsh/history
  echo '' >> ~/.zshrc
  echo 'source /opt/.zsh_aliases' >> ~/.zshrc
  wget -O /opt/.zsh_aliases https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/zsh/aliases
}

function banners() {
  echo "[EXEGOL] Installing lolcat and figlet (it is essential here)"
  wget https://github.com/busyloop/lolcat/archive/master.zip
  unzip master.zip
  cd lolcat-master/bin
  gem install lolcat
  cd ../../ && rm -r lolcat-master master.zip
  apt -y install figlet
  wget -O /usr/share/figlet/Bloody.flf https://raw.githubusercontent.com/xero/figlet-fonts/master/Bloody.flf
  echo '#echo ""' >> ~/.zshrc
  echo '#figlet -f Bloody "Exegol" -w 10000 | lolcat' >> ~/.zshrc
  echo '#echo ""' >> ~/.zshrc
}

function dependencies() {
  echo "[EXEGOL] Installing most required dependencies"
  apt -y install python-setuptools python3-setuptools
  pip3 install wheel
  pip install wheel
}

function Responder() {
  echo "[EXEGOL] Installing Responder"
  git -C /opt/tools/ clone https://github.com/lgandx/Responder
  sed -i 's/ Random/ 1122334455667788/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/AccessDenied.html/\/opt\/tools\/Responder\/files\/AccessDenied.html/g' /opt/tools/Responder/Responder.conf
  sed -i 's/files\/BindShell.exe/\/opt\/tools\/Responder\/files\/BindShell.exe/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.crt/\/opt\/tools\/Responder\/certs\/responder.crt/g' /opt/tools/Responder/Responder.conf
  sed -i 's/certs\/responder.key/\/opt\/tools\/Responder\/certs\/responder.key/g' /opt/tools/Responder/Responder.conf
}

function Sublist3r() {
  echo "[EXEGOL] Installing Sublist3r"
  git -C /opt/tools/ clone https://github.com/aboul3la/Sublist3r.git
  pip3 install -r /opt/tools/Sublist3r/requirements.txt
}

function ReconDog() {
  echo "[EXEGOL] Installing ReconDog"
  git -C /opt/tools/ clone https://github.com/s0md3v/ReconDog
  pip3 install -r /opt/tools/ReconDog/requirements.txt
}

function CloudFail() {
  echo "[EXEGOL] Installing CloudFail"
  git -C /opt/tools/ clone https://github.com/m0rtem/CloudFail
  pip3 install -r /opt/tools/CloudFail/requirements.txt
}

function OneForAll() {
  echo "[EXEGOL] Installing OneForAll"
  git -C /opt/tools/ clone https://github.com/shmilylty/OneForAll.git
  pip3 install -r /opt/tools/OneForAll/requirements.txt
}

function EyeWitness() {
  echo "[EXEGOL] Installing EyeWitness"
  git -C /opt/tools/ clone https://github.com/FortyNorthSecurity/EyeWitness
  cd /opt/tools/EyeWitness/setup
  ./setup.sh
}

function wafw00f() {
  echo "[EXEGOL] Installing wafw00f"
  git -C /opt/tools/ clone https://github.com/EnableSecurity/wafw00f
  cd /opt/tools/wafw00f
  python setup.py install
}

function JSParser() {
  echo "[EXEGOL] Installing JSParser"
  git -C /opt/tools/ clone https://github.com/nahamsec/JSParser
  cd /opt/tools/JSParser
  python setup.py install
}

function LinkFinder() {
  echo "[EXEGOL] Installing LinkFinder"
  git -C /opt/tools/ clone https://github.com/GerbenJavado/LinkFinder.git
  cd /opt/tools/LinkFinder
  pip3 install -r requirements.txt
  python3 setup.py install
}

function SSRFmap() {
  echo "[EXEGOL] Installing SSRFmap"
  git -C /opt/tools/ clone https://github.com/swisskyrepo/SSRFmap
  cd /opt/tools/SSRFmap
  pip3 install -r requirements.txt
}

function NoSQLMap() {
  echo "[EXEGOL] Installing NoSQLMap"
  git -C /opt/tools clone https://github.com/codingo/NoSQLMap.git
  cd /opt/tools/NoSQLMap
  python setup.py install
}

function fuxploider() {
  echo "[EXEGOL] Installing fuxploider"
  git -C /opt/tools/ clone https://github.com/almandin/fuxploider.git
  cd /opt/tools/fuxploider
  pip3 install -r requirements.txt
}

function CORScanner() {
  echo "[EXEGOL] Installing CORScanner"
  git -C /opt/tools/ clone https://github.com/chenjj/CORScanner.git
  cd /opt/tools/CORScanner
  pip install -r requirements.txt
}

function Blazy() {
  echo "[EXEGOL] Installing Blazy"
  git -C /opt/tools/ clone https://github.com/UltimateHackers/Blazy
  cd /opt/tools/Blazy
  pip install -r requirements.txt
}

function XSStrike() {
  echo "[EXEGOL] Installing XSStrike"
  git -C /opt/tools/ clone https://github.com/s0md3v/XSStrike.git
  pip3 install fuzzywuzzy
}

function Bolt() {
  echo "[EXEGOL] Installing Bolt"
  git -C /opt/tools/ clone https://github.com/s0md3v/Bolt.git
}

function CrackMapExec() {
  echo "[EXEGOL] Downloading CrackMapExec"
  apt -y install libssl-dev libffi-dev python-dev build-essential python3-winrm
  git -C /opt/tools/ clone --recursive https://github.com/byt3bl33d3r/CrackMapExec
  cd /opt/tools/CrackMapExec
  git submodule update --recursive
  python3 setup.py install
}

function lsassy() {
  echo "[EXEGOL] Installing lsassy"
  git -C /opt/tools/ clone https://github.com/Hackndo/lsassy/
  cd /opt/tools/lsassy
  python3 setup.py install
  #wget -O /opt/tools/CrackMapExec/cme/modules/lsassy3.py https://raw.githubusercontent.com/Hackndo/lsassy/master/cme/lsassy3.py
  #cd /opt/tools/CrackMapExec
  #python3 setup.py install
  pip3 install 'asn1crypto>=1.3.0'
}

function sprayhound() {
  echo "[EXEGOL] Installing sprayhound"
  git -C /opt/tools/ clone https://github.com/Hackndo/sprayhound
  cd /opt/tools/sprayhound
  apt -y install libsasl2-dev libldap2-dev
  pip3 install "pyasn1<0.5.0,>=0.4.6"
  python3 setup.py install
}

function Impacket() {
  echo "[EXEGOL] Installing Impacket scripts"
  git -C /opt/tools/ clone https://github.com/SecureAuthCorp/impacket
  cd /opt/tools/impacket/
  wget -O 0001-User-defined-password-for-LDAP-attack-addComputer.patch https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/patches/0001-User-defined-password-for-LDAP-attack-addComputer.patch
  git apply 0001-User-defined-password-for-LDAP-attack-addComputer.patch
  pip3 install .
  wget -O /usr/share/grc/conf.ntlmrelayx https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/grc/conf.ntlmrelayx
  wget -O /usr/share/grc/conf.secretsdump https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/grc/conf.secretsdump
}

function BloodHound() {
  echo "[EXEGOL] Installing neo4j and Python ingestor for BloodHound"
  git -C /opt/tools/ clone https://github.com/fox-it/BloodHound.py
  cd /opt/tools/BloodHound.py/
  python setup.py install
  apt -y install neo4j
}

function mitm6_sources() {
  echo "[EXEGOL] Installing mitm6 from sources"
  git -C /opt/tools/ clone https://github.com/fox-it/mitm6
  cd /opt/tools/mitm6/
  pip3 install --user -r requirements.txt
  python3 setup.py install
}

function mitm6() {
  echo "[EXEGOL] Installing mitm6 with pip"
  pip3 install mitm6
}

function aclpwn() {
  echo "[EXEGOL] Installing aclpwn with pip"
  pip3 install aclpwn
  sed -i 's/neo4j.v1/neo4j/g' /usr/local/lib/python3.8/dist-packages/aclpwn/database.py
}

function IceBreaker() {
  echo "[EXEGOL] Installing IceBreaker"
  apt -y install lsb-release python3-libtmux python3-libnmap python3-ipython
  pip install pipenva
  git -C /opt/tools/ clone https://github.com/DanMcInerney/icebreaker
  cd /opt/tools/icebreaker/
  ./setup.sh
  pipenv --three install
}

function Empire() {
  echo "[EXEGOL] Installing Empire"
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
  echo "[EXEGOL] Installing DeathStar"
  git -C /opt/tools/ clone https://github.com/byt3bl33d3r/DeathStar
  cd /opt/tools/DeathStar
  pip3 install -r requirements.txt
}

function Sn1per() {
  echo "[EXEGOL] Installing Sn1per"
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

function dementor(){
  echo "[EXEGOL] Installing dementor"
  mkdir /opt/tools/dementor
  pip install pycrypto
  wget -O /opt/tools/dementor/dementor.py https://gist.githubusercontent.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc/raw/7c7f09ea46eff4ede636f69c00c6dfef0541cd14/dementor.py
}

function subjack(){
  echo "[EXEGOL] Installing subjack"
  go get -u -v github.com/haccer/subjack
}

function assetfinder(){
  echo "[EXEGOL] Installing assetfinder"
  go get -u -v github.com/tomnomnom/assetfinder
}

function subfinder(){
  echo "[EXEGOL] Installing subfinder"
  go get -u -v github.com/projectdiscovery/subfinder/cmd/subfinder
}

function gobuster(){
  echo "[EXEGOL] Installing gobuster"
  go get -u -v github.com/OJ/gobuster
}

function amass(){
  echo "[EXEGOL] Installing amass"
  go get -v -u github.com/OWASP/Amass/v3/...
}

function ffuf(){
  echo "[EXEGOL] Installing ffuf"
  go get -v -u github.com/ffuf/ffuf
}

function gitrob(){
  echo "[EXEGOL] Installing gitrob"
  go get -v -u github.com/michenriksen/gitrob
}

function shhgit(){
  echo "[EXEGOL] Installing shhgit"
  go get -v -u github.com/eth0izzle/shhgit
}

function waybackurls(){
  echo "[EXEGOL] Installing waybackurls"
  go get -v -u github.com/tomnomnom/waybackurls
}

function subover(){
  echo "[EXEGOL] Installing SubOver"
  go get -v -u github.com/Ice3man543/SubOver
}

function subzy(){
  echo "[EXEGOL] Installing subzy"
  go get -u -v github.com/lukasikic/subzy
  go install -v github.com/lukasikic/subzy
}

function gron(){
  echo "[EXEGOL] Installing gron"
  go get -u -v github.com/tomnomnom/gron
}

function timing_attack() {
  echo "[EXEGOL] Installing timing_attack"
  gem install timing_attack
}

function updog() {
  echo "[EXEGOL] Installing updog"
  pip3 install updog
}

function findomain() {
  echo "[EXEGOL] Installing findomain"
  wget -O /opt/tools/bin/findomain https://github.com/Edu4rdSHL/findomain/releases/latest/download/findomain-linux
  chmod +x /opt/tools/bin/findomain
}

function proxychains(){
  echo "[EXEGOL] Editing /etc/proxychains.conf for ntlmrelayx.py"
  sed -i 's/9050/1080/g' /etc/proxychains.conf
}

function grc(){
  echo "[EXEGOL] Installing and configuring grc"
  apt -y install grc
  wget -O /etc/grc.conf https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/grc/grc.conf
}

function pykek(){
  echo "[EXEGOL] Installing Python Kernel Exploit Kit (pykek) for MS14-068"
  git -C /opt/tools/ clone https://github.com/preempt/pykek
}

function autorecon(){
  echo "[EXEGOL] Installing autorecon"
  git -C /opt/tools/ clone https://github.com/Tib3rius/AutoRecon
  cd /opt/tools/AutoRecon/
  pip3 install -r requirements.txt
}

function privexchange(){
  echo "[EXEGOL] Installing privexchange"
  git -C /opt/tools/ clone https://github.com/dirkjanm/PrivExchange
}

function LNKUp(){
  echo "[EXEGOL] Installing LNKUp"
  git -C /opt/tools/ clone https://github.com/Plazmaz/LNKUp
  cd /opt/tools/LNKUp
  pip install -r requirements.txt
}

function pwntools(){
  echo "[EXEGOL] Installing pwntools"
  pip install pwntools
  pip3 install pwntools
}

function pwndbg(){
  echo "[EXEGOL] Installing pwndbg"
  apt -y install python3.8 python3.8-dev
  git -C /opt/tools/ clone https://github.com/pwndbg/pwndbg
  cd /opt/tools/pwndbg
  ./setup.sh
  echo 'set disassembly-flavor intel' >> ~/.gdbinit
}

function darkarmour(){
  echo "[EXEGOL] Installing darkarmour"
  git -C /opt/tools/ clone https://github.com/bats3c/darkarmour
  cd /opt/tools/darkarmour
  apt -y install mingw-w64-tools mingw-w64-common g++-mingw-w64 gcc-mingw-w64 upx-ucl osslsigncode
}

function powershell() {
  echo "[EXEGOL] Installing powershell"
  apt -y install powershell
  mv /opt/microsoft /opt/tools/microsoft
  rm /usr/bin/pwsh
  ln -s /opt/tools/microsoft/powershell/7/pwsh /usr/bin/pwsh
}

function fzf() {
  echo "[EXEGOL] Installing fzf"
  git -C /opt/tools/ clone --depth 1 https://github.com/junegunn/fzf.git
  cd /opt/tools/fzf
  ./install --all
}

function shellerator() {
  echo "[EXEGOL] Installing shellerator"
  git -C /opt/tools clone https://github.com/ShutdownRepo/shellerator
  cd /opt/tools/shellerator
  pip3 install -r requirements.txt
}

function kadimus() {
  echo "[EXEGOL] Installing kadimus"
  apt -y install libcurl4-openssl-dev libpcre3-dev libssh-dev
  git -C /opt/tools/ clone https://github.com/P0cL4bs/Kadimus
  cd /opt/tools/Kadimus
  make
}

function testssl() {
  echo "[EXEGOL] Installing testssl"
  apt -y install testssl.sh bsdmainutils
}

function fimap() {
  echo "[EXEGOL] Installing fimap"
  git -C /opt/tools/ clone https://tha-imax.de/git/root/fimap
  cd /opt/tools/fimap
  pip install httplib2
}

function bat() {
  echo "[EXEGOL] Installing bat"
  wget https://github.com/sharkdp/bat/releases/download/v0.13.0/bat_0.13.0_amd64.deb
  apt install -f ./bat_0.13.0_amd64.deb
  rm bat_0.13.0_amd64.deb
}

function mdcat() {
  echo "[EXEGOL] Installing mdcat"
  wget https://github.com/lunaryorn/mdcat/releases/download/mdcat-0.16.0/mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  tar xvfz mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz
  mv mdcat-0.16.0-x86_64-unknown-linux-musl/mdcat /opt/tools/bin
  rm -r mdcat-0.16.0-x86_64-unknown-linux-musl.tar.gz mdcat-0.16.0-x86_64-unknown-linux-musl
}

function xsrfprobe() {
  echo "[EXEGOL] Installing XSRFProbe"
  git -C /opt/tools/ clone https://github.com/0xInfection/XSRFProbe
  cd /opt/tools/XSRFProbe
  python3 setup.py install
}

function krbrelayx() {
  echo "[EXEGOL] Installing krbrelayx"
  git -C /opt/tools/ clone https://github.com/dirkjanm/krbrelayx
}

function hakrawler() {
  echo "[EXEGOL] Installing hakrawler"
  go get -u -v github.com/hakluke/hakrawler
}

function jwt_tool() {
  echo "[EXEGOL] Installing JWT tool"
  git -C /opt/tools/ clone https://github.com/ticarpi/jwt_tool
  pip3 install pycryptodomex
}

function jwt_cracker() {
  echo "[EXEGOL] Installing JWT cracker"
  apt -y install npm
  npm install --global jwt-cracker
}

function wuzz() {
  echo "[EXEGOL] Installing wuzz"
  go get -u -v github.com/asciimoo/wuzz
}

function gf_install() {
  echo "[EXEGOL] Installing gf"
  mkdir ~/.gf
  go get -u -v github.com/tomnomnom/gf
  echo 'source $GOPATH/src/github.com/tomnomnom/gf/gf-completion.zsh' >> ~/.zshrc
  cp -rv ~/go/src/github.com/tomnomnom/gf/examples/* ~/.gf
  gf -save redirect -HanrE 'url=|rt=|cgi-bin/redirect.cgi|continue=|dest=|destination=|go=|out=|redir=|redirect_uri=|redirect_url=|return=|return_path=|returnTo=|rurl=|target=|view=|from_url=|load_url=|file_url=|page_url=|file_name=|page=|folder=|folder_url=|login_url=|img_url=|return_url=|return_to=|next=|redirect=|redirect_to=|logout=|checkout=|checkout_url=|goto=|next_page=|file=|load_file='
}

function rockyou() {
  echo "[EXEGOL] Extracting /usr/share/wordlists/rockyou.txt.gz"
  gunzip -d /usr/share/wordlists/rockyou.txt.gz
}

function rbcd-attack() {
  echo "[EXEGOL] Installing rbcd-attack"
  git -C /opt/tools/ clone https://github.com/tothi/rbcd-attack
}

function evilwinrm() {
  echo "[EXEGOL] Installing evil-winrm"
  gem install evil-winrm
}

function pypykatz() {
  echo "[EXEGOL] Installing pypykatz"
  pip3 install pypykatz
}

function enyx() {
  echo "[EXEGOL] Installing enyx"
  git -C /opt/tools/ clone https://github.com/trickster0/Enyx
}

function enum4linux-ng() {
  echo "[EXEGOL] Installing enum4linux-ng"
  git -C /opt/tools/ clone https://github.com/cddmp/enum4linux-ng
}

function git-dumper() {
  echo "[EXEGOL] Installing git-dumper"
  git -C /opt/tools/ clone https://github.com/arthaud/git-dumper
  cd /opt/tools/git-dumper
  pip3 install -r requirements.txt
}

function gopherus() {
  echo "[EXEGOL] Installing gopherus"
  git -C /opt/tools/ clone https://github.com/tarunkant/Gopherus
  cd /opt/tools/Gopherus
  ./install.sh
}

function ysoserial() {
  echo "[EXEGOL] Installing ysoserial"
  wget -O /opt/tools/ysoserial.jar "https://jitpack.io/com/github/frohoff/ysoserial/master-SNAPSHOT/ysoserial-master-SNAPSHOT.jar"
}

function john() {
  echo "[EXEGOL] Installing john the ripper"
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

function rockyou() {
  echo "[EXEGOL] Decompressing rockyou.txt"
  gunzip -d /usr/share/wordlists/rockyou.txt.gz
}

function memcached-cli() {
  echo "[EXEGOL] Installing memcached-cli"
  npm install -g memcached-cli
}

function zerologon() {
  echo "[EXEGOL] Pulling CVE-2020-1472 exploit and scan scripts"
  git -C /opt/tools/ clone https://github.com/SecuraBV/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-scan
  git -C /opt/tools/ clone https://github.com/dirkjanm/CVE-2020-1472
  mv /opt/tools/CVE-2020-1472 /opt/tools/zerologon-exploit
}

function resources() {
  echo "[EXEGOL] Fetching useful resources (sysinternals, LinEnum, Rubeus, JuicyPotato...)"
  mkdir -p  /opt/resources/ /opt/resources/windows/ /opt/resources/linux/ /opt/resources/mac/ /opt/resources/webshells/ /opt/resources/webshells/PHP/ /opt/resources/webshells/ASPX/
  # SysInternals
  wget -O /opt/resources/windows/sysinternals.zip "https://download.sysinternals.com/files/SysinternalsSuite.zip"
  unzip -d /opt/resources/windows/sysinternals /opt/resources/windows/sysinternals.zip
  rm /opt/resources/windows/sysinternals.zip
  # WinEnum.bat
  git -C /opt/resources/windows/ clone https://github.com/mattiareggiani/WinEnum
  # pspy
  mkdir -p /opt/resources/linux/pspy
  wget -O /opt/resources/linux/pspy/pspy32 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32"
  wget -O /opt/resources/linux/pspy/pspy64 "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64"
  wget -O /opt/resources/linux/pspy/pspy32s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy32s"
  wget -O /opt/resources/linux/pspy/pspy64s "$(curl -s https://github.com/DominicBreuker/pspy/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/pspy64s"
  # linPEAS, winPEAS
  git -C /opt/resources/ clone https://github.com/carlospolop/privilege-escalation-awesome-scripts-suite
  cp /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x64/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x64.exe
  cp /opt/resources/windows/winPEAS/winPEASexe/winPEAS/bin/x86/Release/winPEAS.exe /opt/resources/windows/winPEAS/winPEAS_x86.exe
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/linPEAS /opt/resources/linux
  mv /opt/resources/privilege-escalation-awesome-scripts-suite/winPEAS /opt/resources/windows
  rm -r /opt/resources/privilege-escalation-awesome-scripts-suite
  # linux smart enumeration (lse.sh)
  wget -O /opt/resources/linux/lse.sh "https://github.com/diego-treitos/linux-smart-enumeration/raw/master/lse.sh"
  # LinEnum.sh
  wget -O /opt/resources/linux/LinEnum.sh "https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh"
  # linux exploit suggester (les.sh)
  wget -O /opt/resources/linux/les.sh "https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh"
  # mimikatz
  wget -O /opt/resources/windows/mimikatz.zip "$(curl -s https://github.com/gentilkiwi/mimikatz/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/mimikatz_trunk.zip"
  unzip -d /opt/resources/windows/mimikatz /opt/resources/windows/mimikatz.zip
  # PowerSploit
  git -C /opt/resources/windows/ https://github.com/PowerShellMafia/PowerSploit
  # PrivescCheck (Windows)
  git -C /opt/resources/windows/ https://github.com/itm4n/PrivescCheck
  # Rubeus
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_3.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/Rubeus_4.5.exe"
  # Inveigh and Inveigh-Relay
  git -C /opt/resources/windows https://github.com/Kevin-Robertson/Inveigh
  # SharpHound
  mkdir /opt/resources/windows/SharpHound
  wget -P /opt/resources/windows/SharpHound/ "https://github.com/BloodHoundAD/BloodHound/raw/master/Ingestors/SharpHound.exe"
  wget -P /opt/resources/windows/SharpHound/ "https://github.com/BloodHoundAD/BloodHound/raw/master/Ingestors/SharpHound.ps1"
  # JuicyPotato
  wget -P /opt/resources/windows/ "$(curl -s https://github.com/ohpe/juicy-potato/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/JuicyPotato.exe"
  # Impacket examples Windows
  git -C /opt/resources/windows/ clone https://github.com/maaaaz/impacket-examples-windows
  # Webshells
  git -C /opt/resources/webshells/PHP/ clone https://github.com/mIcHyAmRaNe/wso-webshell
  sed -i 's/fa769dac7a0a94ee47d8ebe021eaba9e/5f4dcc3b5aa765d61d8327deb882cf99/g' /opt/resources/webshells/PHP/wso-webshell/wso.php
  echo 'password' > /opt/resources/webshells/PHP/wso-webshell/password.txt
  git -C /opt/resources/webshells/PHP/ clone https://github.com/flozz/p0wny-shell
  wget -O /opt/resources/webshells/ASPX/webshell.aspx "https://raw.githubusercontent.com/xl7dev/WebShell/master/Aspx/ASPX%20Shell.aspx"
  # nc
  cp /usr/bin/nc.traditional /opt/resources/linux/nc
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/nc.exe"
  # SpoolSample
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample.exe"
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/SpoolSample_v4.5_x64..exe"
  # Diaghub
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/diaghub.exe"
  # LaZagne
  git -C /tmp/ clone https://github.com/AlessandroZ/LaZagne
  mv /tmp/LaZagne/Linux /opt/resources/linux/LaZagne
  mv /tmp/LaZagne/Mac /opt/resources/mac/LaZagne
  mv /tmp/LaZagne/Windows /opt/resources/widnows/LaZagne
  wget -P /opt/resources/windows/LaZagne/ "$(curl -s https://github.com/AlessandroZ/LaZagne/releases/latest | grep -o '"[^"]*"' | tr -d '"' | sed 's/tag/download/')/lazagne.exe"
  rm -r /tmp/LaZagne
  # sublinacl
  wget -P /opt/resources/windows/ "https://gitlab.com/onemask/pentest-tools/-/raw/master/windows/sublinacl.exe"
  # PowerSploit
  git -C /opt/resources/windows/ clone https://github.com/PowerShellMafia/PowerSploit
  # mimipenguin
  git -C /opt/resources/linux/ clone https://github.com/huntergregal/mimipenguin
  # mimipy
  git -C /opt/resources/linux/ clone https://github.com/n1nj4sec/mimipy
  # plink
  wget -O /opt/resources/windows/plink32.exe "https://the.earth.li/~sgtatham/putty/latest/w32/plink.exe"
  wget -O /opt/resources/windows/plink64.exe "https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe"
  # deepce
  wget -O /opt/resources/linux/deepce "https://github.com/stealthcopter/deepce/raw/master/deepce.sh"
}

function cleaning() {
  echo "[EXEGOL] Cleaning..."
  rm /tmp/gobuster.7z
  rm -r /tmp/gobuster-linux-amd64
}

function main(){
  update || exit
  apt_packages || exit
  python-pip
  filesystem
  ohmyzsh
  banners
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
  CrackMapExec
  sprayhound
  BloodHound
  #mitm6_sources
  mitm6
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
  fimap
  bat
  mdcat
  xsrfprobe
  krbrelayx
  hakrawler
  jwt_tool
  jwt_cracker
  wuzz
  gf_install
  #rockyou
  rbcd-attack
  evilwinrm
  pypykatz
  enyx
  enum4linux-ng
  git-dumper
  gopherus
  ysoserial
  john
  rockyou
  memcached-cli
  zerologon
  resources
  cleaning
}

if [[ $EUID -ne 0 ]]; then
  echo "You must be a root user" 2>&1
  exit 1
else
  if [[ -f '/.dockerenv' ]]; then
    BG='\033[1;32m'
    NC='\033[0m'
    echo -e "${BG}"
    echo "This script is running in docker, as it should :)"
    echo "If you see things in red, don't panic, it's usually not errors, just badly handled colors"
    echo "---"
    echo "A successful build whill output the following last two lines:"
    echo "Successfully built d30d7f163c89"
    echo "Successfully tagged nwodtuhs/exegol:latest"
    echo -e "${NC}"
    sleep 2
    main "$@"
  else
    echo "[!] Careful : this script is supposed to be run inside a docker/VM, do not run this on your host unless you know what you are doing and have done backups. You are warned :)"
    echo "[*] Sleeping 30 seconds, just in case... You can still stop this"
    sleep 30
    main "$@"
  fi
fi
