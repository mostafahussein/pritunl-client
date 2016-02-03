from pritunl_client.constants import *
from pritunl_client.exceptions import *

from pritunl_client import profile
from pritunl_client import utils
from pritunl_client import interface

import threading
import time
import sys

class App(object):
    def __init__(self):
        self._icon_state = None
        self._cur_icon_path = None
        self.icon = interface.StatusIconApp()
        self.icon.set_tooltip(APP_NAME_FORMATED)
        self.set_icon_state(False)
        self.icon.set_callback(self.update_icon)
        self.update_menu()

    def set_icon_state(self, state):
        self._icon_state = state
        if state:
            self.icon.set_icon(utils.get_connected_logo())
        else:
            self.icon.set_icon(utils.get_disconnected_logo())

    def get_icon_state(self):
        return self._icon_state

    def toggle_icon_state(self):
        self.set_icon_state(not self.get_icon_state())

    def update_menu(self):
        self.update_icon()
        menu = interface.Menu()
        profile_count = 0

        for prfl in profile.Profile.iter_profiles():
            profile_count += 1
            active = prfl.status in ACTIVE_STATES

            profile_menu = interface.Menu()
            if active:
                profile_menu.set_label(
                    '%s - %s' % (prfl.name, prfl.status.capitalize()))
            else:
                profile_menu.set_label(prfl.name)

            menu_item = interface.MenuItem()
            menu_item.set_label('Disconnect' if active else 'Connect')
            menu_item.set_callback(self.on_disconnect_profile if
                active else self.on_connect_profile, prfl.id)
            profile_menu.add_item(menu_item)

            menu_item = interface.MenuItem()
            menu_item.set_label('Rename')
            menu_item.set_callback(self.on_rename_profile, prfl.id)
            profile_menu.add_item(menu_item)

            menu_item = interface.MenuItem()
            menu_item.set_label('Delete')
            menu_item.set_callback(self.on_delete_profile, prfl.id)
            profile_menu.add_item(menu_item)

            if not prfl.auth_passwd:
                menu_item = interface.CheckMenuItem()
                menu_item.set_label('Autostart')
                menu_item.set_active(prfl.autostart)
                menu_item.set_callback(self.on_no_autostart_profile if
                    prfl.autostart else self.on_autostart_profile,
                    prfl.id)
                profile_menu.add_item(menu_item)

            menu.add_item(profile_menu)

        if not profile_count:
            menu_item = interface.MenuItem()
            menu_item.set_label('No Profiles Available')
            menu_item.set_state(False)
            menu.add_item(menu_item)

        menu_item = interface.SeparatorMenuItem()
        menu.add_item(menu_item)

        menu_item = interface.MenuItem()
        menu_item.set_label('Import Profile')
        menu_item.set_callback(self.show_import_profile)
        menu.add_item(menu_item)

        menu_item = interface.MenuItem()
        menu_item.set_label('Import Profile URI')
        menu_item.set_callback(self.show_import_profile_uri)
        menu.add_item(menu_item)

        menu_item = interface.MenuItem()
        menu_item.set_label('About')
        menu_item.set_callback(self.show_about)
        menu.add_item(menu_item)

        menu_item = interface.MenuItem()
        menu_item.set_label('Exit')
        menu_item.set_callback(self.exit)
        menu.add_item(menu_item)

        self.icon.set_menu(menu)

    def update_icon(self):
        icon_path = utils.get_disconnected_logo()
        if self._cur_icon_path != icon_path:
            self._cur_icon_path = icon_path
            self.set_icon_state(self.get_icon_state())

    def show_connect_error(self, prfl, status):
        error_msgs = {
            ERROR: 'An error occurred while connecting to server',
            AUTH_ERROR: 'Failed to authenticate with server',
            TIMEOUT_ERROR: 'Server connection timed out',
        }

        dialog = interface.MessageDialog()
        dialog.set_type(MESSAGE_ERROR)
        dialog.set_buttons(BUTTONS_OK)
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Unable to connect to %s' % prfl.name)
        dialog.set_message_secondary(error_msgs[status])
        dialog.run()
        dialog.destroy()

    def on_status_change(self):
        conn_count = 0
        active_count = 0

        for prfl in profile.Profile.iter_profiles():
            if prfl.status == CONNECTED:
                conn_count += 1
            if prfl.status in ACTIVE_STATES:
                active_count += 1

        self.set_icon_state(bool(conn_count))
        self.update_menu()

    def on_connect_profile(self, profile_id):
        passwd = None
        prfl = profile.Profile.get_profile(profile_id)
        if prfl.status in ACTIVE_STATES:
            return

        prfl.sync_conf()

        auth_type = prfl.auth_type
        if auth_type:
            passwd = ''

            if 'password' in auth_type:
                dialog = interface.InputDialog()
                dialog.set_title(APP_NAME_FORMATED)
                dialog.set_icon(utils.get_logo())
                dialog.set_message('Profile Password Required')
                dialog.set_message_secondary('Enter password for %s' % (
                    prfl.name))
                dialog.set_input_label('Password:')
                dialog.set_input_width(16)
                dialog.set_visibility(False)
                passwd += dialog.run()
                dialog.destroy()
                if passwd is None:
                    return

            if 'pin' in auth_type:
                dialog = interface.InputDialog()
                dialog.set_title(APP_NAME_FORMATED)
                dialog.set_icon(utils.get_logo())
                dialog.set_message('Profile Pin Required')
                dialog.set_message_secondary('Enter pin for %s' % (
                    prfl.name))
                dialog.set_input_label('Pin:')
                dialog.set_input_width(16)
                dialog.set_visibility(False)
                passwd += dialog.run()
                dialog.destroy()
                if passwd is None:
                    return

            if 'otp' in auth_type:
                dialog = interface.InputDialog()
                dialog.set_title(APP_NAME_FORMATED)
                dialog.set_icon(utils.get_logo())
                dialog.set_message('Profile Authenticator Required')
                dialog.set_message_secondary(
                    'Enter authenticator key for %s' % (prfl.name))
                dialog.set_input_label('Authenticator Key:')
                dialog.set_input_width(16)
                passwd += dialog.run()
                dialog.destroy()
                if passwd is None:
                    return

        dialog = interface.MessageDialog()
        dialog.set_type(MESSAGE_LOADING)
        dialog.set_buttons(BUTTONS_CANCEL)
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Connecting to %s' % prfl.name)
        dialog.set_message_secondary('Conecting to the server...')

        def connect_callback():
            dialog.close()

        threading.Thread(target=prfl.start,
            args=(self.on_status_change, connect_callback, passwd)).start()

        response = dialog.run()
        dialog.destroy()
        if response is False:
            threading.Thread(target=prfl.stop).start()
            return

        if prfl.status in ERROR_STATES:
            self.show_connect_error(prfl, prfl.status)

    def on_disconnect_profile(self, profile_id):
        prfl = profile.Profile.get_profile(profile_id)
        prfl.stop()

    def on_rename_profile(self, profile_id):
        prfl = profile.Profile.get_profile(profile_id)
        dialog = interface.InputDialog()
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Rename Profile')
        dialog.set_message_secondary('Enter new name for profile %s' % (
            prfl.name))
        dialog.set_input_label('Profile Name:')
        dialog.set_input_width(32)
        response = dialog.run()
        if response is not None:
            prfl.set_name(response[:32])
            self.update_menu()
        dialog.destroy()

    def on_delete_profile(self, profile_id):
        prfl = profile.Profile.get_profile(profile_id)
        dialog = interface.MessageDialog()
        dialog.set_type(MESSAGE_ERROR)
        dialog.set_buttons(BUTTONS_OK_CANCEL)
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Delete profile')
        dialog.set_message_secondary(
            'Are you sure you want to delete the profile %s' % prfl.name)
        response = dialog.run()
        if response:
            prfl.delete()
            self.update_menu()
        dialog.destroy()

    def on_autostart_profile(self, profile_id):
        prfl = profile.Profile.get_profile(profile_id)
        prfl.set_autostart(True)
        self.update_menu()

    def on_no_autostart_profile(self, profile_id):
        prfl = profile.Profile.get_profile(profile_id)
        prfl.set_autostart(False)
        self.update_menu()

    def show_about(self):
        from pritunl_client import __version__
        dialog = interface.MessageDialog()
        dialog.set_type(MESSAGE_INFO)
        dialog.set_buttons(BUTTONS_OK)
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_image(utils.get_logo())
        dialog.set_message(('<b>%s - v%s</b>\n\n' +
            'Copyright (c) 2013-2016 Pritunl\n\n' +
            'http://pritunl.com/') % (
                APP_NAME_FORMATED,
                __version__,
            ))
        dialog.run()
        dialog.destroy()

    def show_import_profile_error(self, message):
        dialog = interface.MessageDialog()
        dialog.set_type(MESSAGE_ERROR)
        dialog.set_buttons(BUTTONS_OK)
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Failed to import profile:')
        dialog.set_message_secondary(str(message).capitalize())
        dialog.run()
        dialog.destroy()

    def show_import_profile(self):
        dialog = interface.FileChooserDialog()
        dialog.set_title(APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.add_filter('Pritunl Profile', '*.ovpn')
        dialog.add_filter('Pritunl Profile', '*.conf')
        dialog.add_filter('Pritunl Profile', '*.tar')

        response = dialog.run()
        if response:
            try:
                profile.import_file(response)
            except Exception as exception:
                self.show_import_profile_error(exception)
            self.update_menu()
        dialog.destroy()

    def show_import_profile_uri(self):
        dialog = interface.InputDialog()
        dialog.set_title('%s - Import Profile URI' % APP_NAME_FORMATED)
        dialog.set_icon(utils.get_logo())
        dialog.set_message('Import Profile URI')
        dialog.set_message_secondary('Enter profile URI to import...')
        dialog.set_input_label('Profile URI:')
        dialog.set_input_width(32)
        response = dialog.run()
        if response:
            try:
                profile.import_uri(response)
            except Exception as exception:
                self.show_import_profile_error(exception)
            self.update_menu()
        dialog.destroy()

    def autostart(self):
        time.sleep(0.3)
        for prfl in profile.Profile.iter_profiles():
            if not prfl.autostart:
                continue
            threading.Thread(target=prfl.start_autostart,
                args=(self.on_status_change,)).start()

    def exit(self):
        for prfl in profile.Profile.iter_profiles():
            prfl.stop()
        self.icon.destroy()
        sys.exit(0)

    def main(self):
        try:
            thread = threading.Thread(target=self.autostart)
            thread.daemon = True
            thread.start()
            self.icon.run()
        finally:
            for prfl in profile.Profile.iter_profiles():
                prfl.stop()
            self.icon.destroy()
