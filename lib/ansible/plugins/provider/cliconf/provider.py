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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import copy

from ansible.plugins import PluginLoader
from ansible.plugins.provider import ProviderBase

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


package = lambda name: 'ansible.plugins.provider.cliconf.%s' % name

class Provider(ProviderBase):

    provider = 'cliconf'
    package = property(lambda self: package(self._play_context.network_os))

    @staticmethod
    def play_context_overrides(play_context):
        context = copy.deepcopy(play_context)
        context.connection = 'network_cli'
        context.remote_user = play_context.connection_user
        context.become = True
        return context

