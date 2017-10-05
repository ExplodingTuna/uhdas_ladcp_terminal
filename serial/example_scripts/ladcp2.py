#!/usr/bin/env python


### edit this section for your cruise ###
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
font_size = 14                          # try 12, 14, 16, 18, 20

cruiseName = 'AB1705'                   # Cruise name

backup = './rditerm_temp'               # 2nd copy (data and  and logs here)
## backup = ''                          # or set to empty string to disable

device_slave = '/dev/ttyUSB0'              # up-looker: com port
data_baud_slave = None                     # up-looker: download baud rate
                                        #      None to use instrument default
comm_baud_slave = 9600                     # up-looker: communication baud rate
cmd_filename_slave = 'ladcp_slave.cmd'        # up-looker: command file

device_master = '/dev/ttyUSB1'              # down-looker: com port
data_baud_master = None                     # down-looker: download baud rate
comm_baud_master = 9600                     # down-looker: communication baud rate
cmd_filename_master = 'ladcp_master.cmd'        # down-looker: command file

##### end of section to edit ###

from six.moves.tkinter import *
from uhdas.serial.rditerm import terminal
import os, sys
import Pmw

root = Tk()
Pmw.initialise(root = root, size=font_size, fontScheme = 'default')
root.title("Dual LADCP")


R_slave = terminal(device = device_slave, master = root,
               data_baud = data_baud_slave,
               baud = comm_baud_slave,
               prefix = '',
               suffix = 's',
               cruiseName = cruiseName,                
               backup = backup,
               cmd_filename = cmd_filename_slave)
logfilename = 'rditerm_%s.log' % os.path.split(device_slave)[-1]
print("Saving terminal IO to %s." % logfilename)
R_slave.begin_save(logfilename)


R_master = terminal(device = device_master, master = root,
               data_baud = data_baud_master,
               baud = comm_baud_master,
               prefix = '',
               suffix = 'm',
               cruiseName = cruiseName,               
               backup = backup,
               cmd_filename = cmd_filename_master)
logfilename = 'rditerm_%s.log' % os.path.split(device_master)[-1]
print("Saving terminal IO to %s." % logfilename)
R_master.begin_save(logfilename)

R_slave.display.Text.configure(height = 20)
R_master.display.Text.configure(height = 20)

# Synchronize the stacast.  Both of the following are essential.
R_master.stacastentry.configure(textvariable = R_slave.stacastSV)
R_master.stacastSV = R_slave.stacastSV

R_slave.Frame.pack_forget()
R_slave.Frame.pack(side = TOP, expand = YES, fill = BOTH)
R_master.Frame.pack_forget()
R_master.Frame.pack(side = TOP, expand = YES, fill = BOTH)

def shutdown():
    R_slave.close_terminal()
    R_master.close_terminal()
    sys.exit()

root.protocol("WM_DELETE_WINDOW", shutdown)

root.mainloop()
