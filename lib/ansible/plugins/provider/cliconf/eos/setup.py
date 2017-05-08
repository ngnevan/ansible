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
from ansible.plugins.provider.cliconf.eos import Cliconf
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

        if '| json' in command:
            output = 'json'

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

    VERSION_MAP = frozenset((
        ('version', 'version'),
        ('serialNumber', 'serialnum'),
        ('modelName', 'model')
    ))

    COMMANDS = [
        'show version | json',
        'show hostname | json',
        'bash timeout 5 cat /mnt/flash/boot-config'
    ]

    def populate(self):
        responses = [self.run(cmd) for cmd in self.COMMANDS]
        self.facts.update(self.transform_dict(responses[0], self.VERSION_MAP))
        self.facts.update(responses[1])
        self.facts.update(self.parse_image(responses[2]))

    def parse_image(self, data):
        if isinstance(data, dict):
            data = data['messages'][0]
        match = re.search(r'SWI=(.+)$', data, re.M)
        if match:
            value = match.group(1)
        else:
            value = None
        return dict(image=value)

class Hardware(FactsBase):

    def populate(self):
        self.facts.update(self.populate_filesystems())
        self.facts.update(self.populate_memory())

    def populate_filesystems(self):
        data = self.run('dir all-filesystems')
        fs = re.findall(r'^Directory of (.+)/', data, re.M)
        return {'filesystems': fs}

    def populate_memory(self):
        values = self.run('show version | json')
        return {
            'memfree_mb': int(values['memFree']) / 1024,
            'memtotal_mb': int(values['memTotal']) / 1024
        }


class Interfaces(FactsBase):

    INTERFACE_MAP = frozenset((
        ('description', 'description'),
        ('physicalAddress', 'macaddress'),
        ('mtu', 'mtu'),
        ('bandwidth', 'bandwidth'),
        ('duplex', 'duplex'),
        ('lineProtocolStatus', 'lineprotocol'),
        ('interfaceStatus', 'operstatus'),
        ('forwardingModel', 'type')
    ))

    COMMANDS = [
        'show interfaces | json',
        'show lldp neighbors | json'
    ]

    def populate(self):
        responses = [self.run(cmd) for cmd in self.COMMANDS]

        self.facts['all_ipv4_addresses'] = list()
        self.facts['all_ipv6_addresses'] = list()

        data = responses[0]
        self.facts['interfaces'] = self.populate_interfaces(data)

        data = responses[1]
        self.facts['neighbors'] = self.populate_neighbors(data['lldpNeighbors'])

    def populate_interfaces(self, data):
        facts = dict()
        for key, value in iteritems(data['interfaces']):
            intf = dict()

            for remote, local in iteritems(dict(self.INTERFACE_MAP)):
                if remote in value:
                    intf[local] = value[remote]

            if 'interfaceAddress' in value:
                intf['ipv4'] = dict()
                for entry in value['interfaceAddress']:
                    intf['ipv4']['address'] = entry['primaryIp']['address']
                    intf['ipv4']['masklen'] = entry['primaryIp']['maskLen']
                    self.add_ip_address(entry['primaryIp']['address'], 'ipv4')

            if 'interfaceAddressIp6' in value:
                intf['ipv6'] = dict()
                for entry in value['interfaceAddressIp6']['globalUnicastIp6s']:
                    intf['ipv6']['address'] = entry['address']
                    intf['ipv6']['subnet'] = entry['subnet']
                    self.add_ip_address(entry['address'], 'ipv6')

            facts[key] = intf

        return facts

    def add_ip_address(self, address, family):
        if family == 'ipv4':
            self.facts['all_ipv4_addresses'].append(address)
        else:
            self.facts['all_ipv6_addresses'].append(address)

    def populate_neighbors(self, neighbors):
        facts = dict()
        for value in neighbors:
            port = value['port']
            if port not in facts:
                facts[port] = list()
            lldp = dict()
            lldp['host'] = value['neighborDevice']
            lldp['port'] = value['neighborPort']
            facts[port].append(lldp)
        return facts


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    interfaces=Interfaces
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
