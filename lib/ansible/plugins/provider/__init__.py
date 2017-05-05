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

import os
import sys
import json
import socket
import struct
import signal
import traceback
import datetime
import fcntl
import time

from abc import ABCMeta, abstractmethod, abstractproperty
from functools import partial

from ansible import constants as C
from ansible.module_utils._text import to_bytes, to_native
from ansible.utils.path import unfrackpath, makedirs_safe
from ansible.errors import AnsibleConnectionFailure, AnsibleError
from ansible.utils.display import Display
from ansible.plugins import connection_loader
from ansible.module_utils.six import with_metaclass, iteritems
from ansible.plugins import PluginLoader


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


def send_data(s, data):
    packed_len = struct.pack('!Q',len(data))
    return s.sendall(packed_len + data)

def recv_data(s):
    header_len = 8 # size of a packed unsigned long long
    data = b""
    while len(data) < header_len:
        d = s.recv(header_len - len(data))
        if not d:
            return None
        data += d
    data_len = struct.unpack('!Q',data[:header_len])[0]
    data = data[header_len:]
    while len(data) < data_len:
        d = s.recv(data_len - len(data))
        if not d:
            return None
        data += d
    return data

def do_fork():
    '''
    Does the required double fork for a daemon process. Based on
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/
    '''
    try:
        pid = os.fork()
        if pid > 0:
            return pid

        #os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)

            if C.DEFAULT_LOG_PATH != '':
                out_file = file(C.DEFAULT_LOG_PATH, 'a+')
                err_file = file(C.DEFAULT_LOG_PATH, 'a+', 0)
            else:
                out_file = file('/dev/null', 'a+')
                err_file = file('/dev/null', 'a+', 0)

            os.dup2(out_file.fileno(), sys.stdout.fileno())
            os.dup2(err_file.fileno(), sys.stderr.fileno())
            os.close(sys.stdin.fileno())

            return pid
        except OSError as e:
            sys.exit(1)
    except OSError as e:
        sys.exit(1)


plugin_loader = partial(
    PluginLoader,
    class_name='ProviderModule',
    config='provider_plugin',
    subdir='provider_plugin'
)

