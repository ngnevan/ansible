#
# (c) 2016 Red Hat Inc.
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
import logging
import traceback
import datetime

from xml.etree.ElementTree import tostring, fromstring

from ansible import constants as C
from ansible.plugins import PluginLoader
from ansible.plugins.provider import ProviderBase
from ansible.errors import AnsibleConnectionFailure, AnsibleError

try:
    from ncclient import manager
    from ncclient.operations import RPCError
    from ncclient.transport.errors import SSHUnknownHostError
    from ncclient.xml_ import to_ele, to_xml
except ImportError:
    raise AnsibleError("ncclient is not installed")

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

logging.getLogger('ncclient').setLevel(logging.INFO)


package = lambda name: 'ansible.plugins.provider.ncclient.%s' % name


class Provider(ProviderBase):

    provider = 'ncclient'
    package = property(lambda self: package(self._play_context.network_os))

    @staticmethod
    def play_context_overrides(play_context):
        context = copy.deepcopy(play_context)
        context.remote_user = play_context.connection_user
        context.port = play_context.port or 830
        return context

    def create_connection(self):
        display.display('ssh connection done, stating ncclient', log_only=True)
        display.display('  network_os is %s' % self._play_context.network_os, log_only=True)

        allow_agent = True
        if self._play_context.password is not None:
            allow_agent = False

        key_filename = None
        if self._play_context.private_key_file:
            key_filename = os.path.expanduser(self._play_context.private_key_file)

        if not self._play_context.network_os:
            raise AnsibleConnectionFailure('network_os must be set for netconf connections')

        try:
            connection = manager.connect(
                host=self._play_context.remote_addr,
                port=self._play_context.port or 830,
                username=self._play_context.remote_user,
                password=self._play_context.password,
                key_filename=str(key_filename),
                hostkey_verify=C.HOST_KEY_CHECKING,
                look_for_keys=C.PARAMIKO_LOOK_FOR_KEYS,
                allow_agent=allow_agent,
                timeout=self._play_context.timeout,
                device_params={'name': self._play_context.network_os}
            )
        except SSHUnknownHostError as exc:
            raise AnsibleConnectionFailure(str(exc))

        display.display('ncclient manager object created successfully', log_only=True)

        return connection
