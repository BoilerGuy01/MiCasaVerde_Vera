# -*- coding: utf-8 -*-

# MIT License
#
# Copyright 2020 Kevin G. Schlosser
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""
This file is part of the **micasaverde_vera**
project https://github.com/kdschlosser/MiCasaVerde_Vera.

:platform: Unix, Windows, OSX
:license: MIT
:synopsis: authentication

.. moduleauthor:: Kevin Schlosser @kdschlosser <kevin.g.schlosser@gmail.com>
"""

import requests
import json
import threading
import base64
import time
import random
import logging
from hashlib import sha1
from requests import (
    ConnectionError,
    Timeout,
    ReadTimeout,
    ConnectTimeout
)
from .event import Notify
from .vera_exception import (
    VeraNotImplementedError,
    VeraUnsupportedByDevice
)
from .constants import PY3
from . import connect
from . import utils

logger = logging.getLogger(__name__)

AUTH_SERVER = (
    'https://vera-us-oem-autha11.mios.com/autha/auth/username/{lower_user_id}'
    '?SHA1Password={sha1_user_password}&PK_Oem=1'
)


class Auth(object):

    def __init__(self, user_id, user_password):

        self.user_id = user_id
        self.user_password = user_password
        self.lower_user_id = user_id.lower()
        self.password_seed = 'oZ7QE6LcLJp6fiWzdqZc'
        self.sha1_user_password = sha1(
            self.lower_user_id +
            self.user_password +
            self.password_seed
        ).hexdigest()

        self.auth_url = AUTH_SERVER.format(
            lower_user_id=self.lower_user_id,
            sha1_user_password=self.sha1_user_password
        )

        self._auth_token = None
        self._auth_sig_token = None
        self._server_account = None
        self._server_account_alt = None
        self._pk_account = None
        self._auth_token_expiration = None

    @property
    def token_expired(self):

        return time.time() >= self._auth_token_expiration

    @property
    def token(self):
        if self._auth_token is None or self.token_expired:
            self._get_token()

        return self._auth_token

    @property
    def sig_token(self):
        if self._auth_sig_token is None or self.token_expired:
            self._get_token()

        return self._auth_sig_token

    def _get_token(self):
        if self._auth_token is None or self.token_expired:
            response = requests.get(self.auth_url)
            response = json.loads(response.content)

            self._auth_token = response['Identity']
            self._auth_sig_token = response['IdentitySignature']
            self._server_account = response['Server_Account']
            self._server_account_alt = response['Server_Account_Alt']

            if PY3:
                pk_account_data = json.loads(
                    base64.decodebytes(self._auth_token)
                )
            else:
                # noinspection PyDeprecation
                pk_account_data = json.loads(
                    base64.decodestring(self._auth_token)
                )
            self._pk_account = pk_account_data['PK_Account']
            self._auth_token_expiration = pk_account_data['Expires']

    @property
    def pk_account(self):
        if self._pk_account is None or self.token_expired:
            self._get_token()

        return self._pk_account

    @property
    def server_account(self):
        if self._server_account is None or self.token_expired:
            self._get_token()

        return self._server_account

    @property
    def server_account_alt(self):
        if self._server_account_alt is None or self.token_expired:
            self._get_token()

        return self._server_account_alt


class MIOSServer(object):

    def __init__(self, auth, server, extra_url):
        self._lock = threading.Lock()
        self._connected = None
        self._params = {}
        self._auth = auth
        url = 'https://{server}/info/session/token'.format(server=server)
        header = dict(
            MMSAuth=auth.token,
            MMSAuthSig=auth.sig_token
        )
        response = requests.get(
            url,
            headers=header
        )

        self._session = response.content

        self._url = 'https://{server}{extra_url}'.format(
            server=server,
            extra_url=extra_url
        )

    @utils.logit
    def send(self, extra_url=None, **params):
        self._lock.acquire()

        if extra_url is None:
            url = self._url + '/data_request'
            if 'output_format' not in params:
                params['output_format'] = 'json'
        else:
            url = self._url + extra_url

        try:
            if extra_url is None:
                response = requests.get(
                    url,
                    params=params,
                    headers=dict(MMSSession=self._session)
                )
            else:
                response = requests.get(
                    url,
                    params=params
                )
                return response.content

            if self._connected in (None, False):
                self._connected = True
                Notify('vera.connected', self)
        except (ConnectionError, Timeout, ReadTimeout, ConnectTimeout):
            if self._connected in (True, None):
                self._connected = False
                Notify('vera.disconnected', self)
            time.sleep(random.randrange(1, 5) / 10)
        else:
            try:
                return json.loads(response.content)
            except ValueError:
                if 'ERROR' in response.content:
                    if 'No implementation' in response.content:
                        raise VeraNotImplementedError
                    if (
                        'Device does not handle service/action' in
                        response.content
                    ):
                        raise VeraUnsupportedByDevice
        finally:
            self._lock.release()


class LocalServer(object):

    def __init__(self, ip_address):
        self._lock = threading.Lock()
        self._url = 'http://{0}'.format(ip_address)
        self._params = {}
        self._connected = None

    @utils.logit
    def send(self, extra_url=None, **params):
        self._lock.acquire()
        if extra_url is None:
            url = self._url + ':3480/data_request'
            if 'output_format' not in params:
                params['output_format'] = 'json'
        else:
            url = self._url + extra_url

        try:
            if extra_url is None:
                response = requests.get(url, params=params)
            else:
                response = requests.get(url, params=params)
                return response.content

            if self._connected in (None, False):
                self._connected = True
                Notify('vera.connected', self)
        except (ConnectionError, Timeout, ReadTimeout, ConnectTimeout):
            if self._connected in (True, None):
                self._connected = False
                Notify('vera.disconnected', self)
            time.sleep(random.randrange(1, 5) / 10)
        else:
            try:
                return json.loads(response.content)
            except ValueError:
                if 'ERROR' in response.content:
                    if 'No implementation' in response.content:
                        raise VeraNotImplementedError
                    if (
                        'Device does not handle service/action' in
                        response.content
                    ):
                        raise VeraUnsupportedByDevice
        finally:
            self._lock.release()


class Unit(object):

    def __init__(self):
        self._auth = None
        self.serial = None
        self.server = None
        self.alt_server = None
        self.internal_ip = None
        self._relay_server = None
        self.build_relay = None

    @utils.logit
    def set_remote_relay(self, auth, serial, server, alt_server):
        self._auth = auth
        self.serial = serial
        self.server = server
        self.alt_server = alt_server

        url = 'https://{server}/info/session/token'.format(server=server)
        header = dict(
            MMSAuth=auth.token,
            MMSAuthSig=auth.sig_token
        )
        response = requests.get(
            url,
            headers=header
        )

        session = response.content

        response = requests.get(
            'https://{0}/device/device/device/{1}'.format(server, serial),
            headers=dict(MMSSession=session)
        )

        device_data = json.loads(response.content)
        self.internal_ip = device_data['InternalIP']
        self._relay_server = MIOSServer(
            auth,
            device_data['Server_Relay'],
            '/relay/relay/relay/device/{0}/port_3480'.format(serial)
        )

        self.build_relay = MIOSServer(
            auth,
            device_data['Server_Relay'],
            '/relay/relay/relay/device/{0}/port_80'.format(serial)
        )

    @utils.logit
    def set_local_relay(self, ip_address):
        self.internal_ip = ip_address
        self.build_relay = LocalServer(ip_address)

    @utils.logit
    def relay(self, **params):
        return self._relay_server.send(**params)

    @utils.logit
    def connect(self):
        return connect(self)


