FROM autodeskcloud/pod:1.0.7

#
# - include sshd
#
RUN apt-get update && apt-get install -y sudo openssh-server
RUN mkdir -p /var/run/sshd
RUN adduser --gecos "" jenkins
RUN echo 'jenkins:jenkins' | sudo -S chpasswd
RUN echo 'jenkins ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN sed -i -e 's/^\(session\s\+required\s\+pam_loginuid.so$\)/#\1/' /etc/pam.d/sshd

#
# - add our internal package containing our toolkit
# - install it
#
ADD resources/servo /opt/python/servo
RUN cd /opt/python/servo && python setup.py install

#
# - install yaml and retrying
#
RUN pip install pyyaml retrying

#
# - add our spiffy pod script
# - add the web-hook script
# - add the supervisor config files
# - start supervisor
#
ADD resources/pod /opt/servo/pod
ADD resources/servo /opt/servo/
ADD resources/hook.py /opt/servo/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
