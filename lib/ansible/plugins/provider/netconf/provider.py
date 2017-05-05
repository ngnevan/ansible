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

import os
import sys
import copy
import json
import traceback
import datetime

from ansible.plugins import connection_loader, PluginLoader
from ansible.plugins.provider import ProviderBase
from ansible.errors import AnsibleConnectionFailure

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

loader = lambda name: PluginLoader(
    'NetworkModule',
    'ansible.plugins.provider.netconf.%s' % name,
    'provider_plugins',
    'provider_plugins'
)


class Provider(ProviderBase):

    @staticmethod
    def play_context_overrides(play_context):
        context = copy.deepcopy(play_context)
        context.connection = 'netconf'
        context.remote_user = play_context.connection_user
        context.port = play_context.port or 830
        return context

    get_loader = lambda self: loader(self._play_context.network_os)


