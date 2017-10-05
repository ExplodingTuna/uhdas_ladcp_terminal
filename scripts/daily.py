#!/usr/bin/env python
#
# This program wraps up status-gathering, tar+gz+uuencode and smtp mail
# for UHDAS status email.  Installation-specific information (eg. email
# addresses) are in /home/adcp/config/uhdas_cfg.py
#
# EF,JH 2004/09/10
#
# This is a BUS--a Big Ugly Script.
#

from __future__ import division
import os, glob, time, string, shutil
import pickle
from optparse import OptionParser


from uhdas.system.repo_summary import HGinfo


# add this to find 'hg' in /usr/local/bin; also addded to bash_env
os.environ['PATH'] = os.environ['PATH'] +':/usr/bin:/usr/local/bin'

## Do the option parsing now; defer additional imports and the
## logging system startup so that one can obtain the usage message
## even if the logging system would fail.

usage = """usage: %prog [options]

   "daily.py"           : update the status information, but don't mail it.
   "daily.py --summary" : update directory (without detailed disk info); don't mail it.
"""
parser = OptionParser(usage = usage)
parser.add_option("", "--tarball",
                  action="store",
                  dest="tarball_mailto",
                  help="mail tarball to this list of land-based addresses",
                  default = '')

parser.add_option("", "--local_status",
                  action="store",
                  dest="local_status_mailto",
                  help="mail short status message list of ship-based addresses",
                  default = '')

parser.add_option("", "--shore_status",
                  action="store",
                  dest="shore_status_mailto",
                  help="mail full status message to this list of land-based addresses",
                  default = '')

parser.add_option("", "--debug",
                  action="store",
                  type="int",
                  dest="debug",
                  metavar="N",
                  help="send debugging files from last N days",
                  default = 0)

parser.add_option("", "--tarfilenum",
                  action="store",
                  dest="tarfile_num",
                  help="mail old tarball (default is -1, i.e. most recent)",
                  default = -1)

parser.add_option("", "--summary",
                  action="store_true",
                  dest="summary",
                  help="disk summary only, not 'du -sk' details",
                  default = False)

parser.add_option("", "--noarchive",
                  action="store_true",
                  dest="no_archive",
                  help="do not archive tarfiles",
                  default = False)


parser.add_option("", "--tar_archivedir",
                  action="store",
                  dest="tar_archivedir",
                  help="tar archive directory, defaults to ''",
                  default = '/home/data/archive_dailyreports')


parser.add_option("", "--use_defaults",
                  action="store_true",
                  dest="use_defaults",
                  help="mail to address lists from config/uhdas_cfg.py",
                  default = False)

(options, args) = parser.parse_args()


######  Now we are ready to run; we have to be in something like
######  a normal uhdas setup.

import logging, logging.handlers

L = logging.getLogger()
L.setLevel(logging.DEBUG)
formatter = logging.Formatter(
      '%(asctime)s %(levelname)-8s %(name)-12s %(message)s')

logbasename = '/home/adcp/log/daily.py'

handler = logging.FileHandler(logbasename+'.log', 'w')
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
L.addHandler(handler)

handler = logging.FileHandler(logbasename+'.warn', 'w')
handler.setLevel(logging.WARNING)
handler.setFormatter(formatter)
L.addHandler(handler)


from uhdas.uhdas.procsetup import procsetup
import uhdas.system.system_summary as SS
import uhdas.system.logging_summary as logging_summary
from uhdas.system.mail_report import report_mailer


L.info('Starting daily.py')


## get the cruise info
ci = procsetup(cruisedir = '')  # empty string so it does not raise
os.chdir(ci.daily_dir)


## set up emails --------------------------------------------------

timestring = time.strftime("%Y/%m/%d %H:%M:%S")
namestring = os.popen('uname -rn').read()

def make_address_list(s):
    s = s.split(',')
    s = [f for f in s if f]
    return s

