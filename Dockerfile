# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD sources/install.sh /root/install.sh
RUN chmod +x /root/install.sh

RUN /root/install.sh install_base
RUN /root/install.sh install_tools
RUN /root/install.sh install_tools_gui
RUN /root/install.sh install_resources
RUN /root/install.sh install_clean

RUN rm /root/install.sh

WORKDIR /share
#CMD ["/bin/zsh"]
