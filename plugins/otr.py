"""

This plugin implements `Off The Record messaging`_.

This is a plugin used to encrypt one-to-one conversation using the OTR
encryption method. You can use it if you want good privacy, deniability,
authentication, and strong secrecy. Without this encryption, your messages
are encrypted **at least** from your client (poezio) to your server. The
message is decrypted by your server and you cannot control the encryption
method of your messages from your server to your contact’s server (unless
you are your own server’s administrator), nor from your contact’s server
to your contact’s client.

This plugin does end-to-end encryption. This means that **only** your contact can
decrypt your messages, and it is fully encrypted during **all** its travel
through the internet.

Note that if you are having an encrypted conversation with a contact, you can
**not** send XHTML-IM messages to him (or correct messages, or anything more than
raw text). They will be removed and be replaced by plain text messages.

This is a limitation of the OTR protocol, and it will never be fixed. Some clients
like Pidgin-OTR try do do magic stuff with html unescaping inside the OTR body, and
it is not pretty.

Installation
------------

To use the OTR plugin, you must first install pure-python-otr and pycrypto
(for python3).

You have to install it from the git because a few issues were
found with the python3 compatibility while writing this plugin,
and the fixes did not make it into a stable release yet.

Install the python module:

.. code-block:: bash

    git clone https://github.com/afflux/pure-python-otr.git
    cd pure-python-otr
    python3 setup.py install --user

You can also use pip in a virtualenv (built-in as pyvenv_ with python since 3.3)
with the requirements.txt at the root of the poezio directory.


Usage
-----

Command added to Conversation Tabs and Private Tabs:

.. glossary::

    /otr
        **Usage:** ``/otr [start|refresh|end|fpr|ourfpr|trust|untrust]``

        This command is used to manage an OTR private session.

        - The ``start`` (or ``refresh``) command starts or refreshs a private OTR session
        - The ``end`` command ends a private OTR session
        - The ``fpr`` command gives you the fingerprint of the key of the remote entity
        - The ``ourfpr`` command gives you the fingerprint of your own key
        - The ``trust`` command marks the current remote key as trusted for the current remote JID
        - The ``untrust`` command removes that trust
        - Finally, the ``drop`` command is used if you want to delete your private key (not recoverable).

        .. warning::

            With ``drop``, the private key is only removed from the filesystem,
            *NOT* with multiple rewrites in a secure manner, you should do that
            yourself if you want to be sure.


To use OTR, make sure the plugin is loaded (if not, then do ``/load otr``).

A simple workflow looks like this:

.. code-block:: none

    /otr start

The status of the OTR encryption should appear in the bar between the chat and
the input as ``OTR: encrypted``.

Then you use ``fpr``/``ourfpr`` to check the fingerprints, and confirm your respective
identities out-of-band.

You can then use

.. code-block:: none

    /otr trust

To set the key as trusted, which will be shown when you start or refresh a conversation
(the trust status will be in a bold font and if the key is untrusted, the remote fingerprint
will be shown).

Once you’re done, end the OTR session with

.. code-block:: none

    /otr end

Files
-----

This plugin creates trust files complatible with libotr and the files produced by gajim.


The files are located in :file:`$XDG_DATA_HOME/poezio/otr/` by default (so
:file:`~/.local/share/poezio/otr` in most cases).

Two files are created:

- An account_jid.key3 (:file:`example@example.com.key3`) file, which contains the private key
- An account_jid.fpr (:file:`example@example.com.fpr`) file, which contains the list of trusted
  (or untrusted) JIDs and keys.

Configuration
-------------

.. glossary::
    :sorted:

    decode_xhtml
        **Default:** ``true``

        Decode embedded XHTML.

    decode_entities
        **Default:** ``true``

        Decode XML and HTML entities (like ``&amp;``) even when the
        document isn't valid (if it is valid, it will be decoded even
        without this option).

    decode_newlines
        **Default:** ``true``

        Decode ``<br/>`` and ``<br>`` tags even when the document
        isn't valid (if it is valid, it will be decoded even
        without this option for ``<br/>``, and ``<br>`` will make
        the document invalid anyway).

    keys_dir
        **Default:** ``$XDG_DATA_HOME/poezio/otr``

        The directory in which you want keys and fpr to be stored.

    allow_v2
        **Default:** ``true``

        Allow OTRv2

    allow_v1
        **Default:** ``false``

        Allow OTRv1

    timeout
        **Default:** ``3``

        The number of seconds poezio will wait until notifying you
        that the OTR session was not established. A negative or null
        value will disable this notification.

    log
        **Default:** false

        Log conversations (OTR start/end marker, and messages).

The :term:`allow_v1`, :term:`allow_v2`, :term:`decode_xhtml`, :term:`decode_entities`
and :term:`log` configuration parameters are tab-specific.

Important details
-----------------

The OTR session is considered for a full JID (e.g. toto@example/**client1**),
but the trust is set with a bare JID (e.g. toto@example). This is important
in the case of Private Chats (in a chatroom), since you cannot always get the
real JID of your contact (or check if the same nick is used by different people).

.. _Off The Record messaging: http://wiki.xmpp.org/web/OTR
.. _pyvenv: https://docs.python.org/3/using/scripts.html#pyvenv-creating-virtual-environments

"""

