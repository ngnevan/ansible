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

from functools import partial

from ansible.plugins.provider.base import ProviderModuleBase
from ansible.plugins.provider.cliconf.nxos import Cliconf
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list



class ProviderModule(ProviderModuleBase, Cliconf):

    USER_MAP = frozenset((
        ('username', 'usr_name', None),
        ('sshkey', 'sshkey_info', None),
        ('update_password', None, None),
        ('password', None, None),
        ('state', None, 'present')
    ))

    def run(self, module_params):
        """Implements the net_user module
        """
        output = self.send_command('show user-account | json')

        try:
            data = self.from_json(output)
            values = to_list(data['TABLE_template']['ROW_template'])
        except (ValueError, TypeError, KeyError):
            return self.fail_json(msg='unable to parse command output')

        instances = self.transform_list(values, self.USER_MAP, values)
        updates = dict()

        for entry in module_params['collection']:
            for index, item in enumerate(instances):
                if item['username'] == entry['username']:
                    # match found, do the diff and add to updates; be sure to
                    # include the matched field which will never return from
                    # the diff function
                    del instances[index]
                    diff = self.diff_params(item, entry)
                    obj = {'want': entry, 'have': item, 'diff': diff}
                    updates[entry['username']] = obj
                    break
            else:
                # there wasn't a match in the current instances so this is
                # a new item therefore just add the whole item
                updates[entry['username']] = {'want': entry, 'have': {}, 'diff': entry}

        commands = list()

        # iterate over the updates dict and call the attribute setters
        for user, attrs in iteritems(updates):
            for key, value in iteritems(attrs.get('diff')):
                method = getattr(self, 'set_%s' % key, None)
                if method and value is not None:
                    method(user, attrs, commands)

        # purge instances that are currently configured
        if module_params['purge']:
            for item in instances:
                self.purge(item, commands)

        result = {'changed': False}

        # load the commands into the device
        if commands:
            diff = self.edit_config(commands)
            if self.diff:
                result['diff'] = diff
            result['changed'] = True

        return result

    def purge(self, item, commands):
        commands.append('no username %s' % item['username'])

    add = lambda self, user, value: 'username %s %s' % (user, value)

    def set_state(self, user, attrs, commands):
        if attrs['want']['state'] == 'absent':
            return self.purge(attrs['want'], commands)

    def set_sshkey(self, user, attrs, commands):
        value = 'sshkey %s' % attrs['want']['sshkey']
        commands.append(self.add(user, value))

    def set_password(self, user, attrs, commands):
        value = 'password %s' % attrs['want']['password']
        command_string = self.add(user, value)
        if command_string not in commands:
            commands.append(command_string)

    def set_update_password(self, user, attrs, commands):
        if attrs['want']['update_password'] == 'always':
            return self.set_password(user, attrs, commands)
