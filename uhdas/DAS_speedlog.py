"""
Speedlog script routine.  The stub is in scripts.

There are two styles: the old $PUHAW,UVH for the Palmer
and Gould, and the new and standard $VDVBW message.  VMDAS
can generate the latter.  The former likely will be retired
at the next LMG upgrade; it works only for the NB150, and its
code is much more complicated than the new VDVBW code.
"""

from __future__ import absolute_import
from __future__ import division
from future.builtins import object, PY3

import time, os
from threading import Thread
import array
from functools import reduce

import zmq
import numpy as np

from pycurrents.file.fileglob import fileglob
from pycurrents.file.binfile import binfile
from pycurrents.file.ascfileglob import out_ascfileglob
from pycurrents.num.ringbuf import Ringbuf as rb
from pycurrents.system.pmw_process import SingleFunction
from pycurrents.system.threadgroup import ThreadGroup
from pycurrents.system import Bunch
from pycurrents.adcp.rdiraw import FileBBWHOS
from pycurrents.adcp.transform import Transform, heading_rotate

from uhdas.uhdas.messages import good_attitude_dict, i_heading_dict
from uhdas.serial.serialport import serial_port
from uhdas.uhdas.make_globs import make_rbin_glob


import logging, logging.handlers
L = logging.getLogger()
L.setLevel(logging.INFO)  # change to DEBUG if enabling the debug handler
formatter = logging.Formatter('%(asctime)s %(message)s')

logbasename = '/home/adcp/log/DAS_speedlog.log'
tmplogname = '/home/adcp/uhdas_tmp/DAS_speedlog.log'

## for debugging
#handler = logging.handlers.RotatingFileHandler(tmplogname, 'a', 100000, 9)
#handler.setLevel(logging.DEBUG)
#handler.setFormatter(formatter)
#L.addHandler(handler)

handler = logging.handlers.RotatingFileHandler(logbasename,
                                               'a', 100000, 3)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
L.addHandler(handler)

handler = logging.handlers.RotatingFileHandler(logbasename+'.warn',
                                               'a', 100000, 3)
handler.setLevel(logging.WARNING)
handler.setFormatter(formatter)
L.addHandler(handler)


kt_per_mps = 1.943844


def good_soundspeed(S):
    s = float(S[1])
    if s > 1450 and s < 1600:
        return 1
    return 0

notes = '''
Both the soundspeed and the heading classes are rudimentary
in the extreme, with no checking to see that the values
returned are current and reasonable.

'''

class Soundspeed(object):
    def __init__(self, cruisedir = "/home/adcp/cruise",
                 sensor = 'sndspd',
                 msg = 'spd'):
        self.cruisedir = cruisedir
        self.sensor = sensor,
        self.msg = msg,
        self.good_soundspeed = good_soundspeed
        self.i_soundspeed = 1
        self._glob = make_rbin_glob(sensor, msg,
                                    os.path.join(cruisedir, 'rbin'))
        self.stream = fileglob(self._glob, binfile, False)
        self.stream.end_of_stream()
        self.soundspeed_record = None

    def get_last_soundspeed(self):
        records = [r for r in self.stream if self.good_soundspeed(r)]
        if len(records):
            self.soundspeed_record = records[-1]
        if self.soundspeed_record is not None:
            return float(self.soundspeed_record[self.i_soundspeed])


class Heading(object):
    def __init__(self, cruisedir = "/home/adcp/cruise",
                 sensor = 'seapath',
                 msg = 'sea'):
        self.cruisedir = cruisedir
        self.sensor = sensor,
        self.msg = msg,
        self.good_heading = good_attitude_dict[msg]
        self.i_heading = i_heading_dict[msg]
        self.heading_glob = make_rbin_glob(sensor, msg,
                                           os.path.join(cruisedir, 'rbin'))
        self.stream = fileglob(self.heading_glob, binfile, False)
        self.stream.end_of_stream()
        self.heading_record = None

    def get_last_heading(self):
        records = [r for r in self.stream if self.good_heading(r)]
        if len(records):
            self.heading_record = records[-1]
        if self.heading_record is not None:
            return float(self.heading_record[self.i_heading])
        #Note: if there is a dropout of valid data, this will
        # keep returning the last valid value it saw.

