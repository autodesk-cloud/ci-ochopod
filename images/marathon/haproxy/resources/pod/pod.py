#
#  Copyright (c) 2012-2015 by Autodesk, Inc.
#  All rights reserved.
#
#  The information contained herein is confidential and proprietary to
#  Autodesk, Inc., and considered a trade secret as defined under civil
#  and criminal statutes.  Autodesk shall pursue its civil and criminal
#  remedies in the event of unauthorized use or misappropriation of its
#  trade secrets.  Use of this information by anyone other than authorized
#  employees of Autodesk, Inc. is granted only under a written non-
#  disclosure agreement, expressly prescribing the scope and manner of
#  such use.
#
import json
import logging
import os
import time

from jinja2 import Environment, FileSystemLoader
from ochopod.bindings.generic.marathon import Pod
from ochopod.core.tools import Shell
from ochopod.models.piped import Actor as Piped
from ochopod.models.reactive import Actor as Reactive
from os.path import join, dirname

logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    #
    # - load our pod configuration settings
    # - this little json payload is packaged by the marathon toolset upon a push
    # - is it passed down to the container as the $pod environment variable
    #
    cfg = json.loads(os.environ['pod'])

    class Model(Reactive):

        depends_on = ['hook']

    class Strategy(Piped):

        cwd = '/opt/haproxy'

        check_every = 60.0

        pid = None

        since = 0.0

        def sanity_check(self, pid):

            #
            # - simply use the provided process ID to start counting time
            # - this is a cheap way to measure the sub-process up-time
            #
            now = time.time()
            if pid != self.pid:
                self.pid = pid
                self.since = now

            lapse = (now - self.since) / 3600.0

            return \
                {
                    'uptime': '%.2f hours (pid %s)' % (lapse, pid)
                }

        def can_configure(self, cluster):

            #
            # - we need at least one downstream url to redirect traffic to
            #
            assert cluster.grep('hook', 5000), 'need 1+ downstream listener'

        def tear_down(self, running):

            #
            # - force a SIGKILL to shut the proxy down
            #
            running.kill()

        def configure(self, cluster):

            #
            # - grep our listeners (the CI hooks)
            # - render into our 'local' backend directive (which is a standalone file)
            #
            urls = cluster.grep('hook', 5000).split(',')
            env = Environment(loader=FileSystemLoader(join(dirname(__file__), 'templates')))
            logger.info('%d downstream urls ->\n - %s' % (len(urls), '\n - '.join(urls)))
            mappings = \
                {
                    'port': 9000,
                    'listeners': {'listener-%d' % index: endpoint for index, endpoint in enumerate(urls)}
                }

            template = env.get_template('haproxy.cfg')
            with open('%s/haproxy.cfg' % self.cwd, 'w') as f:
                f.write(template.render(mappings))

            #
            # - at this point we have both the global/frontend and our default backend
            # - start haproxy using both configuration files
            #
            return '/usr/sbin/haproxy -f haproxy.cfg', {}

    Pod().boot(Strategy, model=Model, tools=[Shell])