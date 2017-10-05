#!/usr/bin/env python

from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

usage = ''' Summarizing mercurial status.  Runs an informational hg command
    on each Mercurial repository below the directory specified.
    Default directory is the current working directory
    You may use more than one hg command (these are read-only commands)
    For a list of available options, type "hgsummary.py --help"

    Usage: hgsummary.py [options] [dir]

    eg.
        hgsummary.py --log
        hgsummary.py --diff   codas3

    suggest:

        hgsummary.py --status


'''
verbose = True

import os, sys, glob, re, filecmp, getopt, subprocess
from optparse import OptionParser


#---------------------------------

def check_opts(val, allowed):
    if val not in allowed:
        print(' ')
        print(__doc__)
        print('\n\n\nname <%s> is unacceptable.\n' % (val))
        print('choose one of the following:\n')
        print(allowed)
        sys.exit()

#---------------------------------

def varvals(opts):
    strlist = []
    keys = list(opts.keys())           ## need to do this in two lines:
    keys.sort()                  ## (1) get keys, (2) sort it

    for key in keys:
        s = '%s   %s' % (key.ljust(30), str(opts[key]))
        strlist.append(s)
    s = '\n\n'
    strlist.append(s)

    print(' ')
    print(('\n'.join(strlist)))

#----------------------------------

def hgstr(hgdir=None, hgcommand=None):
    '''echo output of "hg command" applied to hgdir
    '''
    if hgdir is None:
        hgdir = os.getcwd()
    if hgcommand is None:
        hgcommand = 'status'

    cmd = "hg %s" % (hgcommand,)
    status, output = subprocess.getstatusoutput(cmd)

    if status != 0:
        raise subprocess.CalledProcessError(status, cmd, output)

#----------------------------------

class OP(OptionParser):
    '''Modified to print a full help message in case of parse error.
    '''
    def error(self, msg):
        self.print_help()
        print(msg)
        sys.exit()

#######################################################

def main():

    # set up this dictionary for help and list of options
    hdict={}
    hdict['--cat']      = 'output the latest or given revisions of files'
    hdict['--diff']     = 'diff working directory (or selected files)'
    hdict['--heads']    = 'show current repository heads'
    hdict['--identify'] = 'print information about the working copy'
    hdict['--log']      = 'show revision history of entire repository or files'
    hdict['--manifest'] = 'output the latest revision of the project manifest'
    hdict['--parents']  = 'show the parents of the working dir or revision'
    hdict['--status']   = 'show changed files in the working directory'
    hdict['--tags']     = 'list repository tags'
    hdict['--tip']      = 'show the tip revision'
    hdict['--verify']   = 'verify the integrity of the repository'
    hdict['--version']  = 'output version and copyright information'

    # use option parser for nicer-looking help
    parser = OP(usage=usage)
    for opt in hdict.keys():
        parser.add_option(opt,
                          action="store_true",
                          default="False",
                          help=hdict[opt])
    (options, args) = parser.parse_args()

    # get the list of arguments from the command line directly
    if len(sys.argv) == 1:  # no switches or arguments
        basedir = './'
    elif sys.argv[-1][0:2] != '--':
        basedir = sys.argv[-1]
    else:
        basedir = './'

    ## get directory list
    cmd = "find %s -name .hg -type d" % (basedir,)
    status, output = subprocess.getstatusoutput(cmd)
    if len(output) == 0:
        print("no repositories below here")
        sys.exit()

    repolist = output.split('\n')
    repolist.sort()

    olist = [aa for aa in sys.argv if aa[0:2]=='--']
    if len(olist) == 0:
        print('---------------\nno options specified\n---------------\n')
        print(usage)

    for o in olist:
        print('checking option %s\n' % (o,))
        check_opts(o, list(hdict.keys()))

    for o in olist:
        option = o[2:]
        print('hg: checking %s\n' % (option,))
        for repo in repolist:
            print("------------------------------------------\n")
            cmd = "hg %s -R %s" % (option, os.path.dirname(repo),)
            print('%s\n' % (cmd,))
            status, output = subprocess.getstatusoutput(cmd)
            print(output)


if __name__ == '__main__':
    main()
