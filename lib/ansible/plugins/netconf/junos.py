#
# (c) 2017 Red Hat, Inc.
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
from xml.etree.ElementTree import Element, SubElement
from xml.etree.ElementTree import tostring, fromstring

from ansible.module_utils.six import string_types
from ansible.plugins.netconf import NetconfBase
from ansible.errors import AnsibleRpcError

ACTIONS = frozenset(['merge', 'override', 'replace', 'update', 'set'])
JSON_ACTIONS = frozenset(['merge', 'override', 'update'])
FORMATS = frozenset(['xml', 'text', 'json'])
CONFIG_FORMATS = frozenset(['xml', 'text', 'json', 'set'])

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class Netconf(NetconfBase):

    network_os = 'junos'

    def _validate_rollback_id(self, value):
        try:
            if not 0 <= int(value) <= 49:
                raise ValueError
        except ValueError:
            raise AnsibleRpcError('rollback must be between 0 and 49')

    def load_configuration(self, candidate=None, action='merge', rollback=None, config_format='xml'):

        if all((candidate is None, rollback is None)):
            raise AnsibleRpcError('one of candidate or rollback must be specified')

        elif all((candidate is not None, rollback is not None)):
            raise AnsibleRpcError('candidate and rollback are mutually exclusive')

        if config_format not in FORMATS:
            raise AnsibleRpcError('invalid format specified')

        if config_format == 'json' and action not in JSON_ACTIONS:
            raise AnsibleRpcError('invalid action for format json')
        elif config_format in ('text', 'xml') and action not in ACTIONS:
            raise AnsibleRpcError('invalid action format %s' % config_format)
        if action == 'set' and not config_format == 'text':
            raise AnsibleRpcError('format must be text when action is set')

        if rollback is not None:
            self._validate_rollback_id(rollback)
            xattrs = {'rollback': str(rollback)}
        else:
            xattrs = {'action': action, 'format': config_format}

        obj = Element('load-configuration', xattrs)

        if candidate is not None:
            lookup = {'xml': 'configuration', 'text': 'configuration-text',
                    'set': 'configuration-set', 'json': 'configuration-json'}

            if action == 'set':
                cfg = SubElement(obj, 'configuration-set')
            else:
                cfg = SubElement(obj, lookup[config_format])

            if isinstance(candidate, string_types):
                cfg.text = candidate
            else:
                cfg.append(candidate)

        return self.send_request(obj)

    def get_configuration(self, compare=False, config_format='xml', rollback='0'):
        if config_format not in CONFIG_FORMATS:
            raise AnsibleRpcError('invalid config format specified')
        xattrs = {'format': config_format}
        if compare:
            self._validate_rollback_id(rollback)
            xattrs['compare'] = 'rollback'
            xattrs['rollback'] = str(rollback)
        return self.send_request(Element('get-configuration', xattrs))

    def commit_configuration(self, confirm=False, check=False, comment=None, confirm_timeout=None):
        obj = Element('commit-configuration')
        if confirm:
            SubElement(obj, 'confirmed')
        if check:
            SubElement(obj, 'check')
        if comment:
            subele = SubElement(obj, 'log')
            subele.text = str(comment)
        if confirm_timeout:
            subele = SubElement(obj, 'confirm-timeout')
            subele.text = int(confirm_timeout)
        return self.send_request(obj)

    def command(self, command, config_format='text', rpc_only=False):
        xattrs = {'format': config_format}
        if rpc_only:
            command += ' | display xml rpc'
            xattrs['format'] = 'text'
        return self.send_request(Element('command', xattrs, text=command))

    lock_configuration = lambda self: self.send_request(Element('lock-configuration'))
    unlock_configuration = lambda self: self.send_request(Element('unlock-configuration'))


