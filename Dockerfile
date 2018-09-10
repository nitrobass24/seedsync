FROM ubuntu:18.04

LABEL maintainer="nitrobass24"

ARG USERNAME=docker

ENV USERNAME=$USERNAME \
    UID=991 \
    GID=991 \
    TZ=America/Chicago

#Create service account
RUN echo $UID \
    echo $GID \
    echo $USERNAME
RUN useradd -u $UID -g $GID $USERNAME

# Install dependencies
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y \
    libssl-dev \
    lftp \
    openssh-client \
    rar \
    unrar \
    p7zip \
    curl \
    libexpat1 \
    wget
    
RUN wget http://mirrors.kernel.org/ubuntu/pool/main/r/readline6/libreadline6_6.3-8ubuntu2_amd64.deb && dpkg -i libreadline6_6.3-8ubuntu2_amd64.deb

# Disable the known hosts prompt
RUN mkdir -p /root/.ssh && echo "StrictHostKeyChecking no\nUserKnownHostsFile /dev/null" > /root/.ssh/config

#Install Seedsync from Latest Github Release https://github.com/ipsingh06/seedsync
RUN wget `curl -s https://api.github.com/repos/ipsingh06/seedsync/releases/latest | grep browser_download_url | grep '64[.]deb' | cut -d '"' -f 4`
RUN echo "seedsync seedsync/username string $USER" | debconf-set-selections
RUN dpkg -i seedsync*.deb

#create directories
RUN mkdir /downloads /config /config/log

#WORKDIR /config

EXPOSE 8800
VOLUME /confg /downloads
