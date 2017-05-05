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

from ansible.plugins.cliconf.eos import NetworkModule as _NetworkModule
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(_NetworkModule):

    def run(self, module_params):
        """Implements module net_user
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


        return commands

    @memoize
    def instances(self):
        """Load instances from the remote device
        """
        rc, out, err = self.connection.exec_command('show running-config section username')
        data = str(out).strip()

        match = re.findall(r'^username (\S+)', data, re.M)
        if not match:
            return list()

        instances = list()

        for item in set(match):
            config = re.findall(r'username %s .+$' % item, data, re.M)
            config = '\n'.join(config)
            instances.append({
                'username': item,
                'state': 'present',
                'password': None,
                'sshkey': self.parse_sshkey(config),
            })

        return instances