from gettext import gettext as _
import potr
import logging

log = logging.getLogger(__name__)
import os
import html
import curses

from potr.context import NotEncryptedError, UnencryptedMessage, ErrorReceived, NotOTRMessage,\
        STATE_ENCRYPTED, STATE_PLAINTEXT, STATE_FINISHED, Context, Account, crypt

import xhtml
from common import safeJID
from config import config
from plugin import BasePlugin
from tabs import ConversationTab, DynamicConversationTab, PrivateTab
from theming import get_theme, dump_tuple

OTR_DIR = os.path.join(os.getenv('XDG_DATA_HOME') or
        '~/.local/share', 'poezio', 'otr')

POLICY_FLAGS = {
        'ALLOW_V1':False,
        'ALLOW_V2':True,
        'REQUIRE_ENCRYPTION': False,
        'SEND_TAG': True,
        'WHITESPACE_START_AKE': True,
        'ERROR_START_AKE': True
}

log = logging.getLogger(__name__)


def hl(tab):
    if tab.state != 'current':
        tab.state = 'private'

    conv_jid = safeJID(tab.name)
    if 'private' in config.get('beep_on', 'highlight private').split():
        if not config.get_by_tabname('disable_beep', conv_jid.bare, default=False):
            curses.beep()

class PoezioContext(Context):
    def __init__(self, account, peer, xmpp, core):
        super(PoezioContext, self).__init__(account, peer)
        self.xmpp = xmpp
        self.core = core
        self.flags = {}
        self.trustName = safeJID(peer).bare

    def getPolicy(self, key):
        if key in self.flags:
            return self.flags[key]
        else:
            return False

    def inject(self, msg, appdata=None):
        message = self.xmpp.make_message(mto=self.peer,
                                         mbody=msg.decode('ascii'),
                                         mtype='chat')
        message.enable('carbon_private')
        message.send()

    def setState(self, newstate):
        color_jid = '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID)
        color_info = '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT)

        tab = self.core.get_tab_by_name(self.peer)
        if not tab:
            tab = self.core.get_tab_by_name(safeJID(self.peer).bare,
                                            DynamicConversationTab)
            if tab and not tab.locked_resource == safeJID(self.peer).resource:
                tab = None
        if self.state == STATE_ENCRYPTED:
            if newstate == STATE_ENCRYPTED:
                log.debug('OTR conversation with %s refreshed', self.peer)
                if tab:
                    if self.getCurrentTrust():
                        msg = _('%(info)sRefreshed \x19btrusted\x19o%(info)s'
                                ' OTR conversation with %(jid_c)s%(jid)s') % {
                                        'info': color_info,
                                        'jid_c': color_jid,
                                        'jid': self.peer
                                        }
                        tab.add_message(msg, typ=self.log)
                    else:
                        msg = _('%(info)sRefreshed \x19buntrusted\x19o%(info)s'
                                ' OTR conversation with %(jid_c)s%(jid)s'
                                '%(info)s, key: \x19o%(key)s') % {
                                   'jid': self.peer,
                                   'key': self.getCurrentKey(),
                                   'info': color_info,
                                   'jid_c': color_jid}

                        tab.add_message(msg, typ=self.log)
                    hl(tab)
            elif newstate == STATE_FINISHED or newstate == STATE_PLAINTEXT:
                log.debug('OTR conversation with %s finished', self.peer)
                if tab:
                    tab.add_message('%sEnded OTR conversation with %s%s' % (
                                        color_info, color_jid, self.peer),
                                    typ=self.log)
                    hl(tab)
        else:
            if newstate == STATE_ENCRYPTED:
                if tab:
                    if self.getCurrentTrust():
                        msg = _('%(info)sStarted a \x19btrusted\x19o%(info)s '
                                'OTR conversation with %(jid_c)s%(jid)s') % {
                                        'jid': self.peer,
                                        'info': color_info,
                                        'jid_c': color_jid}
                        tab.add_message(msg, typ=self.log)
                    else:
                        msg = _('%(info)sStarted an \x19buntrusted\x19o%(info)s'
                                ' OTR conversation with %(jid_c)s%(jid)s'
                                '%(info)s, key: \x19o%(key)s') % {
                                        'jid': self.peer,
                                        'key': self.getCurrentKey(),
                                        'info': color_info,
                                        'jid_c': color_jid}
                        tab.add_message(msg, typ=self.log)
                    hl(tab)

        log.debug('Set encryption state of %s to %s', self.peer, states[newstate])
        super(PoezioContext, self).setState(newstate)
        if tab:
            self.core.refresh_window()
            self.core.doupdate()

