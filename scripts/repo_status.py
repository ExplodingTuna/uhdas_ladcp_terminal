#!/usr/bin/env  python
'''
This program is a shortcut to getting tip+status for common groups of repos.
It was primarily created as a tool for managing UHDAS directories.

Groups are
-u (uhdas)    #default
-l (ladcp)
-a (all)

Other options:
-i (installed) -- print out "hg_status.installed" if it exists
-s (short) -- print out changeset and rev number

            repo_status.py [options]


'''
## GOTCH:  At present this imports HGinfo and everything else
## locally, if run from within a PROGRAMS directory.
## FIXME: options for solving:
##   - manipulate sys.path (dangerous)
##   - change directories (eg "cd ..") run it, and change back
##            (did not work, even with most imports in __main__)



from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import os
import string
import sys

from uhdas.system.repo_summary import HGinfo  # imported locally, if in PROGRAMS
from optparse import OptionParser

def useful_message():
    print('FAILED\n\n')
    print(__doc__)
    cwd = os.getcwd()
    astr = '\n'.join(sys.argv)
    print('possibly try changing to another directory and then run it, eg.')
    print('cd; %s -d %s' % (astr, cwd))


more_uhdas_repolist = ['matlab', 'moreships']
ladcp_repolist = ['ladcp', 'ladcp_srcdoc','geomag']


if __name__ == "__main__":


    usage = string.join(["\n\nusage:",
       "  ",
       " repo_status.py  [options] [additional_repos]\n",
       " NOTE: NO repos are listed; you must choose something to list:",
       " options are",
       "    --uhdas  [-u]     # repos for a UHDAS installation",
       "                      #    presently:",
       "                      #   ['adcp_srcdoc',",
       "                      #   'codas3', 'pycurrents', 'uhdas',",
       "                      #   'onship', 'onship_private', 'pytide', 'scripts',]",
       "    --more_uhdas [-m] #  ['matlab', 'moreships',]",
       "    --ladcp  [-l]     # just repos of interest for ladcp, ",
       "                      #    presently:",
       "                      #   ['ladcp', 'ladcp_srcdoc','geomag']",
       "    --all    [-a]     # all",
       "    --repolist [-r]   # colon-delimited list of repos",
       "    --installed [-i]  # show hg_status.py for requested repos",
       "    --short [-s]      # just show changeset and rev number ",
       "                      #                                     ",
       " "],
       '\n')


    parser = OptionParser(usage)


    parser.add_option("-u","--uhdas", action="store_true", dest="uhdas_repos",
                      default=True)
    parser.add_option("-m","--more_uhdas", action="store_true",
                      dest="more_uhdas_repos", default=False)
    parser.add_option("-l","--ladcp", action="store_true", dest="ladcp_repos",
                      default=False)
    parser.add_option("-a","--all", action="store_true", dest="all_repos",
                      default=False)
    parser.add_option("-i","--installed", action="store_true", dest="installed",
                      default=False)
    parser.add_option("-s","--short", action="store_true", dest="short",
                      default=False)
    parser.add_option("-d", "--dir", dest="repobase", default='.')
    parser.add_option("-r", "--repolist", dest="repolist", default=None)
                        # base directory

    (options, args) = parser.parse_args()


    HG = HGinfo()

    repobase = options.repobase

    if options.all_repos:
        HG.get_all_repos(repobase)
        repolist = HG.repolist
    else:
        repolist=[]
        if options.uhdas_repos:
            for r in HG.uhdas_repolist:
                repolist.append(os.path.join(repobase, r))
        if options.more_uhdas_repos:
            for r in more_uhdas_repolist:
                repolist.append(os.path.join(repobase, r))
        if options.ladcp_repos:
            for r in ladcp_repolist:
                if r not in repolist:
                    repolist.append(os.path.join(repobase, r))

    if options.repolist is not None:
        rlist = options.repolist.split(':')
        for r in rlist:
            if r not in repolist:
                repolist.append(os.path.join(repobase, r))

    for arg in args:
        if arg not in repolist:
            repolist.append(os.path.join(repobase, arg))

    if len(repolist) == 0:
        print(usage)
        sys.exit()

    outlist = []
    for r in repolist:
        s = HG.assemble_strings(r, show_installed=options.installed,
                                short=options.short)
        outlist.append(s)

    outlist.append('\n')
    print('\n'.join(outlist))
