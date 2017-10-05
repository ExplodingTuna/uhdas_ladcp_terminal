#!/usr/bin/env python

'''

usage:
    uhdas_newntp.py -s shipletters [-o outfile]

action:
    revises orig file by
       - commenting out lines beginning with "server"
       - add lines "server xx.xx.xx.xx" for each ship server
    if outputfile is not specified, just print new file to stdout
       else
       - write file to specified location, use as replacement
       - moves /etc/ntp.conf to /etc/ntp.conf.orig
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import string, sys
import subprocess
from optparse import OptionParser

import onship.shipnames  as uh_shipnames

# keys are the same 2-letter abbreviation, eg. 'kk'
from pycurrents.adcp import uhdas_defaults


ntpfile = '/etc/ntp.conf'

if ('--help' in sys.argv) or (len(sys.argv) == 1):
    print(__doc__)
    sys.exit()


def new_ntpfile(IPlist):
    lines = open(ntpfile,'r').readlines()
    newlines=[]
    servernums = []
    count = 0
    for line in lines:
        if line[:6] == 'server':
            newlines.append('#'+line)
            servernums.append(count)
        else:
            newlines.append(line)
        count+=1
#
    splitnum= servernums[-1]+1
    serverlines = ['\n\n\n## ==> new server line for ship:\n']
    for arg in IPlist:
        serverlines.append('server %s\n' % (arg))
    allnewlines = newlines[:splitnum] + serverlines + newlines[splitnum:]
    return ''.join(allnewlines)


if __name__ == "__main__":
    icnf = None
    if '--shipinfo' in sys.argv:
        icnf = sys.argv.index('--shipinfo')
    elif '-p' in sys.argv:
        icnf = sys.argv.index('-p')

    if icnf is None:
        from  onship import shipnames
    else:
        shipinfo = sys.argv[icnf+1]
        mod = __import__(shipinfo)
        shipnames = getattr(mod, 'shipnames')

    qsletters=[]
    for k in shipnames.shipletters:
        qsletters.append("'%s'" % k)
    shipletters=string.join(qsletters,', ')

    usage = string.join(["\n\nusage for UH-managed ships:",
         "  ",
         " write a new /etc/ntp.conf file",
         "      uhdas_newntp.py  -s ka ",
         " ",
         " Usage for homebrewed collection of ships: ",
         " same as above, but add the following option (python module):",
         "     --shipinfo shipinfo  # or '-p shipinfo' ",
         " where 'shipinfo' has these files, ",
         " (consistent with the syntax in the 'onship' repository):",
         "     proc_defaults.py",
         "     uhdas_defaults.py",
         "     system_defaults.py",
         "     sensor_cfgs/XX_sensor_cfg.py  #XX is ship letters",
         " and  shipnames.py, consistent with pycurrents/adcp/shipnames.py",
         " ",
         "   choose one ship abbreviation from:",
         shipletters,
         "",
         "",
         ],
         '\n')

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)

    parser.add_option("-s",  "--shipkey", dest="shipkey",
       default=None,
       help="ship abbreviation")

    parser.add_option("-p",  "--shipinfo", dest="shipinfo",
       default=None,
       help="directory with ship configuration (compatible with 'onship')")

    parser.add_option("-o",  "--outfile", dest="outfile",
       default=None,
       help="temporary file with new ntp.conf info. default is to stdout, and no file copy")


    ## NOTE you cannot choose "--shipinfo onship" because
    ## shipnames.py is in pycurrents/adcp
    ## see pycurrents/adcp/uhdas_defaults for more info.

    (options, args) = parser.parse_args()

    if not options.shipkey:
        print(usage)
        raise IOError('MUST specify ship letters')
    if options.shipkey not in uh_shipnames.shipletters:
        print(usage)
        raise IOError('must specify CORRECT ship letters')



    shipkey = options.shipkey
    shipinfo = options.shipinfo
    Sdef = uhdas_defaults.System_defaults(shipkey=shipkey, shipinfo=shipinfo)

    newstr = new_ntpfile(Sdef.defaults['ntp_server'])

    if not options.outfile:
        print(newstr)
        print('\n\nwrote to stdout.  To write to file, use --outfile tmpfile')
    else:
        open(options.outfile,'w').write(newstr)

        cmd1 = 'sudo mv %s %s.orig' % (ntpfile, ntpfile)
        cmd2 = 'sudo cp %s  /etc/ntp.conf' % (options.outfile)
        status, output = subprocess.getstatusoutput(cmd1)
        if status:
            print(output)
            raise IOError('FAILED: %s' % (cmd1))

        status, output =subprocess.getstatusoutput(cmd2)

        if status:
            print(output)
            raise IOError('FAILED: %s' % (cmd2))
        else:
            print('copied %s to /etc/ntp.conf' % (options.outfile))
            cmd3 = 'diff /etc/ntp.conf.orig /etc/ntp.conf'
            status, output = subprocess.getstatusoutput(cmd3)
            print('results of\n%s' % (cmd3))
            print(output)

