#!/bin/bash
# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

function colorecho() {
  BG='\033[1;32m'
  NC='\033[0m'
  echo -e "${BG}$@${NC}"
  sleep 2
}

function update() {
  colorecho "[+] Updating, upgrading, cleaning"
  apt -y update && apt -y install apt-utils && apt -y upgrade && apt -y autoremove && apt clean
}

function apt_packages() {
  colorecho "[+] Installing APT packages"
  apt install -y --no-install-recommends aircrack-ng crunch curl dirb dirbuster dnsenum dnsrecon dnsutils dos2unix enum4linux exploitdb ftp git gobuster hashcat hping3 hydra john joomscan masscan metasploit-framework mimikatz nasm ncat netcat-traditional nikto nmap patator php powersploit proxychains python-impacket python-pip python2 python3 recon-ng samba samdump2 seclists smbclient smbmap snmp socat sqlmap sslscan testssl.sh theharvester tree vim nano weevely wfuzz wget whois wordlists seclists wpscan zsh ssh iproute2 iputils-ping python3-pip python-dev python3-dev sudo tcpdump gem tidy impacket-scripts passing-the-hash powershell
  #apt install -y sslstrip
}

function ohmyzsh() {
  colorecho "[+] Installing oh-my-zsh, theme and plugins"
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  sed -i 's/robbyrussell/gentoo/g' ~/.zshrc
  sed -i 's/plugins=(git)/plugins=(git sudo docker docker-compose)/g' ~/.zshrc
  echo 'TIME_="%{$fg[white]%}[%{$fg[red]%}%D %T%{$fg[white]%}]%{$reset_color%}"' >> ~/.zshrc
  echo 'PROMPT="$TIME_%{$FX[bold]$FG[013]%} Exegol %{$fg_bold[blue]%}%(!.%1~.%c) $(prompt_char)%{$reset_color%} "' >> ~/.zshrc
}

