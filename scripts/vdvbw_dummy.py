"""
Test jig: send zmq $VDVBW messages
"""

import time
import zmq
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:38020")

t0 = time.time()

def vdvbw_msg():
    minutes = (time.time() - t0) / 60
    u = np.random.randn(1)[0] + np.sin(minutes) + np.sin(minutes/4)
    v = np.random.randn(1)[0] + np.cos(minutes/2) + np.cos(minutes/6)
    return ("$VDVBW,%.2f,%.2f,A,,," % (u, v)).encode('ascii')

while True:
    msg = vdvbw_msg()
    socket.send(msg)
    print(msg)
    time.sleep(1)
