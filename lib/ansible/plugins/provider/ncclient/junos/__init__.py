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

from ansible.module_utils.six import iteritems, string_types
from ansible.plugins.provider.ncclient import NcclientBase

from ncclient.xml_ import to_ele, to_xml
from ncclient.xml_ import new_ele, sub_ele

ACTIONS = frozenset(['merge', 'override', 'replace', 'update', 'set'])
JSON_ACTIONS = frozenset(['merge', 'override', 'update'])
FORMATS = frozenset(['xml', 'text', 'json'])
CONFIG_FORMATS = frozenset(['xml', 'text', 'json', 'set'])

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class Ncclient(NcclientBase):

    def load_config(self, config):
        """Load the config into the remote device
        """
        diff = None
        try:
            self.lock_configuration()

            reply = self.load_configuration(config)

            self._connection.validate()

            reply = self.get_configuration(compare=True, config_format='text')
            output = reply.find('.//configuration-output')
            diff = str(output.text).strip()

            if diff:
                if not self.check_mode:
                    self.commit_configuration()
                else:
                    self._connection.discard_changes()

        finally:
            self.unlock_configuration()

        return diff

    def _validate_rollback_id(self, value):
        try:
            if not 0 <= int(value) <= 49:
                raise ValueError
        except ValueError:
            raise AnsibleError('rollback must be between 0 and 49')

    def load_configuration(self, candidate=None, action='merge', rollback=None, config_format='xml'):

        if all((candidate is None, rollback is None)):
            raise AnsibleError('one of candidate or rollback must be specified')

        elif all((candidate is not None, rollback is not None)):
            raise AnsibleError('candidate and rollback are mutually exclusive')

        if config_format not in FORMATS:
            raise AnsibleError('invalid format specified')

        if config_format == 'json' and action not in JSON_ACTIONS:
            raise AnsibleError('invalid action for format json')
        elif config_format in ('text', 'xml') and action not in ACTIONS:
            raise AnsibleError('invalid action format %s' % config_format)
        if action == 'set' and not config_format == 'text':
            raise AnsibleError('format must be text when action is set')

        if rollback is not None:
            self._validate_rollback_id(rollback)
            xattrs = {'rollback': str(rollback)}
        else:
            xattrs = {'action': action, 'format': config_format}

        obj = new_ele('load-configuration', xattrs)

        if candidate is not None:
            lookup = {'xml': 'configuration', 'text': 'configuration-text',
                    'set': 'configuration-set', 'json': 'configuration-json'}

            if action == 'set':
                cfg = sub_ele(obj, 'configuration-set')
            else:
                cfg = sub_ele(obj, lookup[config_format])

            if isinstance(candidate, string_types):
                cfg.text = candidate
            else:
                cfg.append(candidate)

        return self.send_request(obj)

    def get_configuration(self, compare=False, config_format='xml', rollback='0'):
        if config_format not in CONFIG_FORMATS:
            raise AnsibleError('invalid config format specified')
        xattrs = {'format': config_format}
        if compare:
            self._validate_rollback_id(rollback)
            xattrs['compare'] = 'rollback'
            xattrs['rollback'] = str(rollback)
        return self.send_request(new_ele('get-configuration', xattrs))

    def commit_configuration(self, confirm=False, check=False, comment=None, confirm_timeout=None):
        obj = new_ele('commit-configuration')
        if confirm:
            sub_ele(obj, 'confirmed')
        if check:
            sub_ele(obj, 'check')
        if comment:
            subele = sub_ele(obj, 'log')
            subele.text = str(comment)
        if confirm_timeout:
            subele = sub_ele(obj, 'confirm-timeout')
            subele.text = int(confirm_timeout)
        return self.send_request(obj)

    def command(self, command, config_format='text', rpc_only=False):
        xattrs = {'format': config_format}
        if rpc_only:
            command += ' | display xml rpc'
            xattrs['format'] = 'text'
        return self.send_request(new_ele('command', xattrs, text=command))

    lock_configuration = lambda self: self.send_request(new_ele('lock-configuration'))
    unlock_configuration = lambda self: self.send_request(new_ele('unlock-configuration'))


