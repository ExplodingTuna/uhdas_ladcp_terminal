#!/usr/bin/env  python
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
import os
import string
import subprocess
import sys
from optparse import OptionParser
from importlib import import_module


#####
#########

if __name__ == "__main__":

    usage = string.join([
    "This program HAS CHANGED."
    " - it must be run from the UH programs root directory, $prog,",
    "   eg. /home/currents/programs.  ",
    " - it will dump the output of 'repo_status.py' (status, tip) for the",
    "       directories below, into a file in onship/repo_tags,"
    " - the 'tag' below, should have NO SPACES, and",
    "       - should have the ship name YYYY-MM-DD_shipname_computer",
    "       - sets the name of the file",
    "       - is used in the commit message for the new file",
    "\n\nusage:",
    "  ",
    " tag_repos.py  -u name  [options]   tagname\n",
    " options are",
    "    -R repolist    # colon-delimited list of directories",
    "                   # default splits to this list        ",
    "                   #   ['adcp_srcdoc', 'codas3', 'pycurrents',",
    "                   #    'onship', 'onship_private', 'uhdas',  ", 
    "                   #    'scripts', 'pytide'   ]",
    "                   #                                    ",
    "    -u name        # REQUIRED username (quote it if using spaces)",
    " ",
    " eg:\n\n     tag_repos.py -ujules 2012-11-01_ronbrown_currents43"],
    '\n')


    parser = OptionParser(usage)


    parser.add_option("-R",  dest="repos",
       default=':'.join(['adcp_srcdoc',  'codas3', 'pycurrents',
                          'onship', 'onship_private','uhdas',
                          'scripts', 'pytide']),
       help="colon-delimited list of repositories to tag")

    parser.add_option("-u",  dest="user",
       default=None,
       help="username; quote if there are spaces")


    (options, args) = parser.parse_args()

    if len(args) != 1:
        print(usage)
        print('\n\nMUST specify tagname')
        sys.exit()

    tagname = args[0]
    if ' ' in tagname:
        print(usage)
        print('\n\FAILED: tagname cannot have spaces')
        sys.exit()

    if options.user is None:
        print(usage)
        print('\n ERROR : must have user name')
        sys.exit()
    else:
        if ' ' in options.user:
            print(usage)
            print('\n\FAILED: username cannot have spaces')
            sys.exit()


    outfile = 'onship/repo_tags/%s.txt' % (tagname)
    if os.path.exists(outfile):
        print('NOT overwriting existing file %s. \nCHOOSE A NEW NAME' % (outfile))
        sys.exit()
    cmd = 'repo_status.py --install -r %s' % (options.repos)
    output = subprocess.getoutput(cmd)
    output += '\n'
    open(outfile,'w').write(output)

    msg =  '%s: adding repo_status.py output added to onship/repo_tags' % (tagname)
    print(msg)


    cmd1 = 'hg add %s' % (outfile)
    cmd2 = 'hg commit -R onship -u %s -m "%s"' % (options.user, msg)
    print(cmd1)
    output = subprocess.getoutput(cmd1)

    print(cmd2)
    output = subprocess.getoutput(cmd2)

    print('\n\n to see the output, do this:\ncat %s' % (outfile))






