"""
Unattended operation of UHDAS for the VOS application.


TODO:
    handle regions with a longitude wrap
    check everything for handling of any possible error condition

Configuration files contain:

# The first region is the default; it doesn't need a polygon.  If it has
one, it will be ignored.
regions= [make_region(name='default',
                      cmdfiles=dict(wh300='pilot_wh300_default.cmd')),
          make_region(name='Honolulu_Harbor',
                      poly=[[-157.8674,   21.2923],
                            [-157.8866,   21.3011],
                            [-157.894 ,   21.3176],
                            [-157.8796,   21.3274],
                            [-157.8603,   21.3112]],
                      in_port=True),
          make_region(name='South_Shore',
                      poly=[[-157.8674,   21.2923],
                            [-157.8866,   21.3011],
                            [-157.894 ,   21.3176],
                            [-158.1258,   21.352 ],
                            [-158.1258,   21.2224],
                            [-157.8242,   21.2568]],
                      cmdfiles=dict(wh300='pilot_wh300_shallow.cmd')),
         ]



config = Bunch(median_window=60, # samples -- simplest for now
               check_interval=10, # seconds between region checks
               restart=30,       # seconds: watchdog when pinging.
               cmd_timeout=30,   # seconds: wait for command completion
               cruise_prefix='km',
               regions=regions,
               pub_addr='tcp://127.0.0.1:38030,      # for monitoring
               req_rep_addr='tcp://127.0.0.1:38031',  # for comm. with DAS
               )

"""



from __future__ import division, print_function, unicode_literals

from six import text_type as ustr
import zmq

import time, datetime
import os
import subprocess

import numpy as np

import logging, logging.handlers
from pycurrents.system import logutils
L = logging.getLogger()
L.setLevel(logging.DEBUG)

formatter = logutils.formatterTLN

logbasename = '/home/adcp/log/DAS_autopilot'

handler = logging.handlers.RotatingFileHandler(logbasename+'.log',
                                               'a', 100000, 9)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
L.addHandler(handler)
#L.addHandler(logging.StreamHandler())


from pycurrents.data.nmea import msg as nmea_msg
from pycurrents.data import navcalc
from pycurrents.num import points_inside_poly
from pycurrents.system import Bunch

configdir = '/home/adcp/config'

class CommandTimeout(Exception):
    pass

_RegionTemplate = Bunch(name=None,
                       poly=None,
                       cmdfiles=None,
                       in_port=False, # if True: don't ping; reset cruise name
                       min_speed=0)   # possibly ping if speed exceeds this.

def make_region(**kw):
    reg = Bunch(_RegionTemplate)
    reg.update_values(strict=True, **kw)
    return reg

def from_sensor_cfg(sensor_cfg=None, dir=None):
    if sensor_cfg is None:
        sensor_cfg = 'sensor_cfg.py'
    if dir is None:
        dir = configdir
    fpath = os.path.join(configdir, sensor_cfg)
    cfg = Bunch().from_pyfile(fpath)
    entries = {}
    pub = cfg.publishers[0]  # always use the first one
    entries['gpsnav_addr'] = ustr(pub['pub_addr'])
    entries['gpsnav_prefix'] = ustr(pub['autopilot_msg'])

    instlist = [item['instrument'] for item in cfg.ADCPs]
    sensord = dict([(s['instrument'], s) for s in cfg.sensors])
    entries['adcps'] = {}
    for inst in instlist:
        opts = sensord[inst]['opt'].split()
        addr = None
        for i in range(len(opts) - 1):
            if opts[i] == '-Z':
                addr = opts[i+1]
                break
        if addr is None:
            raise RuntimeError("could not find addr for %s" % inst)
        entries['adcps'][inst] = ustr(addr)

    return entries

def read_config(configfile=None, sensor_cfg=None, dir=None):
    if configfile is None:
        configfile = 'autopilot_cfg.py'
    if dir is None:
        dir = configdir
    fpath = os.path.join(dir, configfile)
    sensor_info = from_sensor_cfg(sensor_cfg, dir)
    cfg = Bunch().from_pyfile(fpath).config
    cfg.update(sensor_info)
    return Bunch(**cfg)   # could customize printing...

class NavBuf(object):
    def __init__(self, nsamp):
        self.buf = np.ma.zeros((nsamp, 3), float)
        self.buf[:] = np.ma.masked
        self.nsamp = nsamp
        self.i = 0

    def append(self, txy):
        self.buf[self.i] = np.ma.masked_invalid(txy)
        self.i += 1
        self.i %= self.nsamp

    def median_txy(self):
        return np.ma.median(self.buf, axis=0)


