from pritunl_client.constants import *

import optparse
import sys
import os
import re
import subprocess
import signal
import time
import hashlib
import json
import requests

def client_gui():
    from pritunl_client import app
    parser = optparse.OptionParser()
    parser.add_option('--version', action='store_true', help='Print version')
    (options, args) = parser.parse_args()

    if options.version:
        print '%s v%s' % (pritunl.__title__, pritunl.__version__)
    else:
        client_app = app.App()
        client_app.main()

def client_shell():
    from pritunl_client import constants
    constants.set_shell()
    from pritunl_client import click

    @click.group()
    def cli():
        pass

    @click.command('daemon',
        help='Start client service daemon',
    )
    @click.option('--pidfile',
        help='Path to create pid file',
        default=None,
    )
    @click.option('--foreground',
        help='Run daemon in foreground',
        is_flag=True,
    )
    def daemon_cmd(pidfile, foreground):
        if not foreground:
            pid = os.fork()
            if pid > 0:
                if pidfile:
                    with open(pidfile, 'w') as pid_file:
                        pid_file.write('%s' % pid)
                sys.exit(0)
        else:
            if pidfile:
                with open(pidfile, 'w') as pid_file:
                    pid_file.write(str(os.getpid()))

        from pritunl_client import shell_app
        shell_app.ShellApp()
    cli.add_command(daemon_cmd)

    @click.command('list',
        help='List imported profiles and status',
    )
    def list_cmd():
        response = requests.get(
            'http://localhost:9797/list',
        )

        if response.status_code == 200:
            click.echo(response.content)
        else:
            click.echo(response.content)
            sys.exit(1)
    cli.add_command(list_cmd)

    @click.command(name='import',
        help='Import new profile archive, conf or uri. Can be ' + \
            'path to profile conf or path to archive or profile uri',
    )
    @click.argument('profile_ins',
        nargs=-1,
    )
    def import_cmd(profile_ins):
        for profile_in in profile_ins:
            data = {}
            if os.path.exists(profile_in):
                data['profile_path'] = os.path.abspath(profile_in)
            else:
                data['profile_uri'] = profile_in

            response = requests.post(
                'http://localhost:9797/import',
                headers={
                    'Content-type': 'application/json',
                },
                data=json.dumps(data),
            )

            if response.status_code == 200:
                click.echo('Successfully imported profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(import_cmd)

    @click.command('remove',
        help='Remove a profile by profile ID or space separated list of IDs',
    )
    @click.argument('profile_ids',
        nargs=-1,
    )
    def remove_cmd(profile_ids):
        for profile_id in profile_ids:
            response = requests.delete(
                'http://localhost:9797/remove/%s' % profile_id,
            )

            if response.status_code == 200:
                click.echo('Successfully removed profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(remove_cmd)

    @click.command('start',
        help='Start a profile by profile ID or space separated list of IDs',
    )
    @click.argument('profile_ids',
        nargs=-1,
    )
    @click.option('--password',
        help='Password for profile if required',
        default=None,
    )
    def start_cmd(profile_ids, password):
        for profile_id in profile_ids:
            if password:
                headers = {
                    'Content-type': 'application/json',
                }
                data = json.dumps({
                    'passwd': password,
                })
            else:
                headers = None
                data = None

            response = requests.put(
                'http://localhost:9797/start/%s' % profile_id,
                headers=headers,
                data=data,
            )

            if response.status_code == 200:
                click.echo('Successfully started profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(start_cmd)

    @click.command('stop',
        help='Stop a profile by profile ID or space separated list of IDs',
    )
    @click.argument('profile_ids',
        nargs=-1,
    )
    def stop_cmd(profile_ids):
        for profile_id in profile_ids:
            response = requests.put(
                'http://localhost:9797/stop/%s' % profile_id,
            )

            if response.status_code == 200:
                click.echo('Successfully stopped profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(stop_cmd)

    @click.command('enable',
        help='Enable a profile to autostart by profile ID or space ' + \
            'separated list of IDs',
    )
    @click.argument('profile_ids',
        nargs=-1,
    )
    def enable_cmd(profile_ids):
        for profile_id in profile_ids:
            response = requests.put(
                'http://localhost:9797/enable/%s' % profile_id,
            )

            if response.status_code == 200:
                click.echo('Successfully enabled profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(enable_cmd)

    @click.command('disable',
        help='Disable a profile to stop autostart by profile ID or space ' + \
            'separated list of IDs',
    )
    @click.argument('profile_ids',
        nargs=-1,
    )
    def disable_cmd(profile_ids):
        for profile_id in profile_ids:
            response = requests.put(
                'http://localhost:9797/disable/%s' % profile_id,
            )

            if response.status_code == 200:
                click.echo('Successfully disabled profile')
            else:
                click.echo(response.content)
                sys.exit(1)
    cli.add_command(disable_cmd)

    cli()

def _pk_start(autostart=False):
    regex = r'(?:/pritunl_client/profiles/[a-z0-9]+\.ovpn)$'
    if not re.search(regex, sys.argv[1]):
        raise ValueError('Profile must be in home directory')
    if autostart:
        with open(sys.argv[1], 'r') as profile_file:
            profile_hash = hashlib.sha1(profile_file.read()).hexdigest()
        profile_hash_path = os.path.join(os.path.abspath(os.sep),
            'etc', 'pritunl_client', profile_hash)
        if not os.path.exists(profile_hash_path):
            raise ValueError('Profile not authorized to autostart')

    args = ['openvpn', '--config', sys.argv[1]]

    if len(sys.argv) > 2:
        os.chown(sys.argv[2], os.getuid(), os.getgid())
        args.append('--auth-user-pass')
        args.append(sys.argv[2])

    script_path = os.path.join(SHARE_DIR, 'update-resolv-conf.sh')

    args.extend(['--script-security', '2'])
    args.extend(['--up', script_path])
    args.extend(['--down', script_path])

    try:
        process = subprocess.Popen(args)
        def sig_handler(signum, frame):
            process.send_signal(signum)
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)
        sys.exit(process.wait())
    finally:
        if len(sys.argv) > 2:
            os.remove(sys.argv[2])

def pk_start():
    _pk_start(False)

def pk_autostart():
    _pk_start(True)

def pk_stop():
    pid = int(sys.argv[1])
    cmdline_path = '/proc/%s/cmdline' % pid
    regex = r'/pritunl_client/profiles/[a-z0-9]+\.ovpn'
    if not os.path.exists(cmdline_path):
        return
    with open('/proc/%s/cmdline' % pid, 'r') as cmdline_file:
        cmdline = cmdline_file.read().strip().strip('\x00')
        if not re.search(regex, cmdline):
            raise ValueError('Not a pritunl client process')
    os.kill(pid, signal.SIGTERM)
    for i in xrange(int(5 / 0.1)):
        time.sleep(0.1)
        if not os.path.exists('/proc/%s' % pid):
            break
        os.kill(pid, signal.SIGTERM)

def pk_set_autostart():
    regex = r'(?:/pritunl_client/profiles/[a-z0-9]+\.ovpn)$'
    if not re.search(regex, sys.argv[1]):
        raise ValueError('Profile must be in home directory')
    with open(sys.argv[1], 'r') as profile_file:
        profile_hash = hashlib.sha1(profile_file.read()).hexdigest()
    etc_dir = os.path.join(os.path.abspath(os.sep),
        'etc', 'pritunl_client')
    if not os.path.exists(etc_dir):
        os.makedirs(etc_dir)
    profile_hash_path = os.path.join(etc_dir, profile_hash)
    with open(profile_hash_path, 'w') as profile_hash_file:
        pass

def pk_clear_autostart():
    profile_hash_path = os.path.join(os.path.abspath(os.sep),
        'etc', 'pritunl_client', sys.argv[1])
    if os.path.exists(profile_hash_path):
        os.remove(profile_hash_path)
