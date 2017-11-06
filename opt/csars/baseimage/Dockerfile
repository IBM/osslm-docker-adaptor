FROM ubuntu:latest

RUN apt-get update && apt-get install -y unzip curl net-tools netcat vim iproute2 build-essential collectd collectd-utils python3 python3-yaml python3-pip librdkafka-dev iputils-ping

RUN pip3 install Jinja2 urllib3 netifaces netaddr

COPY utilities/* /usr/local/bin/
RUN chmod -R +x /usr/local/bin/*

ADD entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY collectd.conf /etc/collectd/

ENTRYPOINT ["/entrypoint.sh"]
