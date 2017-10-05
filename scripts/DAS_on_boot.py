#!/usr/bin/env python

"""
This is run at boot time by a script in ~adcp/scripts,
which is in turn run by rc.local.
"""

import subprocess

cmd = "zmq_publisher.py --start --quiet"
subprocess.call(cmd, shell=True)

cmd = "printenv > /home/adcp/log/env.log"
subprocess.call(cmd, shell=True)

cmd = "export DISPLAY=:0.0; DAS_autopilot.py > /home/adcp/log/on_boot.log 2>&1 &"
subprocess.call(cmd, shell=True)

