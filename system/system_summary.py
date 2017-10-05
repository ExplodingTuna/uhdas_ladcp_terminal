'''
Classes and functions intended mainly for daily UHDAS status reports.

Some may also be useful for scanning entire cruises of data.

'''
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from future.builtins import zip
from future import standard_library
standard_library.install_hooks()
from future.builtins import object

import os, subprocess, time, glob, stat, datetime
from importlib import import_module

#import logging
#L = logging.getLogger()


import numpy as np
from pycurrents.file.binfile_n import BinfileSet

system_log = "syslog"  # formerly "messages"

class CommandError(Exception):
    def __init__(self, cmd, status, output):
        msg = "Command '%s' failed with status %d\n" % (cmd, status)
        Exception.__init__(self, msg + output)

def test_backupdir(location):
    '''
    location is one of these:
         - a directory (eg. '/disk2/home/data' or '/media/UHDAS/data')
         - a remote location for rsync using ssh keys (eg. 'rigel:/home/data')
         - a remote location for rsync using rsyncd (eg. 'healynas::/uhdas/data')
    returns error msg (string), empty string if test write is successful
    '''
    if location.count(':') == 1:  #assume remote rsync
        testfile = '/tmp/.testrsync'
        open(testfile,'w').write('test rsync\n')
        cmd = 'rsync %s %s' % (testfile, location)
        status, errstr = subprocess.getstatusoutput(cmd)
        return errstr
    elif location.count('::') == 1:  #assume remote rsyncd
        testfile = '/tmp/mount_test'
        open(testfile,'w').write('test rsync\n')
        cmd = 'rsync %s %s' % (testfile, location)
        status, errstr = subprocess.getstatusoutput(cmd)
        return errstr
    else:
        # check writing to directory
        if os.access(location, os.W_OK):
            return ''
        else:
            return 'Cannot write to backup directory %s' % (location)

def disk_summary():
    '''
    Return the output of 'df -lk' as a string and a dictionary.

    The dictionary uses the mount points as keys.
    Fields are size, used, available KB, and percent used.
    '''
    cmd = "df -lk"
    status, output = subprocess.getstatusoutput(cmd)
    if status != 0:
        raise CommandError(cmd, status, output)
    lines = output.split('\n')[1:]
    lines.sort()
    outstring = '\n'.join([line.rstrip() for line in lines]) + '\n'
    d = dict()
    for line in lines:
        fields = line.split()
        if len(fields) == 6:
            numbers = [int(x) for x in fields[1:4]] # KB size, used, avail
            numbers.append(int(fields[4][:-1]))     # percent used
            d[fields[5]] = numbers
    return outstring, d

def disk_usage(glob_pattern, within_days=None): # entries created in last N days
    full_list = glob.glob(glob_pattern)
    full_list.sort()
    if within_days is None:
        filelist = full_list
    else: # days
        now_secs = time.mktime(time.gmtime())
        earliest = now_secs - abs(within_days)*86400
        filelist = []
        for ff in full_list:
            if os.path.getmtime(ff) > earliest:
                filelist.append(ff)
    # loop now
    d = dict()
    lines = []
    for ff in filelist:
        cmd = "du -sk %s" % (ff,)
        status, output = subprocess.getstatusoutput(cmd)
        #if status != 0:
        #   return "Command '%s' failed with status %d" % (cmd, status)
        # We don't want this; it will fail if there are any "permission denied"
        # errors, but the output is still fine.
        output.rstrip()
        try:
            bytes, directory = output.split()
            d[directory] = int(bytes)
            lines.append(output)
        except:
            pass
    outstring = '\n'.join(lines) + '\n'
    return outstring, d

