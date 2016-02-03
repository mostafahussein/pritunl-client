from pritunl_client.constants import *
from pritunl_client.exceptions import *

if PLATFORM == SHELL:
    raise TypeError('Interface not supported for platform')

import gobject
import pygtk
pygtk.require('2.0')
import gtk
import os

HAS_APPINDICATOR = False
try:
    import appindicator
    HAS_APPINDICATOR = os.environ.get(
        'XDG_CURRENT_DESKTOP', '').lower() == 'unity'
except ImportError:
    pass

_mappings = {
    BUTTONS_OK: gtk.BUTTONS_OK,
    BUTTONS_CANCEL: gtk.BUTTONS_CANCEL,
    BUTTONS_OK_CANCEL: gtk.BUTTONS_OK_CANCEL,
    MESSAGE_INFO: gtk.MESSAGE_INFO,
    MESSAGE_QUESTION: gtk.MESSAGE_QUESTION,
    MESSAGE_ERROR: gtk.MESSAGE_ERROR,
    MESSAGE_LOADING: gtk.MESSAGE_INFO,
}

def lookup_icon(name):
    icons = gtk.icon_theme_get_default()
    logo = icons.lookup_icon(name, -1, 0)
    if logo:
        return logo.get_filename()

def add_idle_call(call, *args):
    gobject.idle_add(call, *args)

class MessageDialog:
    def __init__(self):
        self._dialog = None
        self._type = None
        self._buttons = None
        self._title = None
        self._message = None
        self._message_secondary = None
        self._image_path = None
        self._icon = None

    def _build_dialog(self):
        if not self._type or not self._buttons:
            return
        self._dialog = gtk.MessageDialog(
            type=_mappings[self._type],
            buttons=_mappings[self._buttons])
        self._dialog.set_position(gtk.WIN_POS_CENTER)
        self._dialog.set_skip_taskbar_hint(False)
        self._dialog.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NORMAL)

        if self._type == MESSAGE_LOADING:
            spinner = gtk.Spinner()
            spinner.set_size_request(45, 45)
            spinner.start()
            self._dialog.set_image(spinner)

        if self._title:
            self.set_title(self._title)
        if self._icon:
            self.set_icon(self._icon)
        if self._message:
            self.set_message(self._message)
        if self._message_secondary:
            self.set_message_secondary(self._message_secondary)
        if self._image_path:
            self.set_image(self._image_path)

    def set_title(self, title):
        self._title = title
        if self._dialog:
            self._dialog.set_title(title)
        else:
            self._build_dialog()

    def set_icon(self, icon_path):
        self._icon = icon_path
        if self._dialog:
            self._dialog.set_icon_from_file(icon_path)
        else:
            self._build_dialog()

    def set_message(self, message):
        self._message = message
        if self._dialog:
            self._dialog.set_markup(message)
        else:
            self._build_dialog()

    def set_message_secondary(self, message):
        self._message_secondary = message
        if self._dialog:
            self._dialog.format_secondary_text(message)
        else:
            self._build_dialog()

    def set_image(self, image_path):
        self._image_path = image_path

        if self._dialog:
            pix_buf = gtk.gdk.pixbuf_new_from_file(image_path)
            pix_buf = pix_buf.scale_simple(90, 90, gtk.gdk.INTERP_BILINEAR)
            image = gtk.Image()
            image.set_from_pixbuf(pix_buf)
            image.show()
            self._dialog.set_image(image)
        else:
            self._build_dialog()

    def set_type(self, type):
        self._type = type
        if not self._dialog:
            self._build_dialog()

    def set_buttons(self, buttons):
        self._buttons = buttons
        if not self._dialog:
            self._build_dialog()

    def run(self):
        self._dialog.show_all()
        self._dialog.set_keep_above(True)
        self._dialog.set_keep_above(False)
        response = self._dialog.run()
        if response == gtk.RESPONSE_OK:
            return True
        elif response == gtk.RESPONSE_CANCEL:
            return False

    def destroy(self):
        self._dialog.destroy()

    def close(self):
        self.destroy()

class InputDialog:
    def __init__(self):
        self._dialog = gtk.MessageDialog(
            type=gtk.MESSAGE_QUESTION,
            buttons=gtk.BUTTONS_OK_CANCEL,
        )
        self._dialog.set_position(gtk.WIN_POS_CENTER)
        self._dialog.set_skip_taskbar_hint(False)
        self._dialog.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NORMAL)
        self._label = gtk.Label()
        self._entry = gtk.Entry()

    def set_title(self, title):
        self._dialog.set_title(title)

    def set_icon(self, icon_path):
        self._dialog.set_icon_from_file(icon_path)

    def set_message(self, message):
        self._dialog.set_markup(message)

    def set_message_secondary(self, message):
        self._dialog.format_secondary_text(message)

    def set_input_label(self, label):
        self._label.set_label(label)

    def set_input_width(self, width):
        self._entry.set_width_chars(width)

    def set_visibility(self, visibility):
        self._entry.set_visibility(visibility)

    def run(self):
        hbox = gtk.HBox()
        hbox.pack_start(self._label, False, 5, 5)
        hbox.pack_end(self._entry)
        self._dialog.vbox.pack_end(hbox, True, True, 0)
        self._dialog.show_all()
        self._dialog.set_keep_above(True)
        self._dialog.set_keep_above(False)
        response = self._dialog.run()
        if response == gtk.RESPONSE_OK:
            return self._entry.get_text()

    def destroy(self):
        self._dialog.destroy()

    def close(self):
        self.destroy()

