#!/usr/bin/env python
"""
Print messages from zmq publishers.

Specify publisher addresses via command-line arguments.

"""

from __future__ import unicode_literals

import sys
import zmq

if len(sys.argv) < 2 or '-h' in sys.argv or '--help' in sys.argv:
    print('Supply zmq address[es] as command-line arguments')
    sys.exit(0)

context = zmq.Context()
poller = zmq.Poller()

sockets = []
for addr in sys.argv[1:]:
    sock = context.socket(zmq.SUB)
    sock.setsockopt_string(zmq.SUBSCRIBE, '')
    sock.connect(addr)
    poller.register(sock, flags=zmq.POLLIN)
    sockets.append(sock)

if not sockets:
    sys.exit(0)

while True:
    events = dict(poller.poll())
    for sock, event in events.items():
        msg = sock.recv().decode('ascii', 'ignore')
        print(msg)


