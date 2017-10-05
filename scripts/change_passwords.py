#!/usr/bin/env  python
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import string
import subprocess
import sys
from optparse import OptionParser


#####
#########

if __name__ == "__main__":

    usage = string.join(["\n\nusage:",
       " \n\nRUN AS ROOT\n\n ",
       " change_passwords.py [-u userlist]  [--root] [-n] password\n",
       " options are",
       "    -u userlist           # colon-delimited list of directories",
       "                          # default splits to this list        ",
       "                          #   ['adcp', 'science',",
       "                          #   'adcpproc', 'uhdas_admin',",
       "                          #   'jules', 'efiring']",
       "    -r [--root]           #  add 'root' to the list",
       "    -n                    # NO don't do it, just print the commands",
       " "],
       '\n')


    parser = OptionParser(usage)

    parser.add_option("-u",  dest="userlist",
       default=':'.join(['adcp', 'science',
                         'jules', 'efiring',
                         'adcpproc', 'uhdas_admin']),
       help="colon-delimited list of users for password change")

    parser.add_option("-r", "--root", dest="doroot",
       action="store_true",
       help="change root password also",
       default=False)

    parser.add_option("-n", dest="donot",
       action="store_true",
       help="echo commands, do not perform",
       default=False)

    (options, args) = parser.parse_args()
    if len(args) != 1:
        print(usage)
        print('\n\nmust specify one password')
        sys.exit()

    userlist = options.userlist.split(':')
    if options.doroot:
        userlist.append('root')

    password = args[0]
    for user in userlist:
        cmd = "echo %s:%s | chpasswd" % (user, password)
        if options.donot:
            print(cmd)
        else:
            print('running %s' % (cmd,))
            status, output = subprocess.getstatusoutput(cmd)
            if status != 0:
                print(output)
                print('\n\n --> must be run as root (or sudo).  Are you root??\n')
                sys.exit()

