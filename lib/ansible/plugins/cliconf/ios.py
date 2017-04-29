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

from itertools import chain

from ansible.plugins.cliconf import CliconfBase, enable_mode
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.network_common import to_list


class Cliconf(CliconfBase):

    network_os = 'ios'

    terminal_stdout_re = [
        re.compile(r"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$"),
        re.compile(r"\[\w+\@[\w\-\.]+(?: [^\]])\] ?[>#\$] ?$")
    ]

    terminal_stderr_re = [
        re.compile(r"% ?Error"),
        re.compile(r"% ?Bad secret"),
        re.compile(r"invalid input", re.I),
        re.compile(r"(?:incomplete|ambiguous) command", re.I),
        re.compile(r"connection timed out", re.I),
        re.compile(r"[^\r\n]+ not found", re.I),
        re.compile(r"'[^']' +returned error code: ?\d+"),
    ]

    def _on_open_session(self):
        try:
            for cmd in ['terminal length 0', 'terminal width 512']:
                self._exec_cli_command(cmd)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def _on_authorize(self, passwd=None):
        if self._get_prompt().endswith('#'):
            return

        cmd = {'command': 'enable'}
        if passwd:
            cmd['prompt'] = r"[\r\n]?password: $"
            cmd['answer'] = passwd

        try:
            self._exec_cli_command(json.dumps(cmd))
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to elevate privilege to enable mode')

    @enable_mode
    def edit_config(self, commands):
        diff = {}

        if self._diff:
            diff['before'] = self.get_config(source='running')

        if not self._play_context.check_mode:
            for command in chain(['configure'], to_list(commands), ['end']):
                self.send_command(command)

        if diff:
            diff['after'] = self.get_config(source='running')

        return diff

    @memoize
    @enable_mode
    def get_config(self, source='running'):
        lookup = {'running': 'running-config', 'startup': 'startup-config'}
        output = self.send_command('show %s' % lookup[source])
        return str(output).strip()
