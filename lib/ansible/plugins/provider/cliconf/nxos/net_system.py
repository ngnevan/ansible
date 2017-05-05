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

from ansible.plugins.provider.base import ProviderModuleBase
from ansible.plugins.provider.cliconf.nxos import Cliconf
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ProviderModule(ProviderModuleBase, Cliconf):

    def run(self, module_params):
        """Implements the net_system module
        """
        config = self.get_config()

        instance = {
            'hostname': self.parse_hostname(config, module_params),
            'domain_name': self.parse_domain_name(config, module_params),
            'domain_search': re.findall('^ip domain-list (\S+)', config, re.M),
            'name_servers': self.parse_name_servers(config, module_params)
        }

        diff = self.diff_dict(instance, module_params)

        commands = list()
        for key, value in iteritems(diff):
            method = getattr(self, 'set_%s' % key, None)
            if method:
                updates = method(value, module_params, instance)
                commands.extend(to_list(updates))

        result = {'changed': False}

        if commands:
            diff = self.edit_config(commands)
            if self.diff:
                result['diff'] = diff
            result['changed'] = True

        return result

    def parse_hostname(self, config, module_params):
        match = re.search('^hostname (\S+)', config, re.M)
        if match:
            return match.group(1)

    def parse_domain_name(self, config, module_params):
        match = re.search('^ip domain-name (\S+)', config, re.M)
        if match:
            return match.group(1)

    def parse_lookup_source(self, config, module_params):
        objects = list()
        regex = 'ip domain lookup (?:vrf (\S+) )*source-interface (\S+)'
        for vrf, intf in re.findall(regex, config, re.M):
            if len(vrf) == 0:
                vrf= None
            objects.append({'interface': intf, 'vrf': vrf})
        return objects

    def parse_name_servers(self, config, module_params):
        objects = list()
        match = re.search('^ip name-server (.+)$', config, re.M)
        if match:
            for item in match.group(1).split(' '):
                objects.append(item)
        return objects

    def set_hostname(self, value, item, instance):
        return 'hostname %s' % value

    def set_domain_name(self, value, item, instance):
        return 'ip domain-name %s' % value

    def set_domain_search(self, value, item, instance):
        current, desired = item['current']['domain_search'], item['desired']['domain_search']
        for item, op in diff_list(current, desired):
            adds = list()
            removes = list()
            if op == 'remove':
                removes.append('no ip domain-list %s' % item)
            elif op == 'add':
                adds.append('ip domain-list %s' % item)
        return removes + adds

    def set_name_servers(self, value, item, instance):
        adds = list()
        removes = list()
        for item, op in self.diff_list(instance['name_servers'], value):
            if op == 'remove':
                removes.append('no ip name-server %s' % item)
            elif op == 'add':
                adds.append('ip name-server %s' % item)
        return removes + adds
