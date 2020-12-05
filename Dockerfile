# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD sources /root/sources
RUN chmod +x /root/sources/install.sh

RUN /root/sources/install.sh install_base

RUN /root/sources/install.sh install_most_used_tools

# RUN /root/sources/install.sh install_misc_tools
# RUN /root/sources/install.sh install_osint_tools
# RUN /root/sources/install.sh install_web_tools
# RUN /root/sources/install.sh install_ad_tools
# RUN /root/sources/install.sh install_network_tools
# RUN /root/sources/install.sh install_mobile_tools
# RUN /root/sources/install.sh install_wifi_tools
# RUN /root/sources/install.sh install_forensic_tools
# RUN /root/sources/install.sh install_reverse_tools
# RUN /root/sources/install.sh install_all_tools_gui

RUN /root/sources/install.sh install_resources
RUN /root/sources/install.sh install_clean

RUN rm -rf /root/sources

WORKDIR /data
#CMD ["/bin/zsh"]
