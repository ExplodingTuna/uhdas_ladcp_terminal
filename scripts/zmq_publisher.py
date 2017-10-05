#!/usr/bin/env python
'''
Read sensor_cfg.py and read the "monitors" section.
Generate a call to
Launch that process
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import logging, logging.handlers
from pycurrents.system import logutils
import sys, os, time
import signal
import subprocess
from optparse import OptionParser

from pycurrents.system import Bunch, safe_makedirs

#-----------------

LF = logging.getLogger()
LF.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
LF.addHandler(handler)

formatter = logutils.formatterTLN
logbasename = '/home/adcp/log/zmq_monitor'

handler = logging.handlers.RotatingFileHandler(logbasename+'.log', 'a',
                                              100000, 9)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
LF.addHandler(handler)

handler = logging.handlers.TimedRotatingFileHandler(logbasename+'.warn',
            'midnight', 1, 20)
handler.setLevel(logging.WARNING)
handler.setFormatter(formatter)
LF.addHandler(handler)

#----------------



def get_process_list(cmd, dir):
    """
    Returns a list of lists.

    Each entry in the list contains two strings; the first
    is the PID, the second is the command line.
    """
    ps = os.popen('ps -C %s -o pid,args --no-headers' % cmd)
    procs = ps.readlines()
    procs = [l.strip() for l in procs if cmd in l and dir in l]
    pidcmds = [l.split(None,1) for l in procs]
    # Exclude the present process, in case we want to use this
    # to ensure only a single zmq_publisher.py is running.
    pidcmds = [p for p in pidcmds if int(p[0]) != os.getpid()]
    return pidcmds


def check_zmq(out_dir_base):
    '''
    return all instances of 'ser_asc_zmq'
    '''
    plist=get_process_list('ser_asc_zmq', out_dir_base)
    if plist:
        for p in plist:
            LF.info('found %s', p)
    else:
        LF.info('No instances of ser_asc_zmq found')
    return plist


def check_serialports(publish_dict):
    '''
    check whether serial port exists
    '''
    found_ports = []
    for subdir in publish_dict.keys():
        publisher = publish_dict[subdir]
        device = publisher['in_device']
        sp = '/dev/%s' % (device)
        if os.path.exists(sp):
            found_ports.append(sp)
        else:
            msg = 'serial port %s does not exist' % (sp)
            LF.error(msg)
            sys.exit(1)
    return found_ports

#----------------

def generate_zmq_cmds(sensor_file, out_dir_base, year=None):
    '''
    read sensor_cfg.py and use sensors and publishers; glean info
    "subdir" name identifies publisher

    '''

    ## now read the file and look for variables
    ## Control of publishers depends on "use_publishers" in sensor_cfg.py
    S = Bunch().from_pyfile(sensor_file)
    sensors = S.sensors

    # for sensor_cfg not yet zmq-enabled
    if 'use_publishers' not in S.keys():
        return None, None

    if not S.use_publishers :
        return None, None

    # now we think we have a modern sensor_cfg.py
    publishers = S.publishers
    publish_dict = dict((x['subdir'], x) for x in publishers)

    cmdlist = []

    for subdir in publish_dict.keys():
        publisher = Bunch(publish_dict[subdir])
        publisher.out_dir = os.path.join(out_dir_base, publisher.subdir)
        if not os.path.exists(publisher.out_dir):
            os.mkdir(publisher.out_dir)
        if year is None:
            publisher.year=time.gmtime(time.time()).tm_year

        elist = []
#        for s in publisher.strings[:1]:  # Use only the first: gga
        for s in publisher.strings:    # undo changeset 868: need all messages
            if s[0] == '$':
                elist.append('\\%s' % (s))  #need to have an extra here
            else:
                elist.append(s)
        publisher.esc_strings = ' '.join(elist)
        publisher.file_opts =  '-f zzz -m 1 -H 24 -F'

        # fill in options
        zlist = [
            # these options come from Sensor publisher
            " -Z %(pub_addr)s", # tcp://127.0.0.1:6789
            " %(sample_opts)s",   # '-tc -s60'
            ## these come from sensor:
            " -b %(baud)d",       # 9600
            " -P %(in_device)s",  # 'ttyUSB3'
            " -e %(ext)s",        # extension 'gps'
            # these are generated above
            " -d %(out_dir)s",    # '/home/data/0mon/raw/gpsnav'
            " -y %(year)d",       # 2015
            " %(file_opts)s",     # '-f zzz -m 1 -H 24 -F'
            " %(esc_strings)s ",  # '\$GPGGA'  (modified with escapes)
        ]
        cmd= "ser_asc_zmq" + ' '.join(zlist) % (publisher)
        cmdlist.append(cmd)
    return cmdlist, publish_dict


#-------

def start_zmq(cmd, quiet=False):
    LF.info('about to start command: ' + cmd)
    qstr=''
    if quiet:
        qstr = ' >  /dev/null 2>&1 '
    subprocess.call(cmd + qstr + ' &', shell=True)

#--------

sensor_file = '/home/adcp/config/sensor_cfg.py'
out_dir_base = '/home/data/0mon/raw'

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("--quiet", action="store_true", dest="quiet",
                      help="redirect stderr+stdout to /dev/null",  default=False)

    parser.add_option("--stop", action="store_true", dest="stop",
                      help="kill all ser_asc_zmq conduits",  default=False)

    parser.add_option("--start", action="store_true", dest="start",
                      help="start ser_asc_zmq conduit",  default=False)

    parser.add_option("--show_cmds", action="store_true", dest="show_cmds",
                    help="show commands used to start ser_asc_zmq publishers",
                      default=False)

    parser.add_option("--debug", action="store_true", dest="debug",
                    help="show dictionaries used to make  commands",
                      default=False)

    parser.add_option("--query", action="store_true", dest="query",
                      help="show running processes and exit",
                      default=False)

    parser.add_option("-d", "--out_dir_base", default=out_dir_base,
                      dest='out_dir_base',
                      help="output directory for zmq output files")

    parser.add_option("--sensor_file", default=sensor_file, dest='sensor_file',
                      help="file containing 'publishers' ")

    (options, args) = parser.parse_args()

    if not (options.stop or options.start or options.show_cmds or options.query):
        msg='no action. must choose from --start, --stop, --show_cmds, --debug, --query'
        LF.error(msg)

    if options.start:
        if not os.path.isdir(options.out_dir_base):
            try:
                safe_makedirs(options.out_dir_base)
                LF.info('Made output directory: %s', options.out_dir_base)
            except:
                LF.exception('Failed to make output directory: %s',
                              options.out_dir_base)
                sys.exit(1)

    if options.start or options.show_cmds:
        if not os.path.exists(options.sensor_file):
            LF.error('sensor file %s does not exist', options.sensor_file)
            sys.exit(1)

    out_dir_base = options.out_dir_base
    zlist = check_zmq(out_dir_base)
    if options.query:
        sys.exit(0)

    if options.start or options.stop:  # always kill old before starting
        for p in zlist:
            msg = 'terminating ' + str(p[0])
            LF.info(msg)
            try:
                os.kill(int(p[0]), signal.SIGTERM)
            except:
                pass
        time.sleep(0.2)
        for p in check_zmq(out_dir_base):
            try:
                LF.info('using SIGKILL on %s', p[0])
                os.kill(int(p[0]), signal.SIGKILL)
            except:
                pass

        if len(zlist):  # we tried to kill some
            zlist = check_zmq(out_dir_base)  # do they remain?
            if len(zlist):
                LF.error('ser_asc_zmq processes survived assassination attempt')
                sys.exit(1)

        if options.stop:
            sys.exit(0)


    if options.start or options.show_cmds:
        cmdlist, publish_dict = generate_zmq_cmds(options.sensor_file,
                                                    options.out_dir_base)
        if cmdlist is None:
            estr = '\n'.join(['no command generated.',
                              'check "use_publisers=False" in sensor_cfg.py?'])
            LF.error(estr)
            sys.exit(1)

        if options.debug:
            LF.debug('\ncmdlist is: ' + str(cmdlist))
            LF.debug('\npublish_dict is: ' + str(publish_dict))

        if options.show_cmds:
            for cmd in cmdlist:
                LF.info(cmd)
            sys.exit(0)

    if options.start:
        check_serialports(publish_dict)
        for cmd in cmdlist:
            try:
                LF.info('starting zmq...')
                start_zmq(cmd, quiet=options.quiet)
                if options.debug:
                    LF.debug('starting:\n' + cmd)
            except:
                LF.exception("Failed to start: %s", cmd)
        time.sleep(0.5)
        zlist = check_zmq(out_dir_base)
        if not zlist:
            LF.error('Process did not start')


## aiming at this:
'''
 ser_asc_zmq
-b 9600
-P ttyUSB3
-d /home/data/0mon/raw
-y 2015
-e gps
-f zzz -F -m 1 -H 24
-tc -s60
-Z tcp://127.0.0.1:6789
\$GPGGA
'''
