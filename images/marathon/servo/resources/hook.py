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
import string
import tempfile
import time
import shutil
import sys

from flask import Flask, request
from ochopod.core.fsm import diagnostic
from ochopod.core.utils import shell
from os import path

logger = logging.getLogger('ochopod')

web = Flask(__name__)


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        #
        blocked = {}
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')

        @web.route('/callback/<token>', methods=['POST'])
        @web.route('/callback/<token>/<tag>', methods=['POST'])
        def _set_callback(token, tag='callback.raw'):

            if token not in blocked:
                return '', 404

            #
            # - dump the incoming payload under the temp directory
            # - use the specified filename
            #
            with open(path.join(blocked[token], tag), 'w') as f:
                logger.info('callback received for %s (%d B)' % (token, len(request.data)))
                f.write(request.data)

            return '', 200

        @web.route('/run/<scripts>', methods=['POST'])
        def _from_curl(scripts):

            #
            # - retrieve the X-Signature header
            # - fast-fail on a HTTP 403 if not there or if there is a mismatch
            #
            if not 'X-Signature' in request.headers:
                return '', 403

            #
            # - force a json output if the Accept header matches 'application/json'
            # - otherwise default to a text/plain response
            # - create a temporary directory to run from
            #
            ok = 0
            log = []
            alphabet = string.letters + string.digits
            token = ''.join(alphabet[ord(c) % len(alphabet)] for c in os.urandom(8))
            raw = request.accept_mimetypes.best_match(['application/json']) is None
            tmp = tempfile.mkdtemp()
            try:

                #
                # - any request header in the form X-Var-* will be kept around and passed as
                #   an environment variable when executing the script
                # - make sure the variable is spelled in uppercase
                #
                local = {key[6:].upper(): value for key, value in request.headers.items() if key.startswith('X-Var-')}

                #
                # - craft a unique callback URL that points to this pod
                # - this will be passed down to the script to enable transient testing jobs
                #
                cwd = path.join(tmp, 'uploaded')
                local['CALLBACK'] = 'http://%s/callback/%s' % (env['local'], token)
                blocked[token] = cwd
                for key, value in local.items():
                    log += ['$%s = %s' % (key, value)]

                #
                # - download the archive
                # - compute the HMAC and compare (use our pod token as the key)
                # - fail on a 403 if mismatch
                #
                where = path.join(tmp, 'bundle.tgz')
                request.files['tgz'].save(where)
                with open(where, 'rb') as f:
                    bytes = f.read()
                    digest = 'sha1=' + hmac.new(env['token'], bytes, hashlib.sha1).hexdigest()
                    if digest != request.headers['X-Signature']:
                        return '', 403

                #
                # - extract it into its own folder
                # - make sure the requested script is there
                #
                code, _ = shell('mkdir uploaded && tar zxf bundle.tgz -C uploaded', cwd=tmp)
                assert code == 0, 'unable to open the archive (bogus payload ?)'

                #
                # - decrypt any file whose extension is .aes
                # - just run openssl directly and dump the output in the working directory
                # - note: at this point we just look for .aes file in the top level directory
                #
                for file in os.listdir(cwd):
                    bare, ext = path.splitext(file)
                    if ext != '.aes':
                        continue

                    code, _ = shell('openssl enc -d -base64 -aes-256-cbc -k %s -in %s -out %s' % (env['token'], file, bare), cwd=cwd)
                    if code == 0:
                        log += ['decrypted %s' % file]

                #
                # - run each script in order
                # - abort immediately if the script exit code is not zero
                # - keep the script output as a json array
                #
                for script in scripts.split('+'):
                    now = time.time()
                    assert path.exists(path.join(cwd, script)), 'unable to find %s (check your scripts)' % script
                    code, lines = shell('python %s 2>&1' % script, cwd=cwd, env=local)
                    log += lines + ['%s ran in %d seconds' % (script, int(time.time() - now))]
                    assert code == 0, '%s failed on exit code %d' % (script, code)

                ok = 1

            except AssertionError as failure:

                log += ['failure (%s)' % failure]

            except Exception as failure:

                log += ['unexpected failure (%s)' % diagnostic(failure)]

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                del blocked[token]
                shutil.rmtree(tmp)

            if raw:

                #
                # - if 'application/json' was not requested simply dump the log as is
                # - force the response code to be HTTP 412 upon failure and HTTP 200 otherwise
                #
                code = 200 if ok else 412
                return '\n'.join(log), code, \
                    {
                        'Content-Type': 'text/plain; charset=utf-8'
                    }

            else:

                #
                # - if 'application/json' was requested always respond with a HTTP 200
                # - the response body then contains our serialized JSON output
                #
                js = \
                    {
                        'ok': ok,
                        'log': log
                    }

                return json.dumps(js), 200, \
                    {
                        'Content-Type': 'application/json; charset=utf-8'
                    }

        #
        # - run our flask endpoint on TCP 5000
        #
        web.run(host='0.0.0.0', port=5000, threaded=True)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)