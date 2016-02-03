from pritunl_client.constants import *
from pritunl_client.exceptions import *
from pritunl_client import utils
from pritunl_client import logger

if PLATFORM != SHELL:
    from pritunl_client import interface

import os
import json
import time
import uuid
import subprocess
import threading
import tarfile
import requests

_connections = {}

class Profile(object):
    def __init__(self, id=None):
        if id:
            self.id = id
        else:
            self.id = uuid.uuid4().hex
        self._loaded = False

        self.profile_name = None
        self.user_name = None
        self.org_name = None
        self.server_name = None
        self.user_id = None
        self.org_id = None
        self.server_id = None
        self.password_mode = None
        self.sync_hash = None
        self.sync_token = None
        self.sync_secret = None
        self.sync_hosts = []
        self.autostart = False
        self.auth_passwd = False
        self.pid = None

        if not os.path.isdir(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)

        self.path = os.path.join(PROFILES_DIR, '%s.ovpn' % self.id)
        self.conf_path = os.path.join(PROFILES_DIR, '%s.conf' % self.id)
        self.log_path = os.path.join(PROFILES_DIR, '%s.log' % self.id)
        self.passwd_path = os.path.join(PROFILES_DIR, '%s.passwd' % self.id)

        if id:
            self.load()

        if self.status not in ACTIVE_STATES and self.pid:
            self._kill_pid(self.pid)
            self.pid = None
            self.commit()

    def dict(self):
        return {
            'name': self.profile_name,
            'user': self.user_name,
            'organization': self.org_name,
            'server': self.server_name,
            'user_id': self.user_id,
            'org_id': self.org_id,
            'server_id': self.server_id,
            'password_mode': self.password_mode,
            'sync_hash': self.sync_hash,
            'sync_token': self.sync_token,
            'sync_secret': self.sync_secret,
            'sync_hosts': self.sync_hosts,
            'autostart': self.autostart,
            'pid': self.pid,
        }

    def __getattr__(self, name):
        if name == 'name':
            if self.profile_name:
                return self.profile_name
            elif self.user_name and self.org_name and self.server_name:
                return '%s@%s (%s)' % (self.user_name, self.org_name,
                    self.server_name)
            else:
                return 'Unknown Profile'
        elif name == 'status':
            connection_data = _connections.get(self.id)
            if connection_data:
                return connection_data.get('status', ENDED)
            return ENDED
        elif name not in self.__dict__:
            raise AttributeError('Config instance has no attribute %r' % name)
        return self.__dict__[name]

    @property
    def auth_type(self):
        if self.password_mode:
            return self.password_mode
        if self.auth_passwd:
            return 'password'
        return None

    def load(self):
        try:
            if os.path.exists(self.conf_path):
                with open(self.conf_path, 'r') as conf_file:
                    data = json.loads(conf_file.read())
                    self.profile_name = data.get('name')
                    self.user_name = data.get('user')
                    self.org_name = data.get('organization')
                    self.server_name = data.get('server')
                    self.user_id = data.get('user_id')
                    self.org_id = data.get('org_id')
                    self.server_id = data.get('server_id')
                    self.password_mode = data.get('password_mode')
                    self.sync_hash = data.get('sync_hash')
                    self.sync_token = data.get('sync_token')
                    self.sync_secret = data.get('sync_secret')
                    self.sync_hosts = data.get('sync_hosts', [])
                    self.autostart = data.get('autostart', False)
                    self.pid = data.get('pid')

                with open(self.path, 'r') as ovpn_file:
                    self.auth_passwd = 'auth-user-pass' in ovpn_file.read()

                if self.auth_passwd:
                    self.autostart = False
        except (OSError, ValueError):
            pass

    def commit(self):
        temp_path = self.conf_path + '_%s.tmp' % uuid.uuid4().hex
        try:
            with open(temp_path, 'w') as conf_file:
                os.chmod(temp_path, 0600)
                conf_file.write(json.dumps(self.dict()))
            try:
                os.rename(temp_path, self.conf_path)
            except:
                os.remove(self.conf_path)
                os.rename(temp_path, self.conf_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _parse_profile(self, data):
        json_data = ''

        for line in data.splitlines():
            if line.startswith('#'):
                json_data += line[1:].strip()
            else:
                break

        try:
            conf_data = json.loads(json_data)
        except ValueError:
            conf_data = {}

        return conf_data

    def write_profile(self, profile_data):
        conf_data = self._parse_profile(profile_data)
        with open(self.path, 'w') as profile_file:
            os.chmod(self.path, 0600)
            profile_file.write(profile_data)

        self.user_name = conf_data.get('user')
        self.org_name = conf_data.get('organization')
        self.server_name = conf_data.get('server')
        self.user_id = conf_data.get('user_id')
        self.org_id = conf_data.get('organization_id')
        self.server_id = conf_data.get('server_id')
        self.password_mode = conf_data.get('password_mode')
        self.sync_hash = conf_data.get('sync_hash')
        self.sync_token = conf_data.get('sync_token')
        self.sync_secret = conf_data.get('sync_secret')
        self.sync_hosts = conf_data.get('sync_hosts', [])
        self.auth_passwd = 'auth-user-pass' in profile_data
        self.commit()

    def update_profile(self, data):
        with open(self.path, 'r') as profile_file:
            profile_data = profile_file.read()

        tls_auth = ''
        if 'key-direction' in profile_data and 'key-direction' not in data:
            tls_auth += 'key-direction 1\n'

        s_index = profile_data.find('<tls-auth>')
        e_index = profile_data.find('</tls-auth>')
        if s_index >= 0 and e_index >= 0:
            tls_auth += profile_data[s_index:e_index + 11] + '\n'

        s_index = profile_data.find('<cert>')
        e_index = profile_data.find('</cert>')
        if s_index < 0 or e_index < 0:
            raise ValueError('Cant find cert')
        cert = profile_data[s_index:e_index + 7] + '\n'

        s_index = profile_data.find('<key>')
        e_index = profile_data.find('</key>')
        if s_index < 0 or e_index < 0:
            raise ValueError('Cant find key')
        key = profile_data[s_index:e_index + 6] + '\n'

        self.write_profile(data + tls_auth + cert + key)

    def set_name(self, name):
        self.profile_name = name
        self.commit()

    def set_autostart(self, state):
        self.autostart = state
        self.commit()

    def delete(self):
        self.stop()
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.conf_path):
            os.remove(self.conf_path)
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def _set_status(self, status, connect_event=True):
        data = _connections.get(self.id)
        if not data:
            return
        data['status'] = status

        if connect_event:
            callback = data.get('connect_callback')
            if callback:
                data['connect_callback'] = None
                if PLATFORM != SHELL:
                    interface.add_idle_call(callback)
                else:
                    callback()

        callback = data.get('status_callback')
        if callback:
            if PLATFORM != SHELL:
                interface.add_idle_call(callback)
            else:
                callback()

    def start(self, status_callback, connect_callback=None, passwd=None):
        if self.status in ACTIVE_STATES:
            self._set_status(self.status)
            return False
        self._start(status_callback, connect_callback, passwd)
        return True

    def start_autostart(self, status_callback, connect_callback=None):
        if self.status in ACTIVE_STATES:
            return
        self._start_autostart(status_callback, connect_callback)

    def _start(self, status_callback, connect_callback, passwd):
        raise NotImplementedError()

    def sync_conf(self):
        status_code = None
        for i, sync_host in enumerate(self.sync_hosts):
            try:
                response = utils.auth_request('get', sync_host,
                    '/key/%s/%s/%s/%s' % (
                        self.org_id,
                        self.user_id,
                        self.server_id,
                        self.sync_hash,
                    ),
                    token=self.sync_token,
                    secret=self.sync_secret,
                    timeout=SYNC_CONF_TIMEOUT,
                )
                status_code = response.status_code
            except:
                if i >= len(self.sync_hosts) - 1:
                    logger.exception('Failed to sync conf', 'profile',
                        sync_host=sync_host,
                        sync_hosts=self.sync_hosts,
                        org_id=self.org_id,
                        user_id=self.user_id,
                        server_id=self.server_id,
                        sync_hash=self.sync_hash,
                    )
                    return
                else:
                    continue

            if status_code == 480:
                logger.info('Failed to sync conf, no subscription',
                    'profile',
                    status_code=status_code,
                    sync_host=sync_host,
                    sync_hosts=self.sync_hosts,
                    org_id=self.org_id,
                    user_id=self.user_id,
                    server_id=self.server_id,
                    sync_hash=self.sync_hash,
                )
                return
            elif status_code == 404:
                logger.warning('Failed to sync conf, user not found',
                    'profile',
                    status_code=status_code,
                    sync_host=sync_host,
                    sync_hosts=self.sync_hosts,
                    org_id=self.org_id,
                    user_id=self.user_id,
                    server_id=self.server_id,
                    sync_hash=self.sync_hash,
                )
                return
            elif status_code == 200 and response.content:
                self.update_profile(response.content)
                return

        if status_code is not None and status_code != 200:
            logger.error('Failed to sync conf, unknown error',
                'profile',
                status_code=status_code,
                sync_host=sync_host,
                sync_hosts=self.sync_hosts,
                org_id=self.org_id,
                user_id=self.user_id,
                server_id=self.server_id,
                sync_hash=self.sync_hash,
            )

    def _run_ovpn(self, status_callback, connect_callback, passwd,
            args, on_exit, **kwargs):
        data = {
            'status': CONNECTING,
            'process': None,
            'status_callback': status_callback,
            'connect_callback': connect_callback,
            'started': False,
        }
        _connections[self.id] = data
        self._set_status(CONNECTING, connect_event=False)

        if passwd:
            with open(self.passwd_path, 'w') as passwd_file:
                os.chmod(self.passwd_path, 0600)
                passwd_file.write('pritunl_client\n')
                passwd_file.write('%s\n' % passwd)

        process = subprocess.Popen(args,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        data['process'] = process
        self.pid = process.pid
        self.commit()

        def connect_thread():
            time.sleep(CONNECT_TIMEOUT)
            if not data.get('connect_callback'):
                return
            self._set_status(TIMEOUT_ERROR)
            self.stop(silent=True)

        def poll_thread():
            started = False
            with open(self.log_path, 'w') as _:
                pass
            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    else:
                        continue
                data['started'] = True
                print line.strip()
                with open(self.log_path, 'a') as log_file:
                    log_file.write(line)
                if not started:
                    started = True
                    thread = threading.Thread(target=connect_thread)
                    thread.daemon = True
                    thread.start()
                if 'Initialization Sequence Completed' in line:
                    self._set_status(CONNECTED)
                elif 'Inactivity timeout' in line:
                    self._set_status(RECONNECTING)
                elif 'AUTH_FAILED' in line or 'auth-failure' in line:
                    self._set_status(AUTH_ERROR)

            try:
                if os.path.exists(self.passwd_path):
                    os.remove(self.passwd_path)
            except:
                pass

            on_exit(data, process.returncode)

        thread = threading.Thread(target=poll_thread)
        thread.daemon = True
        thread.start()

    def stop(self, silent=False):
        self._stop(silent)

    def _stop(self):
        raise NotImplementedError()

    @classmethod
    def iter_profiles(cls):
        if os.path.isdir(PROFILES_DIR):
            for profile_path in os.listdir(PROFILES_DIR):
                profile_id, extension = os.path.splitext(profile_path)
                if extension == '.ovpn':
                    yield cls.get_profile(profile_id)

    @classmethod
    def get_profile(cls, id=None):
        if PLATFORM == LINUX:
            from pritunl_client import profile_linux
            return profile_linux.ProfileLinux(id)
        elif PLATFORM == SHELL:
            from pritunl_client import profile_shell
            return profile_shell.ProfileShell(id)
        else:
            raise NotImplementedError('Platform %s not supported' % PLATFORM)

def import_file(profile_path):
    if os.path.splitext(profile_path)[1] == '.tar':
        tar = tarfile.open(profile_path)
        for member in tar:
            prfl = Profile.get_profile()
            prfl.write_profile(tar.extractfile(member).read())
    else:
        with open(profile_path, 'r') as profile_file:
            prfl = Profile.get_profile()
            prfl.write_profile(profile_file.read())

def import_uri(profile_uri):
    if profile_uri.startswith('pritunl:'):
        profile_uri = profile_uri.replace('pritunl', 'https', 1)
    elif profile_uri.startswith('pts:'):
        profile_uri = profile_uri.replace('pts', 'https', 1)
    elif profile_uri.startswith('pt:'):
        profile_uri = profile_uri.replace('pt', 'http', 1)
    elif profile_uri.startswith('https:'):
        pass
    elif profile_uri.startswith('http:'):
        pass
    else:
        profile_uri = 'https://' + profile_uri
    profile_uri = profile_uri.replace('/k/', '/ku/', 1)

    for i in xrange(2):
        try:
            response = requests.get(profile_uri, verify=False,
                timeout=IMPORT_TIMEOUT)
            if response.status_code != 400:
                break
        except:
            if i == 1:
                raise
        if profile_uri.startswith('https'):
            profile_uri = profile_uri.replace('https', 'http', 1)
        else:
            profile_uri = profile_uri.replace('http', 'https', 1)
    if response.status_code == 200:
        pass
    elif response.status_code == 404:
        raise ValueError('Key link is not valid')
    else:
        raise ValueError('Pritunl server returned error code %s' % (
            response.status_code))
    data = response.json()

    for key in data:
        prfl = Profile.get_profile()
        prfl.write_profile(data[key])
