#!/usr/bin/env python
## DAS_while_logging.py : called when "Start Recording" is pushed

import sys, os, os.path

import logging, logging.handlers
from pycurrents.system import logutils
L = logging.getLogger()
L.setLevel(logging.INFO)

formatter = logutils.formatterTLN

logbasename = '/home/adcp/log/DAS_while_logging'

handler = logging.handlers.RotatingFileHandler(logbasename+'.log', 'a',
                                              100000, 9)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
L.addHandler(handler)

handler = logging.handlers.TimedRotatingFileHandler(logbasename+'.warn',
            'midnight', 1, 20)
handler.setLevel(logging.WARNING)
handler.setFormatter(formatter)
L.addHandler(handler)

L.info('Starting DAS_while_logging.py')

from pycurrents.system import repeater
from uhdas.uhdas.incr_class import Translate
from uhdas.system import cleanup_figs
from uhdas.system.uhdas_webgen import make_simplefiglinks
from uhdas.system.uhdas_webgen import make_ttable
from uhdas.system.uhdas_webgen import make_beamdiag_ttable
from uhdas.system.uhdas_webgen import make_tsstats_ttable
from uhdas.system.uhdas_webgen import make_sci_ttable

# Handle asc2bin messages separately in a single set of log files.
La2b = logging.getLogger('asc2bin')
handler = logging.handlers.TimedRotatingFileHandler(
                    '/home/adcp/log/asc2bin.log',
                    'midnight', 1, 3)
handler.setFormatter(formatter)
La2b.addHandler(handler)
La2b.setLevel(logging.INFO)
La2b.propagate=False


from uhdas.uhdas.procsetup import procsetup
ci = procsetup(logging = True)

workdir = ci.workdir
#short_t = ci.short_t  # enslength is being used instead of this.
long_t = ci.long_t

CI = ci.CI

L.info('Cruiseid: %s', CI.cruiseid)

from pycurrents.system.pmw_process import SingleFunction

