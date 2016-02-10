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
import hashlib
import hmac
import json
import logging
import ochopod
import os
import redis
import requests
import sys

from flask import Flask, request
from ochopod.core.fsm import diagnostic
from random import choice

logger = logging.getLogger('ochopod')

web = Flask(__name__)


if __name__ == '__main__':

    try:

        def _slack(line):

            headers = \
                {
                    'Content-Type': 'application/json'
                }

            requests.post('http://%s' % os.environ['slack'], data=line, headers=headers)

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - grab redis & connect to it
        #
        hints = json.loads(os.environ['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)

        #
        # - we got a tally of how many pods we have for each slave category
        # - we'll use it to perform the module and shard the queues
        #
        slaves = json.loads(os.environ['slaves'])

        @web.route('/ping', methods=['GET'])
        def _ping():

            return '', 200

        @web.route('/status/<branch>/<path:path>', methods=['GET'])
        def _status(branch, path):

            logger.info('HTTP -> GET /status/%s/%s' % (branch, path))

            #
            # - force a json output if the Accept header matches 'application/json'
            # - otherwise default to a text/plain response
            #
            key = '%s:%s' % (branch, path)
            raw = request.accept_mimetypes.best_match(['application/json']) is None
            payload = client.get('status:%s' % key)
            if payload is None:
                return '', 404

            if raw:

                #
                # - if 'application/json' was not requested simply dump the log as is
                # - force the response code to be HTTP 412 upon failure and HTTP 200 otherwise
                #
                js = json.loads(payload)
                code = 200 if js['ok'] else 412
                return '\n'.join(js['log']), code, \
                    {
                        'Content-Type': 'text/plain; charset=utf-8'
                    }

            else:

                #
                # - if 'application/json' was requested always respond with a HTTP 200
                # - the response body then contains our serialized JSON output
                #
                return payload, 200, \
                    {
                        'Content-Type': 'application/json; charset=utf-8'
                    }

        @web.route('/', methods=['POST'], defaults={'capabilities': None})
        @web.route('/<capabilities>', methods=['POST'])
        def _git_hook(capabilities):

            logger.info('HTTP -> POST /')

            #
            # - if we have no build slaves, fast-fail on a 304
            #
            if not slaves:
                return '', 304

            #
            # - we want the hook to be signed
            # - fail on a HTTP 403 if not
            #
            if not 'X-Hub-Signature' in request.headers:
                return '', 403

            #
            # - compute the HMAC and compare (use our pod token as the key)
            # - fail on a 403 if mismatch
            #
            digest = 'sha1=' + hmac.new(os.environ['token'], request.data, hashlib.sha1).hexdigest()
            if digest != request.headers['X-Hub-Signature']:
                return '', 403

            #
            # - retrieve the branch
            #
            logger.debug('git payload -> %s' % request.data)
            js = json.loads(request.data)
            branch = js['ref'].split('/')[-1]

            if capabilities is None:

                #
                # - no specific capability requested, just pick a slave cluster at random
                #
                cluster = choice(slaves.keys())

            else:

                #
                # - look at our slave dependencies
                # - try to match the requested capabilities against what the various slaves offer
                # - the slave clusters are named slave-[<token>]* where each token is a capability
                #
                cluster = None
                caps = set(capabilities.split('+'))
                for tag in sorted(slaves.keys(), key=lambda item: (len(item), item)):
                    offered = set(tag.split('-'))
                    logger.debug(caps)
                    logger.debug(offered)
                    if caps.issubset(offered):
                        cluster = tag
                        break

            #
            # - if we couldn't find a match abort on a 304
            # - otherwise use the # of slaves in that cluster as our modulo
            #
            if not cluster:
                logger.info('unable to find a slave (capabilities -> %s)' % capabilities)
                return '', 304

            #
            # - hash the data from git to send it to a specific queue
            # - we do this to splay out the traffic amongst our slaves while retaining stickiness
            #
            cfg = js['repository']
            path = cfg['full_name']
            modulo = slaves[cluster]
            qid = hash(path) % modulo
            key = '%s:%s' % (branch, path)
            client.set('git:%s' % key, request.data)
            client.set('slave:%s' % key, cluster)
            logger.debug('updated git push data @ %s' % key)
            _slack(':rocket: git push for *%s* (%s), keyed @ _%s_' % (key, branch, cluster))

            build = \
                {
                    'key':    key,
                    'branch': branch
                }

            to = 'queue-%s-%d' % (cluster, qid)
            client.rpush(to, json.dumps(build))
            logger.debug('requested build @ %s -> %s' % (key, to))
            return '', 200

        @web.route('/build/<branch>/<path:path>', methods=['POST'])
        def _build(branch, path):

            logger.info('HTTP -> POST /build/%s/%s' % (branch, path))

            #
            # - if we have no build slaves, fast-fail on a 304
            #
            if not slaves:
                return '', 304

            #
            # - look the specified repository up
            # - fail on a 404 if not found
            #
            key = '%s:%s' % (branch, path)
            payload = client.get('git:%s' % key)
            if payload is None:
                return '', 404

            #
            # -
            #
            cluster = client.get('slave:%s' % key)
            assert cluster is not None, 'slave:%s not found in redis (bug ?)' % key
            if cluster not in slaves:
                return '', 304

            modulo = slaves[cluster]
            qid = hash(path) % modulo
            _slack(':rocket: HTTP request for *%s* (%s), keyed @ _%s_' % (key, branch, cluster))

            #
            # - simply push they key to the appropriate queue
            #
            reset = 'X-Reset' in request.headers and request.headers['X-Reset'] == 'true'
            build = \
                {
                    'key': key,
                    'branch': branch,
                    'reset': reset
                }

            client.rpush('queue-%s-%d' % (cluster, qid), json.dumps(build))
            logger.debug('requested build @ %s -> %s' % (key, cluster))
            return '', 200

        #
        # - run our flask endpoint on TCP 5000
        #
        web.run(host='0.0.0.0', port=5000)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)