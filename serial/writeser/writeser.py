#!/usr/bin/env python

'''
2001/02/06 EF
This is a script for writing data from a file to
a serial port, for use in testing data logging
routines.
'''
import  sys, os, os.path, time,  types, getopt

from uhdas.serial.serialport import *


if __name__ == '__main__':
    baud = 9600
    gap = 1
    format = 'line'
    port = '/dev/ttyS0'
    optlist, args = getopt.getopt(sys.argv[1:], 'P:b:g:f:',
                   ['port=', 'baud=', 'gap=', 'format='])
    for o, a in optlist:
        if o in ('-b', '--baud'):
            baud = int(a)
        elif o in ('-g', '--gap'):
            gap = float(a)
        elif o in ('-f', '--format'):
            format = a
        elif o in ('-P', '--port'):
            port = a

    print(args)
    print()
    sp = serial_port(device=port, baud=baud)
    sp.open_port()
    w = writer(sp, format=format, gap=gap)
    w.sendfiles(args)
    sp.close_port()