class ProviderBase(with_metaclass(ABCMeta, object)):

    __rpc__= frozenset(['is_running', 'exec_module', 'exec_command', 'put_file',
                        'fetch_file', 'close'])

    def __init__(self, socket_path, play_context):

        self._running = False

        self._socket_path = socket_path
        self._play_context = play_context

        self._start_time = datetime.datetime.now()
        self._connection = self.create_connection()
        connection_time = datetime.datetime.now() - self._start_time
        display.display('connection established to %s in %s' % (self._play_context.remote_addr, connection_time), log_only=True)

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self._socket_path)
        self.socket.listen(1)

        signal.signal(signal.SIGALRM, self.alarm_handler)

        self._running = True
        display.display('provider is running', log_only=True)

    def package(self):
        pass

    def is_running(self):
        return self._running

    def alarm_handler(self, signum, frame):
        '''
        Alarm handler
        '''
        # hooks the connection plugin to handle any cleanup
        if hasattr(self._connection, 'alarm_handler'):
            self._connection.alarm_handler(signum, frame)
        self.socket.close()
        self._running = False

    @staticmethod
    def play_context_overrides(play_context):
        return play_context

    def create_connection(self):
        display.display(
            'creating new control socket for host %s:%s as user %s' %
            (self._play_context.remote_addr, self._play_context.port, self._play_context.remote_user),
            log_only=True
        )

        display.display("using connection plugin %s" % self._play_context.connection, log_only=True)

        connection = connection_loader.get(self._play_context.connection, self._play_context, sys.stdin)
        connection._connect()

        if not connection.connected:
            raise AnsibleConnectionFailure('unable to connect to remote host %s' % self._play_context.remote_addr)

        return connection

    def exec_module(self, module_name, module_params):
        check_mode = self._play_context.check_mode
        diff = self._play_context.diff


        loader = plugin_loader(package=self.package)
        display.display('plugin loader package is %s' % loader.package, log_only=True)

        if not loader:
            raise AnsibleError("provider does not support '%s'" % module_name)

        module = loader.get(module_name, self._connection, check_mode, diff)

        if not module:
            raise AnsibleError('unable to load provider module')

        result = module.run(module_params)

        if module.warnings:
            result['warnings'] = module.warnings

        return result

    @classmethod
    def start(cls, play_context):
        play_context = cls.play_context_overrides(play_context)

        # create the persistent connection dir if need be and create the paths
        # which we will be using later
        tmp_path = unfrackpath("$HOME/.ansible/pc")
        makedirs_safe(tmp_path)
        lk_path = unfrackpath("%s/.ansible_pc_lock" % tmp_path)

        ssh = connection_loader.get('ssh', class_only=True)
        cp = ssh._create_control_path(play_context.remote_addr, play_context.port, play_context.connection_user)
        socket_path = unfrackpath(cp % dict(directory=tmp_path))
        display.vvvv('connection socket_path is %s' % socket_path, play_context.remote_addr)

        lock_fd = os.open(lk_path, os.O_RDWR|os.O_CREAT, 0o600)
        fcntl.lockf(lock_fd, fcntl.LOCK_EX)

        if not os.path.exists(socket_path):
            pid = do_fork()
            if pid == 0:
                try:
                    server = cls(socket_path, play_context)
                except:
                    display.display(traceback.format_exc(), log_only=True)
                else:
                    fcntl.lockf(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                    server.run()

            else:
                req = json.dumps({'jsonrpc': '2.0', 'method': 'is_running'})
                resp = {}

                # make sure the server is running before continuing
                while not resp.get('result'):
                    if os.path.exists(socket_path):
                        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        sock.connect(socket_path)
                        send_data(sock, req)
                        resp = json.loads(recv_data(sock))
                    time.sleep(1)

        return socket_path

    def run(self):
        try:
            while True:
                # set the alarm, if we don't get an accept before it
                # goes off we exit (via an exception caused by the socket
                # getting closed while waiting on accept())
                signal.alarm(C.PERSISTENT_CONNECT_TIMEOUT)
                try:
                    (s, addr) = self.socket.accept()
                    display.display('incoming request accepted on persistent socket', log_only=True)
                    # clear the alarm
                    signal.alarm(0)
                except:
                    break

                while True:
                    data = recv_data(s)
                    if not data:
                        break

                    signal.alarm(C.DEFAULT_TIMEOUT)

                    rc = 255
                    try:
                        request = json.loads(data)

                        method = request.get('method')

                        if method not in self.__rpc__:
                            error = self.method_not_found()
                            response = json.dumps(error)

                        params = request.get('params')
                        setattr(self, '_identifier', request.get('id'))

                        if method.startswith('rpc.') or method.startswith('_'):
                            error = self.invalid_request()
                            response = json.dumps(error)

                        args = []
                        kwargs = {}

                        if all((params, isinstance(params, list))):
                            args = params
                        elif all((params, isinstance(params, dict))):
                            kwargs = params

                        try:
                            rpc_method = getattr(self, method, None)
                        except AttributeError:
                            rpc_method = geatttr(self._connection, method, None)

                        if not rpc_method:
                            error = self.method_not_found()
                            response = json.dumps(error)

                        else:
                            try:
                                result = rpc_method(*args, **kwargs)
                            except Exception as exc:
                                display.display(traceback.format_exc(), log_only=True)
                                error = self.internal_error(data=str(exc))
                                response = json.dumps(error)
                            else:
                                response = self.response(result)
                                response = json.dumps(response)

                    except:
                        response = traceback.format_exc()

                    signal.alarm(0)

                    delattr(self, '_identifier')
                    send_data(s, to_bytes(response))

                s.close()

        except Exception as e:
            display.display(traceback.format_exc(), log_only=True)

        finally:
            # when done, close the connection properly and cleanup
            # the socket file so it can be recreated
            end_time = datetime.datetime.now()
            delta = end_time - self._start_time
            display.display('shutting down control socket, connection was active for %s secs' % delta, log_only=True)
            try:
                self._connection.close()
                self.socket.close()
            except Exception as e:
                pass
            os.remove(self._socket_path)

    header = lambda self: {'jsonrpc': '2.0', 'id': self._identifier}

    def response(self, result=None):
        response = self.header()
        response['result'] = result or 'ok'
        return response

    def error(self, code, message, data=None):
        response = self.header()
        error = {'code': code, 'message': message}
        if data:
            error['data'] = data
        response['error'] = error
        return response

    def internal_error(self, data=None):
        return self.error(-32603, 'Internal error', data)

    def method_not_found(self, data=None):
        return self.error(-32601, 'Method not found', data)

    def parse_error(self, data=None):
        return self.error(-32700, 'Parse error', data)

    def invalid_request(self, data=None):
        return self.error(-32600, 'Invalid request', data)

    def invalid_params(self, data=None):
        return self.error(-32602, 'Invalid params', data)
