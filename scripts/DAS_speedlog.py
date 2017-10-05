#!/usr/bin/env python

import sys
from uhdas.uhdas.DAS_speedlog import main

action = None
if len(sys.argv) > 1:
    args = sys.argv[1:]
    if 'replace' in args:
        action = 'replace'
    elif 'keep_old' in args:
        action = 'keep_old'

main(action=action)
