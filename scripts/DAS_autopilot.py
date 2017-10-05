#!/usr/bin/env python

"""
Unattended operation of UHDAS for the VOS application.

"""
from __future__ import print_function

import sys, os, signal
import time
from optparse import OptionParser

from uhdas.uhdas.autopilot import Autopilot, read_config

flagdir = '/home/adcp/flags'
runflag = os.path.join(flagdir, 'DAS_autopilot.running')
stopflag = os.path.join(flagdir, 'DAS_autopilot.stop')

configfile = '/home/adcp/config/autopilot_cfg.py'

if __name__ == '__main__':
    parser = OptionParser()

    parser.add_option("--stop", action="store_true", dest="stop",
                      help="kill any pre-existing DAS_autopilot process, "
                            "and exit",
                      default=False)

    parser.add_option("--query", action="store_true", dest="query",
                      help="show running processes and exit",
                      default=False)

    parser.add_option("--check_config", action="store_true", dest="check",
                      help="show config info and exit",
                      default=False)

    options, args = parser.parse_args()

    if options.query or options.stop:
        def get_pid(runflag):
            try:
                with open(runflag, 'rt') as rf:
                    return int(rf.readline())
            except (OSError, IOError, TypeError):
                return None

        pid = get_pid(runflag)
        if pid is None:
            print("No other running DAS_autopilot.py was found")
            sys.exit(0)

        os.system('ps -p %s --no-headers' % pid)
        if options.query:
            sys.exit(0)

        if options.stop:
            with open(stopflag, 'w') as sf:
                pass
            print('shutting down', end='')
            for i in range(50):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except OSError:
                    print("\npid %s ended via stopflag" % pid)
                    sys.exit(0)
                print('.', end='')
            print("\nsending SIGKILL to pid %s" % pid)
            os.kill(pid, signal.SIGKILL)
            sys.exit(0)


    if options.check:
        if not os.path.isfile(configfile):
            print("file %s is not found" % configfile)
            sys.exit(0)
        print(read_config(configfile))
        sys.exit(0)

    # normal on-boot exit for research ships (not running autopilot)
    if not os.path.isfile(configfile):
        sys.exit(0)

    # If we got here, we will run in autopilot mode, replacing
    # any existing process.
    config = read_config(configfile)

    autopilot = Autopilot(flagdir=flagdir,
                          action='replace',
                          args=(config,), # tuple with one member
                          )
    autopilot.start()

