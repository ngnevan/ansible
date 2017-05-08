#
# (c) 2017 Red Hat Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re
import json

from ansible.plugins.cliconf import CliconfBase
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.network_common import to_list


class Cliconf(CliconfBase):

    network_os = 'junos'

    terminal_stdout_re = [
        re.compile(r"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$|%"),
    ]

    terminal_stderr_re = [
        re.compile(r"unknown command"),
        re.compile(r"syntax error,")
    ]

    def _on_open_session(self):
        try:
            prompt = self._get_prompt()
            if prompt.strip().endswith('%'):
                display.vvv('starting cli', self._connection._play_context.remote_addr)
                self._exec_cli_command('cli')
            for c in ['set cli timestamp disable', 'set cli screen-length 0', 'set cli screen-width 1024']:
                self._exec_cli_command(c)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')
