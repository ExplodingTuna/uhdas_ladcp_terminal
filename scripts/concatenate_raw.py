#!/usr/bin/env python

"""
Concatenate .raw and .raw.log files that were split by bug in ser_bin.

In ser_bin prior to 2011/04/30, a power interruption to an adcp would
cause the generation of new .raw and .raw.log files, but not of
.raw.log.bin.  To process such data with the python version of
single-ping processing, we need to concatenate the .raw and .raw.log
files so that they correspond to the .raw.log.bin files and to
all the other data streams.

Usage: concatenate_raw.py sourcedir destdir
"""
from __future__ import print_function
from future.builtins import zip


import sys
import os
import glob

try:
    sourcedir, destdir = sys.argv[1:]
except ValueError:
    print(__doc__)
    sys.exit()

try:
    os.makedirs(destdir)
except OSError:
    pass

src_raw = glob.glob(os.path.join(sourcedir, '*.raw'))
src_raw.sort()
src_rawlog = glob.glob(os.path.join(sourcedir, '*.raw.log'))
src_rawlog.sort()
src_rawlogbin = glob.glob(os.path.join(sourcedir, '*.raw.log.bin'))
src_rawlogbin.sort()


print(len(src_raw))
print(len(src_rawlog))
print(len(src_rawlogbin))

if len(src_raw) != len(src_rawlog):
    print("raw and raw.log files don't match")
    sys.exit()

lastraw = None
lastrawlog = None
for raw, rawlog in zip(src_raw, src_rawlog):
    match_rawlogbin = rawlog + ".bin"
    if match_rawlogbin in src_rawlogbin:
        os.system("/bin/cp %s %s" % (raw, destdir))
        os.system("/bin/cp %s %s" % (rawlog, destdir))
        os.system("/bin/cp %s %s" % (match_rawlogbin, destdir))
        lastraw = os.path.join(destdir, os.path.basename(raw))
        lastrawlog = os.path.join(destdir, os.path.basename(rawlog))
    else:
        os.system("/bin/cat %s >> %s" % (raw, lastraw))
        os.system("/bin/cat %s >> %s" % (rawlog, lastrawlog))
