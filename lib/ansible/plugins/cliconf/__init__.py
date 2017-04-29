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

import re
import time

from functools import wraps

from abc import ABCMeta, abstractmethod

from ansible.plugins import PluginLoader
from ansible.errors import AnsibleError, AnsibleConnectionFailure
from ansible.module_utils.six import with_metaclass

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


def enable_mode(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        prompt = self.get_prompt()
        if not str(prompt).strip().endswith('#'):
            raise AnsibleError('operation requires privilege escalation')
        return func(self, *args, **kwargs)
    return wrapped

def memoize(obj):
    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer

class CliconfBase(with_metaclass(ABCMeta, object)):
    """Base class for implement Cliconf protocol on network devices
    """

    # compiled regular expression as stdout
    terminal_stdout_re = []

    # compiled regular expression as stderr
    terminal_stderr_re = []

    # compiled regular expression to remove ANSI codes
    ansi_re = [
        re.compile(r'(\x1b\[\?1h\x1b=)'),
        re.compile(r'\x08.')
    ]

    def __init__(self, connection):
        self._connection = connection

        self.loader = PluginLoader(
            'NetworkModule',
            'ansible.plugins.network.cliconf.%s' % self.network_os,
            'network_plugins',
            'network_plugins'
        )

    def execute_module(self, module_name, module_params):
        start_time = time.time()

        if module_name not in self.loader:
            msg = "network_os '%s' does not support module '%s'" % (self.network_os, module_name)
            raise AnsibleError(msg)

        check_mode = getattr(self._connection._play_context, 'check_mode', False)
        diff = getattr(self._connection._play_context, 'diff', False)

        module = self.loader.get(module_name, self, check_mode, diff)
        result = module.run(module_params)

        result['elapsed_time'] = float(time.time() - start_time)

        return result

    def _on_open_session(self):
        """Called after the SSH session is established

        This method is called right after invoke_shell() is called from
        the Paramiko SSHClient instance.  It provides an opportunity to setup
        terminal parameters such as disabling paging for instance.
        """
        pass

    def _on_close_session(self):
        """Called before the connection is closed

        This method gets called once the connection close has been requested
        but before the connection is actually closed.  It provides an
        opportunity to clean up any terminal resources before the shell is
        actually closed
        """
        pass

    def _on_authorize(self, passwd=None):
        """Called when privilege escalation is requested

        This method is called when the privilege is requested to be elevated
        in the play context by setting become to True.  It is the responsibility
        of the terminal plugin to actually do the privilege escalation such
        as entering `enable` mode for instance
        """
        pass

    def _on_deauthorize(self):
        """Called when privilege deescalation is requested

        This method is called when the privilege changed from escalated
        (become=True) to non escalated (become=False).  It is the responsibility
        of the this method to actually perform the deauthorization procedure
        """
        pass

    def _on_authorized(self):
        """Called after the CLi session has been authorized

        This method will be called once a command line session has been
        successfully authorized and privilege escalation is complete.
        """
        pass

    def send_command(self, command, prompts=None, answer=None, send_only=False):
        """Send the command to the device and return the output

        This method will send the command to the remote device and return
        the output from the command.
        """
        display.display('cmd: %s' % command, log_only=True)
        return self._connection.send(command, prompts, answer, send_only)

    def get_prompt(self):
        """Returns the last matched prompt

        This method will return the last prompt that was matched by the set
        of compiled regular expressions
        """
        return str(self._connection._matched_prompt).strip()

    @abstractmethod
    def edit_config(self, config):
        """Load the specified configuration into the remote device

        This method will load the configuration specified by the argument
        into the remote device and merge it with the current running
        configuration
        """
        pass

    @abstractmethod
    def get_config(self, source='running'):
        """Retrieve the configuration specified by source

        This method will retrieve the specified configuration from the remote
        device and return it to the caller.
        """
        pass