def du_difference(old_d, new_d, show_zero = False,
                  old_prefix = '', new_prefix = ''):
    i0_old = len(old_prefix)
    i0_new = len(new_prefix)
    _old_d = dict()
    for key, value in old_d.items():
        _old_d[key[i0_old:]] = value
    _new_d = dict()
    for key, value in new_d.items():
        _new_d[key[i0_new:]] = value

    common_keys = [key for key in list(_new_d.keys()) if key in list(_old_d.keys())]
    common_keys.sort()
    lost_keys = [key for key in list(_old_d.keys()) if key not in list(_new_d.keys())]
    new_keys = [key for key in list(_new_d.keys()) if key not in list(_old_d.keys())]
    lines = []
    if len(new_keys) > 0:
        new_keys.sort()
        lines.append("New directories: %s" % ' '.join(new_keys))
    if len(lost_keys) > 0:
        lost_keys.sort()
        lines.append("Deleted directories: %s" % ' '.join(lost_keys))
    if len(common_keys) > 0:
        s = "%s  %s" % ("Changed directories".ljust(35), " increase (k)")
        lines.append(s)
        for key in common_keys:
            change = _new_d[key] - _old_d[key]
            if show_zero or change != 0:
                s = "%35s %6d" % (key.ljust(35), change)
                lines.append(s)
    return '\n'.join(lines) + '\n'

def list_recent(glob_pattern, dt, style='long', out='string'):
    '''
    List files in a given directory, or matching a glob, that were
    last modified within some interval.

    args:
        glob_pattern : directory, or file glob pattern
        dt : maximum modification time in seconds before present
    kwargs:
        style = 'long' : full ls -l
                'short': skip mode, user, group
        out = 'string' : multi-line string with separators
              'stringlist' : list of ls -l outputs
              'files' : list of filenames
    Note: having a kwarg control what sort of thing is output
    triggers a warning in pychecker.  It would be better to use
    separate functions, or always return a tuple with all types
    of output, or use a class with the different types of output
    as properties or the return values of methods.
    '''
    now = time.time()
    start = now - dt
    if os.path.isdir(glob_pattern):
        glob_pattern = os.path.join(glob_pattern, '*')
    filelist = glob.glob(glob_pattern)
    newfiles = [f for f in filelist if (os.path.getmtime(f) > start
                                           and os.path.isfile(f))]
    if out == 'files':
        return newfiles
    if len(newfiles) == 0:
        if out == 'stringlist':
            return []
        return ''
    cmd = "ls -l %s" % ' '.join(newfiles)
    output = subprocess.getoutput(cmd)
    lines = output.split('\n')
    slines = []
    for line in lines:
        line = line.rstrip()
        if style == 'short':
            if len(line) > 0:
                ll = line.split()
                sline = '%10s  %s %s %s %s' % (ll[4], ll[5], ll[6], ll[7], ll[8])
                slines.append(sline)
        else:
            slines.append(line)

    if out == 'stringlist':
        return slines
    outstring = '\n'.join(slines)
    slist = ['------%s; last %.2f days-------'% (glob_pattern, dt/86400.0),
             outstring,
            '--------------------------------------\n']
    return '\n'.join(slist)



def delete_old(glob_pattern, dt):
    now = time.time()
    start = now - dt
    filelist = glob.glob(glob_pattern)
    oldfiles = [f for f in filelist if (os.path.getmtime(f) < start
                                           and os.path.isfile(f))]
    if len(oldfiles) == 0:
        return ''
    cmd = "ls -l %s" % ' '.join(oldfiles)
    output = subprocess.getoutput(cmd)
    lines = output.split('\n')
    outstring = '\n'.join([line.rstrip() for line in lines])
    slist = ['deleted these files (last %.2f days)' % (dt/86400.0),
             outstring,
            '--------------------------------------\n']
    for filename in oldfiles:
        os.remove(filename)
    return '\n'.join(slist)


def del_processingfiles():
    for ff in glob.glob('*.bin'):
        try:
            os.remove(ff)
        except:
            pass
    for ff in glob.glob('*gyrodh*'):
        try:
            os.remove(ff)
        except:
            pass
    for ff in glob.glob('processing_*.txt'):
        try:
            os.remove(ff)
        except:
            pass
    for ff in glob.glob('*gbin.txt'):
        try:
            os.remove(ff)
        except:
            pass
    for ff in glob.glob('run3day*.txt'):
        try:
            os.remove(ff)
        except:
            pass
    try:
        os.remove('tails.txt')
    except:
        pass
    try:
        os.remove('sonar_summary.txt')
    except:
        pass
    try:
        os.remove('cals.txt')
    except:
        pass




