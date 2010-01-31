#!/usr/bin/python
# -*- coding:utf-8 -*-
#
# Copyright 2010 Le Coz Florent <louizatakk@fedoraproject.org>
#
# This file is part of Poezio.
#
# Poezio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Poezio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Poezio.  If not, see <http://www.gnu.org/licenses/>.

import curses
from logging import logger

def get_next_line(str, length):
    pos = str.rfind(' ', 0, length)
    if pos == -1:
        return str[:length], str[length:]
    else:
        return str[:pos], str[pos+1:]

def cut_line(str, length):
    tab = []
    while len(str) > length:
        cut, str = get_next_line(str, length)
        tab.append(cut)
    tab.append(str)
    return tab

class Win(object):
    def __init__(self, height, width, y, x, parent_win):
        self._resize(height, width, y, x, parent_win)

    def _resize(self, height, width, y, x, parent_win):
        self.height, self.width, self.x, self.y = height, width, x, y
        # try:
        self.win = parent_win.subwin(height, width, y, x)
        # except:

    def refresh(self):
        self.win.noutrefresh()

class UserList(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)
        self.win.attron(curses.color_pair(2))
        self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
        self.color_dict = {'moderator': 3,
                           'participant':2,
                           'visitor':4}

    def refresh(self, users):
        self.win.clear()
        self.win.attron(curses.color_pair(2))
        self.win.vline(0, 0, curses.ACS_VLINE, self.height)
        self.win.attroff(curses.color_pair(2))
        y = 0
        for user in users:
            try:
                color = self.color_dict[user.role]
            except:
                color = 1
            self.win.attron(curses.color_pair(color))
            self.win.addstr(y, 1, user.nick)
            self.win.attroff(curses.color_pair(color))
            y += 1
        self.win.refresh()

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

class Info(Win):
    def __init__(self, height, width, y, x, parent_win):
        Win.__init__(self, height, width, y, x, parent_win)

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)

    def refresh(self, room_name):
        self.win.clear()
        self.win.addstr(0, 0, room_name + " "*(self.width-len(room_name)-1)
                        , curses.color_pair(1))
        self.win.refresh()

class TextWin(object):
    """
    keep a dict of {winname: window}
    when a new message is received in a room, just add
    the line at the bottom (and scroll if needed)
    when the current room is changed, just refresh the
    associated window
    When the term is resized, rebuild ALL the windows
    (the complete lines lists are keeped in the Room class)
    """
    def __init__(self, height, width, y, x, parent_win):
        self.height = height
        self.width = width
        self.y = y
        self.x = x
        self.parent_win = parent_win
        self.wins = {}

    def rebuild(self, lines):
        """
        called when the terminal is resized.
        resize all the windows, clear them and rewrite
        the lines in them
        """
        pass # TODO

    def redraw(self, room):
        """
        called when the buffer changes or is
        resized (a complete redraw is needed)
        """
        win = self.wins[room.name].win
        win.clear()
        win.move(0, 0)
        for line in room.lines:
            self.add_line(room, line)

    def refresh(self, winname):
        self.wins[winname].refresh()

    def add_line(self, room, line):
        win = self.wins[room.name].win
        users = room.users
        if len(line) == 2:
            win.addstr('\n['+line[0].strftime("%H:%M:%S") + "] ")
            win.attron(curses.color_pair(8))
            win.addstr(line[1])
            win.attroff(curses.color_pair(8))
        elif len(line) == 3:
            for user in users:
                if user.nick == line[1]:
                    break
            try:
                try:win.addstr('\n['+line[0].strftime("%H:%M:%S") + "] <")
                except:pass         # exception happens on resize, but it doesn't change anything...
                length = len('['+line[0].strftime("%H:%M:%S") + "] <")
                try:win.attron(curses.color_pair(user.color))
                except:pass
                win.addstr(line[1])
                try:win.attroff(curses.color_pair(user.color))
                except:pass
                win.addstr("> ")
                win.addstr(line[2])
            except:pass

    def new_win(self, winname):
        newwin = Win(self.height, self.width, self.y, self.x, self.parent_win)
        newwin.win.idlok(True)
        newwin.win.scrollok(True)
        self.wins[winname] = newwin

    def resize(self, height, width, y, x, stdscr):
        for winname in self.wins.keys():
            self.wins[winname]._resize(height, width, y, x, stdscr)

