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

from tools.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            '''
            '''

        tag = 'hipchat'

        def customize(self, parser):

            parser.add_argument('room', type=str, nargs=1, help='hipchat room id, e.g 123456')
            parser.add_argument('message', type=str, nargs='+', help='1+ tokens forming the message to deliver')
            parser.add_argument('-c', dest='color', type=str, default='yellow', help='optional notification color')
            parser.add_argument('-t', dest='token', type=str, help='optional hipchat api token')

        def body(self, args):

            assert args.color in ['yellow', 'green', 'red', 'purple', 'gray'], 'invalid color (check the v2 API)'

            #
            # - if the API token is not specify go look in the canned presets
            # - those are passed as serialized json payload in $PRESETS
            #
            presets = json.loads(os.environ['PRESETS'])
            blk = presets['hipchat']
            token = blk['token'] if not args.token else args.token

            js = \
                {
                    'message': ' '.join(args.message),
                    'message_format': 'text',
                    'color': args.color,
                    'from': 'CI backend'
                }

            reply = requests.post(
                'https://api.hipchat.com/v2/room/%s/notification?auth_token=%s' % (args.room[0], token),
                headers={'Content-Type': 'application/json'},
                data=json.dumps(js))

            assert reply.status_code < 300, 'failed to deliver hipchat notification (HTTP %d)' % reply.status_code
            return 0

    return _Tool()