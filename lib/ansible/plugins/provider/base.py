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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from abc import ABCMeta, abstractmethod

from ansible.module_utils.six import with_metaclass, iteritems


class ProviderModuleBase(with_metaclass(ABCMeta, object)):

    def __init__(self, connection, check_mode, diff):
        self._connection = connection
        self.check_mode = check_mode
        self.diff = diff
        self.warnings = []

    @abstractmethod
    def run(self, module_params):
        pass

    def inovke(self, name, *args, **kwargs):
        method = getattr(self, name, None)
        if method:
            return method(*args, **kwargs)

    def warn(self, warning):
        self.warnings.append(warning)

    def fail_json(self, msg):
        return {'failed': True, 'msg': msg}

