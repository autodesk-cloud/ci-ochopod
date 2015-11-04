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

from requests.auth import HTTPBasicAuth
from tools.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            '''
            '''

        tag = 'jenkins'

        def customize(self, parser):

            parser.add_argument('path', type=str, nargs=1, help='full job path, e.g master/job/folder/job/foo')
            parser.add_argument('-u', dest='user', type=str, help='optional jenkins user')
            parser.add_argument('-t', dest='token', type=str, help='optional jenkins api token')

        def body(self, args):

            #
            # - if the API token is not specify go look in the canned presets
            # - those are passed as serialized json payload in $PRESETS
            #
            presets = json.loads(os.environ['PRESETS'])
            blk = presets['jenkins']
            master = blk['master']
            user = blk['username'] if not args.user else args.user
            token = blk['token'] if not args.token else args.token

            #
            # -
            #
            path = args.path[0].split('/')
            assert len(path) > 3 and path[-2] == 'job', 'malformed jenkins path'
            tag = path[-1]
            auth = HTTPBasicAuth(user, token)
            cb = os.environ['QUERY_URL']
            script = \
                [
                    '#!/bin/bash',
                    'CODE=$(curl -s -o /dev/null --write-out "%%{http_code}" -H "Accept: text/plain" %s)' % cb,
                    'if [[ $CODE -ne 200 ]] ; then',
                    'exit 1',
                    'fi'
                ]

            xml = \
                """
                    <project>
                        <actions/>
                        <description>auto-generated CI project for repo %s</description>
                        <assignedNode>ECS</assignedNode>
                        <builders>
                            <hudson.tasks.Shell>
                                <command>%s</command>
                            </hudson.tasks.Shell>
                        </builders>
                    </project>
                """

            requests.post(
                '%s/%s/createItem?name=%s' % (master,'/'.join(path[:-2]), tag),
                data=xml % (tag, '\n'.join(script)),
                headers={'Content-Type': 'application/xml'},
                auth=auth)

            reply = requests.post('%s/%s/build' % (master, args.path[0]), auth=auth)

            assert reply.status_code < 300, 'failed to trigger a jenkins build (HTTP %d)' % reply.status_code
            return 0

    return _Tool()