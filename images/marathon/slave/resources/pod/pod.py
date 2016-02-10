#
# Copyright (c) 2015 Autodesk Inc.
# All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    class Model(Reactive):

        depends_on = ['slack-relay', 'redis']

    class Strategy(Piped):

        cwd = '/opt/slave'

        check_every = 60.0

        pid = None

        since = 0.0

        strict = True

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

            return {'uptime': '%.2f hours (pid %s)' % (lapse, pid)}

        def can_configure(self, cluster):

            assert len(cluster.dependencies['redis']) == 1, 'need 1 redis'

        def configure(self, cluster):

            #
            # - render ~/.netrc which will set our git credentials
            #
            settings = json.loads(os.environ['pod'])
            env = Environment(loader=FileSystemLoader('/opt/slave/pod/templates'))
            template = env.get_template('netrc')
            git = settings['git']
            mappings = \
                {
                    'login':    git['username'],
                    'password': git['password']
                }

            with open('/root/.netrc', 'w') as f:
                f.write(template.render(mappings))

            #
            # - note we use supervisor to socat the unix socket used by the underlying docker daemon
            # - it is bound to TCP 9001 (e.g any curl to localhost:9001 will talk to the docker API)
            # - the index is unique amongst the slave cluster and used to shard builds on specific hosts
            # - run the slave
            #
            return 'python slave.py', \
                   {
                       'index': cluster.index,
                       'redis': cluster.grep('redis', 6379),
                       'slack': cluster.grep('slack-relay', 9000)
                   }

    Pod().boot(Strategy, model=Model, tools=[Shell])