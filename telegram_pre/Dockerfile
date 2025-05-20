FROM ubuntu:jammy
COPY . /app
RUN apt-get -y update && \
    apt-get -y update && \
    apt-get install -y wget python3.11 python3-pip python3.11-dev && \
    wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.19_amd64.deb && \
    dpkg -i libssl1.1_1.1.1f-1ubuntu2.19_amd64.deb


RUN  pip --no-cache-dir  install --user -r /app/requirements.txt

RUN  apt-get autoremove -y \
    && apt-get remove -y python3-pip

WORKDIR /app
# -u print打印出来
CMD ["/bin/bash", "-c", "set -e && python3 -u bot.py"]
