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
    'supported_by': 'core'
}


DOCUMENTATION = """
"""

EXAMPLES = """
"""

RETURN = """
"""
import os
import copy

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import execute_module
from ansible.module_utils.network_common import EntityCollection, to_list
from ansible.module_utils.pycompat24 import get_exception


def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        name=dict(),
        collection=dict(type='list'),

        description=dict(),
        enabled=dict(type='bool'),

        state=dict(default='present', choices=['present', 'absent']),
        oper_status=dict(default='up', choices=['up', 'down']),
        neighbors=dict(type='list'),

        purge=dict(type='bool', default=False),
        hold_time=dict(type='int', default=30)
    )

    mutually_exclusive = [('name', 'collection')]

    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    collection = copy.deepcopy(module.params['collection']) or to_list(module.params['name'])

    args = frozenset(('name', 'description', 'enabled', 'state', 'oper_status'))
    keys = frozenset(('name',))

    try:
        spec = EntityCollection(module, args=args, keys=keys, from_argspec=True)
        module_params = {
            'collection': spec(collection, strict=True),
            'purge': module.params['purge'],
            'hold_time': module.params['hold_time']
        }
    except:
        exc = get_exception()
        module.fail_json(msg=str(exc))

    module.exit_json(params=module_params, spec=spec.serialize())

    result = execute_module(module, module.params)
    module.exit_json(**result)

if __name__ == '__main__':
    main()
