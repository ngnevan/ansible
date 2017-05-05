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

from ansible.module_utils.six import with_metaclass, iteritems


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


NS_MAP = {'nc': "urn:ietf:params:xml:ns:netconf:base:1.0"}


class NetworkBase(with_metaclass(ABCMeta, object)):

    def __init__(self, connection, check_mode, diff):
        self._connection = connection
        self.check_mode = check_mode
        self.diff = diff

    @abstractmethod
    def run(self, module_params):
        pass

    def invoke(self, name, *args, **kwargs):
        meth = getattr(self, name, None)
        if meth:
            return meth(*args, **kwargs)

    def send_request(self, obj, check_rc=False):
        """Send the XML request to the remote device and return the reply
        """
        reply = self._connection.rpc(obj)

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

