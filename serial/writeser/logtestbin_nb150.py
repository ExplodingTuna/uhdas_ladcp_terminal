#!/usr/bin/env python

# Top level process for starting and monitoring
# a set of ADCP-related logging processes on the NBP.

from uhdas.serial.logsubs import Loggers

logs = Loggers() # Create the Loggers object.
# Add each desired logging process:

logs.add(program = '/usr/local/bin/ser_bin',
         instrument = 'ADCP',
         options = "-rlE -t0.05 -f km -e raw_nocheck -m 1 -H 2 -v1 -V0",
         device = 'ttyUSB1',
         baud = 9600,
         directory = './test')

logs.start()  # Now start everything at once.
