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

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = """
"""

EXAMPLES = """
"""

RETURN = """
"""
import copy

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import execute_module
from ansible.module_utils.network_common import EntityCollection, to_list
from ansible.module_utils.pycompat24 import get_exception


def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        username=dict(),
        collection=dict(type='list'),

        password=dict(no_log=True),
        update_password=dict(default='always', choices=['on_create', 'always']),
        sshkey=dict(),

        state=dict(default='present', choices=['present', 'absent']),

        purge=dict(type='bool', default=False),
    )


    mutually_exclusive = [('username', 'collection')]

    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    if module._socket_path is None:
        module.fail_json(msg='modules requires a provider')

    args = frozenset(['username', 'password', 'update_password', 'sshkey', 'state'])
    keys = frozenset(['username'])

    collection = copy.deepcopy(module.params['collection']) or to_list(module.params)

    try:
        spec = EntityCollection(module, args=args, keys=keys, from_argspec=True)
        module_params = {
            'collection': spec(collection),
            'purge': module.params['purge']
        }

    except ValueError:
        exc = get_exception()
        module.fail_json(msg=str(exc))

    result = execute_module(module, module_params)
    module.exit_json(**result)

if __name__ == '__main__':
    main()
