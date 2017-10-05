''' Continuous incremental translation of ascii to binary files.

    This is a driver for the asc2bin routines, providing
    multi-threaded incremental processing of ascii files as
    they are being logged, always working on the most recent
    file.

    2004/06/13 EF: changed gzipping strategy; note that it
    requires a change in the fileglob.

## Sample use of a Translate object:

if __name__ == '__main__':
    T = Translate(dir_asc_base = '/home/data/km0505a/raw',
                  dir_bin_base = '/home/data/km0505a/rbin',
                  yearbase = 2005,
                          gzip = 1,
                          showbad = 1,
                          sleepseconds = 2,  # sleepseconds = 1,  #<=test9
                          verbose = 0,
                   subdir_messages = {'ashtech': ('gps', 'adu'),
                                     'posmv': ('gps', 'pmv'),
                                     'gyro': ('hdg',),
                                     'simrad': ('gps',)})
    T.start()
    while T.running:
        try:
            time.sleep(1)
        except:  # Ctl-C
            T.stop()


'''

import os, glob, threading, stat

import logging, logging.handlers
L = logging.getLogger('Translate')
logging.basicConfig()  # Only acts if a handler is not already present.
L.setLevel(logging.INFO)

from pycurrents.data.nmea import asc2bin
from pycurrents.system.threadgroup import ThreadGroup

class Translate(ThreadGroup):
    def __init__(self, keep_running = None,
                       yearbase = None,
                       showbad = 1,
                       verbose = 0,
                       gzip = 0,
                       redo = 0,
                       sleepseconds = 2,
                       dir_asc_base = None,
                       dir_bin_base = None,
                       dir_logfile = '',
                       fileglob =  '*_???_?????.???',
                       subdir_messages = None
                       ):
        ThreadGroup.__init__(self, keep_running = keep_running)
        # The ThreadGroup will add its own version of keep_running.
        self.yearbase = yearbase
        self.showbad = showbad
        self.verbose = verbose
        self.gzip = gzip
        self.redo = redo
        self.sleepseconds = sleepseconds
        self.dir_asc_base = dir_asc_base
        self.dir_bin_base = dir_bin_base
        self.dir_logfile = dir_logfile
        self.fileglob = fileglob
        self.subdir_messages = subdir_messages

        for subdir in list(self.subdir_messages.keys()):
            dir_in = os.path.join(self.dir_asc_base, subdir)
            dir_out = os.path.join(self.dir_bin_base, subdir)
            if not os.path.isdir(dir_out):
                os.makedirs(dir_out)
            primary = 1   # flag for first thread in a subdirectory
            for message in self.subdir_messages[subdir]:
                T = threading.Thread(target = self.translate,
                                  args = (dir_in, dir_out, message, primary))
                T.setDaemon(1)
                self.add(T)
                L.info("%s %s %s" % (subdir, message, str(primary)))
                L.info(str(T))
                primary = 0  # next one is not primary

    def translate(self, dir_in, dir_out, message, primary):
        kwargs = {'showbad' : self.showbad,
                  'verbose' : self.verbose,
                  'redo'    : self.redo,
                  'sleepseconds' : self.sleepseconds,
                  'keep_running' : self.keep_running,
                  'outfiledir' : dir_out,
                  'message' : message,
                  'yearbase' : self.yearbase,
                  'update' : 1}

        first_time = 1
        fields = [f for f in os.path.split(dir_in) if len(f) > 1]
        if len(fields):
            inst = fields[-1]
        else:
            inst = 'unknown'
        fn = inst + '_' + message
        log = logging.getLogger(fn)
        log.propagate = 0  # Don't pass messages up to the root logger.
        log.setLevel(logging.INFO)
        file_interval = 24
        n_files = 2
        if self.verbose > 1:
            log.setLevel(logging.DEBUG)
            file_interval = 1
            n_files = 24
        formatter = logging.Formatter('%(asctime)s %(message)s')
        p = os.path.join(self.dir_logfile, fn)
        handler = logging.handlers.TimedRotatingFileHandler(p, 'H',
                              file_interval, n_files)
        handler.setFormatter(formatter)
        log.addHandler(handler)
        kwargs['logname'] = fn
        kwargs_old = kwargs.copy()
        kwargs_old['update'] = 0
        kwargs_old['showbad'] = 0

        last_mtime = 0
        while self.keep_running():
            ascfiles = glob.glob(os.path.join(dir_in, self.fileglob))
            ascfiles.sort()
            log.debug('ascfiles: %s' % str(ascfiles))
            files = ascfiles[:-1]
            if first_time and len(files) > 0:
                log.debug('first time files: %s' % str(files))
                asc2bin.asc2bin(**kwargs_old).translate_files(files)
                first_time = 0
            ziplist = ascfiles[:-2]
            if len(ziplist) > 0 and primary and self.gzip:
                cmd = '(nice gzip %s ) &' % ' '.join(ziplist)
                log.info(cmd)
                os.system(cmd)
            n = -1
            for _file in ascfiles[-1:]:  # slice of empty list returns empty list
                mtime = os.stat(_file)[stat.ST_MTIME]
                if mtime <= last_mtime:
                    log.debug('File %s is not recently modified', str(_file))
                    continue
                log.debug('_file: %s' % str(_file))
                n = asc2bin.asc2bin(**kwargs).translate_files([_file])
                last_mtime = mtime
            if n < 1:         # Nothing new in the last file, or no file, ...
                self.timer(self.sleepseconds)

        # On exit, zip anything left, *except* the last file;
        # this process might be terminated while logging is still
        # underway, and we don't want to zip a file out from under
        # the logger.  It would be nice if we could *lock* the file
        # to which the logger is writing.
        L.info( "translate exiting, %s %s " % (message, dir_out))
        ziplist = glob.glob(os.path.join(dir_in, self.fileglob))
        ziplist.sort()
        if len(ziplist) > 1 and primary and self.gzip:
            cmd = '(nice gzip %s ) &' % ' '.join(ziplist[:-1])
            L.info(cmd)
            os.system(cmd)