def list_files(glob_pattern, style='long'):  # skip mode, user, group
    if os.path.isdir(glob_pattern):
        glob_pattern = os.path.join(glob_pattern, '*')
    filelist = glob.glob(glob_pattern)
    newfiles = [f for f in filelist if os.path.isfile(f)]
    cmd = "ls -l %s" % ' '.join(newfiles)
    output = subprocess.getoutput(cmd)
    lines = output.splitlines()
    slines = []
    for line in lines:
        line = line.rstrip()
        if style == 'short':
            if len(line) > 0:
                ll = line.split()
                sline = '%10s  %s %s %s %s' % (ll[4], ll[5], ll[6], ll[7], ll[8])
                slines.append(sline)
        else:
            slines.append(line)
    outstring = '\n'.join(slines)
    slist = ['------%s-------'% (glob_pattern),
             outstring,
            '--------------------------------------\n']
    return '\n'.join(slist)

def list_file_ages(glob_pattern, reverse = True, maxfiles = 50):
    if os.path.isdir(glob_pattern):
        glob_pattern = os.path.join(glob_pattern, '*')
    filelist = glob.glob(glob_pattern)
    now = time.time()
    ages = list()
    newfiles = [f for f in filelist if os.path.isfile(f)]
    for f in newfiles:
        ages.append(now - os.stat(f)[stat.ST_MTIME])
    age_files = list(zip(ages, newfiles))
    age_files.sort(key=lambda x: x[0], reverse = reverse)
    slist = ['age (minutes)          filename\n']
    for age, f in age_files[:maxfiles]:
        slist.append('  %6d      %s\n' % (int(age/60.0), f))
    return ''.join(slist)


def list_processes(pattern, switches='-f'):
    cmd = "/bin/ps %s -U adcp | /bin/grep %s" % (switches, pattern,)
    output = subprocess.getoutput(cmd)
    lines = output.splitlines()
    lines = [l for l in lines if not "/bin/grep" in l]
    slist = ['--------%s--------' % cmd,
             ('\n').join(lines),
             '------------------------------------------------\n']
    return '\n'.join(slist)

def check_ntpq():
    cmd = 'ps -ef | grep ntpd | grep -v grep'
    s1 = subprocess.getoutput(cmd)
    if len(s1) == 0:
        s1 = "ntp is not running"
    else:
        cmd = 'ntpq -p'
        s1 = subprocess.getoutput(cmd)
        if 'refused' not in s1:
            # Melville: ntpq -p doesn't work; use a workaround.
            if len(s1.split('\n')) < 2:
                lines = open('/etc/ntp.conf').readlines()
                lines = [l.split('#', 1)[0] for l in lines]
                servers = []
                for line in lines:
                    fields = line.strip().split()
                    if len(fields) > 0:
                        if fields[0] == 'server' and len(fields) == 2:
                            servers.append(fields[1])
                if servers:
                    cmd = "%s %s" % (cmd, ' '.join(servers))
                    s1 = subprocess.getoutput(cmd)

    slist = ['---------- %s ------------'%cmd,
             s1,
             '------------------------------------------\n']
    return '\n'.join(slist)


def check_ntpd():
    s2 = subprocess.getoutput('grep -h ntpd /var/log/syslog /var/log/syslog.0')
    if not s2:
        return 'No ntpd lines in syslog\n'
    now = datetime.datetime.today() # log uses local time, which should be GMT
    earliest = now - datetime.timedelta(days=3)
    lines = s2.split('\n')
    kept = []
    for line in lines:
        tstring = '%d %s' % (now.year, line[:15])
        try:
            ttag = datetime.datetime.strptime(tstring, "%Y %b %d %H:%M:%S")
            if ttag > now:
                tstring = '%d %s' % (now.year-1, line[:15])
                ttag = datetime.datetime.strptime(tstring, "%Y %b %d %H:%M:%S")
            if ttag > earliest:
                kept.append(line)
        except ValueError:
            pass
    s2 = '\n'.join(kept)
    slist = ['------  ntpd in /var/log/syslog[.0], 3 days --------',
             s2,
             '\n------------------------------------------\n']
    return '\n'.join(slist)


def check_uptime():
    cmd = 'uptime'
    s1 = subprocess.getoutput(cmd)
    slist = ['---------- %s ------------'%cmd,  s1]
    return '\n'.join(slist)


