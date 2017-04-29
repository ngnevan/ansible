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

from ansible.plugins.cliconf import CliconfBase
from ansible.plugins.cliconf import enable_mode
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.network_common import to_list


class Cliconf(CliconfBase):

    network_os = 'eos'

    terminal_stdout_re = [
        re.compile(r"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$"),
        re.compile(r"\[\w+\@[\w\-\.]+(?: [^\]])\] ?[>#\$] ?$")
    ]

    terminal_stderr_re = [
        re.compile(r"% ?Error"),
        re.compile(r"^% \w+", re.M),
        re.compile(r"% User not present"),
        re.compile(r"% ?Bad secret"),
        re.compile(r"invalid input", re.I),
        re.compile(r"(?:incomplete|ambiguous) command", re.I),
        re.compile(r"connection timed out", re.I),
        re.compile(r"[^\r\n]+ not found", re.I),
        re.compile(r"'[^']' +returned error code: ?\d+"),
        re.compile(r"[^\r\n]\/bin\/(?:ba)?sh")
    ]

    def _on_open_session(self):
        try:
            self.send_command('terminal length 0')
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def _on_authorize(self, passwd=None):
        if self.get_prompt().endswith('#'):
            return

        try:
            prompts = [r"[\r\n]?password: $"]
            self.send_command('enable', prompts=prompts, answer=passwd)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to elevate privilege to enable mode')

    @enable_mode
    def edit_config(self, commands):
        multiline = False

        for command in chain(['configure'], to_list(commands), ['end']):
            if command.startswith('banner') or multiline:
                multiline = True
            elif command == 'EOF' and multiline:
                multiline = False

            self.send_command(command, send_only=multiline)

    @enable_mode
    def get_config(self, source='running'):
        lookup = {'running': 'running-config', 'startup': 'startup-config'}
        output = self.send_command('show %s' % lookup[source])
        return str(output).strip()
