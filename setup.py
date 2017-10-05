from __future__ import print_function

import os
import sys
import glob

from numpy.distutils.core import setup
from numpy.distutils.extension import Extension
import numpy

#from pycurrents.setup_helper import write_hg_status
#write_hg_status()  #  give dir argument if/when we switch to "lib"

all_opt = "--all"
install_all = False
if all_opt in sys.argv:
    print("Installing all scripts")
    install_all = True
    sys.argv.remove(all_opt)
else:
    print("Installing only user scripts; use '--all' option for all scripts")

print("Possibly modified setup argument list is:\n  ", ' '.join(sys.argv[1:]))

ext_modules = []

packages = ['uhdas',
            'uhdas.uhdas',
            'uhdas.serial',
            'uhdas.system',
            ]

package_data = dict()

user_scripts = ['scripts/tk_terminal.py',
                'scripts/showlast.py',
                'scripts/hgsummary.py',
                'scripts/repo_status.py',
                ]

if install_all:
    script_files = glob.glob('scripts/*.py')
    scripts = []
    for fname in script_files:
        with open(fname, 'rt') as f:
            topline = f.readline()
        if "#!/usr/bin/env" in topline:
            scripts.append(fname)
else:
    scripts = user_scripts

print("Installing these scripts:\n  ", "\n   ".join(scripts))

setup(
      name = 'uhdas',
      packages=packages,
      package_dir={'uhdas':''},
      package_data=package_data,
      ext_modules = ext_modules,
      scripts=scripts,
)