class Speedlog(object):
    """
    Speedlog class for ancient narrowband; this will go away
    when the last nb150 is retired.
    """
    def __init__(self, cruisedir = "/home/adcp/cruise",
                 instrument = 'nb150',
                 serial_device = '',
                 baud = 9600,
                 dir_output = '',
                 get_heading = lambda : 0.0,  ## must be overridden
                 get_soundspeed = lambda : 1536.0,
                 heading_offset = 0.0,
                 scale = 1.0,
                 bins = (1, 12),
                 threadgroup = None):

        if instrument == 'nb150':
            from pycurrents.data.adcp.nbfile import PingFromRawLog, PingParser
            from pycurrents.data.adcp.nbspeed import get_speed
            self.nominal_SS = 1536.0
        else:
            raise NotImplementedError
        self.get_speed = get_speed
        self.cruisedir = cruisedir
        self.serial_device = serial_device
        self.default_soundspeed = self.nominal_SS
        self.baud = baud
        self.get_heading = get_heading
        self.get_soundspeed = get_soundspeed
        self.heading_offset = heading_offset
        self.scale = scale
        self.threadgroup = threadgroup
        self.i0, self.i1 = bins
        if threadgroup:
            self.timer = threadgroup.timer
            self.running = threadgroup.keep_running
        else:
            self.timer = time.sleep
            self.running = lambda x: True

        self.port = serial_port(device = serial_device, mode = 'w', baud = baud)
        self.port.open_port()
        self.rbU = rb(12) # needs to be a tunable parameter?
        self.rbV = rb(12)
        self.pingparser = PingParser()

        raw_glob = os.path.join(self.cruisedir, 'raw', instrument, '*.raw.log')

        self.raw_stream = fileglob(raw_glob, PingFromRawLog, False)
        self.raw_stream.end_of_stream()

        if dir_output:
            self.outstream = out_ascfileglob(self.raw_stream,
                                             dir_output, '.uvh')
        else:
            self.outstream = None

    def __del__(self):
        self.port.close_port()

    def run(self):
        L.info('Speedlog starting')
        loopcount = 0
        noheading = 0
        msgcount = 0
        while self.running():
            try:
                for record in self.raw_stream:
                    v = self.pingparser.get_V_stream(record)
                    H = self.get_heading()
                    if H is None:
                        L.warning('No heading')
                        self.timer(10.0) # Wait, to throttle the warnings.
                        noheading += 1
                        if noheading > 1:
                            L.warning('Still no heading; quitting')
                            self.port.close_port()
                            return
                        continue
                    noheading = 0
                    H1 = H + self.heading_offset
                    (U, V, n) = self.get_speed(v, self.i0, self.i1, H1)
                    msg = self.update(U, V, n, H)
                    if msg:
                        msgcount += 1
                        if msgcount % 1000 == 0:
                            L.info('msg %d, loop %d: %s',
                                    msgcount, loopcount, msg.rstrip())
                        L.debug(msg.rstrip())
                        self.port.stream.write(msg)
                        self.port.stream.flush()
                        if self.outstream:
                            self.outstream.write(msg)  # add timestamp later
                        loopcount = 0
            except:
                L.exception('Main loop in speedlog.run; quitting')
                self.port.close_port()
                return
            self.timer(0.5)
            loopcount += 1
            if loopcount > 100:
                L.warning('100 loops, no message, quitting')
                self.port.close_port()
                return # give up and restart the whole thing
                # This is probably overly conservative;
                # normally this exit will only mean that there
                # are no valid velocities.

    def update(self, U, V, n, H):
        SS = self.get_soundspeed()
        if SS is None:
            SS = self.default_soundspeed
        msg = ''
        if n > 0:
            cal = self.scale * SS / self.nominal_SS
            U *= cal
            V *= cal
            self.rbU.add(U)
            self.rbV.add(V)
            if self.rbU.N_good() > 3:
                msg = "$PUHAW,UVH,%.2f,%.2f,%.1f\r\n" % (
                       self.rbU.mean() * kt_per_mps,
                       self.rbV.mean() * kt_per_mps, H)
            else:
                L.debug('Not enough good estimates: %d', self.rbU.N_good())
        else:
            L.debug('in update, n = 0')
        return msg



