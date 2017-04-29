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

from xml.etree.ElementTree import Element, SubElement
from xml.etree.ElementTree import tostring, fromstring

from ansible.plugins.network import NetworkBase
from ansible.module_utils.six import iteritems

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(NetworkBase):

    def load_config(self, config):
        """Load the config into the remote device
        """
        diff = None
        try:
            self._connection.lock_configuration()

            reply = self._connection.load_configuration(config)

            self._connection.validate()

            reply = self._connection.get_configuration(compare=True, config_format='text')
            output = fromstring(reply).find('.//configuration-output')
            diff = str(output.text).strip()

            if not self._check_mode:
                self._connection.commit_configuration()
            else:
                self._connection.discard_changes()

        finally:
            self._connection.unlock_configuration()

        return diff

