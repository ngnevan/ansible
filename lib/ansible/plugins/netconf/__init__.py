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

import os
import re
import sys
import time
import copy

from abc import ABCMeta, abstractmethod
from xml.etree.ElementTree import Element, SubElement
from xml.etree.ElementTree import fromstring, tostring

from ansible.plugins import PluginLoader
from ansible.module_utils.six import with_metaclass, iteritems
from ansible.utils.path import unfrackpath
from ansible.errors import AnsibleRpcError, AnsibleConnectionFailure

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


NS_MAP = {'nc': "urn:ietf:params:xml:ns:netconf:base:1.0"}


class NetconfBase(with_metaclass(ABCMeta, object)):

    def __init__(self, connection):
        self._connection = connection

        self.loader = PluginLoader(
            'NetworkModule',
            'ansible.plugins.network.netconf.%s' % self.network_os,
            'netconf_plugins',
            'netconf_plugins'
        )

    def execute_module(self, module_name, module_params):
        start_time = time.time()

        if module_name not in self.loader:
            msg = "network_os '%s' does not support module '%s'" % (self.network_os, module_name)
            raise AnsibleRpcError(msg)

        check_mode = getattr(self._connection._play_context, 'check_mode', False)
        diff = getattr(self._connection._play_context, 'diff', False)

        module = self.loader.get(module_name, self, check_mode, diff)
        result = module.run(module_params)

        result['elapsed_time'] = float(time.time() - start_time)

        return result

    def get_client_capabilities(self):
        return list(self._connection._manager.client_capabilities)

    def get_server_capabilities(self):
        return list(self._connection._manager.server_capabilities)

    def get_session_id(self):
        return self._connection._manager.session_id

    def send_request(self, obj, check_rc=False):
        """Send the XML request to the remote device and return the reply
        """
        reply = self._connection.send(obj)

        if check_rc:
            fake_parent = Element('root')
            fake_parent.append(reply)

            error_list = fake_parent.findall('.//nc:rpc-error', NS_MAP)
            if error_list:
                raise AnsibleRpcError(str(err))

            warnings = []
            for rpc_error in error_list:
                message = rpc_error.find('./nc:error-message', NS_MAP).text
                severity = rpc_error.find('./nc:error-severity', NS_MAP).text

                if severity == 'warning':
                    display.display('WARNING: %s' % message, log_only=True)
                else:
                    raise AnsibleRpcError(str(err))
            return warnings

        return tostring(reply)

    def children(self, root, iterable):
        for item in iterable:
            try:
                ele = SubElement(ele, item)
            except NameError:
                ele = SubElement(root, item)

    def lock(self, target='candidate'):
        obj = Element('lock')
        self.children(obj, ('target', target))
        return self.send_request(obj)

    def unlock(self, target='candidate'):
        obj = Element('unlock')
        self.children(obj, ('target', target))
        return self.send_request(obj)

    def commit(self):
        return self.send_request(Element('commit'))

    def discard_changes(self):
        return self.send_request(Element('discard-changes'))

    def validate(self):
        obj = Element('validate')
        self.children(obj, ('source', 'candidate'))
        return self.send_request(obj)

    def get_config(self, source='running', config_filter=None):
        obj = Element('get-config')
        self.children(obj, ('source', source))
        if config_filter:
            self.children(obj, ('filter', config_filter))
        return tostring(self.send_request(obj))
