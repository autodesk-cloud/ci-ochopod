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
import base64
import json
import logging
import tempfile
import time
import shutil

from ochopod.core.utils import shell
from tools.tool import Template
from urlparse import urlparse

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            '''
                Leverages the underlying docker daemon to build & push an image. You must run this script
                in a directory that contains a valid Dockerfile. The optional -t switch can be used to specify
                one or more image tags (defaults to latest if not specified).

                The underlying node's docker configuration (.dockercfg) is used when performing the push and must
                be mounted in /host.
            '''

        tag = 'push'

        def customize(self, parser):

            parser.add_argument('repo', type=str, nargs=1, help='docker repo to build, e.g paugamo/test')
            parser.add_argument('-t', dest='tags', type=str, default='latest', help='optional comma separated tags, e.g latest,foo,bar')

        def body(self, args):

            #
            # - setup a temp directory
            # - use it to store a tar of the current folder
            #
            stated = time.time()
            tmp = tempfile.mkdtemp()
            try:

                #
                # - tar the whole thing
                # - loop over the specified image tags
                #
                code, _ = shell('tar zcf %s/bundle.tgz *' % tmp)
                assert code == 0, 'failed to tar'
                for tag in args.tags.split(','):

                    #
                    # - send the archive over to the underlying docker daemon
                    # - make sure to remove the intermediate containers
                    # - by design our container runs a socat on TCP 9001
                    #
                    tick = time.time()
                    _, lines = shell(
                        'curl -H "Content-Type:application/octet-stream" '
                        '--data-binary @bundle.tgz '
                        '"http://localhost:9001/build?forcerm=1\&t=%s:%s"' % (args.repo[0], tag), cwd=tmp)
                    assert len(lines) > 1, 'empty docker output (failed to build or docker error ?)'
                    last = json.loads(lines[-1])

                    #
                    # - the only way to test out for failure is to peek at the end of the docker output
                    #
                    lapse = time.time() - tick
                    assert 'error' not in last, last['error']
                    logger.debug('built tag %s in %d seconds' % (tag, lapse))

                    #
                    # - cat our .dockercfg (which is mounted)
                    # - craft the authentication header required for the push
                    # - push the image using the specified tag
                    #
                    _, lines = shell('cat /host/.docker/config.json')
                    assert lines, 'was docker login run (no config.json found) ?'
                    js = json.loads(' '.join(lines))
                    assert 'auths' in js, 'invalid config.json setup (unsupported docker install ?)'
                    for url, payload in js['auths'].items():
                        tokens = base64.b64decode(payload['auth']).split(':')
                        host = urlparse(url).hostname
                        credentials = \
                            {
                                'serveraddress': host,
                                'username': tokens[0],
                                'password': tokens[1],
                                'email': payload['email'],
                                'auth': ''
                            }

                        tick = time.time()
                        auth = base64.b64encode(json.dumps(credentials))
                        shell(
                            'curl -X POST -H "X-Registry-Auth:%s" '
                            '"http://localhost:9001/images/%s/push?tag=%s"' % (auth, args.repo[0], tag))
                        lapse = time.time() - tick
                        logger.debug('pushed tag %s to %s in %d seconds' % (tag, host, lapse))

                    #
                    # - remove the image we just built if not latest
                    # - this is done to avoid keeping around too many tagged images
                    #
                    if tag != 'latest':
                        shell('curl -X DELETE "http://localhost:9001/images/%s:%s?force=true"' % (args.repo[0], tag))

                #
                # - clean up and remove any untagged image
                # - this is important otherwise the number of images will slowly creep up
                #
                _, lines = shell('curl "http://localhost:9001/images/json?all=0"')
                js = json.loads(lines[0])
                victims = [item['Id'] for item in js if item['RepoTags'] == ['<none>:<none>']]
                for victim in victims:
                    logger.debug('removing untagged image %s' % victim)
                    shell('curl -X DELETE "http://localhost:9001/images/%s?force=true"' % victim)

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

            lapse = int(time.time() - stated)
            logger.info('%s built and pushed in %d seconds' % (args.repo[0], lapse))
            return 0

    return _Tool()