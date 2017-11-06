FROM dockerrm_baseimage

# copy lifecycle scripts to /opt/lifecycle
RUN mkdir /opt/lifecycle && chmod 777 /opt/lifecycle
ADD lifecycle /opt/lifecycle

# copy operation scripts to /opt/operations
ADD operations /opt/lifecycle
RUN chmod 777 /opt/lifecycle/*

COPY collectd.conf /etc/collectd/

# copy software

ENTRYPOINT ["/entrypoint.sh"]
