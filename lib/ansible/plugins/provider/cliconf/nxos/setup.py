#!/usr/bin/python
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
import json

from ansible.plugins.provider.base import ProviderModuleBase
from ansible.plugins.provider.cliconf.nxos import Cliconf
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class FactsBase(object):

    def __init__(self, provider):
        self._provider = provider
        self.facts = {}
        self.warnings = []

    def populate(self):
        pass

    def run(self, command, output=None):

        if output == 'json' and '| json' not in command:
            command += ' | json'
        elif output == 'text' and '| json' in command:
            command = command.split('|')[0]

        resp = self._provider.send_command(command)

        try:
            if resp and output == 'json':
                resp = json.loads(resp)
            return resp
        except (TypeError, ValueError):
            self.warnings.append('unable to load json output for %s' % command)
        except IndexError:
            self.warnings.append('command %s failed, facts will not be populated' % command)

    def transform_dict(self, data, keymap):
        transform = {}
        for key, fact in keymap:
            if key in data:
                transform[fact] = data[key]
        return transform

    def transform_iterable(self, iterable, keymap):
        transform = list()
        for item in to_list(iterable):
            facts.append(self.transform_dict(item, keymap))
        return transform


class Default(FactsBase):

    VERSION_MAP = frozenset([
        ('sys_ver_str', 'version'),
        ('proc_board_id', 'serialnum'),
        ('chassis_id', 'model'),
        ('isan_file_name', 'image'),
        ('host_name', 'hostname')
    ])

    def populate(self):
        data = self.run('show version', 'json')
        if data:
            self.facts.update(self.transform_dict(data, self.VERSION_MAP))


class Hardware(FactsBase):

    def populate(self):
        cmd = {'command': 'dir', 'output': 'text'},
        data = self.run('dir', 'text')
        if data:
            self.facts['filesystems'] = self.parse_filesystems(data)

        data = self.run('show system resources', 'json')
        if data:
            self.facts['memtotal_mb'] = int(data['memory_usage_total']) / 1024
            self.facts['memfree_mb'] = int(data['memory_usage_free']) / 1024

    def parse_filesystems(self, data):
        return re.findall(r'^Usage for (\S+)//', data, re.M)


class Interfaces(FactsBase):

    INTERFACE_MAP = frozenset([
        ('state', 'state'),
        ('desc', 'description'),
        ('eth_bw', 'bandwidth'),
        ('eth_duplex', 'duplex'),
        ('eth_speed', 'speed'),
        ('eth_mode', 'mode'),
        ('eth_hw_addr', 'macaddress'),
        ('eth_mtu', 'mtu'),
        ('eth_hw_desc', 'type')
    ])

    INTERFACE_IPV4_MAP = frozenset([
        ('eth_ip_addr', 'address'),
        ('eth_ip_mask', 'masklen')
    ])

    INTERFACE_IPV6_MAP = frozenset([
        ('addr', 'address'),
        ('prefix', 'subnet')
    ])

    def populate(self):
        self.facts['all_ipv4_addresses'] = list()
        self.facts['all_ipv6_addresses'] = list()

        data = self.run('show interface', 'json')
        if data:
            self.facts['interfaces'] = self.populate_interfaces(data)

        data = self.run('show ipv6 interface', 'json')
        if data:
            self.parse_ipv6_interfaces(data)

        data = self.run('show lldp neighbors')
        if data:
            self.facts['neighbors'] = self.populate_neighbors(data)

    def populate_interfaces(self, data):
        interfaces = dict()
        for item in data['TABLE_interface']['ROW_interface']:
            name = item['interface']

            intf = dict()
            intf.update(self.transform_dict(item, self.INTERFACE_MAP))

            if 'eth_ip_addr' in item:
                intf['ipv4'] = self.transform_dict(item, self.INTERFACE_IPV4_MAP)
                self.facts['all_ipv4_addresses'].append(item['eth_ip_addr'])

            interfaces[name] = intf

        return interfaces

    def populate_neighbors(self, data):
        objects = dict()
        if isinstance(data, str):
            # if there are no neighbors the show command returns
            # ERROR: No neighbour information
            if data.startswith('ERROR'):
                return dict()

            lines = data.split('\n')
            regex = re.compile('(\S+)\s+(\S+)\s+\d+\s+\w+\s+(\S+)')

            for item in data.split('\n')[4:-1]:
                match = regex.match(item)
                if match:
                    nbor = {'host': match.group(1), 'port': match.group(3)}
                    if match.group(2) not in objects:
                        objects[match.group(2)] = []
                    objects[match.group(2)].append(nbor)

        elif isinstance(data, dict):
            data = data['TABLE_nbor']['ROW_nbor']
            for item in to_list(data):
                local_intf = item['l_port_id']
                if local_intf not in objects:
                    objects[local_intf] = list()
                nbor = dict()
                nbor['port'] = item['port_id']
                nbor['host'] = item['chassis_id']
                objects[local_intf].append(nbor)

        return objects

    def parse_ipv6_interfaces(self, data):
        data = data['TABLE_intf']
        for item in to_list(data):
            name = item['ROW_intf']['intf-name']
            intf = self.facts['interfaces'][name]
            intf['ipv6'] = self.transform_dict(item, self.INTERFACE_IPV6_MAP)
            self.facts['all_ipv6_addresses'].append(item['ROW_intf']['addr'])


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    interfaces=Interfaces,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())

class ProviderModule(ProviderModuleBase, Cliconf):

    def run(self, module_params):
        """Implements the setup module (fact gathering)
        """
        gather_subset = module_params['gather_subset']

        runable_subsets = set()
        exclude_subsets = set()

        for subset in gather_subset:
            if subset == 'all':
                runable_subsets.update(VALID_SUBSETS)
                continue

            if subset.startswith('!'):
                subset = subset[1:]
                if subset == 'all':
                    exclude_subsets.update(VALID_SUBSETS)
                    continue
                exclude = True
            else:
                exclude = False

            if subset not in VALID_SUBSETS:
                raise AnsibleError('Bad subset')

            if exclude:
                exclude_subsets.add(subset)
            else:
                runable_subsets.add(subset)

        if not runable_subsets:
            runable_subsets.update(VALID_SUBSETS)

        runable_subsets.difference_update(exclude_subsets)
        runable_subsets.add('default')

        facts = dict()
        facts['gather_subset'] = list(runable_subsets)

        instances = list()
        for key in runable_subsets:
            instances.append(FACT_SUBSETS[key](self))

        warnings = list()

        for inst in instances:
            inst.populate()
            facts.update(inst.facts)
            warnings.extend(inst.warnings)

        ansible_facts = dict()
        for key, value in iteritems(facts):
            key = 'ansible_%s' % key
            ansible_facts[key] = value

        return {'ansible_facts': ansible_facts, 'warnings': warnings}



