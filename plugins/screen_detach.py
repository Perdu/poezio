"""
This plugin will set your status to **away** if you detach your screen.

The default behaviour is to check for both tmux and screen (in that order).

Configuration options
---------------------

.. glossary::

    use_screen
        **Default:** ``true``

        Try to find an attached screen.

    use_tmux
        **Default:** ``true``

        Try to find and attached tmux.

"""

from plugin import BasePlugin
import os
import stat
import pyinotify
import asyncio

DEFAULT_CONFIG = {
        'screen_detach': {
            'use_tmux': True,
            'use_screen': True
        }
}


# overload if this is not how your stuff
# is configured
try:
    LOGIN = os.getlogin()
    LOGIN_TMUX = LOGIN
except Exception:
    LOGIN = os.getenv('USER')
    LOGIN_TMUX = os.getuid()

SCREEN_DIR = '/var/run/screen/S-%s' % LOGIN
TMUX_DIR = '/tmp/tmux-%s' % LOGIN_TMUX

def find_screen(path):
    for f in os.listdir(path):
        path = os.path.join(path, f)
        if screen_attached(path):
            return path

def screen_attached(socket):
    return (os.stat(socket).st_mode & stat.S_IXUSR) != 0

class Plugin(BasePlugin, pyinotify.Notifier):

    default_config = DEFAULT_CONFIG

    def init(self):
        sock_path = None
        if self.config.get('use_tmux'):
            sock_path = find_screen(TMUX_DIR)
        if sock_path is None and config.get('use_screen'):
            sock_path = find_screen(SCREEN_DIR)

        # Only actually do something if we found an attached screen (assuming only one)
        if sock_path:
            self.attached = True
            wm = pyinotify.WatchManager()
            wm.add_watch(sock_path, pyinotify.EventsCodes.ALL_FLAGS['IN_ATTRIB'])
            pyinotify.Notifier.__init__(self, wm, default_proc_fun=HandleScreen(plugin=self))
            asyncio.get_event_loop().add_reader(self._fd, self.process)

    def process(self):
        self.read_events()
        self.process_events()

    def cleanup(self):
        asyncio.get_event_loop().remove_reader(self._fd)

    def update_screen_state(self, socket):
        attached = screen_attached(socket)
        if attached != self.attached:
            self.attached = attached
            status = 'available' if self.attached else 'away'
            self.core.command_status(status)


class HandleScreen(pyinotify.ProcessEvent):
    def my_init(self, **kwargs):
        self.plugin = kwargs['plugin']

    def process_IN_ATTRIB(self, event):
        self.plugin.update_screen_state(event.path)