def varfilelist(filebase):
    '''
    return ungzipped files from /var/log with this suffix
    '''
    cmd = 'ls -tr /var/log/%s* | grep -v .gz' % (filebase)
    s1 = subprocess.getoutput(cmd)
    return s1.split('\n')


def serial_memory():
    flist = glob.glob('/var/lock/LCK..*')
    strlist = ['#                    lockfile   pid        name    RSS   SZ','\n']
    for f in flist:
        x = open(f, 'r').readlines()
        lockfile = os.path.basename(f)
        if len(x) != 1:
            strlist.append(lockfile + ' incorrect contents')
        else:
            parts = x[0].split()
            if len(parts) != 3:
                strlist.append(lockfile + ' incorrect contents')
            else:
                pid, shortcmd = parts[0], parts[1]
                cmd = 'ps -p %s -o rss,sz' % (pid)
                status, meminfo = subprocess.getstatusoutput(cmd)
                mhead, memstr = meminfo.split('\n')
                s = '%30s %5s %12s %s' % (lockfile, pid, shortcmd, memstr)
                strlist.append(s)
    strlist.append('\n')
    return '\n'.join(strlist)

def check_IOerrs():
    flist = varfilelist(system_log)
    sstr = ''
    for f in flist:
        s1 = subprocess.getoutput('grep -i "I/O error" %s' % (f))
        if s1:
            sstr = sstr + s1 + '\n'
    if not sstr:
        return 'no I/O error messages\n', ''
    slist = sstr.split('\n')
    numerrs = len(slist)
    retstr = '\n'.join(['---------- I/O errors in /var/log/%s ------------'
                                                    % (system_log,),
                       '\n'.join(slist[-20:]),
                       '------------------------------------------\n'])
    return retstr, '%6d I/O errors in last 2 /var/log/%s' % (numerrs, system_log)

def check_EDACerrs():
    flist = varfilelist(system_log)
    sstr = ''
    for f in flist:
        s1 = subprocess.getoutput('grep EDAC %s' % (f))
        if s1:
            sstr = sstr + s1 + '\n'
    if not sstr:
        return 'no EDAC error messages\n', ''
    slist = sstr.split('\n')
    numerrs = len(slist)
    retstr = '\n'.join(['---------- EDAC (memory) errors in /var/log/%s ------------'
                                                    % (system_log,),
                       '\n'.join(slist[-20:]),
                       '------------------------------------------\n'])
    return retstr, '%6d EDAC (memory) errors in last 2 /var/log/%s' % (numerrs, system_log)

def check_USBoverrun():
    flist = varfilelist(system_log)
    sstr = ''
    for f in flist:
        s1 = subprocess.getoutput('grep -i "overrun" %s| grep USB' % (f))
        if s1:
            sstr = sstr + s1 + '\n'
    if not sstr:
        return 'no USB overrun messages\n', ''
    slist = sstr.split('\n')
    numerrs = len(slist)-1 #last newline
    retstr = '\n'.join(['----------  USB overrun messages in /var/log/%s ---------'
                                                    % (system_log,),
                       '\n'.join(slist[-20:]),
                       '------------------------------------------\n'])
    return retstr, '%6d "USB overruns" in %s' % (numerrs, system_log)


def check_logwarnings():
    '''
    Note: this returns *two* strings.
    '''
    ## warning files from logging
    warnlist = list_recent('/home/adcp/log/*.warn*', 86400, out='files')
    warnlist = [f for f in warnlist if os.stat(f).st_size > 0]
    if not warnlist:
        return ('no recent warnings\n', '')
    warnlist.sort()
    linelist = []
    countlist = [''] # to put a newline at the start
    for fname in warnlist:
        lines = open(fname).readlines()
        countlist.append('      %d %s' % (len(lines), fname))
        ll = [line.strip() for line in lines[-50:]]
        linelist.append('\n   %d  %s' % (len(lines), fname))
        linelist.extend(ll)
        linelist.append('======== end %s =========\n' % fname)
    linelist.insert(0,
        '---------------- /home/adcp/log/*.warn ---------------------')
    linelist.append('------------------------------------------\n')
    return '\n'.join(linelist), '\n'.join(countlist)

