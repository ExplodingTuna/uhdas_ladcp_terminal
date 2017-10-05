#!/usr/bin/env python

## JH adapted for UHDAS; 2004/09/15

'''
show long listing of last n files (ascii order), or last few lines of files
ascii output                -a     2
raw logging                 -l     2
rbin directories            -r     2
gbin directories            -g     2
rootdir (optional) is the root directory containing raw/, rbin/ or gbin/

      usage: showlast.py  [-a num]  [-l num] [-r num] -g num] rootdir

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
# JH 2003/07/01
import sys, os, string
import re, glob, getopt
from subprocess import getoutput

def find_adcps(basedirname):
    '''
    look for inst + freq, where
             inst is in ['os','nb','bb','wh']
             freq is an integer
    '''
    adcp_types = ['os','nb','bb','wh']
    found_adcps = []
    regex = re.compile('[a-z]{2,2}(\d+)')
    for name in glob.glob(os.path.join(basedirname,'*')):
        if not os.path.isdir(name):
            continue
        [pathname, dirname] = os.path.split(name)
        if dirname[:2] in adcp_types:
            if regex.match(dirname):
                found_adcps.append(dirname)
    return found_adcps



def tailfiles(basedirname, msglist, instname,  numlines = 0, verbose=False):
    # tail of ascii files (number refers to number of lines of each type)
    startdir = os.getcwd()
    dirname = os.path.join(basedirname, instname)
    if verbose: print(dirname)
    if os.path.exists(dirname):
        os.chdir(dirname)
        if msglist == 'raw.log': # raw
            globstr = '*%s' % (msglist,)
            files = glob.glob(globstr)
            if len(files) > 0:
                files.sort()
                lastfile = files[-1]
                print('\n------- %s: -------\n' %  instname)
                command = 'tail -%d %s' % (numlines, lastfile)
                print(command)
                print(getoutput(command))
        else: # ascii
            globstr = '*'
            files = glob.glob(globstr)
            if len(files) > 0:
                files.sort()
                lastfile = files[-1]
                print('\n------- %s: -------\n' %  instname)
                command = 'tail -%d %s' % (2*numlines, lastfile)
                print(getoutput(command))

    os.chdir(startdir)

def listfiles(basedirname, msglist, instname,  numfiles = 0, verbose=False):
    # list logged files (number refers to number of files of each type)
    startdir = os.getcwd()
    dirname = os.path.join(basedirname, instname)
    if verbose: print(dirname)
    if os.path.exists(dirname):
        os.chdir(dirname)
        if msglist is None:
            globstr = '*'
            files = glob.glob(globstr)
            files.sort()
            lastfiles = files[-numfiles :]
            if instname != '':
                print('\n------- %s: -------\n' %  instname)
            if (len(files) > 0):
                command = 'ls -l %s' % string.join(lastfiles,' ')
                print(getoutput(command))
        elif msglist is 'raw':
            rawext = ['raw', 'log', 'bin', 'err']
            print('\n------- %s: -------\n' %  instname)
            for ext in rawext:
                globstr = '*.%s' % (ext,)
                files = glob.glob(globstr)
                files.sort()
                lastfiles = files[-numfiles :]
                if (len(files) > 0):
                    command = 'ls -l %s' % string.join(lastfiles,' ')
                    print(getoutput(command))
                    print(' ')
        else:
            filenames = os.listdir('./')
            msglist = []
            for f in filenames:
                fields = f.split('.')
                if len(fields) == 3:
                    msg = fields[1]
                    if msg not in msglist:
                        msglist.append(msg)
            for msg in msglist:
                globstr = '*.%s.*' % (msg)
                files = glob.glob(globstr)
                if len(files) > 0:
                    files.sort()
                    lastfiles = files[-numfiles :]
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
    options, args = getopt.getopt(sys.argv[1:], 'a:l:r:g:hv',
       ['num_asc=', 'num_log=', 'num_rbin=', 'num_gbin=', 'help', 'verbose' ])
except getopt.GetoptError:
    usage()

help = 0
verbose = False
num_asc = 0
num_log = 0
num_rbin = 0
num_gbin = 0


for o, a in options:
    if o in ('-l', '--logging'):
        num_log = string.atoi(a)
    if o in ('-a', '--ascii'):
        num_asc = string.atoi(a)
    if o in ('-r', '--rbin'):
        num_rbin = string.atoi(a)
    if o in ('-g', '--gbin'):
        num_gbin = string.atoi(a)
    elif o in ('-h', '--help'):
        usage()
    elif o in ('-v', '--verbose'):
        verbose = True

### main

if (num_asc + num_log + num_rbin + num_gbin== 0):
    usage()

if len(args) == 1:
    rootdir = args[0]
    print('root directory is %s\n' % (rootdir))
else:
    rootdir = '/home/adcp/cruise'

if not os.path.exists(rootdir):
    print('raw root directory %s does not exist' % (rootdir))
    sys.exit()

rawdir      = os.path.join(rootdir, 'raw')
rbindir     = os.path.join(rootdir, 'rbin')
gbindirbase = os.path.join(rootdir, 'gbin')  # prefix instrument

instnames = find_adcps(rawdir)
if verbose: print('instnames:' , instnames)
rbinnames = os.listdir(rbindir)
if verbose: print('rbinnames:', rbinnames)
try:
    gbinnames = os.listdir(os.path.join(gbindirbase, instnames[0]))
    if verbose: print('gbinnames: ' , gbinnames)
except:
    gbinnames = []


# list raw logging

if (num_asc > 0):
    print("\n===== ascii data (%s) : last few lines ==============" % (rawdir))
    for instname in instnames:
        pname = os.path.join(rawdir, instname)
        if os.path.exists(pname):
            tailfiles(rawdir, 'raw.log' , instname,
                      numlines=num_asc, verbose=verbose)
            print('')
    for serdir in rbinnames:
        pname = os.path.join(rawdir, serdir)
        if os.path.exists(pname):
            tailfiles(rawdir, None , serdir,
                      numlines=num_asc, verbose=verbose)
    print('')


if (num_log > 0):
    print("\n===== raw data (%s) : last few files ==============" % (rawdir))
    for instname in instnames:
        pname = os.path.join(rawdir, instname)
        if os.path.exists(pname):
            listfiles(rawdir, 'raw' , instname,
                      numfiles=num_log, verbose=verbose)
            print('')
    for serdir in rbinnames:
        pname = os.path.join(rawdir, serdir)
        if os.path.exists(pname):
            listfiles(rawdir, None , serdir,
                      numfiles=num_log, verbose=verbose)
    print('')


if (num_rbin > 0):
    print("\n===== rbin data (%s) : last few files ==============" % (rbindir))
    for serdir in rbinnames:
        pname = os.path.join(rbindir, serdir)
        if os.path.exists(pname):
            listfiles(rbindir, 'rbin', serdir,
                      numfiles=num_rbin, verbose=verbose)
    print('')


if (num_gbin > 0):
    for instname in instnames:
        gbindir = os.path.join(gbindirbase, instname)
        if verbose: print(gbindir)
        if os.path.exists(gbindir):
            print("\n===== gbin data (%s) : last few files ==============" % (gbindir))
            for gbinname in gbinnames:
                gdir = os.path.join(gbindir, gbinname)
                if os.path.exists(gdir):
                    listfiles(gbindir, None, gbinname,
                              numfiles=num_gbin, verbose=verbose)
        else:
            print('%s: no gbin files' % (instname))

    hdir = os.path.join(gbindirbase, 'heading')
    if os.path.exists(hdir):
        print("\n =====  hbin data (%s) =======\n" % (hdir))
        listfiles(hdir, None, '', numfiles=num_gbin, verbose=verbose)
