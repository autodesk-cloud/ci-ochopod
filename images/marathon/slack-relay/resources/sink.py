#
#  Copyright (c) 2012-2014 by Autodesk, Inc.
#  All rights reserved.
#
#  The information contained herein is confidential and proprietary to
#  Autodesk, Inc., and considered a trade secret as defined under civil
#  and criminal statutes.  Autodesk shall pursue its civil and criminal
#  remedies in the event of unauthorized use or misappropriation of its
#  trade secrets.  Use of this information by anyone other than authorized
#  employees of Autodesk, Inc. is granted only under a written non-
#  disclosure agreement, expressly prescribing the scope and manner of
#  such use.
#
import falcon
import json
import logging
import ochopod
import os
import requests

from collections import deque
from ochopod.core.fsm import FSM

#: our ochopod logger
logger = logging.getLogger('ochopod')

#: our falcon endpoint
endpoint = falcon.API()

#
# - load our pod configuration settings
# - this little json payload is packaged by the marathon toolset upon a push
# - is it passed down to the container as the $pod environment variable
# - parse our ochopod hints
# - enable CLI logging
#
cfg = json.loads(os.environ['pod'])
hints = json.loads(os.environ['ochopod'])
ochopod.enable_cli_log(debug=hints['debug'] == 'true')


class _Accumulator(FSM):

    """
    Simple state-machine bundling incoming messages together. This acts as a small accumulator and
    will help avoid being throttled by the API.
    """

    def __init__(self):
        super(_Accumulator, self).__init__()

        self.pending = deque()

    def initial(self, data):

        return 'spin', data, 0

    def reset(self, data):

        return 'spin', data, 0

    def spin(self, data):

        if self.pending:

            #
            # - decorate with the incoming JSON payload
            # - fire to the slack API
            #
            js = \
                {
                    'title':        ':thought_balloon: Notifications',
                    'fallback':     'Notifications',
                    'text':         '\n'.join(self.pending),
                    'mrkdwn_in':    ['text'],
                    'color':        '#7CD197'
                }

            data = \
                {
                    'username':     'Ochopod CI',
                    'token':        cfg['token'],
                    'channel':      cfg['channel'],
                    'attachments':  json.dumps([js])
                }

            requests.post('https://slack.com/api/chat.postMessage', data=data)
            self.pending.clear()

        return 'spin', data, 1.0

    def specialized(self, msg):

        if 'line' in msg:

            #
            # - buffer
            # - push back if > 100
            #
            self.pending.append(msg['line'])
            return len(self.pending) < 100

        else:
            super(_Accumulator, self).specialized(msg)

class _Handler(object):

    accumulator = _Accumulator.start()

    def on_post(self, req, resp):
        body = req.stream.read()
        if not body:
            raise falcon.HTTPError('no content', code=400)

        #
        # - forward to the actor
        # - reject on a HTTP 304 if the internal buffer is full
        #
        if not self.accumulator.ask({'line': body.decode('utf-8')}):
            raise falcon.HTTPError('buffer at capacity', code='304')


endpoint.add_route('/', _Handler())
