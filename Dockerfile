# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD sources /root/sources
RUN chmod +x /root/sources/install.sh

RUN /root/sources/install.sh install_base
RUN /root/sources/install.sh install_tools
RUN /root/sources/install.sh install_tools_gui
RUN /root/sources/install.sh install_resources
RUN /root/sources/install.sh install_clean

RUN rm -rf /root/sources

WORKDIR /dev
#CMD ["/bin/zsh"]
