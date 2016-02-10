#
#  Copyright (c) 2012-2015 by Autodesk, Inc.
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
import logging
import time

from ochopod.bindings.generic.marathon import Pod
from ochopod.core.tools import Shell
from ochopod.models.piped import Actor as Piped

logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    class Strategy(Piped):

        cwd = '/opt/redis-2.8.17'

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
                    'uptime': '%.2f hours (pid %s)' % (lapse, pid)
                }

        def configure(self, _):

            return '/usr/local/bin/redis-server redis-server.conf', {}

    Pod().boot(Strategy, tools=[Shell])