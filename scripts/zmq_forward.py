#!/usr/bin/env python
"""
This is a very special-purpose, possibly temporary, script that
uses sub/pub pairs to forward the 4 standard localhost zmq
ports used by an autopilot system to the machines eth0 interface.

It is intended only for temporary use, mainly in development.

It is run with no arguments, and terminated with Ctrl-C.

"""

from __future__ import print_function

import sys
import subprocess
import zmq

ports = ['38000', '38010', '38020', '38030']
localhost = "127.0.0.1"

eth0 = subprocess.check_output("ifconfig eth0", shell=True).decode('ascii')

print(eth0)

ip = None
for line in eth0.split('\n'):
    line = line.strip()
    if line.startswith("inet addr:"):
        ip = line[10:].split()[0]
        break
if ip is None:
    print("Failed to find host address.")
    sys.exit(-1)

def addr(ip, port):
    return "tcp://%s:%s" % (ip, port)

def forward(sub, pub):
    msg = sub.recv()
    pub.send(msg)

context = zmq.Context()

pairs = []
for port in ports:
    sub = context.socket(zmq.SUB)
    pub = context.socket(zmq.PUB)
    sub.set_hwm(5)
    pub.set_hwm(5)
    sub.setsockopt_string(zmq.SUBSCRIBE, u'')
    sub.connect(addr(localhost, port))
    pub.bind(addr(ip, port))
    pairs.append((sub, pub))

poller = zmq.Poller()
for sub, pub in pairs:
    poller.register(sub, zmq.POLLIN)

while True:
    ready = poller.poll()
    for sub, pub in pairs:
        for socket, event in ready:
            if sub == socket:
                forward(sub, pub)


