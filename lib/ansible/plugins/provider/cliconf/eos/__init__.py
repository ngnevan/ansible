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

from ansible.plugins.provider.cliconf import CliconfBase
from ansible.plugins.provider.cliconf import enable_mode

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class Cliconf(CliconfBase):

    @enable_mode
    def edit_config(self, commands):
        diff = {}

        if self.diff:
            diff['before'] = self.get_config(source='running')

        if not self.check_mode:
            for command in chain(['configure'], to_list(commands), ['end']):
                self.send_command(command)

        if diff:
            diff['after'] = self.get_config(source='running')

        return diff

    @enable_mode
    def get_config(self, source='running'):
        lookup = {'running': 'running-config', 'startup': 'startup-config'}
        output = self.send_command('show %s' % lookup[source])
        return str(output).strip()