class FileChooserDialog:
    def __init__(self):
        self._filters = {}
        self._dialog = gtk.FileChooserDialog(buttons=(gtk.STOCK_CANCEL,
            gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        self._dialog.set_position(gtk.WIN_POS_CENTER)
        self._dialog.set_skip_taskbar_hint(False)
        self._dialog.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NORMAL)

    def set_title(self, title):
        self._dialog.set_title(title)

    def set_icon(self, icon_path):
        self._dialog.set_icon_from_file(icon_path)

    def add_filter(self, name, pattern):
        if name not in self._filters:
            self._filters[name] = gtk.FileFilter()
            self._filters[name].set_name(name)
        self._filters[name].add_pattern(pattern)

    def run(self):
        for file_filter in self._filters.values():
            self._dialog.add_filter(file_filter)
        self._dialog.show_all()
        self._dialog.set_keep_above(True)
        self._dialog.set_keep_above(False)
        response = self._dialog.run()
        if response == gtk.RESPONSE_OK:
            response_path = self._dialog.get_filename()
            if response_path:
                return response_path

    def destroy(self):
        self._dialog.destroy()

    def close(self):
        self.destroy()

class Menu:
    def __init__(self):
        self._label = None
        self._items = []
        self._menu = gtk.Menu()

    def set_label(self, label):
        self._label = label

    def add_item(self, item):
        self._items.append(item)

        if isinstance(item, Menu):
            sub_menu = gtk.MenuItem(item._label)
            sub_menu.set_submenu(item._menu)
            self._menu.append(sub_menu)
        else:
            self._menu.append(item._menu_item)

class MenuItem:
    def __init__(self):
        self._callback = None
        self._callback_data = None
        self._menu_item = gtk.MenuItem()
        self._menu_item.connect('activate', self._on_activate)

    def _on_activate(self, widget):
        if self._callback:
            if self._callback_data:
                self._callback(self._callback_data)
            else:
                self._callback()

    def set_label(self, label):
        self._menu_item.set_label(label)

    def set_state(self, state):
        self._menu_item.set_sensitive(state)

    def set_callback(self, callback, data=None):
        self._callback = callback
        self._callback_data = data

class CheckMenuItem:
    def __init__(self):
        self._callback = None
        self._callback_data = None
        self._menu_item = gtk.CheckMenuItem()
        self._menu_item.connect('activate', self._on_activate)

    def _on_activate(self, widget):
        if self._callback:
            if self._callback_data:
                self._callback(self._callback_data)
            else:
                self._callback()

    def set_label(self, label):
        self._menu_item.set_label(label)

    def set_state(self, state):
        self._menu_item.set_sensitive(state)

    def set_active(self, state):
        self._menu_item.set_active(state)

    def set_callback(self, callback, data=None):
        self._callback = callback
        self._callback_data = data

class SeparatorMenuItem:
    def __init__(self):
        self._menu_item = gtk.SeparatorMenuItem()

class StatusIconApp:
    def __init__(self):
        gtk.threads_init()
        gtk.threads_enter()

        self._callback = None
        if HAS_APPINDICATOR:
            self._icon = None
        else:
            self._menu = None
            self._icon = gtk.StatusIcon()
            self._icon.connect('activate', self._on_activate)
            self._icon.connect('popup_menu', self._on_popup_menu)

        icons = gtk.icon_theme_get_default()
        icons.connect('changed', self._on_theme_change)

    def _on_activate(self, widget):
        self._show_menu(0, 0)

    def _on_popup_menu(self, widget, button, activate_time):
        self._show_menu(button, activate_time)

    def _on_theme_change(self, widget):
        if self._callback:
            self._callback()

    def _show_menu(self, event_button, activate_time):
        self._menu._menu.show_all()
        self._menu._menu.popup(None, None, None, event_button, activate_time)

    def set_tooltip(self, label):
        if not HAS_APPINDICATOR:
            self._icon.set_tooltip(label)

    def set_icon(self, icon_path):
        if HAS_APPINDICATOR:
            if not self._icon:
                self._icon = appindicator.Indicator(APP_NAME, icon_path,
                    appindicator.CATEGORY_APPLICATION_STATUS)
                self._icon.set_status(appindicator.STATUS_ACTIVE)
            else:
                self._icon.set_icon(icon_path)
        else:
            self._icon.set_from_file(icon_path)

    def set_menu(self, menu):
        if HAS_APPINDICATOR:
            self._menu = menu
            menu._menu.show_all()
            self._icon.set_menu(menu._menu)
        else:
            self._menu = menu

    def set_callback(self, callback):
        self._callback = callback

    def run(self):
        gtk.main()
        gtk.threads_leave()

    def destroy(self):
        if not HAS_APPINDICATOR:
            self._icon.set_visible(False)
        gtk.main_quit()
