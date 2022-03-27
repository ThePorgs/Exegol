# Author: Charlie BROMBERG (Shutdown - @_nwodtuhs)

FROM kalilinux/kali-rolling

ADD sources /root/sources
RUN chmod +x /root/sources/install.sh

RUN /root/sources/install.sh install_base

# WARNING: install_most_used_tools can't be used with other functions other than: install_base, install_resources, install_clean
# RUN /root/sources/install.sh install_most_used_tools

# WARNING: the following installs (except: install_base, install_resources, install_clean) can't be used with install_most_used_tools
# this is a temporary limitation
RUN /root/sources/install.sh install_misc_tools
RUN /root/sources/install.sh install_wordlists_tools
RUN /root/sources/install.sh install_cracking_tools
RUN /root/sources/install.sh install_osint_tools
RUN /root/sources/install.sh install_web_tools
RUN /root/sources/install.sh install_c2_tools
RUN /root/sources/install.sh install_services_tools
RUN /root/sources/install.sh install_ad_tools
RUN /root/sources/install.sh install_mobile_tools
RUN /root/sources/install.sh install_iot_tools
RUN /root/sources/install.sh install_rfid_tools
RUN /root/sources/install.sh install_voip_tools
RUN /root/sources/install.sh install_sdr_tools
RUN /root/sources/install.sh install_network_tools
RUN /root/sources/install.sh install_wifi_tools
RUN /root/sources/install.sh install_forensic_tools
RUN /root/sources/install.sh install_cloud_tools
RUN /root/sources/install.sh install_steganography_tools
RUN /root/sources/install.sh install_reverse_tools
RUN /root/sources/install.sh install_crypto_tools
RUN /root/sources/install.sh install_GUI_tools

RUN /root/sources/install.sh install_resources
RUN /root/sources/install.sh install_clean

RUN rm -rf /root/sources

WORKDIR /data
#CMD ["/bin/zsh"]
