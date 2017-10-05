'''
RDI narrowband-specific terminal for shipboard use (NB150)

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import range

from six.moves.tkinter import *
from six.moves import tkinter_tkfiledialog
from six.moves import tkinter_messagebox

import time
import os
import struct

from uhdas.serial.tk_terminal import Tk_terminal

rdi_baud_codes = {300:0, 1200:1, 2400:2,
                  4800:3, 9600:4, 19200:5,
                  38400:6, 57600:7, 115200:8}

# The NB actually uses CRLF to acknowledge commands and as
# a line terminator for its wakeup, but we are now stripping
# the CR out between the serial queue and the buffer (and display),
# so we will use only the LF.

_LF = b'\n'

class terminal(Tk_terminal):
    def __init__(self, master = None, device = '/dev/ttyS0',
                       baud = 19200, standalone = 0,
                       cmd_filename = 'test_nb.cmd',
                       instrument=None,
                       baud2 = 19200):
        Tk_terminal.__init__(self, master = master,
                       device = device, baud = baud,
                       standalone = standalone,
                       termination = b'')
        self.default_baud = baud
        self.cmd_filename = cmd_filename
        self.instrument = instrument
        # baud2 is not actually used; we might want to simply
        # check that it is specified to be the same as baud.


    def set_clock(self):
        #self.wakeup()    #This may do more harm than good.
        DateTime = time.strftime('%m%d%H%M', time.gmtime())
        self.send_commands(['T%s' % DateTime, ])
        ## Ideally, this would be changed to send the appropriate
        ## time on the exact minute; there is no way to set the seconds.



    def wakeup(self):
        '''The NB simple wakeup (and the OS wakeup) are somehow
        unreliable with the digi neo board.  The workaround here is
        to (1) send a first break when not listening, wait, then
        open the port when we hope nothing is being received; the
        ADCP should have finished any data transmission, and it
        should be listening.  Then start listening and send a
        second break.  If that times out, try again, up to three
        times before giving up.
        '''
        self.stop_listening()
        self.change_baud(self.default_baud)
        self.send_break()  # May be needed twice.
        time.sleep(0.5)
        self.start_listening()
        self.waitfor(timeout=2, quiet=0.5)
        self.display.mark()
        self.clear_buffer()
        for ii in range(3):
            try:
                self.send_break()
                self.waitfor(_LF, timeout=1, quiet=0.5)
                break
            except:
                if ii == 2:
                    raise
                continue
        time.sleep(0.2)

    def run_diagnostics(self):
        self.wakeup()
        diagnostics = ('Y1')
        self.send_commands(diagnostics)

    def send_commands(self, commands):
        self.start_listening()
        self.display.mark()
        for cmd in commands:
            print(cmd)
            cmd = cmd.rstrip().encode('ascii', 'ignore')
            self.send(cmd)
            self.waitfor(_LF, timeout=3, quiet=0.3)

    def send_commands_bin_mode(self, commands):
        self.stop_listening()  # closes the port
        self.open_port()
        for cmd in commands:
            print(cmd)
            cmd = cmd.rstrip().encode('ascii', 'ignore')
            cs = 0    # checksum
            for ii in range(len(cmd)):
                self.stream.write(cmd[ii])
                cs = cs + struct.unpack('B', cmd[ii])[0]  # sum byte values
                self.stream.flush()
                time.sleep(0.05)
            cs_str = struct.pack('>H', cs)   # checksum as a short int, big-endian
            for ii in range(len(cs_str)):
                self.stream.write(cs_str[ii:ii+1]) # send the checksum (2 bytes)
                self.stream.flush()
                time.sleep(0.05)
            for ii in range(30):             # look for ACK, or NAK and error code
                resp = self.stream.read(1)
                if len(resp) == 1:
                    b = struct.unpack('B', resp)[0]
                    print(b)
                    break
                time.sleep(0.05)
            if ii == 29:
                print("Timout waiting for ACK")
            elif b == 0x15:                      # NAK
                for ii in range(10):              # read single byte error code
                    resp = self.stream.read(1)
                    if len(resp) == 1:
                        e = struct.unpack('B', resp)[0]
                        print("NAK; error is ", e)
                        break
            elif b == 6:
                print("ACK")
            else:
                print("Strange reply: ", b)
        self.close_port()

    def send_setup(self):
        self.wakeup() # Make sure it is listening.
        fn = self.cmd_filename
        try:
            lines = open(fn, 'r').readlines()
            cmds = [line.strip() for line in lines if len(line) > 1]
            cmds = [c.split('#', 1)[0].strip() for c in cmds]
            cmds = [c for c in cmds if len(c) > 1]
            self.send_commands(cmds)

        except:
            tkinter_messagebox.showerror(message = "Can't send file %s" % fn)
            self.ask_send_setup()



    def ask_send_setup(self):
        dir, name = os.path.split(self.cmd_filename)

        fn = tkinter_tkfiledialog.askopenfilename(initialfile = name,
                       initialdir = dir,
                       filetypes = (('Command', 'nb*.cmd'), ('All', '*')),
                       parent = self.Frame,
                       title = 'Command file')
        if not fn: return
        self.cmd_filename = fn
        self.send_setup()



    # ping at will
    def start_binary(self, cmdlist = None):
        self.begin_save()
        self.wakeup()
        self.set_clock()
        if cmdlist:
            self.send_commands(cmdlist)
        #self.change_all_baud()
        self.send_commands(['W064', ]) # Set binary IO mode.
        self.stop_listening()  # ser_bin will sent the S207 binary mode command
        #self.send_commands_bin_mode(['S207',])

    # The higher baud rate works for normal communications,
    # but doesn't seem to work for the S command!
    def change_all_baud(self):
        self.send_commands(['@4', 'W006'])
        self.change_baud(38400)
        print("Switched to 38400.")


    def make_menu(self, master):
        Tk_terminal.make_menu(self, master)
        mb = self.menubar
        mb.deletemenuitems('Command', 0)

        mb.addmenuitem('Command', 'command', '',
                       label = 'Wakeup',
                       command = self.wakeup)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Set Clock',
                       command = self.set_clock)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Send Setup',
                       command = self.ask_send_setup)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Run Diagnostics  ',
                       command = self.run_diagnostics)
#      mb.addmenuitem('Command', 'command', '',
#                     label = 'Show Config',
#                     command = self.showconfig)

#      mb.addmenuitem('Command', 'command', '',
#                     label = '38400 Baud',
#                     command = self.change_all_baud)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Start Binary',
                       command = self.start_binary)

    def enable_menubar(self):
        self.menubar.enableall()

    def disable_menubar(self):
        self.menubar.disableall()


