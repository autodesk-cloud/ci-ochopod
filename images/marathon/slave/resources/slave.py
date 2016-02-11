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
import ochopod
import os
import re
import redis
import requests
import shutil
import sys
import tempfile
import time
import yaml

from ochopod.core.utils import shell
from ochopod.core.fsm import diagnostic
from os import path
from yaml import YAMLError


logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - parse our $pod settings (defined in the pod yml)
        # - grab redis
        # - connect to it
        #
        hints = json.loads(os.environ['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        settings = json.loads(os.environ['pod'])
        tokens = os.environ['redis'].split(':')
        client = redis.StrictRedis(host=tokens[0], port=int(tokens[1]), db=0)
        while 1:

            def _slack(line):

                headers = \
                    {
                        'Content-Type': 'application/json'
                    }

                requests.post('http://%s' % os.environ['slack'], data=line, headers=headers)

            #
            # - the key passed int the queue is made of the branch & repository tag
            #
            queue = 'queue-%s-%d' % (hints['cluster'], int(os.environ['index']))
            logger.debug('waiting on %s...' % queue)
            try:
                _, js = client.blpop(queue)
                build = json.loads(js)
                branch = build['branch']
                started = time.time()
                payload = client.get('git:%s' % build['key'])
                js = json.loads(payload)

                #
                # - extract the various core parameters from the git push json
                # - prep a directory under /tmp/<repo>-<branch>
                # - we'll stick to it and clone/checkout the code in there
                #
                ok = 1
                complete = 0
                cfg = js['repository']
                tag = cfg['full_name']
                sha = js['after']
                last = js['commits'][0]
                safe = tag.replace('/', '-')
                abridged = []
                log = ['- commit %s (%s)' % (sha[0:10], last['message'])]
                cached = path.join('/tmp', '%s-%s' % (safe, branch))
                tmp = tempfile.mkdtemp()
                try:

                    _slack(':rocket: %s #%d: build starting for *%s* (%s, hash _%s_ "%s")...' % (hints['cluster'], int(os.environ['index']), tag, branch, sha[0:10], last['message']))

                    try:

                        #
                        # - if requested wipe out the directory first
                        # - this will force a git clone
                        #
                        if 'reset' in build and build['reset']:
                            try:
                                shutil.rmtree(cached)
                                logger.info('wiped out %s' % cached)
                            except IOError:
                                pass

                        repo = path.join(cached, cfg['name'])
                        if not path.exists(repo):

                            #
                            # - the repo is not in our cache
                            # - git clone it
                            #
                            os.makedirs(cached)
                            logger.info('cloning %s [%s]' % (tag, branch))
                            url = 'https://%s' % cfg['git_url'][6:]
                            code, _ = shell('git clone -b %s --single-branch %s' % (branch, url), cwd=cached)
                            assert code == 0, 'unable to clone %s' % url
                        else:

                            #
                            # - the repo is already in there
                            # - git pull
                            #
                            shell('git pull', cwd=repo)

                        #
                        # - checkout the specified commit hash
                        #
                        logger.info('checkout @ %s' % sha[0:10])
                        code, _ = shell('git checkout %s' % sha, cwd=repo)
                        assert code == 0, 'unable to checkout %s (wrong credentials and/or git issue ?)' % sha[0:10]

                        #
                        # - prep a little list of env. variable to pass down to the shell
                        #   snippets we'll run
                        #
                        var = \
                            {
                                'HOST':             os.environ['HOST'],
                                'BRANCH':           branch,
                                'COMMIT':           sha,
                                'COMMIT_SHORT':     sha[0:10],
                                'MESSAGE':          last['message'],
                                'TAG':              re.sub(r'[^a-zA-Z0-9=]', '-','%s-%s' % (branch, sha[0:10])),
                                'TIMESTAMP':        last['timestamp']
                            }

                        #
                        # - go look for integration.yml
                        # - if not found abort
                        #
                        with open(path.join(repo, 'integration.yml'), 'r') as f:
                            yml = yaml.load(f)

                        #
                        # - the yaml can either be an array or a dict
                        # - force it to an array for convenience
                        # - otherwise loop and execute each shell snippet in order
                        #
                        js = yml if isinstance(yml, list) else [yml]
                        for blk in js:
                            log += ['- %s' % blk['step']]
                            debug = blk['debug'] if 'debug' in blk else 0
                            cwd = path.join(repo, blk['cwd']) if 'cwd' in blk else repo
                            for snippet in blk['shell']:

                                tick = time.time()
                                tokens = snippet.split(' ')
                                always = tokens[0] == 'no-skip'
                                if always or ok:

                                    #
                                    # - if we used the 'no-skip' directive make sure we remove
                                    #   it from the snippet
                                    #
                                    if always:
                                        snippet = ' '.join(tokens[1:])

                                    #
                                    # - set the $OK and $LOG variables
                                    # - make sure to use the abridged log to avoid exploding the maximum
                                    #   env. variable capacity
                                    #
                                    local = {'LOG': '\n'.join(abridged)}
                                    if ok:
                                        local['OK'] = 'true'

                                    #
                                    # - if block specifies environment variables set them now
                                    #
                                    if 'env' in blk:
                                        for key, value in blk['env'].items():
                                            local[key] = str(value)

                                    #
                                    # - update the environment we'll pass to the shell
                                    # - execute the snippet via a popen()
                                    #
                                    local.update(var)
                                    capped = snippet if len(snippet) < 32 else '%s...' % snippet[:64]
                                    capped = capped.replace('\n', ' ')
                                    logger.debug('running <%s>' % capped)

                                    script = path.join(tmp, 'script.sh')
                                    with file(script, mode='w') as f:
                                        f.write(snippet)

                                    code, lines = shell('/bin/bash %s' % script, cwd=cwd, env=local)

                                    lapse = int(time.time() - tick)
                                    status = 'passed' if not code else 'failed'
                                    memento = '[%s] %s (%d seconds, exit code %d)' % (status, capped, lapse, code)
                                    abridged += [memento]
                                    log += [memento]
                                    logger.debug('<%s> -> %d' % (capped, code))
                                    if debug:
                                        log += ['[%s]   . %s' % (status, line) for line in lines]

                                    #
                                    # - switch the ok trigger off if the shell invocation failed
                                    # - all subsequent shell executions will then be ignored unless
                                    #   the 'no-skip' directive is used
                                    #
                                    if code != 0:
                                        ok = 0

                                else:
                                    log += ['[skipped] %s' % snippet]

                        #
                        # - we went through the whole thing
                        #
                        complete = 1

                    except AssertionError as failure:

                        log += ['* %s' % str(failure)]

                    except IOError:

                        log += ['* unable to load integration.yml (missing from the repo ?)']

                    except YAMLError as failure:

                        log += ['* invalid YAML syntax']

                    except Exception as failure:

                        log += ['* unexpected condition -> %s' % diagnostic(failure)]

                finally:

                    #
                    # - make sure to cleanup our temporary directory
                    #
                    shutil.rmtree(tmp)

                    #
                    # - make sure to cleanup our temporary directory
                    # - update redis with
                    #
                    if not complete:
                        logger.error('build interrupted (%s)' % log[-1])

                    seconds = int(time.time() - started)
                    status = \
                        {
                            'ok': ok and complete,
                            'sha': sha,
                            'log': log,
                            'seconds': seconds
                        }
                    client.set('status:%s' % build['key'], json.dumps(status))
                    logger.info('%s @ %s -> %s %d seconds' % (tag, sha[0:10], 'ok' if status['ok'] else 'ko', seconds))

                icon = ':white_check_mark:' if ok and complete else ':no_entry:'
                _slack(':rocket: %s *%s* (%s, hash _%s_) ran in *%ds* with log:' % (icon, tag, branch, sha[0:10], seconds))
                _slack('```%s```' % '\n'.join(log))

            except Exception as failure:

                _slack(':no_entry: internal failure: "_%s_"' % diagnostic(failure))
                logger.error('unexpected condition -> %s' % diagnostic(failure))

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)