#!/usr/bin/env python

'''
usage:
    uhdas_newssh.py [-o outfile] [-p port1[:port2]]

action:
    revises orig file by
       - adding a line with an additional default (or specified) port (s)
       - if outputfile is not specified, just print new file to stdout
            else
            - write file to specified location, use as replacement
            - moves /etc/ssh/sshd_config  to /etc/ssh/sshd_config.orig

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import sys

from optparse import OptionParser
import subprocess

sshfile = '/etc/ssh/sshd_config'

if '--help' in sys.argv:
    print(__doc__)
    sys.exit()


def new_sshfile(portlist):
    lines = open(sshfile,'r').readlines()
    newlines=[]
    iport = []
    count = 0
    for line in lines:
        if line[:4] == 'Port':
            iport.append(count)
        newlines.append(line)
        count+=1
#
    splitnum= iport[-1]+1
    portlines = ['## ==> new ssh for ship:\n']
    for arg in portlist:
        portlines.append('Port %s\n' % (arg))
    portlines.append('\n')
    allnewlines = newlines[:splitnum] + portlines + newlines[splitnum:]
    return ''.join(allnewlines)

if __name__ == "__main__":
    icnf = None


    usage = __doc__

    parser = OptionParser(usage)

    parser.add_option("-p",  "--ports", dest="ports",
       default=None,
       help="colon-delimited list of ports to add")

    parser.add_option("-o",  "--outfile", dest="outfile",
       default=None,
       help="temporary file with new ntp.conf info. \ndefault is to stdout, and no file copy")


    ## NOTE you cannot choose "--shipinfo onship" because
    ## shipnames.py is in pycurrents/adcp
    ## see pycurrents/adcp/uhdas_defaults for more info.

    (options, args) = parser.parse_args()

    if options.ports:
        ports = options.ports.split(':')
    else:
        ports = ['30075']

    newstr = new_sshfile(ports)

    if not options.outfile:
        print(newstr)
        print('\n\nwrote to stdout.  To write to file, use --outfile tmpfile')
    else:
        open(options.outfile,'w').write(newstr)

        cmd1 = 'sudo mv %s %s.orig' % (sshfile, sshfile)
        status, output = subprocess.getstatusoutput(cmd1)
        print(output)
        if status:
            raise IOError('FAILED: %s' % (cmd1))

        cmd2 = 'sudo cp %s  /etc/ssh/sshd_config' % (options.outfile)
        status, output =subprocess.getstatusoutput(cmd2)
        print(output)
        if status:
            raise IOError('FAILED: %s' % (cmd2))
        else:
            print('copied %s to /etc/ssh/sshd_config.conf' % (options.outfile))
            cmd3 = 'diff /etc/ssh/sshd_config.orig /etc/ssh/sshd_config'
            status, output = subprocess.getstatusoutput(cmd3)
            print('results of \n%s' % (cmd3))
            print(output)

