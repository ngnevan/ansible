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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json

from ansible.errors import AnsibleError, AnsibleConnectionFailure
from ansible.errors import AnsibleRpcError, AnsibleCliError


class Rpc:

    def __init__(self, *args, **kwargs):
        self._rpc_objects = list()
        super(Rpc, self).__init__(*args, **kwargs)

    def _exec_rpc(self, request):

        method = request.get('method')
        params = request.get('params')

        setattr(self, '_identifier', request.get('id'))

        if method.startswith('rpc.') or method.startswith('_'):
            error = self.invalid_request()
            return json.dumps(error)

        args = []
        kwargs = {}

        if all((params, isinstance(params, list))):
            args = params
        elif all((params, isinstance(params, dict))):
            kwargs = params

        for obj in self._rpc_objects:
            rpc_method = getattr(obj, method, None)
            if rpc_method:
                break
        else:
            error = self.method_not_found()
            return json.dumps(error)

        try:
            result = rpc_method(*args, **kwargs)
        except AnsibleCliError as exc:
            error = self.error(1001, 'Cli error', data=str(exc))
            return json.dumps(error)
        except AnsibleRpcError as exc:
            error = self.error(1000, 'Rpc error', data=str(exc))
            return json.dumps(error)
        except (AnsibleError, AnsibleConnectionFailure) as exc:
            error = self.internal_error(data=str(exc))
            return json.dumps(error)

        response = self.response(result)
        return json.dumps(response)

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

