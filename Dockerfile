# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/confs/install.sh /root/install.sh
RUN chmod +x /root/install.sh && /root/install.sh && rm /root/install.sh

WORKDIR /share
