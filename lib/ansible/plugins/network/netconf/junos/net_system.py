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

from xml.etree.ElementTree import Element, SubElement
from xml.etree.ElementTree import tostring

from ansible.plugins.network.netconf.junos import NetworkModule as _NetworkModule
from ansible.module_utils.six import iteritems

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(_NetworkModule):

    def run(self, module_params):
        """Implements module net_system
        """
        element = Element('system')
        for key, value in iteritems(module_params):
            if value is not None:
                self.invoke('set_%s' % key, element, value)

        result = {'changed': False}

        diff = self.load_config(element)

        if diff:
            result['changed'] = True
            if self._diff:
                result['diff'] = {'prepared': diff}

        return result

    def set_hostname(self, element, value):
        subele = SubElement(element, 'host-name')
        subele.text = value

    def set_domain_name(self, element, value):
        subele = SubElement(element, 'domain-name')
        subele.text = value

    def set_name_servers(self, element, values):
        for item in values:
            subele = SubElement(element, 'name-server')
            subele.text = item

    def set_domain_search(self, element, values):
        for item in values:
            subele = SubElement(element, 'domain-search')
            subele.text = item
