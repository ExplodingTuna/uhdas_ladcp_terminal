#!/usr/bin/env python
'''
Clean up figures and data when logging starts and stops.

This must be called with the actual cruise directory
as the first command-line argument; the symlink in /home/adcp
will not suffice, because it may not exist when this is
run.

The second argument must be either "not_logging" or "no_figure".
'''

from uhdas.system.cleanup_figs import main

main()