function banners() {
  colorecho "[+] Installing lolcat and figlet (it is essential here)"
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

function aliases() {
  colorecho "[+] Adding aliases"
  echo "alias l='ls -al'" >> ~/.zshrc
  echo "alias ipa='ip --brief --color a'" >> ~/.zshrc
  echo "alias cme='crackmapexec'" >> ~/.zshrc
  echo "alias nse='ls /usr/share/nmap/scripts | grep '" >> ~/.zshrc
  echo "alias scan-range='nmap -T5 -n -sn'" >> ~/.zshrc
  echo "alias http-server='python3 -m http.server'" >> ~/.zshrc
  echo "alias php-server='php -S 127.0.0.1:8080 -t .'" >> ~/.zshrc
  echo "alias ftp-server='python -m pyftpdlib -u \"mario\" -P \"m4r10\" -p 2121'" >> ~/.zshrc
  echo "alias powershell='pwsh'" >> ~/.zshrc
}

function dependencies() {
  colorecho "[+] Installing most required dependencies"
  apt -y install python-setuptools python3-setuptools
  pip3 install wheel
  pip install wheel
}

function Responder() {
  colorecho "[+] Installing Responder"
  git -C /opt clone https://github.com/lgandx/Responder
  sed -i 's/ Random/ 1122334455667788/g' /opt/Responder/Responder.conf
  echo "alias responder='/opt/Responder/Responder.py'" >> ~/.zshrc
}

function Sublist3r() {
  colorecho "[+] Installing Sublist3r"
  git -C /opt clone https://github.com/aboul3la/Sublist3r.git
  pip3 install -r /opt/Sublist3r/requirements.txt
  echo "alias sublist3r='/opt/Sublist3r/Sublist3r.py'" >> ~/.zshrc
}

function ReconDog() {
  colorecho "[+] Installing ReconDog"
  git -C /opt clone https://github.com/s0md3v/ReconDog
  pip3 install -r /opt/ReconDog/requirements.txt
  echo "alias dog='python3 /opt/ReconDog/dog'" >> ~/.zshrc
}

function CloudFail() {
  colorecho "[+] Installing CloudFail"
  git -C /opt clone https://github.com/m0rtem/CloudFail
  pip3 install -r /opt/CloudFail/requirements.txt
  echo "alias cloudfail='python3 /opt/CloudFail/cloudfail.py'" >> ~/.zshrc
}

function OneForAll() {
  colorecho "[+] Installing OneForAll"
  git -C /opt clone https://github.com/shmilylty/OneForAll.git
  pip3 install -r /opt/OneForAll/requirements.txt
  echo "alias oneforall='python3 /opt/OneForAll/oneforall/oneforall.py'" >> ~/.zshrc
}

function EyeWitness() {
  colorecho "[+] Installing EyeWitness"
  git -C /opt clone https://github.com/FortyNorthSecurity/EyeWitness
  cd /opt/EyeWitness/setup
  ./setup.sh
  echo "alias eyewitness='python3 /opt/EyeWitness/EyeWitness.py'" >> ~/.zshrc
}

function wafw00f() {
  colorecho "[+] Installing wafw00f"
  git -C /opt clone https://github.com/EnableSecurity/wafw00f
  cd /opt/wafw00f
  python setup.py install
}

function JSParser() {
  colorecho "[+] Installing JSParser"
  git -C /opt clone https://github.com/nahamsec/JSParser
  cd /opt/JSParser
  python setup.py install
}

function LinkFinder() {
  colorecho "[+] Installing LinkFinder"
  git -C /opt clone https://github.com/GerbenJavado/LinkFinder.git
  cd /opt/LinkFinder
  pip3 install -r requirements.txt
  python3 setup.py install
}

function SSRFmap() {
  colorecho "[+] Installing SSRFmap"
  git -C /opt clone https://github.com/swisskyrepo/SSRFmap
  cd /opt/SSRFmap
  pip3 install -r requirements.txt
}

function fuxploider() {
  colorecho "[+] Installing fuxploider"
  git -C /opt clone https://github.com/almandin/fuxploider.git
  cd /opt/fuxploider
  pip3 install -r requirements.txt
}

function CORScanner() {
  colorecho "[+] Installing CORScanner"
  git -C /opt clone https://github.com/chenjj/CORScanner.git
  cd /opt/CORScanner
  pip install -r requirements.txt
}

function Blazy() {
  colorecho "[+] Installing Blazy"
  git -C /opt clone https://github.com/UltimateHackers/Blazy
  cd /opt/Blazy
  pip install -r requirements.txt
}

function XSStrike() {
  colorecho "[+] Installing XSStrike"
  git -C /opt clone https://github.com/s0md3v/XSStrike.git
  echo "alias XSStrike='python /opt/XSStrike/xsstrike.py'" >> ~/.zshrc
}

function Bolt() {
  colorecho "[+] Installing Bolt"
  git -C /opt clone https://github.com/s0md3v/Bolt.git
  echo "alias bolt='python3 /opt/Bolt/bolt.py'" >> ~/.zshrc
}

function CrackMapExec() {
  colorecho "[+] Downloading CrackMapExec"
  apt -y install libssl-dev libffi-dev python-dev build-essential python3-winrm
  git -C /opt clone --recursive https://github.com/mpgn/CrackMapExec
  cd /opt/CrackMapExec
  git submodule update --recursive
  python3 setup.py install
}

function lsassy() {
  colorecho "[+] Installing lsassy with pip, and cme module by reinstalling cme with lsassy in cmd/modules/"
  python3.7 -m pip install --user lsassy
  wget -O /opt/CrackMapExec/cme/modules/lsassy3.py https://raw.githubusercontent.com/Hackndo/lsassy/master/cme/lsassy3.py
  cd /opt/CrackMapExec
  python3 setup.py install
}

function sprayhound() {
  colorecho "[+] Installing sprayhound"
  git -C /opt clone https://github.com/Hackndo/sprayhound
  cd /opt/sprayhound
  apt -y install libsasl2-dev libldap2-dev
  pip3 install "pyasn1<0.5.0,>=0.4.6"
  python3 setup.py install
}

function Impacket() {
  colorecho "[+] Installing Impacket"
  git -C /opt clone https://github.com/SecureAuthCorp/impacket
  cd /opt/impacket/
  pip install --force-reinstall .
}

function BloodHound() {
  colorecho "[+] Installing neo4j and Python ingestor for BloodHound"
  git -C /opt clone https://github.com/fox-it/BloodHound.py
  cd /opt/BloodHound.py/
  python setup.py install
  apt -y install neo4j
}

function mitm6_sources() {
  colorecho "[+] Installing mitm6 from sources"
  git -C /opt clone https://github.com/fox-it/mitm6
  cd /opt/mitm6/
  pip3 install --user -r requirements.txt
  python3 setup.py install
  echo "alias mitm6='python3 /opt/mitm6/mitm6/mitm6.py'" >> ~/.zshrc
}

function mitm6() {
  colorecho "[+] Installing mitm6 with pip"
  pip3 install mitm6
}

function aclpwn() {
  colorecho "[+] Installing aclpwn with pip"
  pip3 install aclpwn
}

function IceBreaker() {
  colorecho "[+] Installing IceBreaker"
  apt -y install lsb-release python3-libtmux python3-libnmap python3-ipython
  pip install pipenva
  git -C /opt clone https://github.com/DanMcInerney/icebreaker
  cd /opt/icebreaker/
  ./setup.sh
  pipenv --three install
}

function Empire() {
  colorecho "[+] Installing Empire"
  export STAGING_KEY='123Soleil'
  pip install pefile
  git -C /opt clone https://github.com/BC-SECURITY/Empire
  cd /opt/Empire/setup
  ./install.sh
}

function DeathStar() {
  colorecho "[+] Installing DeathStar"
  git -C /opt clone https://github.com/byt3bl33d3r/DeathStar
  cd /opt/DeathStar
  pip3 install -r requirements.txt
}

function Sn1per() {
  colorecho "[+] Installing Sn1per"
  git -C /opt clone https://github.com/1N3/Sn1per
  sed -i 's/read answer/echo no answer to give/' /opt/Sn1per/install.sh
  sed -i 's/cp/cp -v/g' /opt/Sn1per/install.sh
  sed -i 's/mkdir/mkdir -v/g' /opt/Sn1per/install.sh
  sed -i 's/rm/rm -v/g' /opt/Sn1per/install.sh
  sed -i 's/mv/mv -v/g' /opt/Sn1per/install.sh
  sed -i 's/wget/wget -v/g' /opt/Sn1per/install.sh
  sed -i 's/2> \/dev\/null//g' /opt/Sn1per/install.sh
  cd /opt/Sn1per/
  bash install.sh
}

function dementor(){
  colorecho "[+] Installing dementor"
  wget -O /opt/dementor.py https://gist.githubusercontent.com/3xocyte/cfaf8a34f76569a8251bde65fe69dccc/raw/7c7f09ea46eff4ede636f69c00c6dfef0541cd14/dementor.py
}

function ntlmscanner(){
  colorecho "[+] Installing ntlm-scanner"
  git -C /opt clone https://github.com/preempt/ntlm-scanner
}

function go_tools() {
  colorecho "[+] Installing go tools (subjack, assetfinder, subfinder, gobuster, amass, ffuf, gitrob, shhgit...)"
  apt -y install golang
  echo 'export GOPATH=/root/go/bin' >> ~/.zshrc
  echo 'export GO111MODULE=on' >> ~/.zshrc
  echo 'export PATH=$GOPATH:$PATH' >> ~/.zshrc
  go get -u -v github.com/haccer/subjack
  go get -u -v github.com/tomnomnom/assetfinder
  go get -u -v github.com/projectdiscovery/subfinder/cmd/subfinder
  go get -u -v github.com/OJ/gobuster
  go get -v -u github.com/OWASP/Amass/v3/...
  go get -v -u github.com/ffuf/ffuf
  go get -v -u github.com/michenriksen/gitrob
  go get -v -u github.com/eth0izzle/shhgit
  go get -v -u github.com/tomnomnom/waybackurls
  go get -v -u github.com/Ice3man543/SubOver
  go get -u -v github.com/lukasikic/subzy
  go install -v github.com/lukasikic/subzy
}

function ruby_tools() {
  colorecho "[+] Installing ruby tools"
  gem install timing_attack
}

function python_tools() {
  colorecho "[+] Installing Python tools from pip"
  pip3 install updog
}

function binaries() {
  colorecho "[+] Installing binaries"
  mkdir -p /opt/bin
  echo 'export PATH=/opt/bin:$PATH' >> ~/.zshrc
  wget -O /opt/bin/findomain https://github.com/Edu4rdSHL/findomain/releases/latest/download/findomain-linux
  chmod +x /opt/bin/findomain
}

function end_message() {
  colorecho "[+] Installation is done..."
  colorecho "You can use the following aliases on your host to build, run, open a shell, stop the container"
  colorecho "\talias exegol-build='docker build --tag exegol /PATH/TO/Exegol/'"
  colorecho "\talias exegol-run='docker run --interactive --tty --detach --network host --volume /PATH/TO/Exegol/shared-volume:/share --name exegol exegol'"
  colorecho "\talias exegol-shell='docker exec -it exegol zsh'"
  colorecho "\talias exegol-stop='docker stop exegol && docker rm exegol'"
}

function main(){
  update
  apt_packages
  ohmyzsh
  banners
  aliases
  dependencies
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
  fuxploider
  CORScanner
  Blazy
  XSStrike
  Bolt
  CrackMapExec
  lsassy
  sprayhound
  Impacket
  BloodHound
  mitm6
  aclpwn
  IceBreaker
  Empire
  DeathStar
  Sn1per
  dementor
  ntlmscanner
  go_tools
  ruby_tools
  python_tools
  binaries
  end_message
}

if [[ $EUID -ne 0 ]]; then
  echo "You must be a root user" 2>&1
  exit 1
else
  echo "[!] Careful : this script is supposed to be run inside a docker/VM, do not run this on your host. You are warned :)"
  echo "[*] Sleeping 10 seconds, just in case... You can still stop this"
  sleep 10
  main "$@"
fi
