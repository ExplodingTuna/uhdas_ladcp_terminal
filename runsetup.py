#!/usr/bin/env python

"""
Build and install uhdas. This is a wrapper for
the standard setup.py.  It is a simplified version of its
counterpart in pycurrents.  It does not presently handle
the serial_c subdirectory.

IMPORTANT: codas3 must already have been installed, and
the path to its binaries must already be on your PATH.

There are two possible installation modes:

- in place: the build stage is run, which checks that Python
  code can be byte-compiled, but no installation is done. This
  mode is selected with the --inplace option.

- normal: "setup.py build; setup.py install" is run. Distutils
  defaults are used, with one exception that is described
  below. If the installation
  location is the linux standard, /usr/local, you will need to use
  the --sudo option. Do not use sudo directly on the runsetup.py
  command, and do not use the --sudo option unless you need to.

By default, only two "user" scripts will be installed; for a
full UHDAS installation, use the --all option.  This is passed
to the setup.py script.

It is assumed that on Windows, a version of gcc has been found
and used to compile codas3.

Note that there is no need to use runsetup.py at all; you can
use, for example, the Python standard

    python setup.py build --all
    sudo python setup.py install --all

with any of the normal setup.py options.

The special case handled by runsetup.py is this: if the codas
installation prefix is a path that starts with the Python sys.prefix,
then scripts will be installed in the codas binary location.

"""
from __future__ import print_function


import os
import subprocess
import sys
import shutil
from optparse import OptionParser

#from pycurrents.setup_helper import find_codasbase

def main():
    parser = OptionParser()
    parser.add_option('--scratch', action='store_true',
                                   default=False,
                                   help='delete build directory first')
    parser.add_option('--clean', action='store_true',
                                   default=False,
                                   help='delete build directory')
    parser.add_option('--inplace', action='store_true',
                                   default=False,
                                   help='build extensions inplace')
    parser.add_option('--show', action='store_true',
                                   default=False,
                                   help='show installation prefix and exit')
    parser.add_option('--sudo', action='store_true',
                                   default=False,
                                   help='use sudo for install step')
    parser.add_option('--all', action='store_true',
                                   default=False,
                                   help='install all scripts')

    options, args = parser.parse_args()

    print("Python executable for building is", sys.executable)

    #codas_prefix = find_codasbase()
    #print("codas prefix is", codas_prefix)

    scripts = None
    #if codas_prefix.startswith(sys.prefix):
    #    print("Using codas prefix for scripts: ", codas_prefix)
    #    scripts = os.path.join(codas_prefix, 'bin')

    if options.show:
        return

    if options.clean:
        clean()
        return

    if options.scratch:
        clean()

    build(options, scripts)

def build(options, scripts):
    cmd = sys.executable
    if options.inplace:
        cmd += ' setup.py build_ext --inplace '
    else:
        cmd += ' setup.py build'
    if options.all:
        cmd += ' --all'
    print('running command:')
    print(cmd)
    subprocess.call(cmd.split())

    if not options.inplace:
        cmd = ''
        if options.sudo:
            cmd += 'sudo '
        cmd += sys.executable
        cmd += ' setup.py install'
        if scripts is not None:
            cmd += ' --install-scripts=%s ' % scripts
    if options.all:
        cmd += ' --all'
    print('running command:')
    print(cmd)
    subprocess.call(cmd.split())


def clean():
    remove_build()

def remove_build():
    if not os.path.exists('build'):
        return
    print('removing build directory')
    for dirpath, dirnames, filenames in os.walk('build', topdown=False):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            #print 'deleting ', p
            os.remove(p)
        for dir in dirnames:
            p = os.path.join(dirpath, dir)
            #print 'removing', p
            os.rmdir(p)
    os.rmdir('build')

if __name__ == '__main__':
    main()


