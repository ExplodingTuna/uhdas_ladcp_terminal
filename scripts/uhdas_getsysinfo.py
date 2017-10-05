#!/usr/bin/env python

import commands, os

cmdlist = ['fdisk -l',
           'df -h',
           'sudo blkid',
           'cat /etc/fstab',
           'lspci',
           'lsusb',
           'lscpu',
           'lsblk',
           'lshw',
           'cat /etc/lsb-release',
           'uname -a',
           'cat /proc/meminfo | grep Mem',
           'ifconfig -a',
           'rsync -a /etc/NetworkManager/system-connections/ NetworkManager',
           ]

outfile = 'sysinfo.txt'

outlist = []
for cmd in cmdlist:
    status, output = commands.getstatusoutput(cmd)
    outlist.append('\n#========# %s #==========#\n' % (cmd))
    if status:
        outlist.append(status)
        print 'failed. running as root?'
    else:
        outlist.append(output)

open(outfile,'w').write('\n'.join(outlist))
os.chown(outfile, 51076, 1076)

print 'wrote to ', outfile
