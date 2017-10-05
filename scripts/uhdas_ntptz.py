#!/usr/bin/env  python
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
import string
import subprocess
import sys
from optparse import OptionParser


### Precise 12.04 default ntp.conf, with one template for server
ntp_str = '''
# /etc/ntp.conf, configuration for ntpd; see ntp.conf(5) for help

driftfile /var/lib/ntp/ntp.drift


# Enable this if you want statistics to be logged.
#statsdir /var/log/ntpstats/

statistics loopstats peerstats clockstats
filegen loopstats file loopstats type day enable
filegen peerstats file peerstats type day enable
filegen clockstats file clockstats type day enable

# Specify one or more NTP servers.

# Use servers from the NTP Pool Project. Approved by Ubuntu Technical Board
# on 2011-02-08 (LP: #104525). See http://www.pool.ntp.org/join.html for
# more information.
$server

# Access control configuration; see /usr/share/doc/ntp-doc/html/accopt.html for
# details.  The web page <http://support.ntp.org/bin/view/Support/AccessRestrictions>
# might also be helpful.
#
# Note that "restrict" applies to both servers and clients, so a configuration
# that might be intended to block requests from certain clients could also end
# up blocking replies from your own upstream servers.

# By default, exchange time with everybody, but don't allow configuration.
restrict -4 default kod notrap nomodify nopeer noquery
restrict -6 default kod notrap nomodify nopeer noquery

# Local users may interrogate the ntp server more closely.
restrict 127.0.0.1
restrict ::1

# Clients from this (example!) subnet have unlimited access, but only if
# cryptographically authenticated.
#restrict 192.168.123.0 mask 255.255.255.0 notrust


# If you want to provide time to your local subnet, change the next line.
# (Again, the address is an example only.)
#broadcast 192.168.123.255

# If you want to listen to time broadcasts on your local subnet, de-comment the
# next lines.  Please do this only if you trust everybody on the network!
#disable auth
#broadcastclient

'''

def get_serverlines():
    output=subprocess.getoutput('grep server /etc/ntp.conf')
    lines=output.split('\n')
    serverlines=[]
    for line in lines:
        parts = line.split()
        if parts[0] == 'server':
            serverlines.append(line)
    return serverlines


#####
#########

if __name__ == "__main__":

    usage = string.join(["\n\nusage:",
       " \n\nRUN AS ROOT to change ntp server\n\n ",
       " check_ntptz.py [-s server] \n",
       " ",
       " show timezone information and ntp server",
       " optionally, replace make /etc/ntp.conf use specified server"
       " options are",
       "    -s server             # ntp server to use",
       " "],
       '\n')


    parser = OptionParser(usage)

    parser.add_option("-s","--server",  dest="server",
       default=None,   help="ntp server to use")

    (options, args) = parser.parse_args()

    cmdlist = [
        'strings /etc/localtime',
        'cat /etc/timezone',
        ]
    print('----------------------')
    for cmd in cmdlist:
        status, output = subprocess.getstatusoutput(cmd)
        if status != 0:
            print(output)
            print('\n\n --> must be run as root (or sudo).  Are you root??\n')
            sys.exit()
        else:
            print('output from "%s":' % (cmd))
            print(output)
            print('----------------------')

    serverlines = get_serverlines()
    print('/etc/ntp.conf server lines:\n ', '\n'.join(serverlines))
    print('----------------------')


    if options.server is not None:
        s=string.Template(ntp_str)
        ss=s.substitute(server='server %s' % (options.server))
        try:
            open('/etc/ntp.conf','w').writelines(ss)
            print('wrote ntp.conf  \nNew server line:')
            serverlines = get_serverlines()
            print('/etc/ntp.conf server lines:\n ', '\n'.join(serverlines))


        except:
            print('\n\n --> Failed.')
            print('Must be run as root (or sudo).  Are you root??\n')
            raise

