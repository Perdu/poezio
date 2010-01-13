# -*- coding: utf-8 -*-

# Copyright 2009, 2010 Erwan Briand
# Copyright 2010, Florent Le Coz <louizatakk@fedoraproject.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Implementation of the XEP-0045: Multi-User Chat.

from xmpp import NS_MUC_ADMIN
from xmpp.protocol import Presence, Iq, Message, JID

from handler import Handler

def get_stripped_jid(jid):
    """Return the stripped JID (bare representation)"""
    if isinstance(jid, basestring):
        jid = JID(jid)
    return jid.getStripped()

def is_jid(jid):
    """Return True if this is a valid JID"""
    if JID(jid).getNode() != '':
        return True

class MultiUserChat(object):
    def __init__(self, connection):
        self.connection = connection

        self.rooms = []
        self.rn = {}

        self.handler = Handler()
        self.handler.connect('join-room', self.join_room)
        self.handler.connect('quit-room', self.quit_room)
        self.handler.connect('on-disconnected', self.on_disconnect)
        self.handler.connect('xmpp-iq-handler', self.on_iq)
        self.handler.connect('xmpp-presence-handler', self.on_presence)
        self.handler.connect('xmpp-message-handler', self.on_message)
        self.handler.connect('eject-user', self.eject_user)
        self.handler.connect('change-user-role', self.change_role)
        self.handler.connect('change-user-affiliation', self.change_aff)
        self.handler.connect('change-subject', self.change_subject)
        self.handler.connect('change-nick', self.change_nick)

    def join_room(self, room, nick):
        """Join a new room"""
        print "banane"
        self.rooms.append(room)
        self.rn[room] = nick

        pres = Presence(to='%s/%s' % (room, nick))
        self.connection.send(pres)

    def quit_room(self, room, nick):
        """Quit a room"""
        if room is None and nick is None:
            self.on_disconnect()
            return

        pres = Presence(to='%s/%s' % (room, nick), typ='unavailable')
        self.connection.send(pres)

        self.rooms.remove(unicode(room))
        del self.rn[room]

    def on_disconnect(self):
        """Called at disconnection"""
        for room in self.rooms:
            pres = Presence(to='%s/%s' % (room, self.rn[room]),
                            typ='unavailable')
            self.connection.send(pres)

        self.rooms = []
        self.rn = {}

    def on_iq(self, iq):
        """Receive a MUC iq notification"""
        from_ = iq.getFrom().__str__()

        if get_stripped_jid(from_) in self.rooms:
            children = iq.getChildren()
            for child in children:
                if child.getName() == 'error':
                    code = int(child.getAttr('code'))
                    msg = None

                    echildren = child.getChildren()
                    for echild in echildren:
                        if echild.getName() == 'text':
                            msg = echild.getData()

                    self.handler.emit('on-muc-error',
                                      room=from_,
                                      code=code,
                                      msg=msg)



    def on_presence(self, presence):
        """Receive a MUC presence notification"""
        from_ = presence.getFrom().__str__()

        if get_stripped_jid(from_) in self.rooms:
            self.handler.emit('on-muc-presence-changed',
                               jid=from_.encode('utf-8'),
                               priority=presence.getPriority(),
                               show=presence.getShow(),
                               status=presence.getStatus(),
                               stanza=presence
                              )

    def on_message(self, message):
        """Receive a MUC message notification"""
        from_ = message.getFrom().__str__().encode('utf-8')

        if get_stripped_jid(from_) in self.rooms:
            body_ = message.getBody()
            type_ = message.getType()
            subj_ = message.getSubject()
            self.handler.emit('on-muc-message-received',
                              jid=from_, msg=body_, subject=subj_,
                              typ=type_, stanza=message)

    def eject_user(self, room, action, nick, reason):
        """Eject an user from a room"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')

        if action == 'kick':
            item.setAttr('role', 'none')
            if is_jid(nick):
                item.setAttr('jid', nick)
            else:
                item.setAttr('nick', nick)
        elif action == 'ban':
            item.setAttr('affiliation', 'outcast')
            item.setAttr('jid', nick)

        if reason is not None:
            rson = item.addChild('reason')
            rson.setData(reason)

        self.connection.send(iq)

    def change_role(self, room, nick, role):
        """Change the role of an user"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)

        self.connection.send(iq)

    def change_aff(self, room, jid, aff):
        """Change the affiliation of an user"""
        iq = Iq(typ='set', to=room)
        query = iq.addChild('query', namespace=NS_MUC_ADMIN)
        item = query.addChild('item')
        item.setAttr('jid', jid)
        item.setAttr('affiliation', aff)

        self.connection.send(iq)

    def change_subject(self, room, subject):
        """Change the subject of a room"""
        message = Message(typ='groupchat', to=room)
        subj = message.addChild('subject')
        subj.setData(subject)

        self.connection.send(message)

    def change_nick(self, room, nick):
        """Change the nickname"""
        pres = Presence(to='%s/%s' % (room, nick))
        self.connection.send(pres)