class SpeedlogRunner(SingleFunction):
    '''
    Outer shell for running the speedlog.

    This works for the old (NB150) and new (OS WH BB) speedlog.
    '''
    def __init__(self, flagdir = None, action=None, kwargs = {}):
        SingleFunction.__init__(self, flagdir = flagdir, action=action,
                                kwargs = kwargs)
        self.__dict__.update(kwargs)
        self.kwargs = kwargs

    def keep_running(self):
        return (os.path.isfile(self.flagfile) and
                not os.path.isfile(self.stopflagfile))

    def run(self, *args, **kwargs):
        TG = ThreadGroup(keep_running = self.keep_running)

        if self.instrument.startswith('nb'):
            H = Heading(sensor = self.heading_sensor,
                        msg = self.heading_msg)

            if self.soundspeed_sensor is None:
                get_soundspeed = lambda: self.nominal_soundspeed
            else:
                S = Soundspeed(cruisedir = self.cruisedir,
                               sensor = self.soundspeed_sensor,
                               msg = self.soundspeed_msg)
                get_soundspeed = S.get_last_soundspeed
            SL = Speedlog(serial_device = self.serial_device,
                          dir_output = self.dir_output,
                          get_heading = H.get_last_heading,
                          get_soundspeed = get_soundspeed,
                          heading_offset = self.heading_offset,
                          scale = self.scale,
                          bins = self.bins,
                          threadgroup = TG)
        else:
            SL = Speedlog2(threadgroup=TG, params=self.kwargs)

        th = Thread(target = SL.run)
        TG.add(th)
        TG.start()
        while self.keep_running() and th.isAlive():
            TG.timer(1.0)
            os.utime(self.flagfile, None) # Touch the flagfile.
        L.debug("Ready to call TG.stop()")
        TG.stop()
        L.debug("After TG.stop()")


class Velsmooth(object):
    def __init__(self, n, weights=None):
        self.n = n
        self.weights = weights
        self.vel = np.ma.zeros((n, 2), dtype=float)
        self.vel[:] = np.ma.masked

    def update(self, uv):
        self.vel[:-1] = self.vel[1:]
        self.vel[-1] = uv
        weights = self.weights
        if weights is None:
            return self.vel.mean(axis=0)
        mask0 = np.ma.getmaskarray(uv[:, 0])
        if mask0.any():
            mweights = np.ma.array(weights, mask=mask0)
            uvsm = uv * mweights[:, np.newaxis] / mweights.sum()
        else:
            uvsm = uv * weights[:, np.newaxis] / weights.sum()
        return uvsm

# The following is here in case someone needs this non-standard
# way of handling missing data; we will probably delete this
# function.
def to_VBW_zero(sf, btsf):
    template = "$VDVBW,%.2f,%.2f,A,%.2f,%.2f,A"
    ss, ff = sf.filled(0)
    bss, bff = btsf.filled(0)
    return template % (ff, ss, bff, bss)

def to_VBW_blank(sf, btsf):
    """
    Generate the core of a VBW message.

    *sf* and *btsf* are 2-element masked arrays with u, v
    from water and bottom tracking, respectively.

    Returns a string with the message up to the checksum.
    """
    parts = ["$VDVBW"]
    if sf.count() >= 2:
        ss, ff = sf.data
        parts.append("%.2f,%.2f,A" % (ff, ss))
    else:
        parts.append(",,")
    if btsf.count() >= 2:
        ss, ff = btsf.data
        parts.append("%.2f,%.2f,A" % (ff, ss))
    else:
        parts.append(",,")
    return ','.join(parts)

