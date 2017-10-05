#!/usr/bin/env python

# Top level process for logging and monitoring
# ADCP and GGA logging on the R/V Melville (CLIVAR P02)

from __future__ import absolute_import
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from .logsubs import Loggers
import time, sys, os, os.path
from six.moves.tkinter import *
from six.moves import tkinter_messagebox
import signal
yearbase = 2004
datadir = '/home/data/mv0407/'

existing_DAS_msg = """
A P02.py process (log_P2) is already running.\
Kill it and start a new process (OK)? Or Cancel \
to leave the old process running.
"""

process_name = os.path.split(sys.argv[0])[-1]

this_pid = os.getpid()
pidlist = os.popen('pgrep -x %s' % (process_name,)).readlines()
if len(pidlist) > 1:
    print(pidlist)
    print(this_pid)
    root = Tk() # Temporary root for message window.
    root.withdraw()
    kill = tkinter_messagebox.askokcancel(title = "Old process found",
             message = existing_DAS_msg)
    if kill:
        root.destroy()  # Get rid of it so it doesn't interfere with main app.
        for p in pidlist:
            pid = int(p.strip())
            if pid != this_pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    os.kill(pid, signal.SIGKILL)
                except:
                    pass

    else:
        sys.exit()



logs = Loggers(yearbase = yearbase) # Create the Loggers object.
# Add each desired logging process:

logs.add(program = '/usr/local/bin/ser_bin',
         instrument = 'ADCP ensembles',
         options = "-F -lE  -f ensemble  -m 3 ",
         device = 'ttyS18',
         baud = 4800,
         directory = '/home/data/mv0407/adcp',
         timeout = 350)

logs.add(program = '/usr/local/bin/ser_asc',
         instrument = 'Trimble GPS',
         options = " -F -f gps -m3  -e gps -c '$GPGGA'",
         device = 'ttyS17',
         baud = 9600,
         directory = datadir + 'pcode')


logs.start()  # Now start everything at once.