class Procs(SingleFunction):
    def keep_running(self):
        runflag = (os.path.islink(CI.pd.homecruiseD)
                    and os.path.isfile(self.flagfile)
                    and not os.path.isfile(self.stopflagfile))
        return  runflag

    def run_speedlog(self):
        speedlog_stopflagfile = None
        speedlog_runflagfile = None
        if ci.speedlog_cmd:
            cmd = ci.speedlog_cmd.strip().split()[0]
            base, ext = os.path.splitext(cmd)
            fbase = os.path.basename(base)
            speedlog_stopflagfile = os.path.join(CI.pd.flagD, fbase + '.stop')
            speedlog_runflagfile = os.path.join(CI.pd.flagD, fbase + '.running')
            L.info('speedlog_stopflagfile: %s', speedlog_stopflagfile)
            L.info('speedlog_runflagfile: %s', speedlog_runflagfile)
            if self.action is None:
                command = '%s &' % (ci.speedlog_cmd,)
            else:
                command = '%s %s &' % (ci.speedlog_cmd, self.action)
            os.system(command)
            L.info('speedlog command is %s' % (command,))
        self.speedlog_stopflagfile = speedlog_stopflagfile
        self.speedlog_runflagfile = speedlog_runflagfile

    def run(self):
        L.info("starting run method")
        self.run_speedlog()

        try:
            gzip_serial_files = ci.gzip_serial_files
        except AttributeError:
            gzip_serial_files = False

        T = Translate(dir_asc_base = CI.pd.rawD,
                      dir_bin_base = CI.pd.rbinD,
                      dir_logfile = workdir,
                      yearbase = CI.yearbase,
                              gzip = gzip_serial_files,
                              redo = 0,
                              showbad = 1,       ##
                              sleepseconds = 2,  # sleepseconds = 1,  #<=test9
                              keep_running = self.keep_running,
                              verbose = 0,           # 2 turns on full debugging
                       subdir_messages = CI.subdir_messages)
        T.start()

        R = repeater.Repeater(self.keep_running, poll_interval = 5,
                              timeout = 900, flagfile = self.flagfile)

        L.info('active_procdirnames: %s', ci.active_procdirnames)

        ktpref = [inst for inst in ci.kts_dir_instrument
                                  if inst in ci.active_procdirnames]

        for procdirname in ci.active_procdirnames:

            switches = ' --update_pygbin --averages --plotens_mpl --kt_vecprof --pingwarnN 30'
            if procdirname == ktpref[0]:
                switches = switches + ' --ktsdir'

            time_fname = os.path.join(ci.procdirbase, procdirname,
                                           'load', 'wrote_ens_time')
            cmd = 'cd %s; run_lastensq.py -d %s %s' % (
                                           workdir, procdirname, switches)
            R.add(repeater.PeriodicSystem(cmd,
                                           interval=ci.enslength[procdirname] + 10,
                                           name = '%s_lastensq' % (procdirname,),
                                           time_fn = time_fname,
                                           shell=True,
                                           at_exit = 0))


            cmd = 'cd %s; run_grab_lastpings.py -d %s ' % (
                                           workdir, procdirname)
            R.add(repeater.PeriodicSystem(cmd,
                                           interval=ci.enslength[procdirname] + 20,
                                           name = '%s_10pings' % (procdirname,),
                                           shell=True,
                                           at_exit = 0))

            #-----

            cmd = 'cd %s; run_quick.py -d %s ' % (workdir, procdirname)
            R.add(repeater.PeriodicSystem(cmd, interval=long_t,
                                           name = '%s_quick' % (procdirname,),
                                           shell=True,
                                           at_exit = 0))

            cmd = 'cd %s; run_3dayplots_mpl.py -d %s ' % (
                                           workdir, procdirname)
            R.add(repeater.PeriodicSystem(cmd, interval=long_t,
                                           name = '%s_3dayplots' % (procdirname,),
                                           shell=True,
                                           at_exit = 0))


            cmd = 'cd %s; run_plot_tsstats.py %s ' % (
                                           workdir, procdirname)
            R.add(repeater.PeriodicSystem(cmd, interval=long_t,
                                           name = '%s_tsstats' % (procdirname,),
                                           shell=True,
                                           at_exit = 0))

        # adding beam diagnstics with separate timers;
        for procdirname in ci.active_procdirnames:
            for plottype in ci.beamstats:
                try:
                    cmd = 'cd %s; plot_beamdiagnostics.py ' % (workdir,)

                    cmd =  cmd + ' -d %s --savefigs --webcopy -p %s' % (procdirname, plottype)
                    R.add(repeater.PeriodicSystem(cmd, interval=900, #15min
                                                  name = '%s_beamplots' % (procdirname,),
                                                  shell=True,
                                                  at_exit = 0))
                except:
                    L.exception("plot_beamdiagnostics.py -p %s..." % (plottype))


        # regenerate new html quick_links for the relevant processing dirs
        make_ttable(ci.html_dir, ci.active_procdirnames)
        make_beamdiag_ttable(ci.html_dir, ci.active_procdirnames)
        make_tsstats_ttable(ci.html_dir, ci.active_procdirnames)
        make_sci_ttable(ci.html_dir, ci.active_procdirnames)
        make_simplefiglinks(ci.html_dir, ci.active_procdirnames,
                            ci.attitude_devices,
                            beamstats=ci.beamstats,
                            hdg_inst=ci.hdg_inst)

        # monitor quality of heading devices
        # "attitude_devices" was made in procsetup from hdg_inst_msgs
        #        and is shorthand for "heading instruments except for primary"
        for attitude_device in ci.attitude_devices:
            # update plots every 5 minutes
            try:
                switches = '--plotdh --printstats'
                cmd = 'cd %s; run_hbinhcorrstats.py --hcorr_inst %s %s'
                cmd = cmd %   (workdir, attitude_device, switches)
                R.add(repeater.PeriodicSystem(cmd, interval=300,
                                 name = '%s_hcorrstats' % (attitude_device,),
                                 shell=True,
                                 at_exit = 0))
            except:
                L.exception("run_hcorrstats.py")

        # plot posmv_qc if they exist
        for (hdg_inst, hdg_msg) in ci.hdg_inst_msgs:
            if 'pmv' in hdg_msg:   # i.e. PASHR message: eg. posmv, coda_f185
                try:
                    cmd = 'cd %s; run_plotposmv.py -n25 -d %s' % (workdir, hdg_inst)
                    R.add(repeater.PeriodicSystem(cmd, interval=300,
                                 name = '%s_plotposmv' % (hdg_inst,),
                                 shell=True,
                                 at_exit = 0))
                except:
                    L.exception("run_plotposmv.py")



        L.info("cleanup_figs no_figure")
        cleanup_figs.cleanup(ci, "no_figure")

        # The following will start the loop and *block*.
        R.start()

        if (self.speedlog_stopflagfile is not None and
                      os.path.isfile(self.speedlog_runflagfile)):
            open(self.speedlog_stopflagfile, 'w').close()
        L.info("cleanup_figs not_logging")
        cleanup_figs.cleanup(ci, "not_logging")


    ######## End of Procs.run #########################################

if __name__ == "__main__":

    action = None
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        if 'replace' in args:
            action = 'replace'
        elif 'keep_old' in args:
            action = 'keep_old'

    try:
        Procs(flagdir=CI.pd.flagD, action=action).start()
    except:
        L.exception('Error in Procs start')


    L.info('Exiting DAS_while_logging.py')
