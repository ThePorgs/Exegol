# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD https://raw.githubusercontent.com/ShutdownRepo/Exegol/dev/confs/install.sh /root/install.sh
#ADD confs/install.sh /root/install.sh
RUN chmod +x /root/install.sh

RUN /root/install.sh install_base
RUN /root/install.sh install_tools
RUN /root/install.sh install_resources
RUN /root/install.sh install_clean

RUN rm /root/install.sh

WORKDIR /share
CMD ["/bin/zsh"]
