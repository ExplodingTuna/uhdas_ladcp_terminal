#!/usr/bin/env python
'''
Clean up and archive figure files after a cruise.

This must be called with the actual cruise directory
as the only command-line argument; the symlink in /home/adcp
will not suffice, because it may not exist when this is
run.
'''

from uhdas.system.cleanup_archive import main

main()

