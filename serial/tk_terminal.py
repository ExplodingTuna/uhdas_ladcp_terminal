"""
2001/04/03 EF
Serial port routines.

2002/08/22 EF
Tk-based terminal routines.  Subclass the Tk_terminal class to
get special-purpose terminals.
"""
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import range
from future.builtins import object

from six.moves.tkinter import *
from six.moves import tkinter_tkfiledialog
from six.moves import tkinter_messagebox
import Pmw

import termios, sys, os, time
from threading import Thread, Lock
import queue

import logging
L = logging.getLogger()

from uhdas.serial.serialport import serial_port, baud_table, port_flags

L.info("tk_terminal %s", time.strftime('%H:%M:%S'))

class flag_display(object):
    def __init__(self, parent, port):
        self.port = port
        self.flag_value_dict = self.IntVars()
        self.read_flags()
        self.dialog = Pmw.Dialog(parent,
              buttons = ('Apply', 'Reread', 'Quit'),
              defaultbutton = 'Cancel',
              title = 'Serial port flags',
              command = self.execute)
        #Label(self.dialog.interior(), text = 'Testing').pack()
        self.checkboxes = Pmw.RadioSelect(self.dialog.interior(),
              buttontype = 'checkbutton', orient = VERTICAL)
        self.make_checks()
        self.checkboxes.pack()
        #self.dialog.activate()
        # activate() segfaults on jaunty

    def IntVars(self):
        sv = {}
        for key in port_flags.keys():
            sv[key] = IntVar()
        return sv

    def read_flags(self):
        text, self.keys, self.values = self.port.read_flags()
        for i in range(len(self.keys)):
            self.flag_value_dict[self.keys[i]].set(self.values[i])

    def set_flags(self):
        for i in range(len(self.keys)):
            key = self.keys[i]
            new_value = self.flag_value_dict[key].get()
            if new_value != self.values[i]:
                self.port.set_flag(key, new_value)

    def make_checks(self):
        for i in range(len(self.keys)):
            key = self.keys[i]
            self.checkboxes.add(key,
                  var = self.flag_value_dict[key])


    def execute(self, result):
        button_function = {'Apply': self.set_flags,
                           'Reread': self.read_flags,
                           'Quit': self.dialog.destroy}
        button_function[result]()

class Timeout(Exception):
    pass

def no_action(event):
    return "break"



