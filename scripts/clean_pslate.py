#!/usr/bin/env python

# run this to clear out processing directories enough to
#      start over with processing
# for at-sea processing, only when logging is stopped, but cruise is 'live'

from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
import os, glob
from optparse import OptionParser
from uhdas.uhdas.procsetup import procsetup

usage = '\n'.join(["delete processing files for a clean slate",
                     " NOT TO BE UNDERTAKEN LIGHTLY ",
                     " ",
                     "usage: %prog  -d procdirname --del_gbins --DOIT",
                     "   eg.",
                     "       %prog --del_gbins -d nb150         # to show files only",
                     "       %prog --del_gbins -d nb150 --DOIT  # to do it",
                     " \n",
                     " \n",
                     "----------------------",
                     " basically, performs these commands (from processing directory):\n",
                     " /bin/rm `find . -name ens\*`",
                     " /bin/rm `find . -name \*log` ",
                     " /bin/rm adcpdb/*blk ",
                     " #or, more generally (where 'aship' is the database name):",
                     " /bin/rm `find . -name aship\*  ",
                     "----------------------",
                     ""])


parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
      help="processing directory name, eg. nb150, wh300, os38bb, os38nb")
parser.add_option("--del_gbins",
                  action="store_true",
                  dest="del_gbins",
                  default= False)
parser.add_option("--DOIT",
                  action="store_true",
                  dest="doit",
                  default= False)

(options, args) = parser.parse_args()


## make an instance;  copy of the dictionary for formatting

cruiseinfo = procsetup()
cid = cruiseinfo.__dict__.copy()

if options.procdirname == None:
    parser.error('must choose processing directory name')
procdirname = options.procdirname

## test options
if procdirname not in cid['procdirnames']:
    parser.error('Use a UHDAS processing dir:\n%s' % ("\n".join(cid['procdirnames'])))


instname = cid['instname'][procdirname]
cruiseid = cid['cruiseid']
gbindir = '/home/data/%s/gbin/%s' % (cruiseid, instname)


print('doit is ', options.doit)

if options.doit == False:
    sstr = 'would be deleting '
else:
    sstr = 'deleting '


if options.del_gbins:
    print('=========== gbin files ============= ')
    print('finding ALL gbin files from ', gbindir, '\n\n')
    gbinlist = glob.glob('%s/*/*.gbin' % (gbindir))
    for gbinfile in gbinlist:
        print(sstr, gbinfile)
        if options.doit:
            os.remove(gbinfile)


## now delete various important files in the processing directory

fullprocdir = os.path.join("/home/data/%s/proc" % \
                 (cruiseinfo.cruiseid), procdirname)
os.chdir(fullprocdir)

print('=========== processing directory =============')
print('from directory ', fullprocdir)

# load
loadlist = glob.glob('load/ens*')
loadlist.append('load/write_ensblk.log')
# adcpdb
dblist = glob.glob('adcpdb/*blk')
# cal
callist = ['cal/rotate/rotate.log',
           'cal/rotate/ens_hcorr.err',
           'cal/rotate/ens_hcorr.log',
           'cal/rotate/ens_hcorr.ang',
           'cal/watertrk/adcpcal.out',
           'cal/botmtrk/btcaluv.out']


print('\n=======>  deleting files from load/\n')
for fname in loadlist:
    if os.path.exists(fname):
        print(sstr, fname)
        if options.doit:
            os.remove(fname)

print('\n=======>  deleting files from adcpdb/\n')
for fname in dblist:
    if os.path.exists(fname):
        print(sstr, fname)
        if options.doit:
            os.remove(fname)

print('\n=======>  deleting files from cal/\n')
for fname in callist:
    if os.path.exists(fname):
        print(sstr, fname)
        if options.doit:
            os.remove(fname)
