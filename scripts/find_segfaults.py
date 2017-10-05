#!/usr/bin/env python
"""
Quick script to summarize all unique segfault messages in
dmesg.txt from tarballs.

We may want to generalize this so that we can search only
tarballs after a given time, and/or a list of ships rather
than all ships.
"""
from __future__ import print_function


import tarfile
import os
import glob

basedir = "/home/moli4/users/uhdas/ships"


def search_shipdir(dir):
    segfaults = []
    tarfiles = {}
    first_dm = ""
    files = glob.glob(os.path.join(dir, 'tarfiles', '*.tar.gz'))
    for fn in files:
        tf = tarfile.open(fn)
        try:
            dm = tf.extractfile('dmesg.txt')
        except KeyError:
            continue
        except IOError:
            print('IOError:', fn)
            continue
        if first_dm == "":
            first_dm = fn
        seglines = [line for line in dm.readlines() if line.find('segfault') >= 0]
        newsegs = [seg for seg in seglines if seg not in segfaults]
        segfaults.extend(newsegs)
        for seg in newsegs:
            tarfiles[seg] = os.path.split(fn)[-1]
    return segfaults, tarfiles, first_dm

def search_ships(basedir):
    ships = glob.glob(os.path.join(basedir, '*'))
    results = {}
    for ship in ships:
        results[os.path.split(ship)[-1]] = search_shipdir(ship)
    return results

def report_all(basedir):
    results = search_ships(basedir)
    ships = list(results.keys())
    ships.sort()
    for ship in ships:
        sf, tf, dm1 = results[ship]
        print()
        print(ship)
        if dm1:
            print("  first dmesg.txt: ", dm1)
        print("-"*50)
        for seg in sf:
            print(tf[seg], ' ', seg)
        print("-"*50)

if __name__ == "__main__":
    report_all(basedir)