def terminate_NMEA1(msg):
    """
    Terminate with checksum and CR LF.

    Takes a string; returns ascii bytes.
    """
    msg = msg.encode('ascii')  # now it is bytes on Py3
    # We are using the python algorithm from pycurrents/data/nmea/msg.py.
    # We could substitute a modification of the cython version,
    # but the python is probably fast enough.
    _bytes = array.array('B')
    if PY3:
        _bytes.frombytes(msg[1:])
    else:
        _bytes.fromstring(msg[1:])
    cs = reduce(lambda x, y: x ^ y, _bytes)
    msg += ("*%02X\r\n" % cs).encode('ascii')
    return msg

def terminate_NMEA2(msg):
    """
    Terminate without checksum.
    """
    msg = msg.encode('ascii')
    return msg + b'\r\n'

# Include the checksum
terminate_NMEA = terminate_NMEA1

class SpeedlogCalc(object):
    """
    Extract speedlog numbers from raw OS, WH, or BB data.
    """

    varlist = ('Velocity', 'BottomTrack')

    def __init__(self, data_dir, params):
        self.last_fname = ''
        self.last_raw = None
        self.tr = None  # Transform()  # angle=30, geometry='convex'
        self.params = Bunch(params)
        navg = self.params.get('navg', None)
        if navg is not None:
            self.smoother = Velsmooth(navg)
        self.navg = navg
        self.data_dir = data_dir
        self.sonar = self.params.instrument
        self.binslice = slice(*self.params.bins)

    def __call__(self, msg):
        star_for, bt_star_for = self.get_data(msg)
        msg_base = to_VBW_blank(star_for, bt_star_for)
        return terminate_NMEA(msg_base)

    def get_data(self, msg):
        msg = msg.decode('ascii').strip()   # fix this for python 2
        fname, offset, nbytes = msg.split()
        offset = int(offset)
        nbytes = int(nbytes)
        index = int(offset//nbytes)

        if fname != self.last_fname:
            raw = FileBBWHOS(os.path.join(self.data_dir, fname),
                             self.sonar, trim=False)
            self.last_fname = fname
            self.last_raw = raw
        else:
            raw = self.last_raw
            raw.refresh_nprofs()
        ppd = raw.read(varlist=self.varlist, ilist=[index])
        if self.tr is None:
            geom = 'convex' if ppd.sysconfig.convex else 'concave'
            self.tr = Transform(angle=ppd.sysconfig.angle,
                                geometry=geom)
        xyze = self.tr.beam_to_xyz(ppd.vel[0, self.binslice])
        bt_xyze = self.tr.beam_to_xyz(ppd.bt_vel[0])
        sfze = heading_rotate(xyze, self.params.heading_offset)
        bt_sfze = heading_rotate(bt_xyze, self.params.heading_offset)
        star_for = -sfze[:, :2].mean(axis=0) * kt_per_mps * self.params.scale
        bt_star_for = -bt_sfze[:2] * kt_per_mps * self.params.scale

        if self.navg is not None:
            star_for = self.smoother.update(star_for)
        return star_for, bt_star_for

class Speedlog2(object):
    """
    Thread for monitoring the ser_bin zmq publisher and
    sending a serial speedlog message when each ping arrives.
    """
    def __init__(self, threadgroup, params):
        self.threadgroup = threadgroup
        self.params = params

        # Socket to talk to server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(params.zmq_from_bin)
        zip_filter = ''
        # Python 2 - ascii bytes to unicode str
        if isinstance(zip_filter, bytes):
            zip_filter = zip_filter.decode('ascii')
        self.socket.setsockopt_string(zmq.SUBSCRIBE, zip_filter)

        if 'pub_addr' in params and params['pub_addr']:
            self.pub = self.context.socket(zmq.PUB)
            self.pub.bind(params['pub_addr'])
        else:
            self.pub = None

        data_dir = os.path.join(params.cruisedir, "raw", params.instrument)
        self.SC = SpeedlogCalc(data_dir=data_dir, params=params)

        if threadgroup:
            self.timer = threadgroup.timer
            self.running = threadgroup.keep_running
        else:
            self.timer = time.sleep
            self.running = lambda x: True

        if params.serial_device:
            self.port = serial_port(device=params.serial_device,
                                    mode='wb',
                                    baud=params.baud)
            self.port.open_port()
        else:
            self.port = None

    def __del__(self):
        # This might be overkill; it would be potentially useful only
        # if a Speedlog2 instance were made more than once in a
        # running process
        self.context.destroy(linger=0)
        if self.port is not None:
            self.port.close_port()
        L.debug('Speedlog2.__del__ exiting')

    def run(self):
        L.info("Speedlog2 is starting")
        while self.running():
            ready = self.socket.poll(1000) # msec
            L.debug("ready? %s", ready)
            if ready:
                msg = self.socket.recv()
                nmea = self.SC(msg)
                L.debug(nmea.decode('ascii').rstrip())
                if self.port is not None:
                    self.port.stream.write(nmea)
                    self.port.stream.flush()
                if self.pub is not None:
                    self.pub.send(nmea)

        L.info("Speedlog2 is stopping")

######

def zmq_addr_from_cruiseinfo(ci, inst):
    addr = ''
    for sensor in ci.sensors:
        if sensor['instrument'] == inst:
            opt = sensor['opt']
            addr = opt.partition('-Z')[2].strip()
            break
    if not addr:
        raise RuntimeError("Could not find zmq addr for %s", inst)
    return addr

def kwargs_from_cruiseinfo(ci):
    inst = ci.speedlog_config['instrument']
    addr = zmq_addr_from_cruiseinfo(ci, inst)
    kwargs = ci.speedlog_config
    kwargs['zmq_from_bin'] = addr
    kwargs['cruisedir'] = ci.cruisedir
    return kwargs

def main(speedlog_config=None, cruisedir=None, flagdir=None, action=None):
    '''
    sensor_cfg.py needs something like the following for the
    nb150 (now only on the LMG):

    speedlog_config = {
        'instrument'        : 'nb150',
        'serial_device'     : '',
        'baud'              : 9600,
        'dir_output'        : '',
        'heading_offset'    : 0.0,
        'scale'             : 1.0,
        'bins'              : (1,12),  # zero-based

        'heading_sensor'    : 'gyro',
        'heading_msg'       : 'hdg',

        'soundspeed_sensor' : None,
        'soundspeed_msg'    : 'snd',
        'nominal_soundspeed': 1536.0,
    }

    For OS/WH/BB systems, to produce the VDVBW message:

    speedlog_config = {
        'instrument'        : 'os75',
        'serial_device'     : '/dev/ttyUSB2',
        'baud'              : 9600,
        'zmq_from_bin'      : "tcp://127.0.0.1:38010",
        'pub_addr'          : "tcp://127.0.0.1:38020",
        'heading_offset'    : 43.5,    # similar to head_align
        'scale'             : 1.0,     # multiplies velocity measurement
        'bins'              : (1,6),   # zero-based; input to python slice()
        'navg'              : 5,       # pings to average
    }

    The zmq_from_bin item is needed only for testing outside a
    logging UHDAS system.  In UHDAS it will be generated using
    information from the sensor_cfg.py file.

    '''
    if speedlog_config is None:
        # Normal situation: in UHDAS.
        from uhdas.uhdas.procsetup import procsetup
        ci = procsetup()
        flagdir = ci.CI.pd.flagD

        kwargs = kwargs_from_cruiseinfo(ci)
    else:
        # For testing the speedlog outside UHDAS.
        kwargs = speedlog_config
        kwargs['cruisedir'] = cruisedir

    kwargs = Bunch(kwargs)
    SR = SpeedlogRunner(flagdir = flagdir, action=action, kwargs = kwargs)
    SR.start()

