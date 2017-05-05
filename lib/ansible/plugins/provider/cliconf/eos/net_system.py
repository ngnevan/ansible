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

from ansible.plugins.network.cliconf.eos import NetworkModule as _NetworkModule
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(_NetworkModule):

    def run(self, module_params):
        """ Transform the entity to a set of CLI configuration commands
        """
        config = self._connection.get_config()

        instance = {
            'hostname': self.parse_hostname(config, module_params),
            'domain_name': self.parse_domain_name(config, module_params),
            'domain_search': re.findall('^ip domain-list (\S+)', config, re.M),
            'name_servers': self.parse_name_servers(config, module_params)
        }

        commands = list()

        diff = self.diff_dict(instance, module_params)

        commands = list()
        for key, value in iteritems(diff):
            method = getattr(self, 'set_%s' % key, None)
            if method:
                updates = method(value, module_params, instance)
                commands.extend(to_list(updates))


        result = {'changed': False}

        if commands:
            diff = self.load_config(commands)
            if self._diff:
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

    def parse_name_servers(self, config, module_params):
        objects = list()
        for vrf, addr in re.findall('ip name-server vrf (\S+) (\S+)', config, re.M):
            if vrf == (module_params['vrf'] or 'default'):
                objects.append(addr)
        if not objects:
            return None
        return objects

    def set_hostname(self, value, module_params, instance):
        return 'hostname %s' % value

    def set_domain_name(self, value, module_params, instance):
        return 'ip domain-name %s' % value

    def set_domain_search(self, value, module_params, instance):
        adds = list()
        removes = list()
        for item, op in self.diff_list(instance['domain_search'], value):
            if op == 'remove':
                removes.append('no ip domain-list %s' % item)
            elif op == 'add':
                adds.append('ip domain-list %s' % item)
        return removes + adds

    def set_name_servers(self, value, module_params, instance):
        adds = list()
        removes = list()
        for item, op in self.diff_list(instance['name_servers'], value):
            if op == 'remove':
                removes.append('no ip name-server %s' % item)
            elif op == 'add':
                adds.append('ip name-server %s' % item)
        return removes + adds
