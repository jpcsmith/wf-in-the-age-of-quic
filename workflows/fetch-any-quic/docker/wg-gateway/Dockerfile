# Configure a Wireguard VPN Server for the experiment
#
# Each VPN server hosts services multiple clients.  The approach used 
# was taken from [1].
#
# References
# ----------
# [1] https://medium.com/@firizki/running-wireguard-on-docker-container-76355c43787c
#
# TODO: Determine whether this requires wireguard to be installed on the host 

FROM python:3.7-slim-buster

#
# Install Wireguard (from backports) and any necessary dependencies
#
RUN echo "deb http://deb.debian.org/debian buster-backports main" \
        > /etc/apt/sources.list.d/backports.list \
    && apt-get -qq update \
    && apt-get -qq install -y iptables iproute2 wireguard procps \
    && rm -rf /var/lib/apt/lists/*


COPY run-vpn-server /usr/local/sbin/run-vpn-server

CMD ["run-vpn-server"]
