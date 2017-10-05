#!/usr/bin/env python

## JH alter showlast.py

'''
show long listing of last n files (ascii order), or last few lines of files
ascii output                -a     2
raw logging                 -l     2
rbin directories            -r     2
rootdir (optional) is the root directory containing raw/, rbin/

      usage: showlast.py  [-a num]  [-l num] [-r num]  rootdir

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
# JH 2003/07/01
import sys, os, string
import re, glob, getopt
from subprocess import getoutput

def find_instruments(basedirname):
    inst_list=[]
    startdir = os.getcwd()
    if os.path.exists(basedirname):
        os.chdir(basedirname)
    dirlist = os.listdir('./')
    for  d  in dirlist:
        if os.path.isdir(d):
            inst_list.append(d)
    os.chdir(startdir)
    return(inst_list)


def tailfiles(basedirname, instname, numlines = 0, verbose=False):
    # tail of ascii files (number refers to number of lines of each type)
    # basedirname is rawdir or rbindir
    startdir = os.getcwd()
    dirname = os.path.join(basedirname, instname)
    if os.path.exists(dirname):
        os.chdir(dirname)
        globstr = '*'
        files = glob.glob(globstr)
        if len(files) > 0:
            files.sort()
            lastfile = files[-1]
            print('\n------- %s: -------\n' %  instname)
            command = 'tail -%d %s' % (2*numlines, lastfile)
            print(getoutput(command))

    os.chdir(startdir)

def listfiles(basedirname, instname,  numfiles = 0, verbose=False):
    # list logged files (number refers to number of files of each type)
    # basedirname is rawdir or rbindir
    startdir = os.getcwd()
    dirname = os.path.join(basedirname, instname)
    if verbose: print(dirname)
    if os.path.exists(dirname):
        os.chdir(dirname)
        filenames = os.listdir('./')
        if  len(filenames) > 0:
            filenames.sort()
            lastfiles = filenames[-numfiles :]
            print('\n------- %s: -------\n' %  instname)
            command = 'ls -l %s' % string.join(lastfiles,' ')
            print(getoutput(command))
    os.chdir(startdir)


# --- end of listfiles


def usage():
    print(__doc__)

# end of usage   ----------


###-----------------------------------------------------------


# get the options
try:
    options, args = getopt.getopt(sys.argv[1:], 'a:l:r:hv',
       ['num_asc=', 'num_log=', 'num_rbin=', 'help', 'verbose' ])
except getopt.GetoptError:
    usage()

help = 0
verbose = False
num_asc = 0
num_log = 0
num_rbin = 0

for o, a in options:
    if o in ('-l', '--logging'):
        num_log = string.atoi(a)
    if o in ('-a', '--ascii'):
        num_asc = string.atoi(a)
    elif o in ('-h', '--help'):
        usage()
    elif o in ('-v', '--verbose'):
        verbose = True

### main

if (num_asc + num_log + num_rbin == 0):
    usage()

if len(args) == 1:
    rootdir = args[0]
    print('root directory is %s\n' % (rootdir))
else:
    rootdir = '/home/data/0mon'

if not os.path.exists(rootdir):
    print('raw root directory %s does not exist' % (rootdir))
    sys.exit()

rawdir      = os.path.join(rootdir, 'raw')

instnames = find_instruments(rawdir)

# list raw logging

if (num_asc > 0):
    print("\n===== ascii data (%s) : last few lines ==============" % (rawdir))
    for instname in instnames:
        pname = os.path.join(rawdir, instname)
        if os.path.exists(pname):
            tailfiles(rawdir, instname,
                      numlines=num_asc, verbose=verbose)
    print('')


if (num_log > 0):
    print("\n===== raw data (%s) : last few files ==============" % (rawdir))
    for instname in instnames:
        pname = os.path.join(rawdir, instname)
        if os.path.exists(pname):
            listfiles(rawdir, instname,
                      numfiles=num_log, verbose=verbose)
    print('')


if (num_rbin > 0):
    print("\n===== rbin data (%s) : last few files ==============" % (rbindir))
    rbinbase = os.path.join(basedirname, 'rbin')
    for instname in instnames:
        pname = os.path.join(rbinbase, instnames)
        if os.path.exists(pname):
            listfiles(rbinbase, 'rbin', instname,
                      numfiles=num_rbin, verbose=verbose)
    print('')