def check_cals():
    cmd = "for file in `ls /home/adcp/cruise/proc/*/cal/botmtrk/btcaluv.out`; do  echo '---------';  echo $file; echo ' '; tail -10 $file | egrep '(median|phase|edited|amplitude)' | grep -v =; done"
    sb = subprocess.getoutput(cmd)

    cmd = "for file in `ls /home/adcp/cruise/proc/*/cal/watertrk/adcpcal.out`; do  echo '----------'; echo $file; echo ' '; tail -20 $file | egrep '(median|phase|edited|amplitude)' | grep -v =; done"

    sw = subprocess.getoutput(cmd)
    slist = ['---------- BOTTOM TRACK ------------',
             sb,
             '---------- WATER TRACK ------------',
             sw,
             '------------------------------------------\n']
    return '\n'.join(slist)


def get_sonar_summary(cruiseid):
    cmd = "sonar_summary.py %s" % (cruiseid)
    return subprocess.getoutput(cmd)


def check_npings():
    cmd = "for file in `ls /home/adcp/cruise/proc/*/edit/*npings.txt`; do  echo '---------';  echo $file; echo ' '; tail -10 $file; done"
    sb = subprocess.getoutput(cmd)
    slist = ['---------- NUM PINGS from database ------------',
             sb,
             '------------------------------------------\n']
    return '\n'.join(slist)


def tails(globstr, numlines):
    filelist = glob.glob(globstr)
    linelist = []
    for fname in filelist:
        f = open(fname,'r')
        lines = ['------- %s ---------\n' % (fname,),] + f.readlines()[-numlines:]
        f.close()
        linelist.append(''.join(lines))
        linelist.append('')
    return linelist


def dmesg(nlines=None):
    dm = subprocess.getoutput('dmesg')
    if nlines is not None:
        dl = dm.split('\n')[-nlines:]
        dm = '\n'.join(dl) + '\n'
    return dm


def proc_seconds(nlines=None):
    cmd='grep seconds /home/adcp/log/DAS_while_logging.log'
    dm = subprocess.getoutput(cmd)
    if nlines is not None:
        dl = dm.split('\n')[-nlines:]
        dm = '\n'.join(dl) + '\n'
    return dm


def debug_filelist(ndays):
    cwd = os.getcwd()
    os.chdir('/home/adcp')
    flist = os.popen('find log -type f -mtime -%d' % ndays).readlines()
    flist.extend(os.popen('find uhdas_tmp -type f -size -100k -mtime -%d' % ndays).readlines())
    flist.extend(os.popen('/bin/ls flags/*').readlines())
    os.chdir(cwd)
    flist = [f.strip() for f in flist]
    flist = [f for f in flist if '#' not in f]
    flist = [f for f in flist if not f.endswith('ps') and not f.endswith('png')]
    return flist

class Diffstats(object):
    '''
    Calculate and show statistics for a time series.

    This is intended for use with recorded time information
    from a set of rbin files.

    Example:

    import os
    from glob import glob
    from pycurrents.file.binfile_n import BinfileSet
    from uhdas.system.system_summary import Diffstats

    rbindir = '/home/manini/programs/q_demos/uhdas/data/rbin'
    msg = 'adu'
    inst = 'ashtech'
    pat =  os.path.join(rbindir, inst, '*.%s.rbin' % msg)
    filelist = glob(pat)
    filelist.sort()
    bs = BinfileSet(filelist[-15:])
    print Diffstats.labels
    print Diffstats(bs.u_dday)
    print Diffstats(bs.dday)

    '''
    labels = ' ndiff  median     min       max    high   low  vlow  zero   neg'
    def __init__(self, dday):
        '''
        dday is a numpy 1-D array of decimal day times
        '''
        if len(dday) < 2:
            self.ndiffs = 0
            self.median = 0
            self.min = 0
            self.max = 0
            self.n_high = 0
            self.n_low = 0
            self.n_vlow = 0
            self.n_zero = 0
            self.n_negative = 0
            return
        dd = np.diff(dday)*86400.0
        self.ndiffs = len(dd)
        self.median = np.median(dd)
        self.min = dd.min()
        self.max = dd.max()
        self.n_high = (dd > 2.0*self.median).sum()
        self.n_low = (dd < 0.45*self.median).sum()
        self.n_vlow = (dd < 0.05).sum()
        self.n_zero = (dd == 0.0).sum()
        self.n_negative = (dd < 0.0).sum()

    def __str__(self):
        s = '%6d  %6.2f  %6.2f  %8.1f   %5d %5d %5d %5d %5d' % (
             self.ndiffs,
             self.median,
             self.min, self.max,
             self.n_high, self.n_low, self.n_vlow, self.n_zero,
             self.n_negative)
        return s

