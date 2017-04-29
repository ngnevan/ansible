#
# (c) 2016 Red Hat Inc.
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
import copy
import functools

from ansible.plugins.network import NetworkBase
from ansible.module_utils.six import iteritems

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(NetworkBase):

    def _match_instances(self, items, instances, key=None):
        matches = set()

        if len(items) == 1 and len(instances) == 1 and not key:
            for key, value in iteritems(instances[0]):
                items[0][key]['current'] = value
            items[0]['diff'] = self.diff_dict(items[0]['current'], instances[0])
            return items

        for index, instance in enumerate(instances):
            for item in items:
                if item['desired'][key] == instance[key]:
                    item['current'].update(instance)
                    item['diff'] = self.diff_dict(item['current'], item['desired'])
                    matches.add(index)

        for index, instance in enumerate(instances):
            if index not in matches:
                items.append({'current': instance, 'desired': None, 'updates': None})

        return items

    def sort(self, val):
        if isinstance(val, list):
            return sorted(val)
        return val

    def diff_dict(self, current, desired, path=None):
        """Diff two module_params structures and return updated keys

        This will diff two dict objects and return a list of objects that
        represent the updates.  The list of updates is in the form of
        (path, key, current_value, desired_value)
        """
        updates = list()
        path = path or list()
        current = current or {}

        for key, value in iteritems(current):
            if key not in desired:
                desired_value = desired.get(key)
                updates.append((key, desired_value))
            else:
                if isinstance(current[key], dict):
                    path.append(key)
                    updates.extend(self.dict_diff(current[key], desired[key], list(path)))
                    path.pop()
                else:
                    desired_value = desired.get(key)
                    if desired_value is not None:
                        if self.sort(current[key]) != self.sort(desired_value):
                            updates.append((key, desired_value))

        return dict(updates)

    def diff_list(self, current, desired):
        objects = list()
        for item in set(current).difference(desired):
            objects.append((item, 'remove'))
        for item in set(desired).difference(current):
            objects.append((item, 'add'))
        return objects


