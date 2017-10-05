from future import standard_library
standard_library.install_hooks()
import os
import subprocess
import time
import logging
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.data.topo import Etopo_file
from pycurrents.num.stats import Stats
from pycurrents.data.navcalc import pretty_llstr
from  pycurrents import codas
from pycurrents.data.nmea import msg

L = logging.getLogger()

def showlast(filetype, numfiles):
    ## filetype is 'ascii', 'logging', 'rbin', 'gbin' 
    cmd = "showlast.py -%s %d" % (filetype[0], numfiles)
    output = subprocess.getoutput(cmd)
    return output

def showzmq(filetype, numfiles):
    ## filetype is 'ascii', 'logging', 'rbin', 
    cmd = "showzmq.py -%s %d" % (filetype[0], numfiles)
    output = subprocess.getoutput(cmd)
    return output

def zmq_summary(zmqdir='/home/data/0mon', use_publishers=None):
    '''
    return :
    bool (zmq_pub_running)
    summary string
    position tuple
    '''
    zmq_list=['========= zmq summary ==========']
    ## try to write zmq_tails.txt, regardless of cruise status
    if not os.path.isdir(zmqdir):
        zmq_list.append('zmq is not enabled (no output directory %s)' % zmqdir)
        return '\n'.join(zmq_list)
    if use_publishers == False:
        zmq_list.append('NOT USING zmq publishers')
        return '\n'.join(zmq_list)
    if use_publishers is None:
        zmq_list.append('use_publishers is None (unknown state)')
        return '\n'.join(zmq_list)

    zmq_list.append('zmq is enabled, output goes to %s' % (zmqdir))

    # look for processes
    cmd = 'ps -efw | grep zmq | grep asc'
    cmdissued = ''
    output = subprocess.getoutput(cmd)
    processes = output.split('\n')

    zmq_pub_running = False
    for process in processes:
        if 'grep' not in process:
            if 'ser_asc_zmq' in process:
                zmq_pub_running = True
            parts = process.split()
            pid = parts[1]
            cmdcmd = 'ps -w -p %s -o cmd' % (pid)
            cmdissued+= '\n' +  subprocess.getoutput(cmdcmd).split('\n')[1]

    zmq_runstr = {True:'is', False:' **IS NOT** '}[zmq_pub_running]
    zmq_list.append('zmq publisher (ser_asc_zmq) %s running\n' % (zmq_runstr))

    ## the next part should be done with a subscriber, not zmqtail
    if zmq_pub_running:
        tt=time.gmtime()
        ymdhms =  [tt.tm_year, tt.tm_mon, tt.tm_mday, tt.tm_hour, tt.tm_min, tt.tm_sec]
        dday = codas.to_day(tt.tm_year, ymdhms)
        zmq_list.append('current date is: ' + subprocess.getoutput('date -u'))
        zmq_list.append('current PC UTC decimal day is %f' % (dday))
        zmq_list.append('last zmq output to %s:' % (zmqdir))
        output = subprocess.getoutput('showzmq.py -a 10')
        zmq_delay = ''
        xy = None
        lines = output.split('\n')[::-1] # work backwards
        for line in lines:
            if ('GGA' in line):
                zmq_list.append(line)
                [t, x, y, qual, hdop] = msg.get_gga(line)
                xy = (x,y)
                break
        for line in lines:
            if  ('UNIXD' in line):
                zmq_list.append(line)
                zmqdday = float(line.split(',')[1])
                dday_diff = dday-zmqdday
                # take this outside the "if" so it gets appended at thqe end
                if abs(dday_diff) > 0.5:
                    zmq_delay = '\nPC - zmqtail = %5.2f days' % (dday_diff)
                elif abs(dday_diff) > 0.1:
                    zmq_delay = '\nPC - zmqtail = %10.2f min' % (dday_diff*60*24)
                else:
                    zmq_delay = '\nPC - zmqtail = %10.1f sec' % (dday_diff*86400)
                if len(zmq_delay) > 0:
                    zmq_list.append(zmq_delay)
                break

        # append command run at the end
        zmq_list.append('\nrunning command:' + cmdissued)
    else:
        ## SHOULD BE running
        cmd = "zmq_publisher.py --show_cmds"
        output = subprocess.getoutput(cmd)
        ## this should all be refactored, from zmq_publisher
        outlist=output.split('\n')
        zmq_list.append('---> SHOULD BE running:\n' + output)
        xy=None

    return zmq_pub_running, '\n'.join(zmq_list), xy