class Input(Win):
    """
    """
    def __init__(self, height, width, y, x, stdscr):
        Win.__init__(self, height, width, y, x, stdscr)
        self.history = []
        self.text = u''
        self.pos = 0
        self.histo_pos = 0

    def resize(self, height, width, y, x, stdscr):
        self._resize(height, width, y, x, stdscr)
        self.input = curses.textpad.Textbox(self.win)
        self.input.insert_mode = True
        self.win.clear()

    def key_dc(self):
        """delete char"""
        if self.pos == len(self.text):
            return
        (y, x) = self.win.getyx()
        self.text = self.text[:self.pos]+self.text[self.pos+1:]
        self.win.delch(y, x)
        self.refresh()

    def key_up(self):
        if not len(self.history):
            return
        self.win.clear()
        if self.histo_pos >= 0:
            self.histo_pos -= 1
        self.text = self.history[self.histo_pos+1]
        if len(self.text) >= self.width-1:
            self.win.addstr(self.history[self.histo_pos+1][:self.width-1].encode('utf-8'))
        else:
            self.win.addstr(self.history[self.histo_pos+1].encode('utf-8'))
        self.pos = len(self.text)
        self.refresh()

    def key_down(self):
        if not len(self.history):
            return
        self.win.clear()
        if self.histo_pos < len(self.history)-1:
            self.histo_pos += 1
            self.text = self.history[self.histo_pos]
            if len(self.text) >= self.width-1:
                self.win.addstr(self.history[self.histo_pos][:self.width-1].encode('utf-8'))
            else:
                self.win.addstr(self.history[self.histo_pos].encode('utf-8'))
            self.pos = len(self.text)
        else:
            self.histo_pos = len(self.history)-1
            self.text = u''
            self.pos = 0
        self.refresh()

    def key_home(self):
        self.pos = 0
        if len(self.text) >= self.width-1:
            txt = self.text[:self.width-1]
            self.clear_text()
            self.win.addstr(txt)
        self.win.move(0, 0)
        self.refresh()

    def key_end(self):
        self.pos = len(self.text)
        if len(self.text) >= self.width-1:
            txt = self.text[-(self.width-1):]
            self.clear_text()
            self.win.addstr(txt)
            self.win.move(0, self.width-1)
        else:
            self.win.move(0, len(self.text))
        self.refresh()

    def key_left(self):
        (y, x) = self.win.getyx()
        if self.pos > 0:
            self.pos -= 1
            if x == 0:
                txt = self.text[self.pos:self.pos+self.width-1]
                self.clear_text()
                self.win.addstr(txt)
                self.win.move(y, 0)
            else:
                self.win.move(y, x-1)
            self.refresh()

    def key_right(self):
        (y, x) = self.win.getyx()
        if self.pos < len(self.text):
            self.pos += 1
            if x == self.width-1:
                txt = self.text[self.pos-(self.width-1):self.pos]
                open('fion', 'w').write(txt)
                self.clear_text()
                self.win.addstr(txt)
                self.win.move(y, self.width-1)
            else:
                self.win.move(y, x+1)
            self.refresh()

    def key_backspace(self):
        (y, x) = self.win.getyx()
        if len(self.text) > 0 and self.pos != 0:
            self.text = self.text[:self.pos-1]+self.text[self.pos:]
            self.pos -= 1
            self.win.delch(y, x-1)
            self.refresh()

    def do_command(self, key):
        (y, x) = self.win.getyx()
        if x == self.width-1:
            self.win.delch(0, 0)
            self.win.move(y, x-1)
            x -= 1
        try:
            self.text = self.text[:self.pos]+key.decode('utf-8')+self.text[self.pos:]
            self.win.insstr(key)
        except:
            return
        self.win.move(y, x+1)
        self.pos += 1
        self.refresh()

    def get_text(self):
        txt = self.text
        self.text = u''
        self.pos = 0
        self.history.append(txt)
        self.histo_pos = len(self.history)-1
        return txt.encode('utf-8')

    def save_text(self):
        self.txt = self.input.gather()

    def refresh(self):
        self.win.noutrefresh()

    def clear_text(self):
        self.win.clear()

class Window(object):
    """
    The whole "screen" that can be seen at once in the terminal.
    It contains an userlist, an input zone and a chat zone
    """
    def __init__(self, stdscr):
        """
        name is the name of the Tab, and it's also
        the JID of the chatroom.
        A particular tab is the "Info" tab which has no
        name (None). This info tab should be unique.
        The stdscr should be passed to know the size of the
        terminal
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()

        self.user_win = UserList(self.height-3, self.width/10, 1, 9*(self.width/10), stdscr)
        self.topic_win = Info(1, self.width, 0, 0, stdscr)
        self.info_win = Info(1, self.width, self.height-2, 0, stdscr)
        self.text_win = TextWin(self.height-3, (self.width/10)*9, 1, 0, stdscr)
        self.input = Input(1, self.width, self.height-1, 0, stdscr)

    def resize(self, stdscr):
        """
        Resize the whole tabe. i.e. all its sub-windows
        """
        self.size = (self.height, self.width) = stdscr.getmaxyx()
        self.user_win.resize(self.height-3, self.width/10, 1, 9*(self.width/10), stdscr)
        self.topic_win.resize(1, self.width, 0, 0, stdscr)
        self.info_win.resize(1, self.width, self.height-2, 0, stdscr)
        self.text_win.resize(self.height-3, (self.width/10)*9, 1, 0, stdscr)
        self.input.resize(1, self.width, self.height-1, 0, stdscr)

    def refresh(self, room):
        self.text_win.redraw(room)
        self.text_win.refresh(room.name)
        self.user_win.refresh(room.users)
        self.topic_win.refresh(room.topic)
        self.info_win.refresh(room.name)
        self.input.refresh()

    def do_command(self, key):
        self.input.do_command(key)
        self.input.refresh()
