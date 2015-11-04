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
import requests
import string
import time

from ochopod.api import Tool
from ochopod.bindings.generic.marathon import Pod
from ochopod.core.tools import Shell
from ochopod.core.utils import shell
from ochopod.models.piped import Actor as Piped
from ochopod.models.reactive import Actor as Reactive
from os.path import join


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    #
    # - generate a random 32 characters token (valid for the lifetime of the pod)
    # - use it to implement a SHA1 digest verification
    # - this token can also be defined when deploying the pod
    #
    settings = json.loads(os.environ['pod'])
    alphabet = string.letters + string.digits + '+/'
    randomized = ''.join(alphabet[ord(c) % len(alphabet)] for c in os.urandom(32))
    token = settings['token'] if 'token' in settings else randomized
    shell("echo 'jenkins:%s' | sudo -S chpasswd" % token)

    class Run(Tool):
        """
        Dedicated tool to upload/trigger CD scripts from the ochothon CLI. The tool will perform the SHA1
        signature and allow to specify arbitrary variables on the command line. The servo output will passed back
        to the CLI.

        CLI usage:
        $ exec *.servo --force run my-scripts-folder script.py --variable key:value
        """

        tag = 'run'

        def define_cmdline_parsing(self, parser):

            parser.add_argument('tgz', type=str, nargs=1, help='the CD bundle as a TGZ archive')
            parser.add_argument('scripts', type=str, nargs='+', help='1+ scripts to run')
            parser.add_argument('-v', '--variables', action='store', dest='variables', type=str, nargs='+', help='key:value mappings')

        def body(self, args, cwd):

            #
            # - force the output to be formatted in JSON
            # - add any variable defined on the command line using -v
            #
            headers = {'Accept': 'application/json'}
            if args.variables:
                for value in args.variables:
                    tokens = value.split(':')
                    headers['X-Var-%s' % tokens[0]] = tokens[1]

            #
            # - fetch the uploaded TGZ archive in our temp. directory
            # - compute its SHA1 digest
            # - format the corresponding X-Signature header
            #
            tgz = join(cwd, args.tgz[0])
            code, lines = shell('openssl dgst -sha1 -hmac "%s" %s' % (token, tgz))
            assert code == 0, 'failed to sign the archive'
            headers['X-Signature'] = 'sha1=%s' % lines[0].split(' ')[1]

            #
            # - fire a POST /run request to ourselves
            # - pass the response back to the CLI
            #
            with open(tgz, 'rb') as f:

                files = {'tgz': f.read()}
                reply = requests.post('http://localhost:5000/run/%s' % '+'.join(args.scripts), files=files, headers=headers)
                assert reply.status_code < 300, 'invalid response (HTTP %d)' % reply.status_code
                js = json.loads(reply.text)
                return 0 if js['ok'] else 1, js['log']

    class Model(Reactive):

        depends_on = ['portal']

    class Strategy(Piped):

        cwd = '/opt/servo'

        check_every = 60.0

        pid = None

        since = 0.0

        def sanity_check(self, pid):

            #
            # - simply use the provided process ID to start counting time
            # - this is a cheap way to measure the sub-process up-time
            # - display our token as well
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

            assert len(cluster.dependencies['portal']) == 1, 'need 1 portal'

        def configure(self, cluster):

            #
            # - get our pod details
            #
            pod = cluster.pods[cluster.key]

            #
            # - look the ochothon portal up @ TCP 9000
            # - update the resulting connection string into /opt/slave/.portal
            # - this will be used by the CI/CD scripts to issue commands
            #
            with open('/opt/servo/.portal', 'w') as f:
                f.write(cluster.grep('portal', 9000))

            #
            # - pass the token and our local IP:port connection string (used for the callback
            #   mechanism)
            #
            return 'python hook.py', \
                   {
                       'token': token,
                       'local': '%s:%d' % (pod['ip'], pod['ports']['5000'])
                   }

    Pod().boot(Strategy, model=Model, tools=[Run, Shell])