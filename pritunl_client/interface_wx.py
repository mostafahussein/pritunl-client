from pritunl_client.constants import *
from pritunl_client.exceptions import *

if PLATFORM == SHELL:
    raise TypeError('Interface not supported for platform')

import wx
import collections
import sys

_mappings = {
    BUTTONS_OK: wx.OK,
    BUTTONS_CANCEL: wx.CANCEL,
    BUTTONS_OK_CANCEL: wx.OK | wx.CANCEL,
    MESSAGE_INFO: wx.ICON_INFORMATION,
    MESSAGE_QUESTION: wx.ICON_QUESTION,
    MESSAGE_ERROR: wx.ICON_ERROR,
    MESSAGE_LOADING: wx.ICON_INFORMATION,
}

class _App(wx.App):
    def MainLoop(self):
        evt_loop = wx.GUIEventLoop()
        wx.EventLoop.SetActive(evt_loop)

        while not self.interupt:
            while evt_loop.Pending():
                evt_loop.Dispatch()
            wx.MilliSleep(50)
            evt_loop.ProcessIdle()

    def OnInit(self):
        self.interupt = False
        return True

class _TaskBarIcon(wx.TaskBarIcon):
    def CreatePopupMenu(self):
        return self._menu._build()

def add_idle_call(call):
    wx.CallAfter(call)

def lookup_icon(name):
    return {
        'pritunl_client': LOGO_DEFAULT_PATH,
        'pritunl_client_connected': CONNECTED_LOGO_DEFAULT_PATH,
        'pritunl_client_disconnected': DISCONNECTED_LOGO_DEFAULT_PATH,
    }[name]

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
        self._interrupt = False

    def set_title(self, title):
        self._title = title

    def set_icon(self, icon_path):
        self._icon = icon_path

    def set_message(self, message):
        self._message = message.replace('<b>', '').replace('</b>', '')

    def set_message_secondary(self, message):
        self._message_secondary = message.replace(
            '<b>', '').replace('</b>', '')

    def set_image(self, image_path):
        self._image_path = image_path

    def set_type(self, type):
        self._type = type

    def set_buttons(self, buttons):
        self._buttons = buttons

    def run(self):
        if self._type == MESSAGE_LOADING:
            message = self._message + ('\n\n' + self._message_secondary
                if self._message_secondary else '')
            self._dialog = wx.ProgressDialog(
                parent=None,
                title=self._title,
                message=message,
                style=wx.PD_CAN_ABORT)
            self._dialog.Pulse(message)

            while not self._interrupt:
                cont, skip = self._dialog.UpdatePulse()
                if not cont:
                    return False
                wx.MilliSleep(50)
                wx.Yield()

        else:
            self._dialog = wx.MessageDialog(
                parent=None,
                message=self._message + ('\n\n' + self._message_secondary
                    if self._message_secondary else ''),
                caption=self._title,
                style=_mappings[self._buttons] | _mappings[self._type])

            response = self._dialog.ShowModal()
            if response == wx.ID_OK:
                return True
            elif response == wx.ID_CANCEL:
                return False

    def destroy(self):
        self._dialog.Destroy()

    def close(self):
        if self._type == MESSAGE_LOADING:
            self._interrupt = True
        else:
            self.destroy()

class InputDialog:
    def __init__(self):
        self._dialog = None
        self._title = None
        self._message = None
        self._message_secondary = None
        self._icon = None
        self._label = None
        self._entry_width = None

    def set_title(self, title):
        self._title = title

    def set_icon(self, icon_path):
        self._icon = icon_path

    def set_message(self, message):
        self._message = message.replace('<b>', '').replace('</b>', '')

    def set_message_secondary(self, message):
        self._message_secondary = message.replace(
            '<b>', '').replace('</b>', '')

    def set_input_label(self, label):
        self._label = label

    def set_input_width(self, width):
        self._entry_width = width

    def set_visibility(self, visibility):
        pass

    def run(self):
        self._dialog = wx.TextEntryDialog(
            parent=None,
            message=self._message_secondary + (
                '\n\n' + self._label if self._label else ''),
            caption=self._title)
        self._dialog.SetMinSize(self._dialog.GetSize())
        self._dialog.SetMaxSize(self._dialog.GetSize())
        response = self._dialog.ShowModal()
        if response == wx.ID_OK:
            return self._dialog.GetValue()

    def destroy(self):
        self._dialog.Destroy()

    def close(self):
        self.destroy()