class Pilot(object):
    def __init__(self, das, config, context=None):
        self.das = das
        self.instlist = config.adcps.keys()
        self.last_txy = np.ma.zeros((3,), float)
        self.last_txy[:] = np.ma.masked
        self.last_speed = None
        self.navbuf = NavBuf(config.median_window)

        self.uhdas_running = False
        self.uhdas_cruise = False
        self.uhdas_pinging = False
        self.last_ping = 1e38

        self.regions = config.regions  # list of Region
        self.current_region = None
        self.last_region = None

        self.cruise_prefix = config.cruise_prefix
        self.cruise_name = self.update_cruisename()

        if context is not None and config.pub_addr:
            self.zmq_pub = context.socket(zmq.PUB)
            self.zmq_pub.bind(config.pub_addr)
            self.zmq_reqsock = context.socket(zmq.REQ)
            self.zmq_reqsock.connect(config.req_rep_addr)
        else:
            self.zmq_pub = None
            self.zmq_reqsock = None

        self.cmd_timeout = config.cmd_timeout

    def handle_ping(self, msg):
        # later: check for an error in message.
        self.last_ping = time.time()

    def handle_gpsnav(self, msg):
        try:
            parsed = nmea_msg.get_gga(msg)
        except ValueError:
            L.warning('Checksum mismatch for: %s',
                        msg.decode('ascii', 'ignore'))
            return
        if parsed is None:
            L.warning('Bad msg: %s', msg.decode('ascii', 'ignore'))
            return
        self.navbuf.append(parsed[:3])

    def update(self):
        txy = self.navbuf.median_txy()
        if np.ma.getmaskarray(txy).any():
            L.warning('masked txy: %s', txy)
            return False

        if self.zmq_pub is not None:
            msg = '%12.5f %12.5f %12.5f' % tuple(txy)
            msg = msg.encode('ascii', 'ignore')
            self.zmq_pub.send(msg)

        if not np.ma.getmaskarray(self.last_txy).any():
            deltas = txy - self.last_txy
            deltas[0] %= 1
            dx, dy = navcalc.diffxy_from_difflonlat(
                        deltas[1], deltas[2], txy[2])
            self.last_speed = np.hypot(dx, dy) / (deltas[0] * 86400)
            ret = True
        else:
            L.warning('Cannot update speed')
            ret = False
        self.last_txy = txy

        self.current_region = self.regions[0]  # default
        for region in self.regions[1:]:
            if points_inside_poly(txy[1:], region.poly)[0]:
                self.current_region = region
                break
        if self.current_region is not None:
            L.debug(self.current_region.name)
        return ret


    def steer(self):
        reg = self.current_region
        changed = reg != self.last_region
        if self.last_region is not None:
            L.debug('last_region was %s', self.last_region.name)
            if changed and self.last_region.in_port:
                self.update_cruisename()
        if changed:
            L.info('region changed to: %s', reg.name)
        self.last_region = reg

        # for now, assume self.uhdas_running is True
        if reg.in_port:
            self.stop_pinging()
            self.end_cruise()
            return

        if self.last_speed < reg.min_speed:
            self.stop_pinging()
            return

        if changed:  # not in port, speed is ok, new region -> new config
            self.stop_pinging()
            self.start_pinging()
            return

        if not self.uhdas_pinging and self.last_speed >= reg.min_speed:
            self.start_pinging()

    def stop_pinging(self):
        if not self.uhdas_pinging:
            return
        L.info('Stop pinging')
        self.send('stop_logging')
        self.uhdas_pinging = False

    def end_cruise(self):
        if not self.uhdas_cruise:
            return
        L.info('End Cruise')
        self.send('end_cruise')
        self.uhdas_cruise = False

    def start_pinging(self):
        L.info('Start pinging')
        if self.uhdas_pinging:
            L.warn('already pinging')
            return
        if not self.uhdas_cruise:
            self.start_cruise()
        cmdlist = []
        for inst in self.instlist:
            cmdlist.append('%s:%s' %
                           (inst, self.current_region.cmdfiles[inst]))
        self.send('cmdfile ' + ','.join(cmdlist))
        self.send('start_logging')
        self.last_ping = time.time()
        self.uhdas_pinging = True

    def update_cruisename(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.cruise_name = self.cruise_prefix + now
        L.info('New cruise name: %s', self.cruise_name)
        return self.cruise_name

    def start_cruise(self):
        L.info('Start cruise')
        if self.uhdas_cruise:
            L.warn('cruise is already started')
            return
        cmd = 'start_cruise %s' % self.cruise_name
        self.send(cmd)
        self.uhdas_cruise = True

    def send(self, cmd):
        error = False
        L.info('Sending: %s', cmd)
        self.zmq_reqsock.send_string(cmd)
        # Wait for a reply, or timeout
        events = self.zmq_reqsock.poll(timeout=self.cmd_timeout*1000)
        if events == 0:
            L.error('timeout in send')
            raise CommandTimeout(cmd)

        msg = self.zmq_reqsock.recv_string()
        L.info('Reply: %s', msg)
        return error


def preexec_function():
#http://stackoverflow.com/questions/5045771/python-how-to-prevent-subprocesses-from-receiving-ctrl-c-control-c-sigint
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)