class terminal_display(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.Text = Text(self, width = 80, height = 30, wrap = CHAR,
                         setgrid = NO)
        # setting state = 'disabled' disables everything, not
        # only keyboard input
        s = Scrollbar(self, command = self.Text.yview)
        self.Text.configure(yscrollcommand = s.set)
        self.Text.pack(side = LEFT, expand = YES, fill = BOTH)
        s.pack(side = RIGHT, fill = Y)
        self.Text.bind("<KeyPress>", no_action)

    def append(self, str):
        self.Text.insert(END, str)
        self.Text.see(END)

    def get(self, start = '1.0', end = END):
        return self.Text.get(start, end)

    def mark(self, index = "end - 1 c", gravity = "left",
             name = "BeforeCommand"):
        self.Text.mark_set(name, index)
        self.Text.mark_gravity(name, gravity)

    def unmark(self, name = "BeforeCommand"):
        self.Text.mark_unset(name)

    def get_after_mark(self, name = "BeforeCommand"):
        return self.Text.get(name, END)

    def get_line_with(self, _str, **kwargs):
        if 'backwards' not in kwargs:
            kwargs['backwards'] = 1
        try:
            ind = self.Text.search(_str, END, **kwargs)
            if ind == '':
                return ind
            line = self.Text.get(ind + ' linestart', ind + ' lineend')
            return line
        except:
            L.exception("Error in get_line_with <%s>", _str)
            return ""

    def get_lines_from(self, _str):
        try:
            ind = self.Text.search(_str, END, backwards = 1)
            if ind == '':
                return ind
            line = self.Text.get(ind + ' linestart', END)
            return line
        except:
            L.exception("Error in get_lines_from <%s>", _str)
            return ""

    def clear(self):
        self.Text.delete('1.0', END)


class EntryHistory(Entry):
    def __init__(self, master, port, **kw):
        self.send = kw.pop('send_function')
        Entry.__init__(*(self, master), **kw)
        self.port = port  # pass in whole serial port object,
        self.lines = [''] # so that self.port.stream will be current
        self.nlast = 0
        self.curline = 0
        self.sv = StringVar()
        self.configure(textvariable = self.sv)
        self.bind('<Key-Return>', self.input)
        self.bind('<Key-Up>', self.back)
        self.bind('<Key-Down>', self.forward)

    def input(self, event = ''):
        cl = self.get()
        self.send(cl)
        self.lines.append(cl)
        self.nlast = self.nlast + 1
        self.sv.set('')
        self.curline = 0

    def back(self, event = ''):
        if self.nlast:
            self.curline = (self.curline - 1) % (self.nlast + 1)
            self.sv.set(self.lines[self.curline])

    def forward(self, event = ''):
        if self.nlast:
            self.curline = (self.curline + 1) % (self.nlast + 1)
            self.sv.set(self.lines[self.curline])



class Tk_terminal(serial_port):
    def __init__(self,
                 master=None,
                 device='/dev/ttyS0',
                 baud=9600,
                 standalone=0,
                 termination=b'\r\n',
                 show_cwd=False):
        serial_port.__init__(self, device = device,
                                   baud = baud,
                                   mode = 'r+b');
        if not master:
            master = Tk()
            master.protocol("WM_DELETE_WINDOW", self.close_terminal)
            standalone = 1
        self.master = master
        self.standalone = standalone
        self.termination = termination
        self.Frame = Frame(master, relief = RIDGE, borderwidth = 2)
        self.Frame.pack(expand = YES, fill = BOTH)
        lw = Pmw.LabeledWidget(self.Frame, labelpos = 'w',
                               label_text = 'Transmit line:')
        lw.pack(side = BOTTOM, expand = NO, fill = X)
        self.entry = EntryHistory(lw.interior(), self,
                                send_function = self.send,
                                width = 40,
                                state = DISABLED)
        self.entry.pack(side = BOTTOM, expand = NO, fill = X)
        self.display = terminal_display(self.Frame)
        self.display.bind('<Destroy>', self.close_terminal)
        # Putting the binding here seems to keep the close_terminal
        # function from trying to configure a menu item that is
        # already gone.  There may be a cleaner way to ensure that
        # close_terminal is executed early in the shutdown process.
        self.buffer = b''
        self.update_lock = Lock()
        self.save = 0
        self.outfile_name = "term_diary.txt"
        self.outfile = None
        self.new_input = queue.Queue(0)  # 0 -> unbounded size
        self.listening = 0

        self.update_search = None
        self.update_search_callback = lambda x: None
        # return True to end the update cycle

        self.connectedIV = IntVar()
        self.connectedIV.set(self.listening)
        self.baudIV = IntVar()
        self.baudIV.set(self.get_baud())
        toprow = Frame(self.Frame)
        toprow.pack(side = TOP, expand = NO, fill = X)
        self.toprow = toprow
        self.make_menu(master = toprow)
        self.menubar.pack(side = LEFT, expand = NO, fill = NONE, pady = 5)
        if show_cwd:
            wd = os.getcwd()
#            if len(wd) > 30:
#                parts = wd.split(os.path.sep)
#                i = 1
#                while i < len(parts) and len(wd) > 30:
#                    wd = os.path.join('...', *parts[i:])
#                    i += 1

            cwd_label = Label(master=toprow,
                              text=wd,
                              relief=SUNKEN,
                              #padx=3,
                              font=NORMAL,
                              anchor=W)
            cwd_label.pack(side=RIGHT)
        self.statusSV = StringVar()
        self.statusframe = Frame(self.Frame)
        self.statusframe.pack(side = TOP, anchor = W, expand = YES, fill = X)
        self.statusline = Pmw.LabeledWidget(self.statusframe, ##toprow,
                                            labelpos = 'w',
                                            label_text = 'Status:')
        self.statusline.pack(side = LEFT, anchor = W)
        ## Pack the display last, so everything else gets needed
        ## space, and the display gets what's left.
        self.display.pack(side = BOTTOM, expand = YES, fill = BOTH)
        Label(self.statusline.interior(),
              width = 52,
              relief = SUNKEN,
              textvariable = self.statusSV).pack()
        self.set_status()

    def set_status(self, msg = None):
        if msg is None:
            if self.listening:
                C = 'connected.'
            else:
                C = 'not connected.'
            msg = 'Device %s, at %d Baud, is %s' % (
                   self.get_device(), self.get_baud(), C)
        self.statusSV.set(msg)

    def waitfor(self, s=None, timeout=5, quiet=0):
        nchar = len(self.buffer)
        nloops = max(2, int(timeout*10))
        qnloops = max(0, int(quiet*10))
        ii = 0
        jj = 0
        while ii < qnloops:
            jj += 1
            if jj == nloops:
                raise Timeout
            time.sleep(0.1)
            self.update(oneshot=True)
            n = len(self.buffer)
            if n > nchar:
                nchar = n
                ii = 0
            elif not s or n > 0:
                ii += 1
        if not s:
            return ''
        for ii in range(nloops):
            time.sleep(0.05)
            self.update(oneshot = True) ###
            ind = self.buffer.rfind(s)
            if ind != -1:
                buf = self.buffer[:ind+1]
                self.buffer = self.buffer[ind+1:]
                return buf
            time.sleep(0.05)
        raise Timeout

    def streamwaitfor(self, s, timeout=2, maxnchar=50000):
        """
        Wait for the string *s* to appear in the buffer,
        or until *timeout* seconds of no activity, or until
        *maxnchar* have been received.
        """
        nchar = n_orig = len(self.buffer)
        nloops = max(2, int(timeout*10))
        ii = 0
        while ii < nloops:
            time.sleep(0.05)
            self.update(oneshot = True) ###
            n = len(self.buffer)
            if n > nchar:
                nchar = n
                ii = 0
            ind = self.buffer.rfind(s)
            if ind != -1:
                buf = self.buffer[:ind+1]
                self.buffer = self.buffer[ind+1:]
                return buf
            if n - n_orig >= maxnchar:
                raise Timeout
            time.sleep(0.05)
            ii += 1
        raise Timeout

    def clear_buffer(self):
        self.buffer = b''
        self.buffer_i0 = 0

    def start_listening(self, save=True):
        if self.listening:
            self.clear_buffer()
            return
        self.open_port(save=save)      # Might already be open, but make sure.
        self.entry.config(state = NORMAL)
        self.config_menuitem('File', 'Disconnect', state = NORMAL)
        self.config_menuitem('File', 'Connect*', state = DISABLED)
        self.listening = 1
        self.set_status()      # after changing self.listening
        self.thread1 = Thread(target = self.listen)
        self.thread1.start()
        self.connectedIV.set(self.listening)
        self.clear_buffer()
        self.update()

    def update(self, oneshot = False):
        if not self.update_lock.acquire(False):
            if self.listening and not oneshot:
                self.Frame.after(50, self.update)
            return
        try:
            # change to loop count, so it can't get stuck
            # if there is too large a blast of input?
            # while 1:
            cclist = []
            for ii in range(50):
                cc = self.new_input.get_nowait()
                cclist.extend(cc.split(b'\r'))
        except queue.Empty:
            pass

        if cclist:
            cc = b''.join(cclist)
            self.display.append(cc)
            self.buffer += cc
            self.display.update_idletasks()
            #self.display.update()

            if self.update_search:
                s = self.update_search
                self.buffer_i0 -= len(cc)
                ind = self.buffer.rfind(s, self.buffer_i0)
                if ind != -1:
                    self.listening = False
                    self.update_search_callback()
                    self.update_search = None
                    self.buffer_i0 = ind + len(s)
                else:
                    self.buffer_i0 = -len(s)
        if self.listening and not oneshot:
            self.Frame.after(50, self.update)
        self.update_lock.release()

    def set_update_search_callback(self, s, func):
        self.update_lock.acquire()
        self.update_search = s
        self.update_search_callback = func
        self.update_lock.release()

    def listen(self):
        ''' Thread target for listening to a serial port.
            We set vmin to 0 so it won't block; the sleep
            then ensures the main thread gets a time slice.
        '''
        if not self.fd:
            return
        self.set_cc(vmin = 0, vtime = 1) # vtime in 0.1 s
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        while self.listening:
            cc = os.read(self.fd, 500)
            if cc == b"":
                time.sleep(0.001)
            else:
                self.new_input.put(cc)  # via queue to main thread
                if self.save:
                    self.outfile.write(cc)


    # Looks like one must use os.read instead of <fileobject>.read
    # for any value of vmin other than 0.

    def stop_listening(self, restore=True):
        if not self.listening:
            return
        self.listening = 0
        self.entry.config(state = DISABLED)
        self.config_menuitem('File', 'Disconnect', state = DISABLED)
        self.config_menuitem('File', 'Connect*', state = NORMAL)
        self.set_status()
        self.thread1.join(3)
        self.close_port(restore=restore)
        self.connectedIV.set(self.listening)

    def send(self, s):
        '''Send a string, wait for its echo
        '''
        s = s.encode('ascii', 'ignore')
        if self.termination:
            self.stream.write(s + self.termination)
            self.stream.flush()
            self.waitfor(s)
        else:                # for old NB: one character at a time
            for i in range(len(s)):
                self.stream.write(s[i])
                self.stream.flush()
                self.waitfor(s[i])

    def close_terminal(self, event = ''):
        self.stop_listening()
        if self.save:
            self.end_save()
        if self.standalone:
            self.master.quit()

    def clear(self):
        self.display.clear()


    def ask_write_file(self):
        fn = tkinter_tkfiledialog.asksaveasfilename(initialfile ='term_diary.txt',
                       initialdir = './',
                       filetypes = (('Text', '*.txt'), ('All', '*')),
                       parent = self.Frame,
                       title = 'Save Transcript as File')
        if fn == '': return
        try:
            f = open(fn, 'w')
            f.write(self.display.get())
            f.close()
        except:
            L.exception("writing to file <%s>", fn)
            tkinter_messagebox.showerror(message = "Can't write to file %s" % fn)

    def ask_save_file(self):
        dd, ff = os.path.split(self.outfile_name)
        fn = tkinter_tkfiledialog.asksaveasfilename(initialfile = ff,
                       initialdir = dd,
                       filetypes = (('Text', '*.txt'), ('All', '*')),
                       parent = self.Frame,
                       title = 'Save all received characters')
        if fn == '': return
        self.outfile_name = fn
        self.begin_save()

    def begin_save(self, filename = None):
        if filename is not None:
            self.outfile_name = filename
        self.end_save()
        try:
            self.outfile = open(self.outfile_name, 'ab')
        except:
            L.exception("writing to file <%s>", self.outfile_name)
            tkinter_messagebox.showerror(message = "Can't write to file %s" %
                                              self.outfile_name)
            self.ask_save_file()
        self.config_menuitem('File', 'Save incoming', state = DISABLED)
        self.config_menuitem('File', 'Stop saving', state = NORMAL)
        self.save = 1

    def end_save(self):
        try:
            self.outfile.close()
        except:
            pass
        self.config_menuitem('File', 'Save incoming', state = NORMAL)
        self.config_menuitem('File', 'Stop saving', state = DISABLED)
        self.save = 0

    def ask_device(self):
        fn = tkinter_tkfiledialog.askopenfilename(initialfile = self.get_device(),
                       initialdir = '/dev',
                       filetypes = (('ttyUSB', 'ttyUSB*'),
                                    ('ttyS', 'ttyS*'),
                                    ('ttyC', 'ttyC*'),
                                    ('cu', 'cu*'),
                                    ('tty_d*', 'tty_d*'),
                                    ('ttyR', 'ttyR*'),
                                    ('ttyn', 'ttyn*'),
                                    ('tty', 'tty*')),
                       parent = self.Frame,
                       title = 'Select serial port device')
        if fn == '': return
        self.set_device(fn)
        self.set_status()


    def change_baud(self, baud = None):
        self.open_port(save=False)
        if baud == None:
            baud = self.baudIV.get()
        else:
            self.baudIV.set(baud)
        self.set_baud(baud)
        self.set_status()


    def view_set(self):
        self.open_port(save=False)
        flag_display(self.Frame, self)





    def make_menu(self, master = None):
        if not master: master = self.Frame
        mb = Pmw.MenuBar(master)
        #mb.pack(fill = X)
        mb.addmenu('File', '')
        mb.addmenu('Baud', '')
        mb.addmenu('Port', '')
        mb.addmenu('Command', '')

        mb.addmenuitem('File', 'command', '',
                       label = 'Connect to port',
                       command = self.start_listening)
        mb.addmenuitem('File', 'command', '',
                       label = 'Disconnect',
                       command = self.stop_listening,
                       state = DISABLED)
        mb.addmenuitem('File', 'command', '',
                       label = 'Save incoming',
                       command = self.ask_save_file)
        mb.addmenuitem('File', 'command', '',
                       label = 'Stop saving',
                       command = self.end_save,
                       state = DISABLED)

        mb.addmenuitem('File', 'command', '',
                       label = 'Save previous',
                       command = self.ask_write_file)
        mb.addmenuitem('File', 'command', '',
                       label = 'Clear',
                       command = self.clear)
        if self.standalone:
            mb.addmenuitem('File', 'command', '',
                        label = 'Quit',
                        command = self.close_terminal)


        mb.addmenuitem('Command', 'command', '',
                       label = 'Send Break',
                       command = self.send_break)



        bauds = list(baud_table.keys())
        bauds.sort()
        for b in bauds:
            mb.addmenuitem('Baud', 'radiobutton', '',
                        label = str(b),
                        var = self.baudIV,
                        command = self.change_baud,
                        value = b)

        mb.addmenuitem('Port', 'command', '',
                       label = 'Device',
                       command = self.ask_device)
        mb.addmenuitem('Port', 'command', '',
                       label = 'View/Set',
                       command = self.view_set)
        self.menubar = mb

    def config_menuitem(self, menu, item, **kw):
        m = self.menubar.component(menu + '-menu')
        m.entryconfigure(*(item,), **kw)

usage = """

usage:

tk_terminal.py [device [baud]]
eg:
  tk_terminal.py /dev/ttyUSB0
  tk_terminal.py /dev/ttyUSB0 4800

"""

def main():
    if "-h" in sys.argv[1:]:
        print(usage)
        return

    device = '/dev/ttyS0'
    baud = 9600
    if len(sys.argv) > 1:
        device = sys.argv[1]
    if len(sys.argv) > 2:
        baud = int(sys.argv[2])
    T = Tk_terminal(device = device, master = Tk(), baud = baud, standalone = 1)
    T.Frame.mainloop()

if __name__ == '__main__':
    main()

