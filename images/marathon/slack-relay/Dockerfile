FROM autodeskcloud/pod:1.0.7

RUN apt-get update && apt-get install -y python-dev build-essential
RUN pip install --upgrade cython gevent gunicorn
RUN pip install git+https://github.com/falconry/falcon.git

ADD resources/sink.py /opt/relay/sink.py
ADD resources/pod /opt/relay/pod
ADD resources/supervisor /etc/supervisor/conf.d
CMD exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf