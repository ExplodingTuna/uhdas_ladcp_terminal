#!/usr/bin/env  python
'''
consolidate heading correction and time-since-email
'''
from __future__ import division
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import object

import sys, string
from optparse import OptionParser

from onship import shipnames
from uhdas.system.uhdas_webparse import MonitorTable



#========

if __name__ == "__main__":

    usage = string.join(["\n\nusage:",
             "  ",
             " uhdas_webparse.py --outfile      # stats and html to file",
             " "],
             '\n')

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)

    parser.add_option("-w",  "--website", dest="website",
       default='/home/moli20/htdocs/uhdas_fromships',
       help="read ship information from this web site")

    parser.add_option("--outfile",  action="store_true",
                      dest="outfile",
                      help="output to predefined OUPUT files", default=False)

    (options, args) = parser.parse_args()


    shipkeys = shipnames.shipkeys
    shipkeys.sort()

    ## uhdas_fromships with email age
    skiplist = ['ka', 'we', 'zzz', 'oc_whoi', 'ti', 'mv', 'kn',]  #TODO -- move this to onship
    shortshipkeys = []
    for kk in shipnames.shipkeys:
        if kk not in skiplist:
            shortshipkeys.append(kk)

    H=MonitorTable(shortshipkeys)
    H.make_ttable()

    if options.outfile:
        outfile = '/home/moli20/htdocs/uhdas_fromships.html'
        open(outfile,'w').write('\n'.join(H.tlist))
        print('wrote to ' + outfile)