class PoezioAccount(Account):

    def __init__(self, jid, key_dir):
        super(PoezioAccount, self).__init__(jid, 'xmpp', 1024)
        self.key_dir = os.path.join(key_dir, jid)

    def load_privkey(self):
        try:
            with open(self.key_dir + '.key3', 'rb') as keyfile:
                return potr.crypt.PK.parsePrivateKey(keyfile.read())[0]
        except:
            log.error('Error in load_privkey', exc_info=True)

    def drop_privkey(self):
        try:
            os.remove(self.key_dir + '.key3')
        except:
            log.exception('Error in drop_privkey (removing %s)', self.key_dir + '.key3')
        self.privkey = None

    def save_privkey(self):
        try:
            with open(self.key_dir + '.key3', 'xb') as keyfile:
                keyfile.write(self.getPrivkey().serializePrivateKey())
        except:
            log.error('Error in save_privkey', exc_info=True)

    def load_trusts(self):
        try:
            with open(self.key_dir + '.fpr', 'r') as fpr_fd:
                for line in fpr_fd:
                    ctx, acc, proto, fpr, trust = line[:-1].split('\t')

                    if acc != self.name or proto != 'xmpp':
                        continue
                    jid = safeJID(ctx).bare
                    if not jid:
                        continue
                    self.setTrust(jid, fpr, trust)
        except:
            log.error('Error in load_trusts', exc_info=True)

    def save_trusts(self):
        try:
            with open(self.key_dir + '.fpr', 'w') as fpr_fd:
                for uid, trusts in self.trusts.items():
                    for fpr, trustVal in trusts.items():
                        fpr_fd.write('\t'.join(
                                (uid, self.name, 'xmpp', fpr, trustVal)))
                        fpr_fd.write('\n')
        except:
            log.exception('Error in save_trusts', exc_info=True)

    saveTrusts = save_trusts
    loadTrusts = load_trusts
    loadPrivkey = load_privkey
    savePrivkey = save_privkey