def check_rbintimes(rbindir, sensors, nfiles=None):
    '''
    Look for oddly long, short, or negative time deltas between rbin records.

    sensors is the list of sensor dictionaries from sensor_cfg.py

    All sensors logging ascii data will be checked, as will all
    time types that are present.  This is assumed to include
    clock time and monotonic time, and may include the instrument's
    own clock time.
    '''
    wlist = [' ']
    slist = ['        ' + Diffstats.labels]
    sensors = [s for s in sensors if s['format'] == 'ascii']
    for sensor in sensors:
        inst = sensor['subdir']
        for msg in sensor['messages']:
            label = '%s %s %s' % (sensor['instrument'], inst, msg)
            pat = os.path.join(rbindir, inst, '*.%s.rbin' % msg)
            filelist = glob.glob(pat)
            filelist.sort()
            if nfiles is None:
                fl = filelist
            else:
                fl = filelist[-nfiles:]
            label += ' %d files' % len(fl)
            slist.append(label)
            if not fl:
                continue
            bs = BinfileSet(fl)
            if bs.nrows < 3:
                continue
            ds_u_dday = Diffstats(bs.u_dday)
            ds_m_dday = Diffstats(bs.m_dday)
            if ds_u_dday.n_vlow > 0:
                wlist.append('%s %s %s' % (inst, msg, ds_u_dday))
            if ds_m_dday.n_vlow > 0:
                wlist.append('%s %s %s' % (inst, msg, ds_m_dday))
            slist.append('u_dday  %s' % ds_u_dday)
            slist.append('m_dday  %s' % ds_m_dday)
            if 'dday' in bs.columns:
                slist.append('dday    %s' % Diffstats(bs.dday))
            slist.append('')
    return '\n'.join(slist), '\n'.join(wlist)

def check_clock(rbindir, inst, msg, nfiles=None):
    '''
    Look for jumps in the difference between clock time and monotonic time.
    '''
    pat = os.path.join(rbindir, inst, '*.%s.rbin' % msg)
    filelist = glob.glob(pat)
    filelist.sort()
    if nfiles is None:
        fl = filelist
    else:
        fl = filelist[-nfiles:]
    if not fl:
        return '', ''
    bs = BinfileSet(fl)
    if len (bs.u_dday) == 0: #no data
        return '', ''
    dt = (bs.u_dday - bs.m_dday) * 86400
    mdt = np.median(dt)
    dt = dt - mdt
    ddt = np.diff(dt)
    jumpf = ddt > 1  # computer clock jumped forward relative to monotonic
    jumpb = ddt < -1 #                       back
    tlist = []
    wlist = []
    tlist.append('median clock t minus monotonic: %f days' % (mdt/86400.0,))
    tlist.append('dt extremes after removing median: %f %f seconds'
                                                % (dt.min(), dt.max()))
    if jumpf.sum() or jumpb.sum():
        s = 'jumps forward: %d   jumps back: %d' % (jumpf.sum(), jumpb.sum())
        tlist.append(s)
        wlist.append(s)
        if jumpf.sum():
            ii = ddt[jumpf].argmax()
            s = 'max forward %d seconds at dday %f' % (ddt[ii], bs.u_dday[ii])
            tlist.append(s)
            wlist.append(s)
        if jumpb.sum():
            ii = ddt[jumpb].argmin()
            s = 'max backward %d seconds at dday %f' % (-ddt[ii], bs.u_dday[ii])
            tlist.append(s)
            wlist.append(s)
    return '\n'.join(tlist) + '\n', '\n'.join(wlist) + '\n'
