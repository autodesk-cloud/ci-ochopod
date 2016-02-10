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
import logging
import time

from ochopod.bindings.generic.marathon import Pod
from ochopod.core.tools import Shell
from ochopod.models.piped import Actor as Piped

logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    class Strategy(Piped):

        cwd = '/opt/relay'

        check_every = 60.0

        pid = None

        since = 0.0

        pipe_subprocess = True

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

        def configure(self, cluster):

            #
            # - start the hosting web framework on TCP 9000
            #
            return 'gunicorn -b 0.0.0.0:9000 sink:endpoint', {}

    Pod().boot(Strategy, tools=[Shell])