def autopilot_summary():
    '''
    return :
    bool (autopilot_running)
    summary string
    '''
    autopilot_running = False
    if 'DAS_autopilot.running' in subprocess.getoutput('ls /home/adcp/flags'):
        autopilot_running = True
    #        
    autopilot_list=['========= autopilot summary ==========']
    #   
    for cmd in ['ps -ef | grep autopilot',
                'ls -l /home/adcp/config/autopilot_cfg.py',
                'ls -l /home/adcp/flags',
                'tail -3 /home/adcp/log/DAS_autopilot.log']:
        output = subprocess.getoutput(cmd)
        ## this should all be refactored, from zmq_publisher
        autopilot_list.append('\n---------- %s ----------\n' % (cmd))
        autopilot_list.append(output)
    #    
    return autopilot_running, '\n'.join(autopilot_list)


def tail_file(fname, lines):
    if os.path.exists(fname):
        cmd = "tail -%d %s" %  (lines, fname)
        status, output = subprocess.getstatusoutput(cmd)
        if status != 0:
            return "Command '%s' failed with status %d" % (cmd, status)
        return output
    else:
        output = None


def ship_warning(shipabbrev):
    '''
    this used to have NBPalmer JGOF file check
    '''
    return '\n'


def logfile_since(fname, tstart):
    '''
    Return a string with the contents of a logfile later than a given time.

    fname:  logfile name
    tstart: floating point time threshold, in the form returned by
            time.time() or time.mktime()

    Note: it is assumed that the logfile has lines starting with
    time tags in the form YYYY/MM/DD hh:mm:ss.
    Milliseconds will be ignored if present.
    Not all lines need to be tagged.

    '''

    lines = open(fname).readlines()
    for i, line in enumerate(lines):
        fields = line.split()
        try:
            tt = fields[0] + ' ' + fields[1][:8]
            tstruc = time.strptime(tt, "%Y-%m-%d %H:%M:%S")
            tline = time.mktime(tstruc)
        except (IndexError, ValueError, OverflowError):
            continue
        if tline > tstart:
            break
    return ''.join(lines[i:])


def btrk_status(cruisedir, instname):
    ''' return a string saying whether bottom track is on or off
    '''
    nb150_btdict = { 255 : 'BT is off',
                     1   : 'BT is on'}
    oswh_btdict = {  1   : 'BT is on',
                     0   : 'BT is off'}

    fname = os.path.join(cruisedir,'raw',instname,'current.cmd')
    try:
        lines = open(fname).readlines()
        for line in lines:
            bareline = line[:-1]
            if bareline[:2] in ['FH','BP']:
                if instname == 'nb150':
                    return nb150_btdict[int(bareline[2:])]
                else:
                    return oswh_btdict[int(bareline[2:])]
    except:
        return 'cannot determine BT string'



def xyz_str(ci, xy=None, comment=''):
    '''
    find x,y from rbin, or use xy tuple passed in (eg. from zmq)
    find depth
    return pretty string
    '''

    if xy is None:
        rglob = os.path.join(ci.pos_inst, '*.%s.rbin' % (ci.pos_msg))
        data=BinfileSet(os.path.join('/home/data',ci.cruisedir,'rbin',rglob))
        data.set_slice(start=-30)
        Sx=Stats(data.lon)
        Sy=Stats(data.lat)
        x=Sx.mean
        y=Sy.mean
        comment = 'position from serial GPS'
    else:
        x,y = xy
    topo = Etopo_file()
    depth = -topo.nearest(x, y)[0] # make depth positive down
    outlist = ['approximate lat, lon, depth:  %s  %s   depth=%s' % (
                   (pretty_llstr(y, 'lat'), pretty_llstr(x,'lon'), depth)) ,
               comment]
    return '\n'.join(outlist)