options.tarball_mailto = make_address_list(options.tarball_mailto)
options.local_status_mailto = make_address_list(options.local_status_mailto)
options.shore_status_mailto = make_address_list(options.shore_status_mailto)

if options.use_defaults:
    options.tarball_mailto = ci.tarball_mailto
    options.local_status_mailto = ci.local_status_mailto
    options.shore_status_mailto = ci.shore_status_mailto

if options.debug:
    options.shore_status_mailto = ci.shore_status_mailto

#tarball archive options
if options.no_archive:
    save_tarfile = False
else:
    save_tarfile = True
if options.tar_archivedir is None and save_tarfile:
    options.tar_archivedir = '/home/data/archive_dailyreports'
    if not os.path.isdir(options.tar_archivedir):
        try:
            os.mkdir(options.tar_archivedir)
        except:
            L.exception('could not find or make %s' % (options.tar_archivedir))


## maybe only remove stuff older than the beginning of the cruise?
try:
    delete_old = SS.delete_old('*', 7*86500) # for the moment, leave for 1 week
except:
    L.exception('SS.delete_old')


try:
    serbin_processes       = SS.list_processes('ser_bin')
    serasc_processes       = SS.list_processes('ser_asc')
    zmq_processes       = SS.list_processes('zmq')
    DAS_processes          = SS.list_processes('DAS')

    mem_python = SS.list_processes('py', '-eFL')

    processes = [DAS_processes, serbin_processes,
                 serasc_processes, zmq_processes, mem_python]

    dfile = open(os.path.join(ci.daily_dir, 'processes.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write('\n'.join(processes))
    dfile.close()
except:
    L.exception('processes')

try:
    ntpq = SS.check_ntpq()
    ntp_status = SS.check_ntpd()
    dfile = open(os.path.join(ci.daily_dir, 'ntp.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(ntpq)
    dfile.write(ntp_status)
    dfile.close()
except:
    L.exception('ntp')



try:
    sermem = SS.serial_memory()
    dfile = open(os.path.join(ci.daily_dir, 'serial_memory.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(sermem)
    dfile.close()
except:
    L.exception('serial_mem')


try:
    uptime = SS.check_uptime()
except:
    L.exception('uptime')


try:
    IO_status, IO_warnstr = SS.check_IOerrs()
    dfile = open(os.path.join(ci.daily_dir, 'IOerrs.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(IO_status)
    dfile.close()
except:
    L.exception('IO')



try:
    EDAC_status, EDAC_warnstr = SS.check_EDACerrs()
    dfile = open(os.path.join(ci.daily_dir, 'EDACerrs.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(EDAC_status)
    dfile.close()
except:
    L.exception('EDAC')



try:
    USBserial_status, USBserial_warnstr = SS.check_USBoverrun()
    dfile = open(os.path.join(ci.daily_dir, 'USBerrs.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(USBserial_status)
    dfile.close()
except:
    L.exception('USB')

try:
    cal_status = SS.check_cals()
    dfile = open(os.path.join(ci.daily_dir, 'cals.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(cal_status)
    dfile.close()
except:
    L.exception('btwt_cals')


try:
    nping_status = SS.check_npings()
    dfile = open(os.path.join(ci.daily_dir, 'npings.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(nping_status)
    dfile.close()
except:
    L.exception('npings')



try:
    flist = glob.glob(os.path.join(ci.daily_dir,'*pingstats.txt'))
    plist = ['------------- pings per ensemble ----------- ']
    for pfile in flist:
        lines = open(pfile,'r').readlines()
        plist.append(lines[0])
        plist.append(lines[-2])  #last line is just a newline
    plist.append('')
    pingstr = '\n'.join(plist)
except:
    L.exception('pingstats')
    pingstr = ''


try:
    logwarning_status, logwarning_warnstr = SS.check_logwarnings()
    dfname = os.path.join(ci.daily_dir, 'logwarnings.txt')
    dfile = open(dfname, 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(logwarning_status)
    dfile.close()
except:
    L.exception('logwarningstatus')

try:
    dmesg_status = SS.dmesg(20)
    dfile = open(os.path.join(ci.daily_dir, 'dmesg.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(dmesg_status)
    dfile.close()
except:
    L.exception('dmesg')


try:
    seconds_status = SS.proc_seconds(180)
    dfile = open(os.path.join(ci.daily_dir, 'proc_seconds.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write(seconds_status)
    dfile.close()
except:
    L.exception('proc_seconds')


try:

    fname = os.path.join(ci.daily_dir, 'hg_tips.txt')
    HG = HGinfo()

    adcplist=[]
    adcplist.append(HG.summary('/home/adcp/config'))
    adcplist.append(HG.diff(repodir='/home/adcp/config'))

    tips=[]
    HG.get_uhdas_repos()
    for r in HG.repolist:
        tips.append(HG.assemble_strings(r, show_installed=True))
    tips.append('\n')

    ss = ['------- /home/adcp/config --------',
          '\n'.join(adcplist),
          '------- programs status --------',
          '\n'.join(tips)]

    open(fname, 'w').write('\n'.join(ss))

except:
    L.exception('hg_tips')

try:
    dfile = open(os.path.join(ci.daily_dir, 'DAS_main.txt'), 'w')
    s = logging_summary.logfile_since('/home/adcp/log/DAS_main.log',
                                                time.time() -  86400*3)
    dfile.write(s)
    dfile.close()
except:
    L.exception('DAS_main')

try:
    if ci.cruiseid:
        instnames = []
        for pp in ci.instname.keys():
            if ci.instname[pp] not in instnames:
                instnames.append(ci.instname[pp])
        for iname in instnames:
            cmdfile = os.path.join(ci.cruisedir,'raw',iname,'current.cmd')
            dest = os.path.join(ci.daily_dir, 'commands_%s.txt' % (iname))
            shutil.copyfile(cmdfile, dest)
except:
    L.exception('current_cmd')


try:
    if ci.cruiseid:
        for fname in ['proc_cfg.py', 'sensor_cfg.py', 'uhdas_cfg.py']:
            src = os.path.join('/home/adcp/config',fname)
            shutil.copy2(src, ci.daily_dir)
except:
    L.exception('configfiles')


try:
    ## try to write zmq_tails.txt, regardless of cruise status
    lastzmq_ascii=''
    lastzmq_logging='no zmq logging'
    if os.path.exists('/home/data/0mon'):
        lastzmq_logging   = logging_summary.showzmq('logging', 10)
        lastzmq_ascii   = logging_summary.showzmq('ascii', 10)

        tailstring = '\n'.join(["====== zmq monitoring ========",
                                lastzmq_ascii, lastzmq_logging])
        dfile = open(os.path.join(ci.daily_dir, 'zmq_tails.txt'), 'w')
        dfile.write(tailstring)
        dfile.close()
except:
    L.exception('check_zmq')


try:
    ## write autopilot.txt regardless of status
    autopilot_running, autopilot_str = logging_summary.autopilot_summary()
    if autopilot_running:
        autopilot_status = '\n(DAS_autopilot.py is running)\n'
        dfile = open(os.path.join(ci.daily_dir, 'autopilot.txt'), 'w')
        dfile.write(autopilot_str)
        dfile.close()
    else:
        autopilot_status = ''
except:
    L.exception('check_autopilot')

#-------------------------
try:
    disk_summary      = SS.disk_summary()[0]

    if options.summary is True:

        disk_short  = ['%s -- disk usage summary\n' % (timestring,),
                       disk_summary,
                       ]
        dfile = open(os.path.join(ci.daily_dir, 'disk_summary.txt'), 'w')
        dfile.write('%s\n' % timestring)
        dfile.write('\n'.join(disk_short))
        dfile.close()
    else:
        disk1picklefile = os.path.join(ci.daily_dir, 'disk1.pickle')
        old_dud1 = None
        if os.path.exists(disk1picklefile):
            old_dud1 = pickle.load(open(disk1picklefile))
        disk_usage, dud1 = SS.disk_usage('/home/data/*', within_days=90)
        pickle.dump(dud1, open(disk1picklefile, 'w'))
        disk1diff = 'disk1 difference not available'
        try:
            if old_dud1:
                disk1diff = SS.du_difference(old_dud1, dud1)
        except:
            L.exception('disk1diff')

        dud_diff = ''
        for disk in ci.backup_paths:
            disk_usage2 = '%s not accessible' % (disk,)
            try:
                disk_usage2 = disk + '\n'
                gstr = os.path.join(disk, 'data/*')
                disk_usage2, dud2 = SS.disk_usage(gstr, within_days=90)
            except:
                L.exception('disk_usage2')
                continue

            disk_usage += disk_usage2
            try:
                dud_diff += '---- %s ----\n' % (disk,)
                dud_diff += SS.du_difference(dud2, dud1, old_prefix = disk,
                                             new_prefix = '/home')
            except:
                L.exception('dud_diff')

        if dud_diff == '':
            dud_diff = 'not available\n'

        if os.path.exists('/proc/mdstat'):
            MD = open('/proc/mdstat','r')
            mdstat = MD.read()
            MD.close()
        else:
            mdstat = 'not a RAID device\n'


        disk_short  = ['%s -- disk usage summary\n' % (timestring,),
                       disk_summary,
                       '\ndifference, disk1new minus disk1old\n',
                       disk1diff,
                       '\ndifference, disk1 minus others\n',
                       dud_diff,
                       '\n-------- RAID info --------\n',
                       mdstat]
        dfile = open(os.path.join(ci.daily_dir, 'disk_summary.txt'), 'w')
        dfile.write('%s\n' % timestring)
        dfile.write('\n'.join(disk_short))
        dfile.close()


        disk_long =   ['%s -- disk usage details, last 90 days\n' % (timestring),
                       '\nDetails\n', disk_usage]

        dfile = open(os.path.join(ci.daily_dir, 'disk_details.txt'), 'w')
        dfile.write('%s\n' % timestring)
        dfile.write('\n'.join(disk_long))
        dfile.close()

        diskuse_list = glob.glob('disk*.txt')
except:
    L.exception('disk information')

## determine whether logging is on; only send processing info if logging is on
## mostly generate strings below this
uhdas_is_logging = False

try:
    flag_files     = SS.list_files(ci.flag_dir)
    recentlogfiles = SS.list_recent('/home/adcp/log/*', 86500)
    recenttmpfiles = SS.list_recent(ci.workdir, 86500)

    dirlists = ['flags directory\n',
              flag_files,
              '\nlog files\n',  recentlogfiles,
              '\ntmp files\n',  recenttmpfiles]
    dfile = open(os.path.join(ci.daily_dir, 'disk_files.txt'), 'w')
    dfile.write('%s\n' % timestring)
    dfile.write('\n'.join(dirlists))
    dfile.close()
except:
    L.exception('disk_files.txt')


#-----  cruise_str, backupdisk_str -------

backupdisk_warnstr = ''
data_paths = ['/home/data',]
for p in ci.backup_paths:
    bstr = os.path.join(p, 'data')
    data_paths.append(bstr)
for p in data_paths:
    errstr = SS.test_backupdir(p)
    if len(errstr) > 0:
        pstr = '\n--->>>  %s NOT FOUND (check mounts) <<<---\n' % (p,)
        backupdisk_warnstr += pstr
        backupdisk_warnstr += errstr

#------

cruise_str = "no cruise set"

#------

try:
    zmq_pub_running = False
    zmq_summary = ''
    xyz_comment = 'no position from zmq'
    zmq_xy = None

    if not hasattr(ci, 'use_publishers'):
        ci.use_publishers = None
    else:
        tup  = logging_summary.zmq_summary('/home/data/0mon',
                                           use_publishers = ci.use_publishers)
        if len(tup) == 3:
            zmq_pub_running, zmq_summary, zmq_xy = tup
            xyz_comment = 'position from zmq'
except:
    xyz_comment = 'position from serial gps'
    L.exception('zmq_summary')


#------
et_email_str = '''
--- Data logging status --
(1) Panels are green?  (UHDAS Monitor on "currents")
(2) Figures to check:  http://currents/adcp/figures_wframes.html

  top row:    5-minute ensembles  (figures should be less than 10 minutes old)
  middle:     processed data (figures should be less than 2 hours old)
  bottom row: heading corrections, last 300 ensembles
---
'''


#------

def _isrunning(sname):
    '''
    Use flag file to check for running process.
    sname is the base name of the script, e.g. 'DAS_while_cruise'.
    This works for scripts using repeater, or otherwise updating
    the flag file mtime at intervals of a few seconds.
    If the flag file has not been updated in 300 s, the pid is
    checked.
    '''
    fname = sname + '.running'
    fpath = os.path.join(ci.CI.pd.flagD, fname)
    L.debug("checking flag file: %s", fpath)
    try:
        mt = os.path.getmtime(fpath)
        now = time.time()
        L.debug("mt = %f, now= %f, dif is %f", mt, now, now-mt)
        if now - mt > 300:
            L.warn("Flag file update was %d seconds ago", int(now-mt))
            pid = int(file(fpath).read().split()[0])
            try:
                os.kill(pid, 0)
            except OSError:     # no such process
                return False
            return True
        return True
    except os.error: # file doesn't exist
        return False

if ci.cruiseid:
    cruise_str = "Current cruise: %s " % ci.cruiseid
    if os.path.exists(os.path.join(ci.CI.pd.flagD, 'DAS.logging')):
        uhdas_is_logging = True
        cruise_str += '    ** is logging **'
        if not _isrunning('DAS_while_cruise'):
            cruise_str += '\n   DAS_while_cruise.py is *not* running.'
        if not _isrunning('DAS_while_logging'):
            cruise_str += '\n   DAS_while_logging.py is *not* running.'
    else:
        cruise_str += ' *** not logging ***'


    try:
        cruisepath = os.path.join('/home/data',ci.cruiseid)
        sonar_str = SS.get_sonar_summary(cruisepath)
        dfile = open(os.path.join(ci.daily_dir, 'sonar_summary.txt'), 'w')
        dfile.write('%s\n' % timestring)
        dfile.write(sonar_str)
        dfile.close()
    except:
        L.exception('sonar_summary')



#-----  ship-specific ------
## NBP JGOF used to be here

#-----  generic -------

fromships = 'http://currents.soest.hawaii.edu/uhdas_fromships'
land_links = '\n'.join([
        '===============================\n'
        'figures:  %s/%s/figs/' %  (fromships, ci.shipdir),
        'daily report: %s/%s/daily_report/\n' %  (fromships, ci.shipdir)])



## comes from uhdas_cfg.py
email_comment_str = ''
if hasattr(ci, 'email_comment_str'):
    email_comment_str = ci.email_comment_str

#-----  gyro_dh_str  -------

## make messages having to do with logging and processing
rbinwarnstr  = ''
clockwarnstr  = ''
btrk_str = '\n'
gyro_dh_str = ''

if ci.cruiseid:
    L.debug('cruiseid is %s', ci.cruiseid)
    try:
        stderr_tails = SS.tails('/tmp/stderr*',200)
        dfile = open(os.path.join(ci.daily_dir, 'stderr.txt'), 'w')
        dfile.write('------------\n'.join(stderr_tails));
        dfile.close()

    except:
        L.exception("active cruise stderr files")


    if uhdas_is_logging:
        try:

            last_logging = logging_summary.showlast('logging',12)
            last_rbin    = logging_summary.showlast('rbin',12)
            last_gbin    = logging_summary.showlast('gbin',12)
            last_ascii   = logging_summary.showlast('ascii', 12)

            tailstring = '\n'.join([last_ascii, last_logging, last_rbin, last_gbin])
            dfile = open(os.path.join(ci.daily_dir, 'tails.txt'), 'w')
            dfile.write(tailstring)
            dfile.close()

            ## processing.txt
            cruise_str += '\nDatabase time ranges:'
            tnow = time.time()
            dtfmt = "%Y/%m/%d  %H:%M:%S"
            for procdirname in ci.get_active_procdirnames():
                try:
                    procpath = os.path.join(ci.cruisedir, 'proc', procdirname)
                    plist = ['***** %s *******' % (procpath,),]
                    plist.append(logging_summary.tail_file(os.path.join(procpath,'load/write_ensblk.log'),15))
                    plist.append('\n\n\n ---------- database info ----------\n')
                    plist.append(''.join(open('%s/adcpdb/%s.lst' % (procpath, ci.dbname)).readlines()))
                    dfile = open(os.path.join(ci.daily_dir, 'processing_%s.txt' % (procdirname,)) , 'w')
                    dfile.write('%s\n' % timestring)
                    dfile.write('\n-------------'.join(plist))
                    dfile.close()
                    trf = glob.glob(os.path.join(procpath, 'adcpdb', '*.tr'))[0]
                    tr = open(trf).read()
                    t1 = time.mktime(time.strptime(string.split(tr,'to')[-1][1:-1], dtfmt))
                    ago = int((tnow-t1)/60.0)
                    cruise_str += '\n    %8s %s  (%d min. ago)' % (procdirname, tr[:-1], ago)
                except:
                    L.info('processing_%s.txt failed' % (procdirname,))
                    pass

            #lat, lon, depth
            cruise_str += '\n\n' + logging_summary.xyz_str(ci, xy=zmq_xy, comment=xyz_comment) + '\n'

            # accurate = ci.hcorr_inst; reliable = ci.hdg_inst (retain 'gyro' in variables)
            if ci.hcorr_inst == ci.hdg_inst  or  len(ci.hcorr_inst) == 0:
                gyro_dh_str = 'no heading correction device specified'
            else:
                gyro_dh_str = '(heading correction from "%s")\n' % (ci.hcorr_inst,)
            for att_device in ci.attitude_devices:
                gyro_dh_str += '===========================\n'
                gyro_dh_str += '------ %s statistics ------\n' % (att_device,)
                gyro_dh_str += '===========================\n'
                gyro_dh_statsfile = '/home/adcp/daily_report/%s_%s_pystats.txt' % (
                    att_device, ci.hdg_inst)
                if os.path.exists(gyro_dh_statsfile):
                    gyro_dh_str += ''.join(open(gyro_dh_statsfile).readlines()[:20])
                else:
                    gyro_dh_str += '%s does not (yet?) exist\n' % (gyro_dh_statsfile,)

            # add lines to say whether BT is on
            adcplist = list(ci.instname.values())
            tested = []
            for adcp in adcplist:
                if adcp not in tested:
                    tested.append(adcp)
                    btrk_str += adcp + ': ' + logging_summary.btrk_status(ci.cruisedir, adcp) + '\n'

            dfile = open(os.path.join(ci.daily_dir, 'rbintimes.txt'), 'w')
            out, clockwarnstr = SS.check_clock(ci.CI.pd.rbinD,
                                               ci.hdg_inst, ci.hdg_msg, 15)
            dfile.write(out + '\n')
            out, rbinwarnstr = SS.check_rbintimes(ci.CI.pd.rbinD,
                                                    ci.CI.sensors, 15)
            dfile.write(out)
            dfile.close()

        except:
            L.exception("active cruise processing summary")
    else:
        gyro_dh_str = "not logging: no heading correction calculated at this time"

else:
    #lat, lon, depth
    if zmq_pub_running:
        cruise_str += '\n\n' + logging_summary.xyz_str(ci, xy=zmq_xy, comment=xyz_comment) + '\n'
    else:
        if ci.use_publishers:
            cruise_str += '\nzmq is enabled  but zmq_publisher is NOT running.'
        else:
            cruise_str += '\nzmq is not enabled. no zmq position.'
    SS.del_processingfiles()  # only delete these files if the cruise is over
    gyro_dh_str = "no active cruise: no heading correction calculated at this time"

#---------------------------------------
## now stage the emails

# new ET email
if uhdas_is_logging:
    et_text = et_email_str
else:
    et_text = ''

et_lines = ['------ cruise status -----------',
            cruise_str, backupdisk_warnstr,
            '======  heading correction ======',
            gyro_dh_str,
            et_text]


warning_count = 0
warning_summary_str = 'Summary of warnings:\n______________________\n'
warnstr_title = dict(#ship warnings went here
                     IO         = 'I/O warnings',
                     EDAC       = 'EDAC memory warnings',
                     USBserial  = 'serial overruns',
                     logwarning = 'wordcount of log/*.warn',
                     backupdisk = 'expected backup disk not found',
                     rbin       = 'rbin warnings',
                     clock      = 'timestamp warnings')
warnstrings = dict(#ship warnings went here
                   IO         = IO_warnstr,
                   EDAC       = EDAC_warnstr,
                   USBserial  = USBserial_warnstr,
                   logwarning = logwarning_warnstr,
                   backupdisk = backupdisk_warnstr,
                   rbin       = rbinwarnstr,
                   clock      = clockwarnstr)

try:
    for wskey in list(warnstrings.keys()):
        ws = warnstrings[wskey]
        if ws.strip():
            wstitle = warnstr_title[wskey]
            warning_count += 1
            warning_summary_str += '\n(%d) %s:\n%s' % (warning_count, wstitle,ws)

    if warning_count == 0:
        warncount_str = "no warnings"
        warning_summary_str = ''
    else:
        warncount_str = '%d warnings (see bottom)' % (warning_count,)
except:
    L.exception("Generating warning summary")
    warncount_str = "A warnstr was missing so there is no summary"

slist = []
for disk in ['/home'] + ci.backup_paths:
    gyroglob = os.path.join(disk, 'data',
                         '%s', 'raw','gyro', '*') % ci.cruiseid
    slist.append(SS.list_file_ages(gyroglob, reverse = False, maxfiles = 2))
loggingstring = '\n'.join(slist)
lastensglob = os.path.join(ci.web_figdir, '*lastens.png')
lastensstring = SS.list_file_ages(lastensglob)
ddaycontglob = os.path.join(ci.web_figdir, '*ddaycont.png')
ddaycontstring = SS.list_file_ages(ddaycontglob)


# shore-based email
status_strlist = [timestring,
                  namestring,
                  cruise_str,
                  autopilot_status,
                  '---- heading correction ----',
                  gyro_dh_str,
                  '\n---bottom track status--------',
                  btrk_str,
                  ntpq,
                  pingstr,
                  '\n',
                  uptime,
                  land_links,
                  email_comment_str,
                  '\n',
                  zmq_summary,
                  '\n\n',
                  warning_summary_str,
                  '\nFigures and files:',
                  '\n-------------------',
                  '\nGyro logging and backup:',
                  loggingstring,
                  '\nChecking updating of 5-minute plots:',
                  lastensstring,
                  '\nChecking updating of hourly plots:',
                  ddaycontstring ]


status_strlist.append('\n\nlocal_status_mailto:')
status_strlist.append('\n'.join(options.local_status_mailto))
status_strlist.append('\n')
status_str = '\n'.join(status_strlist)
et_str = '\n'.join(et_lines)

sfile = open(os.path.join(ci.daily_dir, 'status_str.txt'), 'w')
sfile.write(status_str)
sfile.close()

efile = open(os.path.join(ci.daily_dir, 'et_email.txt'), 'w')
efile.write(et_str)
efile.close()

# make index.html for this directory
# mk_report_index.py - not implimented yet


########### Send the messages. #######################

# use_SSL comes from uhdas_cfg.py
if not hasattr(ci, 'use_SSL'):
    ci.use_SSL = False
if not hasattr(ci, 'SMTP_port'):
    ci.SMTP_port = None

if options.shore_status_mailto or options.tarball_mailto or options.local_status_mailto:
    try:
        RM = report_mailer(ci.SMTP_server, ci.mail_from, port = ci.SMTP_port, SSL = ci.use_SSL)

        if options.shore_status_mailto:
            L.debug('Mailing shore_status to %s', options.shore_status_mailto)
            RM.mail_string(to = options.shore_status_mailto,
                              msg = status_str,
                              subject = "%s ADCP shore status" % (ci.shipname,) )

        if options.local_status_mailto:
            L.debug('Mailing local_status to %s', options.local_status_mailto)
            RM.mail_string(to = options.local_status_mailto,
                              msg = et_str,
                              subject = "%s ADCP status" % (ci.shipname,) )

        send_tarball = False
        # tarfile ends in .uhdas; stripped and replaced by reader
        if options.tarball_mailto:
            if ci.cruiseid:
                filelist = glob.glob('*.txt') + glob.glob('*.bin')
                filelist.extend(glob.glob('*.asc') + glob.glob('*.stats'))
                filelist.extend(glob.glob('*.npy') + glob.glob('*_qc.png'))
                filelist.extend(glob.glob('*.py'))
                filelist.extend(glob.glob('*pings.raw'))
            else: # send a reduced subset, no data
                filelist = glob.glob('*.txt')
            tarfilename = ci.shipabbrev + time.strftime("%Y_%j_%H%M%S") + ".uhdas" #".tar.gz"
            subject = "%s ADCP tarball" % (ci.shipname,)
            L.debug('Mailing tarball to %s', options.tarball_mailto)
            send_tarball = True
        elif options.debug > 0 and options.shore_status_mailto:
            filelist = SS.debug_filelist(options.debug)
            tarfilename = ci.shipabbrev + time.strftime("%Y_%j_%H%M%S") + "debug.uhdas"
            subject = "%s ADCP debug tarball" % (ci.shipname,)
            L.debug('Mailing debug tarball to %s', options.shore_status_mailto)
            send_tarball = True

        if send_tarball:
            # generate the string, saving tarfile if requested
            if save_tarfile:
                if not os.path.exists(options.tar_archivedir):
                    os.mkdir(options.tar_archivedir)
                tgzfilepath = os.path.join(options.tar_archivedir, tarfilename + '.tar.gz')
                RM.generate_tarball_file(ci.daily_dir, filelist, tgzfilepath)

            L.info("tarfiles coming from %s" % (options.tar_archivedir))
            tgzfilelist = glob.glob(os.path.join(options.tar_archivedir, '*.tar.gz'))
            if len(tgzfilelist) > 0:
                tgzfilelist.sort()
                try:
                    file_of_interest = tgzfilelist[-abs(int(options.tarfile_num))]
                except:
                    L.warn('only %d files exist.  mailing oldest file' % (len(tgzfilelist)))
                    file_of_interest = tgzfilelist[0]

                tgz_str = RM.string_from_tarfile(file_of_interest)
                L.info('reading %s for email attachment' % (file_of_interest))
                tarfilename = os.path.basename(file_of_interest)[:-7]  #strip '.tar.gz'
            else:
                L.info('generating tarball string directly (no saved files)')
                tgz_str = RM.generate_tarball_string(ci.daily_dir, filelist)

            RM.mail_tarball_attachment(options.tarball_mailto, tgz_str,
                                       tarfilename=tarfilename,
                                       subject=subject)

    except:
        L.exception("mailing reports")

L.info('Ending daily.py')
