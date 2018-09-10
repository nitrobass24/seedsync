FROM ubuntu:18.04

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
RUN curl -s https://api.github.com/repos/ipsingh06/seedsync/releases/latest | grep browser_download_url | grep '64[.]deb' | cut -d '"' -f 4
RUN dpkg -i seedsync*.deb

#COPY artifacts /app

#create directories
RUN echo "creating directories"
RUN mkdir /downloads /config /config/log

#ADD setup_default_config.sh /scripts/
#RUN /scripts/setup_default_config.sh

# Must run app inside shell
# Otherwise the container crashes as soon as a child process exits
#CMD [ \
#    "/bin/sh", "-c", \
#    "/app/seedsync -c /config" \
#]

EXPOSE 8800
