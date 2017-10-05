#!/usr/bin/env python
"""
Quick summary of statistics of time difference between adcp
profiles in *.nav file, and fix times in *.gps file.

Usage
  python check_nav_dt.py dbname [navdir1, navdir2, navdir3]

dbname: prefix of dir.blk file
navdir1, navdir2, [etc] : list of nav directories  (defaults to cwd)

eg: from a uhdas cruise directory
   python check_nav_dt.py a_km proc/*/nav


"""
from __future__ import print_function
import os
import sys

import numpy as np
import numpy.ma as ma


if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()


def dtstat(navdir, dbname):
    gfname = os.path.join(navdir, dbname + '.gps')
    afname = os.path.join(navdir, dbname + '.nav')
    if not (os.path.exists(gfname) and os.path.exists(afname)):
        return
    gpst = np.loadtxt(gfname, comments='%', usecols=(0,), unpack=True)
    adcpt = np.loadtxt(afname, comments='%', usecols=(0,), unpack=True)
    gpst = ma.masked_equal(gpst, 1e38)
    adcpt = ma.masked_equal(adcpt, 1e38)

    dt = (adcpt - gpst) * 86400
    med = np.median(dt.compressed())
    print("%30s %4.1f %4.1f %4.1f %4.1f %4.1f" % (navdir,
                            dt.min(), dt.max(), dt.std(), dt.mean(), med))


dbname = sys.argv[1]
if len(sys.argv) == 2:
    navlist = [os.getcwd(),]
else:
    navlist = sys.argv[2:]

navlist.sort()


print("%30s %4s %4s %4s %4s %4s" % ("dataset",
                                    "min", "max", "std", "mean", "med"))
for navdir in navlist:
    try:
        dtstat(navdir, dbname)
    except:
        print("Can't calculate for %s" % (navdir,))
