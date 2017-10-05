#!/usr/bin/env python
# write last N pings to daily email tarball
### Specifically for UHDAS underway processing
## proc_cfg.py, uhdas_cfg.py, sensor_cfg.py

from __future__ import division
from future import standard_library
standard_library.install_hooks()

import logging, logging.handlers
import sys, os
from optparse import OptionParser
import time

# Set up the root logger before importing any of our own code.
from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup
from pycurrents.system import pathops
from pycurrents.adcp.rdiraw import extract_raw
import numpy as np

# Use a return code to tell repeater whether there was a problem.
retcode = 0

####### get options

usage = '\n'.join(["usage: %prog -d procdirname -n numpings ",
         " eg.",
         "  %prog -d nb150  ",
         "  %prog -d os38bb "])

parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
       help="processing directory name, eg. nb150, wh300, os38bb, os38nb")

parser.add_option("-n", "--numpings", dest="numpings",
help="extract last N pings ", default=10)

(options, args) = parser.parse_args()


if options.procdirname == None:
    LF.error('must choose processing directory name')
    sys.exit(1)

procdirname = options.procdirname

## test options
if procdirname[0:2] not in ('os', 'nb', 'wh', 'bb'):
    LF.error('Use UHDAS processing dir, e.g., nb150, os38bb, os38nb')
    sys.exit(1)


scriptutils.addHandlers(LF, procdirname, 'grab_pings')

try:   ## try/except for the entire body of the script
    cruiseinfo = procsetup()
    instname = cruiseinfo.instname[procdirname]
    rawdir = os.path.join(cruiseinfo.cruisedir, 'raw', instname)
    filelist=pathops.make_filelist(os.path.join(rawdir, '*.raw'))

    outfile = os.path.join(cruiseinfo.daily_dir, '%spings.raw' % (instname))
    i0=-1*np.abs(int(options.numpings))-1   #-11
    i1=-1                                 #-1
    infile=filelist[-1]

    data=extract_raw(infile, instname[:2], i0, i1, outfile=outfile, verbose=True)

except:
    LF.exception('In body of run_grab_lastpings.py')
    retcode += 8


sys.exit(retcode)