from pycurrents.system.pmw_process import SingleFunction

class Autopilot(SingleFunction):
    def keep_running(self):
        runflag = (os.path.isfile(self.flagfile)
                    and not os.path.isfile(self.stopflagfile))
        return  runflag

    def run(self, *args, **kw):
        # Outermost loop: complete restart.
        L.info('Starting Autopilot.run()')

        restart = True
        while restart and self.keep_running():
            restart = self.auto_main(*args, **kw)

    def auto_main(self, config):
        L.info('Starting Autopilot.auto_main()')

        try:
            das = subprocess.Popen(['DAS.py',
                                    '--zmq_req_rep=%s' % config.req_rep_addr,
                                    '--endcruise'],
                               stdin=subprocess.PIPE,
                               preexec_fn=preexec_function,
                               )
        except:
            L.exception("Failed to start DAS")
            return False

        context = zmq.Context()

        pilot = Pilot(das, config, context)


        gpsnav = context.socket(zmq.SUB)
        gpsnav.connect(config.gpsnav_addr)
        gpsnav.setsockopt_string(zmq.SUBSCRIBE, config.gpsnav_prefix)

        ## For now, assume we will monitor only one ADCP;
        ## things could get complicated if we have to handle
        ## more than one, especially if sometimes only one would
        ## be pinging.
        adcp = context.socket(zmq.SUB)
        adcp.connect(list(config.adcps.values())[0])   # list() for PY3
        adcp.setsockopt_string(zmq.SUBSCRIBE, "")

        poller = zmq.Poller()

        poller.register(gpsnav, flags=zmq.POLLIN)
        poller.register(adcp, flags=zmq.POLLIN)

        restart = False
        last_time = 0

        try:
            while self.keep_running():
                os.utime(self.flagfile, None)
                events = poller.poll(timeout=2000)  # msec
                if not events:
                    L.info('Nothing received')
                    if das.poll() is not None:
                        L.warn('DAS.py died')
                        restart = True
                        break
                    continue

                for event in events:
                    #L.debug('%s', event)
                    msg = event[0].recv()
                    msg = msg.split(b'\n')[0]   #  stripped off the $UNIXD line
                    msg_str = msg.decode('ascii', 'ignore')
                    if event[0] == adcp:
                        #L.debug("From adcp: %s", msg_str)
                        pilot.handle_ping(msg_str)
                    else:
                        #L.debug("From gpsnav: %s", msg_str)
                        pilot.handle_gpsnav(msg)

                now = time.time()

                if pilot.uhdas_pinging and now - pilot.last_ping > config.restart:
                    L.info('Seconds since last ping: %s', now - pilot.last_ping)
                    restart = True
                    break

                if now - last_time > config.check_interval:
                    last_time = now
                    ok = pilot.update()
                    L.debug('ok: %s', ok)
                    if ok:
                        pilot.steer()
                        L.debug("%s, %s", pilot.last_speed, pilot.last_txy)

                    if das.poll() is not None:
                        L.warn('DAS.py died')
                        restart = True
                        break

                handler.flush()

        except KeyboardInterrupt:
            restart = False
            L.info('keyboard interrupt')
        except:
            restart = True
            L.exception('in main autopilot loop')

        finally:
            L.info("Ending a DAS.py run, restart is %s", restart)
            if das.poll() is None:
                try:
                    pilot.send('quit')
                except:
                    pass
            if das.poll() is None:
                try:
                    das.terminate()
                except:
                    pass

            count = 60
            while das.poll() is None and count > 0:
                time.sleep(1)
                count -= 1
            try:
                das.kill()
            except:
                pass

        context.destroy(0)

        return restart


