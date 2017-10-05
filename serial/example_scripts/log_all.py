#!/usr/bin/env python

# Top level process for starting and monitoring
# a set of ADCP-related logging processes on the NBP.

from __future__ import absolute_import
from .logsubs import Loggers
import time


yearbase = 2003
datadir = '/home/data/adcp/raw/'
common_opts = '-F -f rb -m 1 -H 2 -T %d ' % int(time.time())    #Must have trailing space.

logs = Loggers(yearbase = yearbase) # Create the Loggers object.
# Add each desired logging process:

logs.add(program = '/usr/local/bin/ser_bin',
         instrument = 'ADCP ensembles',
         options = "-F -lE  -f ensemble  -m 3 ",
         #options = common_opts + "-e ens -lE",
         device = 'ttyS0',
         baud = 4800,
         directory = '/home/data/adcp/ensemble')

logs.add(program = '/usr/local/bin/ser_bin',
         instrument = 'ADCP pings',
         options = common_opts + "-e raw -rlEc",
         device = 'ttyS17',
         baud = 9600,
         directory = datadir + 'adcp_pings')

logs.add(program = '/usr/local/bin/ser_asc',
         #instrument = 'Northstar 941X',
         instrument = 'Trimble Centurion', #20636-00 SM
         options = common_opts + "-e gps -tc '$GPGGA'",
         device = 'ttyS18',
         baud = 4800,
         directory = datadir + 'pcode')

logs.add(program = '/usr/local/bin/ser_asc',
         instrument = 'Gyro',
         options = common_opts + "-e hdg -tc -s 5 '$HEHDT'",
         device = 'ttyS19',
         baud = 4800,
         directory = datadir + 'gyro')

logs.add(program = '/usr/local/bin/ser_bin',
         instrument = 'Seapath',
         options = common_opts + "-e sea -rlE -B42",
         device = 'ttyS20',
         baud = 9600,
         directory = datadir + 'seapath1')



logs.start()  # Now start everything at once.
