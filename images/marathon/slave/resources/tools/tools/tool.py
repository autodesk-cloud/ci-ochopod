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

from argparse import ArgumentParser
from logging import DEBUG

logger = logging.getLogger('ochopod')


class Template():
    """
    High-level template defining a CI/CD tool.
    """

    #: Optional short tool description. This is what's displayed when using --help.
    help = ""

    #: Mandatory identifier. The tool will be invoked using "tools <tag>".
    tag = ""

    def run(self, cmdline):

        class _Parser(ArgumentParser):
            def error(self, message):
                logger.error('error: %s\n' % message)
                self.print_help()
                exit(1)

        parser = _Parser(prog=self.tag, description=self.help)
        self.customize(parser)
        parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
        args = parser.parse_args(cmdline)
        if args.debug:
            for handler in logger.handlers:
                handler.setLevel(DEBUG)

        return self.body(args)

    def customize(self, parser):
        pass

    def body(self, args):

        raise NotImplementedError