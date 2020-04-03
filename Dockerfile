# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD https://raw.githubusercontent.com/ShutdownRepo/Exegol/master/install.sh /root/install.sh
RUN chmod +x /root/install.sh && /root/install.sh && rm /root/install.sh

WORKDIR /root
