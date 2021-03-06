"""
A tab listing the ad-hoc commands on a specific JID.  The user can
select one of them and start executing it, or just close the tab and do
nothing.
"""

from gettext import gettext as _

import logging
log = logging.getLogger(__name__)

from . import ListTab

from slixmpp.plugins.xep_0030.stanza.items import DiscoItem

class AdhocCommandsListTab(ListTab):
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, jid):
        ListTab.__init__(self, jid.full,
                         "“Enter”: execute selected command.",
                         _('Ad-hoc commands of JID %s (Loading)') % jid,
                         (('Node', 0), ('Description', 1)))
        self.key_func['^M'] = self.execute_selected_command

    def execute_selected_command(self):
        if not self.listview or not self.listview.get_selected_row():
            return
        node, name, jid = self.listview.get_selected_row()
        session = {'next': self.core.on_next_adhoc_step,
                   'error': self.core.on_adhoc_error}
        self.core.xmpp.plugin['xep_0050'].start_command(jid, node, session)

    def get_columns_sizes(self):
        return {'Node': int(self.width * 3 / 8),
                'Description': int(self.width * 5 / 8)}

    def on_list_received(self, iq):
        """
        Fill the listview with the value from the received iq
        """
        if iq['type'] == 'error':
            self.set_error(iq['error']['type'], iq['error']['code'], iq['error']['text'])
            return
        def get_items():
            substanza = iq['disco_items']
            for item in substanza['substanzas']:
                if isinstance(item, DiscoItem):
                    yield item
        items = [(item['node'], item['name'] or '', item['jid']) for item in get_items()]
        self.listview.set_lines(items)
        self.info_header.message = _('Ad-hoc commands of JID %s') % self.name
        if self.core.current_tab() is self:
            self.refresh()
        else:
            self.state = 'highlight'
            self.refresh_tab_win()
        self.core.doupdate()