states = {
        STATE_PLAINTEXT: 'plaintext',
        STATE_ENCRYPTED: 'encrypted',
        STATE_FINISHED: 'finished',
}

class Plugin(BasePlugin):

    def init(self):
        # set the default values from the config
        allow_v2 = self.config.get('allow_v2', True)
        POLICY_FLAGS['ALLOW_V2'] = allow_v2
        allow_v1 = self.config.get('allow_v1', False)
        POLICY_FLAGS['ALLOW_v1'] = allow_v1

        global OTR_DIR
        OTR_DIR = os.path.expanduser(self.config.get('keys_dir', '') or OTR_DIR)
        try:
            os.makedirs(OTR_DIR)
        except OSError as e:
            if e.errno != 17:
                self.api.information('The OTR-specific folder could not be created'
                        ' poezio will be unable to save keys and trusts', 'OTR')

        except:
            self.api.information('The OTR-specific folder could not be created'
                    ' poezio will be unable to save keys and trusts', 'OTR')

        self.api.add_event_handler('conversation_msg', self.on_conversation_msg)
        self.api.add_event_handler('private_msg', self.on_conversation_msg)
        self.api.add_event_handler('conversation_say_after', self.on_conversation_say)
        self.api.add_event_handler('private_say_after', self.on_conversation_say)

        ConversationTab.add_information_element('otr', self.display_encryption_status)
        PrivateTab.add_information_element('otr', self.display_encryption_status)

        self.account = PoezioAccount(self.core.xmpp.boundjid.bare, OTR_DIR)
        self.account.load_trusts()
        self.contexts = {}
        usage = '[start|refresh|end|fpr|ourfpr|drop|trust|untrust]'
        shortdesc = 'Manage an OTR conversation'
        desc = ('Manage an OTR conversation.\n'
                'start/refresh: Start or refresh a conversation\n'
                'end: End a conversation\n'
                'fpr: Show the fingerprint of the key of the remote user\n'
                'ourfpr: Show the fingerprint of your own key\n'
                'drop: Remove the current key (FOREVER)\n'
                'trust: Set this key for this contact as trusted\n'
                'untrust: Remove the trust for the key of this contact\n')
        self.api.add_tab_command(ConversationTab, 'otr', self.command_otr,
                help=desc,
                usage=usage,
                short=shortdesc,
                completion=self.completion_otr)
        self.api.add_tab_command(PrivateTab, 'otr', self.command_otr,
                help=desc,
                usage=usage,
                short=shortdesc,
                completion=self.completion_otr)

    def cleanup(self):
        for context in self.contexts.values():
            context.disconnect()

        ConversationTab.remove_information_element('otr')
        PrivateTab.remove_information_element('otr')

    def get_context(self, jid):
        jid = safeJID(jid).full
        if not jid in self.contexts:
            flags = POLICY_FLAGS.copy()
            policy = self.config.get_by_tabname('encryption_policy', jid, default='ondemand').lower()
            logging_policy = self.config.get_by_tabname('log', jid, default='false').lower()
            allow_v2 = self.config.get_by_tabname('allow_v2', jid, default='true').lower()
            flags['ALLOW_V2'] = (allow_v2 != 'false')
            allow_v1 = self.config.get_by_tabname('allow_v1', jid, default='false').lower()
            flags['ALLOW_V1'] = (allow_v1 == 'true')
            self.contexts[jid] = PoezioContext(self.account, jid, self.core.xmpp, self.core)
            self.contexts[jid].log = 1 if logging_policy != 'false' else 0
            self.contexts[jid].flags = flags
        return self.contexts[jid]

    def on_conversation_msg(self, msg, tab):
        color_jid = '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID)
        color_info = '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        try:
            ctx = self.get_context(msg['from'])
            txt, tlvs = ctx.receiveMessage(msg["body"].encode('utf-8'))
        except UnencryptedMessage as err:
            # received an unencrypted message inside an OTR session
            text = _('%(info)sThe following message from %(jid_c)s%(jid)s'
                     '%(info)s was \x19bnot\x19o%(info)s encrypted:'
                     '\x19o\n%(msg)s') % {
                             'info': color_info,
                             'jid_c': color_jid,
                             'jid': msg['from'],
                             'msg': err.args[0].decode('utf-8')}
            tab.add_message(text, jid=msg['from'],
                            typ=0)
            del msg['body']
            del msg['html']
            hl(tab)
            self.core.refresh_window()
            return
        except ErrorReceived as err:
            # Received an OTR error
            text = _('%(info)sReceived the following error from '
                     '%(jid_c)s%(jid)s%(info)s:\x19o %(err)s') % {
                             'jid': msg['from'],
                             'err': err.args[0],
                             'info': color_info,
                             'jid_c': color_jid}

            tab.add_message(text, typ=0)
            del msg['body']
            del msg['html']
            hl(tab)
            self.core.refresh_window()
            return
        except NotOTRMessage as err:
            # ignore non-otr messages
            # if we expected an OTR message, we would have
            # got an UnencryptedMesssage
            # but do an additional check because of a bug with py3k
            if ctx.state != STATE_PLAINTEXT or ctx.getPolicy('REQUIRE_ENCRYPTION'):

                text = _('%(info)sThe following message from '
                         '%(jid_c)s%(jid)s%(info)s was \x19b'
                         'not\x19o%(info)s encrypted:\x19o\n%(msg)s') % {
                                 'jid': msg['from'],
                                 'msg': err.args[0].decode('utf-8'),
                                 'info': color_info,
                                 'jid_c': color_jid}
                tab.add_message(text, jid=msg['from'],
                                typ=ctx.log)
                del msg['body']
                del msg['html']
                hl(tab)
                self.core.refresh_window()
                return
            return
        except NotEncryptedError as err:
            text = _('%(info)sAn encrypted message from %(jid_c)s%(jid)s'
                     '%(info)s was received but is unreadable, as you are'
                     ' not currently communicating privately.') % {
                             'info': color_info,
                             'jid_c': color_jid,
                             'jid': msg['from']}
            tab.add_message(text, jid=msg['from'],
                            typ=0)
            hl(tab)
            del msg['body']
            del msg['html']
            self.core.refresh_window()
            return
        except crypt.InvalidParameterError:
            tab.add_message('%sThe message from %s%s%s could not be decrypted.'
                            % (color_info, color_jid, msg['from'], color_info),
                            jid=msg['from'], typ=0)
            hl(tab)
            del msg['body']
            del msg['html']
            self.core.refresh_window()
            return
        except:
            tab.add_message('%sAn unspecified error in the OTR plugin occured'
                            % color_info,
                            typ=0)
            log.error('Unspecified error in the OTR plugin', exc_info=True)
            return

        # remove xhtml
        del msg['html']
        del msg['body']

        if not txt:
            return
        if isinstance(tab, PrivateTab):
            user = tab.parent_muc.get_user_by_name(msg['from'].resource)
            nick_color = None
        else:
            user = None
            nick_color = get_theme().COLOR_REMOTE_USER

        body = txt.decode()
        decode_entities = self.config.get_by_tabname('decode_entities',
                                                     msg['from'].bare,
                                                     default=True)
        decode_newlines = self.config.get_by_tabname('decode_newlines',
                                                     msg['from'].bare,
                                                     default=True)
        if self.config.get_by_tabname('decode_xhtml', msg['from'].bare, default=True):
            try:
                body = xhtml.xhtml_to_poezio_colors(body, force=True)
            except Exception:
                if decode_entities:
                    body = html.unescape(body)
                if decode_newlines:
                    body = body.replace('<br/>', '\n').replace('<br>', '\n')
        else:
            if decode_entities:
                body = html.unescape(body)
            if decode_newlines:
                body = body.replace('<br/>', '\n').replace('<br>', '\n')
        tab.add_message(body, nickname=tab.nick, jid=msg['from'],
                        forced_user=user, typ=ctx.log,
                        nick_color=nick_color)
        hl(tab)
        self.core.refresh_window()
        del msg['body']

    def find_encrypted_context_with_matching(self, bare_jid):
        for ctx in self.contexts:
            if safeJID(ctx).bare == bare_jid and self.contexts[ctx].state == STATE_ENCRYPTED:
                return self.contexts[ctx]
        return None

    def on_conversation_say(self, msg, tab):
        """
        On message sent
        """
        if isinstance(tab, DynamicConversationTab) and tab.locked_resource:
            jid = safeJID(tab.name)
            jid.resource = tab.locked_resource
            name = jid.full
        else:
            name = tab.name
            jid = safeJID(tab.name)

        ctx = self.contexts.get(name)
        if isinstance(tab, DynamicConversationTab) and not tab.locked_resource:
            log.debug('Unlocked tab %s found, falling back to the first encrypted chat we find.', name)
            ctx = self.find_encrypted_context_with_matching(jid.bare)

        if ctx and ctx.state == STATE_ENCRYPTED:
            ctx.sendMessage(0, msg['body'].encode('utf-8'))
            if not tab.send_chat_state('active'):
                tab.send_chat_state('inactive', always_send=True)

            tab.add_message(msg['body'],
                    nickname=self.core.own_nick or tab.own_nick,
                    nick_color=get_theme().COLOR_OWN_NICK,
                    identifier=msg['id'],
                    jid=self.core.xmpp.boundjid,
                    typ=ctx.log)
            # remove everything from the message so that it doesn’t get sent
            del msg['body']
            del msg['replace']
            del msg['html']

    def display_encryption_status(self, jid):
        context = self.get_context(jid)
        if safeJID(jid).bare == jid and context.state != STATE_ENCRYPTED:
            ctx = self.find_encrypted_context_with_matching(jid)
            if ctx:
                context = ctx
        state = states[context.state]
        return ' OTR: %s' % state

    def command_otr(self, arg):
        """
        /otr [start|refresh|end|fpr|ourfpr]
        """
        arg = arg.strip()
        tab = self.api.current_tab()
        name = tab.name
        color_jid = '\x19%s}' % dump_tuple(get_theme().COLOR_MUC_JID)
        color_info = '\x19%s}' % dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
        color_normal = '\x19%s}' % dump_tuple(get_theme().COLOR_NORMAL_TEXT)
        if isinstance(tab, DynamicConversationTab) and tab.locked_resource:
            name = safeJID(tab.name)
            name.resource = tab.locked_resource
            name = name.full
        if arg == 'end': # close the session
            context = self.get_context(name)
            context.disconnect()
            if isinstance(tab, DynamicConversationTab) and not tab.locked_resource:
                ctx = self.find_encrypted_context_with_matching(safeJID(name).bare)
                ctx.disconnect()

        elif arg == 'start' or arg == 'refresh':
            otr = self.get_context(name)
            secs = self.config.get('timeout', 3)
            if isinstance(tab, DynamicConversationTab) and tab.locked_resource:
                was_locked = True
            else:
                was_locked = False
            def notify_otr_timeout():
                nonlocal otr
                if isinstance(tab, DynamicConversationTab) and not was_locked:
                    if tab.locked_resource:
                        name = safeJID(tab.name)
                        name.resource = tab.locked_resource
                        name = name.full
                        otr = self.get_context(name)
                if otr.state != STATE_ENCRYPTED:
                    text = _('%(jid_c)s%(jid)s%(info)s did not enable'
                             ' OTR after %(sec)s seconds.') % {
                                     'jid': tab.name,
                                     'info': color_info,
                                     'jid_c': color_jid,
                                     'sec': secs}
                    tab.add_message(text, typ=0)
                    self.core.refresh_window()
            if secs > 0:
                event = self.api.create_delayed_event(secs, notify_otr_timeout)
                self.api.add_timed_event(event)
            self.core.xmpp.send_message(mto=name, mtype='chat',
                mbody=self.contexts[name].sendMessage(0, b'?OTRv?').decode())
            text = _('%(info)sOTR request to %(jid_c)s%(jid)s%(info)s sent.') % {
                         'jid': tab.name,
                         'info': color_info,
                         'jid_c': color_jid}
            tab.add_message(text, typ=0)
        elif arg == 'ourfpr':
            fpr = self.account.getPrivkey()
            text = _('%(info)sYour OTR key fingerprint is %(norm)s%(fpr)s.') % {
                         'jid': tab.name,
                         'info': color_info,
                         'norm': color_normal,
                         'fpr': fpr}
            tab.add_message(text, typ=0)
        elif arg == 'fpr':
            if name in self.contexts:
                ctx = self.contexts[name]
                if ctx.getCurrentKey() is not None:
                    text = _('%(info)sThe key fingerprint for %(jid_c)s'
                             '%(jid)s%(info)s is %(norm)s%(fpr)s%(info)s.') % {
                                 'jid': tab.name,
                                 'info': color_info,
                                 'norm': color_normal,
                                 'jid_c': color_jid,
                                 'fpr': ctx.getCurrentKey()}
                    tab.add_message(text, typ=0)
                else:
                    text = _('%(jid_c)s%(jid)s%(info)s has no'
                             ' key currently in use.') % {
                                 'jid': tab.name,
                                 'info': color_info,
                                 'jid_c': color_jid}
                    tab.add_message(text, typ=0)
        elif arg == 'drop':
            # drop the privkey (and obviously, end the current conversations before that)
            for context in self.contexts.values():
                if context.state not in (STATE_FINISHED, STATE_PLAINTEXT):
                    context.disconnect()
            self.account.drop_privkey()
            tab.add_message('%sPrivate key dropped.' % color_info, typ=0)
        elif arg == 'trust':
            ctx = self.get_context(name)
            key = ctx.getCurrentKey()
            if key:
                fpr = key.cfingerprint()
            else:
                return
            if not ctx.getCurrentTrust():
                ctx.setTrust(fpr, 'verified')
                self.account.saveTrusts()
                text = _('%(info)sYou added %(jid_c)s%(jid)s%(info)s with key '
                         '\x19o%(key)s%(info)s to your trusted list.') % {
                                 'jid': ctx.trustName,
                                 'key': key,
                                 'info': color_info,
                                 'jid_c': color_jid}
                tab.add_message(text, typ=0)
        elif arg == 'untrust':
            ctx = self.get_context(name)
            key = ctx.getCurrentKey()
            if key:
                fpr = key.cfingerprint()
            else:
                return
            if ctx.getCurrentTrust():
                ctx.setTrust(fpr, '')
                self.account.saveTrusts()
                text = _('%(info)sYou removed %(jid_c)s%(jid)s%(info)s with '
                         'key \x19o%(key)s%(info)s from your trusted list.') % {
                                 'jid': ctx.trustName,
                                 'key': key,
                                 'info': color_info,
                                 'jid_c': color_jid}

                tab.add_message(text, typ=0)
        self.core.refresh_window()

    def completion_otr(self, the_input):
        comp = ['start', 'fpr', 'ourfpr', 'refresh', 'end', 'trust', 'untrust']
        return the_input.new_completion(comp, 1, quotify=False)

