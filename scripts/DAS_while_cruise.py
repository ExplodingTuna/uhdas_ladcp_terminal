#!/usr/bin/env python
## DAS_while_cruise.py : called when "Start Cruise" is pushed

from __future__ import absolute_import
from future import standard_library
standard_library.install_hooks()
import sys, os, os.path
import time
from six.moves import tkinter, tkinter_messagebox

import logging, logging.handlers
from pycurrents.system import logutils
from uhdas.system.system_summary import test_backupdir

L = logging.getLogger()
L.setLevel(logging.DEBUG)
formatter = logutils.formatterTLN

logbasename = '/home/adcp/log/DAS_while_cruise'

handler = logging.handlers.RotatingFileHandler(logbasename+'.log', 'a', 100000, 3)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
L.addHandler(handler)

handler = logging.handlers.TimedRotatingFileHandler(logbasename+'.warn',
                    'midnight', 1, 20)
handler.setLevel(logging.WARNING)
handler.setFormatter(formatter)
L.addHandler(handler)

L.info('Starting DAS_while_cruise.py')

from pycurrents.system import repeater
from uhdas.system import cleanup_archive

from uhdas.uhdas.procsetup import procsetup

ci = procsetup(cruisedir = '')  # cruisedir = '' is needed because we are not
                                # logging yet.
CI = ci.CI

try:
    L.info('Cruiseid: %s', CI.cruiseid)
except AttributeError:
    L.warn('No cruiseid found; exiting now.')
    sys.exit()
    # This should be very unusual, perhaps only occurring when
    # torture-testing autonomous operation; this might lead to
    # a cruise being ended immediately after startup, before
    # this script actually has chance to get going after being
    # launched in the background with os.system().


from pycurrents.system.pmw_process import SingleFunction


class Procs(SingleFunction):
    def keep_running(self):
        runflag = (os.path.islink(CI.pd.homecruiseD)
                    and os.path.isfile(self.flagfile)
                    and not os.path.isfile(self.stopflagfile))
        return  runflag

    def run(self, auto=False):

        #### maybe change the following to /dev/null for a real cruise?
        ### or use tee.py to pull out useful parts?

        ## backup locations could be
        # - a directory (eg. '/disk2/home/data' or '/media/UHDAS/data')
        # - a remote location for rsync using ssh keys (eg. 'rigel:/home/data')
        # - a remote location for rsync using rsyncd (eg. 'healynas::/uhdas/data')


        L.info("starting run method with auto=%s; making repeater", auto)
        R = repeater.Repeater(self.keep_running, poll_interval = 5,
                              timeout = 900, flagfile = self.flagfile)
        L.info("Checking external disk mounts")
        # keep track of those that work
        backup_paths_OK = list(ci.backup_paths)
        #first test mounts other than '/disk2/home' and remote (ssh) locations
        # TODO -- make the backup locations into a dictionary to facilitate testing
        #   
        mountpoints = [p for p in ci.backup_paths if p.startswith('/media')]
        badmounts = [p for p in mountpoints if not os.path.ismount(p)]
        for p in badmounts:
            message = 'external disk %s not mounted.  ' % (p,)
            message += 'Connect and mount %s,' % (p,)
            L.warning(message)
            if not auto:
                message += 'then click "OK"'

                root = tkinter.Tk()
                root.withdraw()
                tkinter_messagebox.showwarning(
                                   title="unmounted disk failure",
                                   message=message)
                root.destroy()
        #remove those that failed
        for p in badmounts:
            backup_paths_OK.pop(backup_paths_OK.index(p))
        L.info("Checking backup paths")
        # test write, for thost that are left
        for p in list(backup_paths_OK):
            pd = os.path.join(p, 'data')
            errstr = test_backupdir(pd)
            if ':' not in pd and len(errstr) > 0:
                try:
                    os.mkdir(pd)
                    errstr = test_backupdir(pd)
                except:
                    pass
            if len(errstr) > 0:
                backup_paths_OK.pop(backup_paths_OK.index(p)) #remove those that failed
                L.warning(errstr)
                if not auto:
                    message = 'Cannot write to backup directory %s.\n' % (pd,)
                    message += 'Check for write permission '
                    message += 'or remount if necessary, '
                    message += 'and then restart the cruise'

                    root = tkinter.Tk()
                    root.withdraw()
                    tkinter_messagebox.showwarning(
                                        title="inaccessible directory failure",
                                        message=message)
                    root.destroy()

        L.info("Starting rsync tasks")
        rsync_opts = '-aux --delete --modify-window=1'
        for p in backup_paths_OK:
            pd = os.path.join(p, 'data')
            cmd = "rsync %s %s %s" % (rsync_opts, CI.pd.baseD, pd)
            R.add(repeater.PeriodicRsync(cmd, interval=ci.rsync_t,
                                           name = "rsync_%s" % (p,),
                                           at_exit = 0))

        L.info("Starting the repeater loop")
        # The following will start the loop and *block*.
        R.start()
        L.info("Repeater loop ended")

        #If there are no backup media, wait until the
        # cruise ends.
        while self.keep_running():
            time.sleep(1)
            os.utime(self.flagfile, None)

        # End of cruise things:

        L.info("cleanup_archive")
        cleanup_archive.cleanup(ci)

        # The following can't be done using the at_exit option of
        # the repeater because then it would be before the archive
        # cleanup
        for p in backup_paths_OK:
            pd = os.path.join(p, 'data')
            cmd = "rsync %s %s %s" % (rsync_opts, CI.pd.baseD, pd)
            L.info(cmd)
            os.system(cmd)

        # make report
        cmd = "uhdas_report_generator.py -u %s " % (CI.pd.baseD)
        L.info(cmd)
        os.system(cmd)


    ######## End of Procs.run #########################################

if __name__ == '__main__':

    kwargs = dict()

    action = None
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        if 'replace' in args:
            action = 'replace'
        elif 'keep_old' in args:
            action = 'keep_old'

        if 'auto' in args:
            kwargs['auto'] = True
            # autonomous: no gui interaction
            action = 'replace'

    try:
        Procs(flagdir=CI.pd.flagD, action=action, kwargs=kwargs).start()
    except:
        L.exception('Error in Procs start')

    L.info('Exiting DAS_while_cruise.py')
