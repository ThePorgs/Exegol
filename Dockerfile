# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

COPY install.sh /root/install.sh

RUN chmod +x /root/install.sh && /root/install.sh && rm /root/install.sh

WORKDIR /root
