FROM autodeskcloud/pod:1.0.7

#
# - add socat, pyyaml & redis
#
RUN apt-get install -y socat
RUN pip install redis pyyaml

#
# - add our internal package containing our python tools
# - install it (that will install a few scripts on the path)
#
ADD resources/tools /opt/python/tools
RUN cd /opt/python/tools && python setup.py install

#
# - add our spiffy pod script
# - add the slave script
# - add the supervisor config files
# - start supervisor
#
ADD resources/pod /opt/slave/pod
ADD resources/slave.py /opt/slave/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
