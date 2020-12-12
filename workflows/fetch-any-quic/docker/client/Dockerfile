# Create an image for fetching websites.
# 
# We attempt to store everything locally and provide it in the docker 
# context.  We forsee that this should help with reproducibility as we
# no longer rely on external servers.
# 
# Wireguard is installed in the image and is disabled by default. 
# set WIREGUARD=1 when running the container (not building) to 
# enable the use of wireguard at runtime.

# =================
# Install Wireguard
# =================
FROM python:3.7-slim-buster as wg-base

RUN echo "deb http://deb.debian.org/debian buster-backports main" \
        > /etc/apt/sources.list.d/backports.list \
    && apt-get -qq update \
    && apt-mark hold nftables \
    && apt-get -qq install -y iptables iproute2 wireguard procps \
    && rm -rf /var/lib/apt/lists/*


# =================
# Install Chromium
# =================
FROM wg-base as chromium

RUN apt-get -qq update && apt-get -qq install -y \
            unzip gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 \
            libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 ethtool \
            libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 \
            libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 \
            libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 \
            libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates libgbm1 \
            fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils wget \
        && rm -rf /var/lib/apt/lists/*

COPY Linux_x64_756066_chrome-linux.zip chrome-linux.zip
RUN unzip -q chrome-linux.zip \
        && rm chrome-linux.zip \
        && ln -s /chrome-linux/chrome /usr/local/bin/chrome


# =====================
# Install chromedriver
# =====================
FROM chromium as chromedriver

COPY Linux_x64_756066_chromedriver_linux64.zip chromedriver_linux64.zip
RUN unzip -q chromedriver_linux64.zip \
        && mv chromedriver_linux64/chromedriver /usr/local/bin \
        && rm chromedriver_linux64.zip \
        && rmdir chromedriver_linux64


# ========================================
# Install the script and its dependencies
# ========================================
FROM chromedriver as fetch-websites

RUN apt-get -qq update \
        && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y \
            wireshark-common \
            git \
            tcpdump \
            python3.7-dev \
            gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

COPY lab.tar.gz /tmp
RUN pip install --pre /tmp/lab.tar.gz

COPY fetch-websites fetch-websites-wrapper /usr/local/bin/


# =====================
# Disable Wireguard and add entrypoint
# =====================
ENV WIREGUARD=0
ENTRYPOINT ["fetch-websites-wrapper"]
