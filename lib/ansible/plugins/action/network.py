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
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import sys
import copy
import json

from ansible.plugins.action.normal import ActionModule as _ActionModule
from ansible.utils.path import unfrackpath
from ansible.errors import AnsibleConnectionFailure

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(_ActionModule):

    def run(self, tmp=None, task_vars=None):
        if self._play_context.connection != 'local':
            return dict(
                failed=True,
                msg='invalid connection specified, expected connection=local, '
                    'got %s' % self._play_context.connection
            )

        context = copy.deepcopy(self._play_context)
        context.remote_user = self._play_context.connection_user
        context.become = True

        if self._play_context.network_api == 'netconf':
            context.connection = 'netconf'
        else:
            context.connection = 'network_cli'

        display.vvv('using connection plugin %s' % context.connection, context.remote_addr)

        socket_path = self._get_socket_path(context)
        display.vvvv('connection socket_path: %s' % socket_path, context.remote_addr)

        if not os.path.exists(socket_path):
            connection = self._shared_loader_obj.connection_loader.get('persistent', context, sys.stdin)

            display.vvv('attempting to start session with remote device', self._play_context.remote_addr)
            request = json.dumps({'jsonrpc': '2.0', 'method': 'connect'})
            rc, out, err = connection.exec_command(request)
            if rc != 0:
                raise AnsibleConnectionFailure('unable to open shell. Please see: https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell')
        else:
            display.vvv('reusing existing session to remote device', self._play_context.remote_addr)

        if not connection:
            raise AnsibleConnectionFailure('unable to establish connection', context.remote_addr)

        task_vars['ansible_socket'] = socket_path

        result = super(ActionModule, self).run(tmp, task_vars)

        if not self._play_context._diff and 'diff' in result:
            del result['diff']

        return result

    def _get_socket_path(self, play_context):
        """Returns the persistent socket path"""
        ssh = self._shared_loader_obj.connection_loader.get('ssh', class_only=True)
        cp = ssh._create_control_path(play_context.remote_addr, play_context.port, play_context.remote_user)
        path = unfrackpath("$HOME/.ansible/pc")
        return cp % dict(directory=path)

