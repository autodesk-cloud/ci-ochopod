FROM autodeskcloud/pod:1.0.7

#
# - build redis 2.8.17 from source
# - install it into /usr/local/bin
# - add our trimmed down config
#
RUN apt-get update && apt-get -y install build-essential wget
RUN wget http://download.redis.io/releases/redis-2.8.17.tar.gz
RUN tar xzf redis-2.8.17.tar.gz
RUN cd redis-2.8.17 && make install
ADD resources/redis-server.conf /opt/redis-2.8.17/redis-server.conf
RUN mkdir /var/lib/redis

#
# - add our spiffy pod script
# - add the redis supervisor config file
# - start supervisor
#
ADD resources/pod /opt/redis-2.8.17/pod
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
