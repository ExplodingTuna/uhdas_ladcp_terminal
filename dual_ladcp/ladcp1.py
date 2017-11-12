#!/usr/bin/env python


### edit this section for your cruise ###

from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
font_size = 16                          # try 12, 14, 16, 18, 20

backup = './rditerm_temp'               # 2nd copy (data and  and logs here)
## backup = ''                          # or set to empty string to disable

device_dn = '/dev/ttyUSB0'              # com port
comm_baud_dn = 9600                     # communication baud rate
data_baud_dn = None                     # download baud rate:
                                        #   19200, 38400, 57600, 115200
                                        #   or None to use instrument default
cmd_filename = 'ladcp_dn.cmd'           # default command file

##### end of section to edit ###


from six.moves.tkinter import *
from uhdas.serial.rditerm import terminal
import os, sys
import Pmw

root = Tk()
Pmw.initialise(root = root, size=font_size, fontScheme = 'default')

root.title("LADCP")


R_dn = terminal(device = device_dn, master = root,
               baud = comm_baud_dn,
               data_baud = data_baud_dn,
               prefix = 'dn',
               backup = backup,
               cmd_filename = cmd_filename)
logfilename = 'rditerm_%s.log' % os.path.split(device_dn)[-1]
print("Saving terminal IO to %s." % logfilename)
R_dn.begin_save(logfilename)

R_dn.display.Text.configure(height = 20)

R_dn.Frame.pack_forget()
R_dn.Frame.pack(side = TOP, expand = YES, fill = BOTH)

def shutdown():
    R_dn.close_terminal()
    sys.exit()

root.protocol("WM_DELETE_WINDOW", shutdown)

root.mainloop()