class FileChooserDialog:
    def __init__(self):
        self._title = None
        self._icon = None
        self._filters = collections.defaultdict(lambda: [])

    def set_title(self, title):
        self._title = title

    def set_icon(self, icon_path):
        self._icon = icon_path

    def add_filter(self, name, pattern):
        self._filters[name].append(pattern)

    def run(self):
        wildcards = []

        for filter_name in self._filters:
            wildcards.append('%s (%s)|%s' % (filter_name,
                ', '.join(self._filters[filter_name]),
                ';'.join(self._filters[filter_name])))

        self._dialog = wx.FileDialog(
            parent=None,
            message=self._title,
            wildcard='|'.join(wildcards))
        response = self._dialog.ShowModal()
        if response == wx.ID_OK:
            return self._dialog.GetPath()

    def destroy(self):
        self._dialog.Destroy()

    def close(self):
        self.destroy()

class Menu:
    def __init__(self):
        self._label = None
        self._items = []

    def _build(self, root_menu=None):
        menu = wx.Menu()
        root_menu = root_menu or menu
        for menu_item in self._items:
            if isinstance(menu_item, Menu):
                sub_menu = menu_item._build(root_menu)
                menu.AppendMenu(wx.NewId(), menu_item._label, sub_menu, '')
            else:
                menu_item._build(menu, root_menu)
        return menu

    def set_label(self, label):
        self._label = label

    def add_item(self, item):
        self._items.append(item)

class MenuItem:
    def __init__(self):
        self._callback = None
        self._callback_data = None
        self._label = ''
        self._state = True

    def _build(self, menu, root_menu):
        item_id = wx.NewId()
        menu.Append(item_id, self._label, '')
        if not self._state:
            menu.Enable(item_id, False)
        menu.Bind(wx.EVT_MENU, self._on_activate, id=item_id)
        root_menu.Bind(wx.EVT_MENU, self._on_activate, id=item_id)

    def _on_activate(self, event):
        if self._callback:
            if self._callback_data:
                self._callback(self._callback_data)
            else:
                self._callback()

    def set_label(self, label):
        self._label = label

    def get_label(self):
        return self._label

    def set_state(self, state):
        self._state = state

    def set_callback(self, callback, data=None):
        self._callback = callback
        self._callback_data = data

class CheckMenuItem:
    def __init__(self):
        self._callback = None
        self._callback_data = None
        self._label = ''
        self._state = True
        self._active = False

    def _build(self, menu, root_menu):
        item_id = wx.NewId()
        menu.AppendCheckItem(item_id, self._label, '')
        if not self._state:
            menu.Enable(item_id, False)
        if self._active:
            menu.Check(item_id, True)
        menu.Bind(wx.EVT_MENU, self._on_activate, id=item_id)
        root_menu.Bind(wx.EVT_MENU, self._on_activate, id=item_id)

    def _on_activate(self, event):
        if self._callback:
            if self._callback_data:
                self._callback(self._callback_data)
            else:
                self._callback()

    def _on_activate(self, event):
        if self._callback:
            if self._callback_data:
                self._callback(self._callback_data)
            else:
                self._callback()

    def set_label(self, label):
        self._label = label

    def get_label(self):
        return self._label

    def set_state(self, state):
        self._state = state

    def set_active(self, state):
        self._active = state

    def set_callback(self, callback, data=None):
        self._callback = callback
        self._callback_data = data

class SeparatorMenuItem:
    def __init__(self):
        pass

    def _build(self, menu, root_menu):
        menu.AppendSeparator()

class StatusIconApp:
    def __init__(self):
        self._tooltip = ''
        self._icon_path = None
        self._callback = None
        self._app = _App(False)
        self._icon = _TaskBarIcon()
        self._icon.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self._on_activate)

    def _on_activate(self, event):
        pass

    def set_tooltip(self, label):
        self._tooltip = label
        if self._icon_path:
            self.set_icon(self._icon_path)

    def set_icon(self, icon_path):
        icon = wx.IconFromBitmap(wx.Bitmap(icon_path))
        self._icon.SetIcon(icon, self._tooltip)

    def set_menu(self, menu):
        self._icon._menu = menu

    def set_callback(self, callback):
        self._callback = callback

    def run(self):
        self._app.MainLoop()

    def destroy(self):
        self._icon.RemoveIcon()
        self._icon.Destroy()
        self._app.Destroy()
        sys.exit(0)
