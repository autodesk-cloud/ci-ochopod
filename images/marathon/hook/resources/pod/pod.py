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
import string
import time

from ochopod.bindings.generic.marathon import Pod
from ochopod.core.tools import Shell
from ochopod.models.piped import Actor as Piped
from ochopod.models.reactive import Actor as Reactive

logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    #
    # - generate a random 32 characters token (valid for the lifetime of the pod)
    # - use it to filter a bit who can POST to us
    # - this token can also be defined when deploying the pod
    #
    settings = json.loads(os.environ['pod'])
    alphabet = string.letters + string.digits + '+/'
    randomized = ''.join(alphabet[ord(c) % len(alphabet)] for c in os.urandom(32))
    token = settings['token'] if 'token' in settings else randomized

    class Model(Reactive):

        depends_on = ['redis', 'slave-*']

    class Strategy(Piped):

        cwd = '/opt/hook'
        
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
                    'token': token,
                    'uptime': '%.2f hours (pid %s)' % (lapse, pid)
                }

        def can_configure(self, cluster):

            assert cluster.grep('redis', 6379), '1 redis required'

        def configure(self, cluster):

            #
            # - grab all the slave dependencies
            # - count how many we have and group by type
            #
            pods = cluster.dependencies['slave-*']
            unrolled = [js['cluster'] for _, js in pods.items()]
            keys = set(unrolled)
            tally = {key: unrolled.count(key) for key in keys}

            return 'python hook.py', \
                   {
                       'token': token,
                       'redis': cluster.grep('redis', 6379),
                       'slaves': json.dumps(tally)
                   }

    Pod().boot(Strategy, model=Model, tools=[Shell])