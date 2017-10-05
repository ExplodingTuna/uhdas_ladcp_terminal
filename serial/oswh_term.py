'''
RDI-specific terminal (BB, WH, OS) for shipboard systems.

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import range

from six.moves.tkinter import *
from six.moves import tkinter_tkfiledialog
from six.moves import tkinter_messagebox

import sys
import time, termios
import os

from uhdas.serial.tk_terminal import Tk_terminal

import logging
L = logging.getLogger('oswh_term')
L.propagate = False
L.setLevel(logging.DEBUG)
formatter = logging.Formatter(
      '%(asctime)s %(levelname)-8s %(message)s')

logbasename = '/home/adcp/log/oswh_term.log'

handler = logging.FileHandler(logbasename, 'w')
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
for h in L.handlers:
    L.removeHandler(h)
L.addHandler(handler)

L.info('Starting oswh_term.py')


## adapted from sonterm for WH, starting 2003/06/08
## adapted at sea (JH) for 150KHz BB 2003/06/19.  needs integration
## more changes for shipboard OS use. EF 2003/12/13
## Add WH Mariner support.  EF 2005/03/19

#### stripped down for shipboard use.

rdi_baud_codes = {300:0, 1200:1, 2400:2,
                  4800:3, 9600:4, 19200:5,
                  38400:6, 57600:7, 115200:8}

class OceanSurveyorIsConfused(Exception):
    pass

class terminal(Tk_terminal):
    def __init__(self, master = None, device = '/dev/ttyS0',
                       baud = 9600, standalone = 0,
                       cmd_filename = None,
                       instrument=None,
                       baud2 = 19200):
        Tk_terminal.__init__(self, master = master,
                       device = device, baud = baud,
                       standalone = standalone,
                       termination = b'\r')  # Command should end in CR only.
        self.default_baud = baud
        self.baud2 = baud2
        self.cmd_filename = cmd_filename
        self.instrument = instrument   ## Key for dictionary lookup in logsubs
        if instrument[:2] == 'os':
            self.TS_fmt = '%y%m%d%H%M%S'
            self.D_cmds = 'WD', 'ND'
            self.check_D_params = self.os_check_D_params
        elif instrument[:2] in ('wh','bb'):
            self.TS_fmt = '%y/%m/%d, %H:%M:%S'
            self.D_cmds = 'WD',
            self.check_D_params = self.whbb_check_D_params
        else:
            raise ValueError("unrecognized instrument: " + instrument)

    def set_clock(self):
        DateTime = time.strftime(self.TS_fmt, time.gmtime())
        # Not sure whether we really need to include the
        # automatic second try here.
        try:
            self.send_commands(['TS%s' % DateTime, ])
        except:
            self.wakeup()
            DateTime = time.strftime(self.TS_fmt, time.gmtime())
            self.send_commands(['TS%s' % DateTime, ])


    def slow_wakeup(self):
        '''Wake up and query time

        This version sends an initial break to stop any data
        transmission before it starts listening; it then sends
        another break and waits for a prompt.  In case of a
        timeout it tries two more times.

        It seems that the allowed time for a response should be
        several seconds; I am not sure what the actual range of
        response times is, and how much of the required allocation
        is caused by delays in handling the incoming characters.

        The behavior seems to vary from system to system, and
        among serial ports on a single system; we seem to get
        more reliable results with standard built-in serial ports
        than with multiport cards.  All such problems seem to be
        confined to the wakeup stage, though.
        '''
        L.debug("Wakeup starting")
        self.stop_listening()
        self.change_baud(self.default_baud)
        L.debug("sending break 0 to stop data transmission")
        self.send_break(400)
        L.debug("break sent")
        time.sleep(0.5)
        self.start_listening()
        self.waitfor(timeout=2.5, quiet=0.5)
        for ii in range(3):
            self.display.mark()
            self.clear_buffer()
            try:
                L.debug("sending break %d", ii + 1)
                self.send_break(400)    # at least 300 msec for Ocean Surveyor
                L.debug("break sent")
                L.debug("buffer: %s", self.buffer)
                self.waitfor(b'>', timeout=3, quiet=0.5)
                break
            except:
                L.error("failure waiting for prompt", exc_info = True)
                L.debug("buffer: %s", self.buffer.decode('ascii', 'ignore'))
                if ii == 2:
                    raise
        L.debug("sending TS?")
        self.send_commands(['TS?'])
        L.debug("Wakeup finished")

    def simple_wakeup(self):
        ''' Older wakeup version for non-buggy serial drivers.
        '''
        self.change_baud(self.default_baud)
        self.start_listening()
        time.sleep(0.1)
        self.display.mark()
        self.clear_buffer()
        L.debug("sending break")
        self.send_break(400)    # at least 300 msec for Ocean Surveyor
        L.debug("break sent")
        self.waitfor(b'>', 3)
        L.debug("sending TS?")
        self.send_commands(['TS?'])

    def wakeup(self):
        ''' See slow_wakeup
        '''
        self.slow_wakeup()
        #self.simple_wakeup()

    def send_commands(self, commands):
        self.start_listening()
        self.display.mark()
        self.clear_buffer()
        for cmd in commands:
            print(cmd)
            cmd = cmd.rstrip().encode('ascii', 'ignore')
            os.write(self.fd, cmd + b'\r')
            termios.tcdrain(self.fd)
            #print "sent %s" % cmd.rstrip()
            self.waitfor(b'>', 3)

    def run_diagnostics(self):
        self.wakeup()
        diagnostics = ('PS0', 'PT200')
        self.send_commands(diagnostics)

    def send_setup(self):
        self.wakeup() # Make sure it is listening.
        fn = self.cmd_filename
        try:
            lines = open(fn, 'r').readlines()
            lines = [line.split("#", 1)[0] for line in lines]
            cmds = [line.strip() for line in lines if len(line) > 1]
            self.send_commands(cmds)

        except:
            tkinter_messagebox.showerror(message = "Can't send file %s" % fn)
            self.ask_send_setup()

    def ask_send_setup(self):
        dir, name = os.path.split(self.cmd_filename)

        fn = tkinter_tkfiledialog.askopenfilename(initialfile = name,
                       initialdir = dir,
                       filetypes = (('Command', 'os*.cmd'), ('All', '*')),
                       parent = self.Frame,
                       title = 'Command file')
        if not fn: return
        self.cmd_filename = fn
        self.send_setup()


    # This may not be useful; it is supposed to
    # get a single ensemble in hex-ascii mode, but
    # the RDI hex-ascii output has no CR/LF so it
    # doesn't work well with the tk_terminal.
    def start_ascii(self):
        self.wakeup()
        #self.set_clock()
        self.stream.write(b'CF01010\r')
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.stream.write(b'CS\r')
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.waitfor(b'>')

    def os_check_D_params(self):
        print("In os_check_D_params")
        params = []
        for C in self.D_cmds:
            C_str = self.display.get_line_with('^%s .*$'%(C,),
                                                regexp=1).split()[1]
            params.append(C_str)
            print("in os_check_D_params: " + str(C_str))
        for p in params:
            if len(p) != 9 or p[-4:] != '0000' or p[:3] != '111':
                raise OceanSurveyorIsConfused

    def whbb_check_D_params(self):
        print("In whbb_check_D_params")
        return

    def start_binary(self, cmdlist = None):
        self.begin_save()
        self.wakeup()
        self.set_clock()
        if cmdlist:
            self.send_commands(cmdlist)
            try:
                self.check_D_params()
            except:
                tkinter_messagebox.showerror(message = "Cycle power on the ADCP; "+
                                                 "it is hopelessly confused."+
                                                 "  Then, restart logging.")
                raise

        self.send_commands(('CF11110',))
        self.change_all_baud(self.baud2)  ### might not want this here in general
        if 0:                   # 0 to let "ser_bin -I" send the CS
            self.display.mark()
            self.stream.write(b'CS\r')
            self.stream.flush()
            termios.tcdrain(self.fd)
            self.waitfor(b'CS')
        self.stop_listening()


    def change_all_baud(self, baud = 19200):
        self.send_commands([''])
        self.stream.write(('CB%d11\r' % rdi_baud_codes[baud]).encode('ascii'))
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.waitfor(b'>', 2)
        self.change_baud(baud)
        time.sleep(0.5) # ad hoc; without delay, local serial port
                        # baud rate does not seem to take effect
                        # before we send a command and receive
                        # a response.


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
#                     label = '115200 Baud',
#                     command = self.change_all_baud)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Start Binary',
                       command = self.start_binary)

    def enable_menubar(self):
        self.menubar.enableall()

    def disable_menubar(self):
        self.menubar.disableall()


def main():
    root = Tk()
    R = terminal(device = sys.argv[2],  instrument = sys.argv[1],
                   master = root,
                   cmd_filename = sys.argv[3],
                   baud = 9600, standalone = 1)
    R.begin_save('rditerm.log')
    root.mainloop()
