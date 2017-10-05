from __future__ import print_function
from future.builtins import zip
from future import standard_library
standard_library.install_hooks()
from future.builtins import range
from future.builtins import object

from six.moves.tkinter import *
from six.moves.tkinter_simpledialog import SimpleDialog

import time, sys, os
import tempfile
from subprocess import Popen, PIPE

from pycurrents.system.tkTimeout import Timeout

def get_time_string():
    return time.strftime('%H:%M:%S',time.gmtime(time.time()))


def check_path(p, mode = 0o775):
    if not os.access(p, os.F_OK):
        try:
            os.makedirs(p, mode)
            print("Created output directory <%s> with mode %o" % (p, mode))
        except OSError:
            print("Cannot access and/or create data output directory <%s>" % (p,))
            print("Check Permissions!")
            sys.exit(1)

class LockError(Exception):
    pass

class SystemCommandError(Exception):
    pass

class DuplicateDeviceError(Exception):
    pass


class Tracker(Frame):
    fmt = '%Y/%m/%d %H:%M:%S'

    def __init__(self, master = None, timeout = 10000):
        Frame.__init__(self, master)
        self.config(relief = GROOVE, bd = 2)

        self.ErrorCount = 0
        self.GoodCount = 0
        self.StartTime = time.time()
        self.LastErrorTime = 0
        self.LastGoodTime = 0

        self.SV_GoodCount = StringVar()
        self.SV_GoodCount.set('0')
        self.SV_ErrorCount = StringVar()
        self.SV_ErrorCount.set('0')

        L_StartTime = Label(self, text =
                    time.strftime(Tracker.fmt, time.gmtime(self.StartTime)),
                    width = 18, bg = 'lightgrey')
        self.SV_LastErrorTime = StringVar()
        self.SV_LastErrorTime.set('')
        self.SV_LastGoodTime = StringVar()
        self.SV_LastGoodTime.set('')

        self.L_GoodCount = Label(self, textvariable = self.SV_GoodCount,
                                   anchor = E, width = 5, bg = 'white')
        self.L_ErrorCount = Label(self, textvariable = self.SV_ErrorCount,
                                   anchor = E, width = 5, bg = 'white')
        self.L_LastGoodTime = Label(self, textvariable = self.SV_LastGoodTime,
                                   anchor = W, width = 18, bg = 'white')
        self.L_LastErrorTime = Label(self, textvariable = self.SV_LastErrorTime,
                                   anchor = W, width = 18, bg = 'white')

        Label(self, text = 'Errors:').grid(row = 3, column = 1, sticky = E)
        self.L_ErrorCount.grid(row = 3, column = 2, sticky = W)
        self.L_LastErrorTime.grid(row = 3, column = 3, sticky = W, padx = 20)

        Label(self, text = 'Good:').grid(row = 2, column = 1, sticky = E)
        self.L_GoodCount.grid(row = 2, column = 2, sticky = W)
        self.L_LastGoodTime.grid(row = 2, column = 3, sticky = W, padx = 20)

        Label(self, text = 'Start:').grid(row = 1, column = 1, sticky = E)
        L_StartTime.grid(row = 1, column = 3, sticky = W, padx = 20)
        self.IV_timed_out = IntVar()   # E.g., for a checkbutton indicator.
        self.timeout = Timeout(master = self, timeout = timeout,
                                      callback = self.timeout_warning)
        #self.timeout_warning() # Start with red; turn green when data arrives.
        # Omitting the above leaves things grey when logging is off; this
        # distinguished "logging is off" from "logging is on but failing".

    def update(self, ok):
        if ok:
            self.GoodCount = self.GoodCount + 1
            self.LastGoodTime = time.time()
            self.SV_GoodCount.set('%d' % self.GoodCount)
            self.SV_LastGoodTime.set(
                     time.strftime(Tracker.fmt, time.gmtime(self.LastGoodTime)))
            self.L_LastGoodTime.config(bg = 'white')
            self.timeout.start()
            self.IV_timed_out.set(0)
        else:
            self.ErrorCount = self.ErrorCount + 1
            self.LastErrorTime = time.time()
            self.SV_ErrorCount.set('%d' % self.ErrorCount)
            self.SV_LastErrorTime.set(
                     time.strftime(Tracker.fmt, time.gmtime(self.LastErrorTime)))

    def write(self, fp):
        fp.write('Error statistics at ' +
                    time.strftime(Tracker.fmt, time.gmtime(time.time())) + '\n')
        fp.write('Start time: ' +
                    time.strftime(Tracker.fmt, time.gmtime(self.StartTime)) + '\n')
        fp.write('Good Count: %d     Error Count: %d\n' % (self.GoodCount, self.ErrorCount) )

    def timeout_warning(self):
        self.L_LastGoodTime.config(bg = 'red')
        self.IV_timed_out.set(1)


class LogProcess(object):  # mainly a data structure for ser_adcp parameters
    def __init__(self, device = 'ttyS0', baud = 9600, program = 'ser_asc',
                   options = '', directory = './',
                   instrument = 'generic', yearbase = 2001):
        # device might end up as a path, e.g. '/dev/ttyS0', after
        # modifications of ser_asc and ser_bin.
        self.device_path = device # In case we might need the original.
        # For making filenames we eliminate the '/':
        self.device = device.replace('/', '-')
        self.baud = baud
        self.program = program
        self.options = options
        self.directory = directory
        self.instrument = instrument
        self.yearbase = yearbase

        pipe_directory = '/tmp/SerialLogger'

        try:
            os.mkdir(pipe_directory)
        except OSError: # as msg:
            pass # Could check for msg other than [Errno 17] file exists,
                 # but don't expect it.

        self.in_pipe = os.path.join(pipe_directory, 'inpipe.%s' % self.device)
        self.out_pipe = os.path.join(pipe_directory, 'outpipe.%s' % self.device)
        self.lock_file = '/var/lock/LCK..%s' % self.device
        self.pipe_lock_file = os.path.join(pipe_directory,
                                            'pipe_pid.%s' % self.device)

        try:
            os.mkfifo(self.in_pipe)
        except OSError:
            pass

        try:
            os.mkfifo(self.out_pipe)
        except OSError:
            pass


    def new_connection(self, start_time = None):
        temp_stderr = os.path.join(tempfile.gettempdir(), 'stderr.%s' % self.device)
        if start_time:
            T_opt = " -T %d " % start_time
        else:
            T_opt = ""
        redirection = "2> %s" % temp_stderr     # Bash
        if self.program.endswith('zmq_asc'):
            command = "%s -y %d -Z %s -d %s -i %s -o %s %s %s %s &" %  (
                     self.program, self.yearbase,
                     self.device_path,  self.directory,
                     self.in_pipe, self.out_pipe, T_opt, self.options,
                     redirection)
        else:  # ser_asc, ser_bin
            command = "%s -y %d -P %s -b %d -d %s -i %s -o %s %s %s %s &" %  (
                     self.program, self.yearbase,
                     self.device_path, self.baud, self.directory,
                     self.in_pipe, self.out_pipe, T_opt, self.options,
                     redirection)

        print(command)
        ret = os.system(command)
        if ret != 0:
            raise SystemCommandError("Error in new_connection:\n" \
                                        + command \
                                        + "\n returned %d\n" % ret)

        for i in range(10):
            time.sleep(0.2)
            if self.is_running():
                return
        msg1 = 'Error in new_connection: %s failed to start.\n' % self.program
        msg2 = 'Command: %s\n' % command
        msg3 = file(temp_stderr).read()
        raise SystemCommandError(msg1 + msg2 + msg3)

    def is_running(self, kill=False):
        try:
            lockfile = open(self.lock_file, 'r')
            pid = int(lockfile.readline().split()[0])
            lockfile.close()
            if pid == os.getpid():
                return 0 # The lock is held by this process, not by a ser_* process.
            os.kill(pid, 0) # raises OSError if no such pid
            if kill:
                os.kill(pid, 9)
                try:
                    os.remove(lockfile)
                except:
                    pass
                return 2
            return 1
        except (OSError, IOError, ValueError):
            pass
        except Exception as e:
            print(e)
        return 0




class LogControl(object):  # mixin for Logger and Loggers
    def make_FB(self, master = None, quit_button = 1):
        """ Frame with horizontal row of start/stop buttons. """
        if not master: master = self
        # Frame with Buttons
        self.FB = Frame(master)
        # Note: it is not packed here because we don't know
        # where we will want to put it.
        # Button Start
        self.BS = Button(self.FB, text = 'Start Logging',
                                   command = self.start_logging)
        self.BS.pack(side = LEFT, expand = YES)
        if quit_button:
            self.BQ = Button(self.FB, text = 'Quit Monitor',
                                       command = self.close_monitor)
            self.BQ.pack(side = LEFT, expand = YES)
        # Button Exit (poor mnemonic and name; fix later)
        self.BE = Button(self.FB, text = 'Stop Logging',
                                   command = self.check_stop_logging)
        self.BE.pack(side = LEFT, expand = YES)
        self.BE.configure(state = DISABLED)

    def confirm_stop(self):
        d = SimpleDialog(self,
                         text = "You can quit this window \n"
                                "without stopping the underlying \n"
                                "data acquisition process.\n\n"
                                "Do you want to stop data acquisition?",
                         buttons = ['Yes', 'No'],
                         default = 0,
                         cancel = 1,
                         title = 'Stop logging?')
        return (d.go() == 0)  # True if Stop Logging is confirmed

    def confirm_close(self):
        d = SimpleDialog(self,
                         text = "The logging processes are still running. \n"
                                "Do you want to close this monitoring window?",
                         buttons = ['Yes', 'No'],
                         default = 0,
                         cancel = 1,
                         title = 'Close window?')
        return (d.go() == 0)  # True if Close window is confirmed


class Loggers(Frame, LogControl):
    def __init__(self, master = None, yearbase = 2001,
                      quit_button = 1,
                      bindir = '/usr/local/bin'):
        self.self_controlled = 0
        if master == None:
            master = Tk()
            master.title("Logger")
            master.iconname("Log")
            master.protocol("WM_DELETE_WINDOW", self.close_monitor)
            self.self_controlled = 1
        Frame.__init__(self, master)
        self.pack()
        self.yearbase = yearbase
        self.bindir = bindir
        self.LogWins = list()
        self.LogWinDict = dict()  #dictionary of Logger objects for easier access
                                  # (We could do everything with either the
                                  # list or the dictionary, but it is easier
                                  # to keep both. We need at least one list
                                  # to keep track of the display order.)
        self.EnabledDict = dict() # True by default; can be set to False
        self.is_logging = 0
        if self.self_controlled:
            self.make_FB(quit_button = quit_button)
            self.FB.pack(side = TOP, expand = YES)
        self.bind('<Destroy>', self.close_monitor)

    def add(self,  device = 'ttyS0', baud = 9600, program = 'ser_asc',
                   options = '', directory = './',
                   instrument = 'generic',
                   timeout = 1000):
        check_path(directory)
        program = os.path.join(self.bindir, program)

        lp = LogProcess(device = device, baud = baud,
                    program = program, options = options,
                    directory = directory, instrument = instrument,
                    yearbase = self.yearbase)
        LoggerInstance = Logger(self, lp, control = 0, timeout = timeout)
        self.LogWins.append(LoggerInstance)
        self.LogWinDict[instrument] = LoggerInstance
        self.EnabledDict[instrument] = True

    def setEnabled(self, instrument, value):
        self.EnabledDict[instrument] = value

    def getEnabled(self, instrument):
        return self.EnabledDict[instrument]

    def add_list(self, sensors, common_opts, base_dir, timeout):
        optlist = ['device', 'baud', 'program', 'options', 'directory',
                   'instrument', 'timeout']
        kwargs = {}
        devs = []
        for sensor in sensors:
            key = sensor['device']
            if key in devs:
                msg = 'serial device %s is found twice in config/sensor_cfg.py' % key
                raise DuplicateDeviceError(msg)
            devs.append(key)
        for sensor in sensors:
            if sensor['format'] == 'ascii':
                sensor['program'] = 'ser_asc'
            elif sensor['format'] == 'zmq_ascii':
                sensor['program'] = 'zmq_asc'
            else:
                sensor['program'] = 'ser_bin'
            opts = " ".join((common_opts,
                                '-e %s' % sensor['ext'],
                                sensor['opt']))
            if sensor['format'] in ('ascii', 'zmq_ascii'):
                for s in sensor['strings']:
                    opts = " %s '%s'" % (opts, s)
            sensor['options'] = opts
            sensor.setdefault('timeout', timeout)
            sensor['directory'] = os.path.join(base_dir, sensor['subdir'])
            for o in optlist:
                kwargs[o] = sensor[o]
            self.add(**kwargs)

    def check_stop_logging(self, auto=False):
        if not self.is_logging:
            return 0
        if auto or self.confirm_stop():
            self.is_logging = 0
            for LW in self.LogWins:
                LW.stop_logging()
            for ii in range(30):  # Give it a whopping 6 seconds...
                time.sleep(0.2)
                nrun = sum(self.list_running()[0], 0)
                if nrun == 0:
                    break
            if nrun == 0:
                print("Loggers.check_stop_logging: all log processes ended")
            else:
                print("Loggers.check_stop_logging: failed to end all processes")
                for LW in self.LogWins:
                    ret = LW.logproc.is_running(kill=True)
                    if ret == 2:
                        print("Killed %s for %s" %  (LW.logproc.program,
                                                     LW.logproc.instrument))
            if hasattr(self, 'BE'):
                self.BE.configure(state = DISABLED)
                self.BS.configure(state = NORMAL)
            return 0
        return 1 # Still logging; changed mind

    def close_monitor(self, event = ''):
        if not self.LogWins:
            return
        if self.self_controlled:
            if self.check_stop_logging(): # still logging
                if not self.confirm_close():
                    return # jump out
        for LW in self.LogWins:
            LW.close_monitor()
        self.LogWins = []
        if event == '':
            self.unbind('<Destroy>')
        if self.self_controlled:
            self.master.destroy()
        else:
            self.destroy()

    def start_logging(self, start_time = None):
        print("Entering Loggers.start_logging")
        if self.is_logging:
            return
        self.is_logging = 1
        for LW in self.LogWins:
            if self.getEnabled(LW.logproc.instrument):
                LW.start_logging(start_time)
                LW.stats.timeout_warning()    # red until first data arrival
        if hasattr(self, 'BE'):
            self.BS.configure(state = DISABLED)
            self.BE.configure(state = NORMAL)
        print("Leaving Loggers.start_logging")

    def list_running(self):
        running = []
        enabled = []
        for LW in self.LogWins:
            if self.getEnabled(LW.logproc.instrument):
                enabled.append(1)
            else:
                enabled.append(0)
            if LW.logproc.is_running():
                running.append(1)
            else:
                running.append(0)
        return running, enabled

    def resume(self):
        ''' If all LogWins correspond to active and enabled logging
        processes, then resume logging; if only some are
        active, kill them, so we get a fresh start.
        Return 1 if resuming, 0 if starting afresh.
        '''
        print("Entering Loggers.resume")
        running, enabled = self.list_running()
        print('running: ', running, 'enabled', enabled)
        ii = 0
        resuming = True
        N_enabled = 0
        N_running = 0
        for R, E in zip(running, enabled):
            if (E and not R) or (R and not E):
                resuming = False
            if R:
                N_running += 1
            if E:
                N_enabled += 1
        if N_running == 0:
            resuming = False
        elif resuming == False: # there was a mismatch
            for ii, LW in enumerate(self.LogWins):
                if running[ii]:
                    LW.start_logging()  # to reconnect
                    LW.stop_logging()   # to shut down cleanly, we hope
        else:
            self.start_logging()      # reconnect to all enabled processes
        return resuming

    def start(self):
        self.start_logging()
        self.mainloop()


class LoggersStatusFrame(Frame):
    def __init__(self, master = None, logs = None):
        Frame.__init__(self, master)
        self.logs = logs # Loggers object
        self.Checkbuttons = []
        for lw in self.logs.LogWins:
            name = lw.logproc.instrument
            IV = lw.stats.IV_timed_out
            cb = Checkbutton(self, variable = IV,
                             text = name,
                             state = DISABLED,
                             indicatoron = 0,
                             selectcolor = 'red', # timed out
                             background = 'grey85', # initial: not logging
                             disabledforeground = 'black')
            cb.pack(side = LEFT, expand = YES, fill = BOTH)
            self.Checkbuttons.append(cb)
        self.check()

    def on(self):
        for cb in self.Checkbuttons:
            cb.config(background = 'green')

    def off(self):
        for cb in self.Checkbuttons:
            cb.config(background = 'grey85')

    def check(self):
        for ii in range(len(self.Checkbuttons)):
            cb = self.Checkbuttons[ii]
            if self.logs.LogWins[ii].is_logging:
                cb.config(background = 'green')
            else:
                cb.config(background = 'grey85')


class Logger(Frame, LogControl):
    def __init__(self, master, logproc, control = 1,
                   timeout = 1000):
        Frame.__init__(self, master)
        self.pack(expand = YES, fill = BOTH)
        self.config(relief = GROOVE, bd = 3)

        self.logproc = logproc    #LogProcess object

        self.nlines = 4  # Can get this in other ways later.

        self.SV_Status = StringVar()
        self.SV_Status.set('Inactive')
        self.is_logging = 0

        self.StatusLine().pack(side = LEFT, expand = NO, pady = 1)
        self.stats = Tracker(self, timeout = timeout)
        self.stats.pack(padx = 5, pady = 5, side = LEFT)

        self.control = control
        if control:
            self.make_FB()

        self.pingline = StringVar()
        self.lines = [''] * self.nlines

        self.MP = Checkbutton(self, textvariable = self.pingline,
                             variable = self.stats.IV_timed_out,
                             state = DISABLED,
                             indicatoron = 0,
                             selectcolor = 'red', # timed out
                             background = 'grey85', # initial: not logging
                             disabledforeground = 'black',
                             justify = LEFT,
                             anchor = W,
                             height = self.nlines,
                             width=80)
        self.MP.config(relief = RIDGE, bd = 2)
        self.MP.pack(side = LEFT, expand = YES, fill = X)

        if control:
            self.bind('<Destroy>', self.close_monitor)
            self.start_logging()

    def StatusLine(self):
        SLframe = Frame(self)
        SLframe.config(relief = RAISED, bd = 2)
        DEV = Label(SLframe, text = '%s\n%s' %
                             (self.logproc.instrument, self.logproc.device),
                             width = 15)
        DEV.pack(side = TOP, padx = 1, pady = 1)
        self.MS = Message(SLframe, textvariable = self.SV_Status)
        self.MS.configure(relief = 'ridge', width = 500, bg = 'white')
        self.MS.pack(side = TOP, pady = 1, padx = 1)
        return SLframe

    def check_stop_logging(self, check = 1):
        if not self.is_logging: return
        if not check or self.confirm_stop():
            self.stop_logging()


    def stop_logging(self, cmd_stop = True):
        if not self.is_logging:   return
        self.tk.deletefilehandler(self.fp)
        if cmd_stop:
            self.fp.close()
            cp = open(self.commandpipename, 'wb')
            cp.write(b'X')
            cp.close()
        self.SV_Status.set('Not Logging')
        self.MS.configure(fg = 'red')
        self.MP.configure(fg='grey85')
        self.is_logging = 0

    def close_monitor(self, event = ''):
        #logfile = open('lograw.log', 'a')
        #self.stats.write(logfile)
        #logfile.close()
        if self.is_logging:
            self.tk.deletefilehandler(self.fp)
            self.fp.close()
        try:
            os.remove(self.logproc.pipe_lock_file)
        except OSError:
            pass
        if self.control and event == '':
            self.unbind('<Destroy>')
        self.destroy()


    def start_logging(self, start_time = None):
        if self.is_logging: return  # so multiple button presses do nothing
        try:
            if not self.logproc.is_running():
                self.logproc.new_connection(start_time)
            self.connect_pipe(self.logproc.out_pipe,
                              self.logproc.in_pipe,
                              self.logproc.pipe_lock_file)
            self.MS.configure(fg = 'green')
        except Exception as msg:
            print(msg)

    def pipes_are_locked(self, lockfilename):
        try:
            lockfile = open(lockfilename, 'r')
            pid = int(lockfile.readline())
            cmd = ['ps', '--noheader', '-p%s' % pid, '-o', 'pid']
            (psout, err) = Popen(cmd, stdout=PIPE,
                                    stderr=PIPE).communicate()
            if int(psout) == pid:
                return pid
        except (OSError, IOError, ValueError):
            pass
        return 0

    def lock_pipe(self, lockfilename):
        locking_pid = self.pipes_are_locked(lockfilename)
        if locking_pid != 0 and locking_pid != os.getpid():
            raise LockError(locking_pid)
        try:
            lockfile = open(lockfilename, 'w')
            lockfile.write(repr(os.getpid()))
            lockfile.close()
        except (OSError, IOError) as msg:
            raise LockError('opening or writing lockfile: ' + msg)


    def connect_pipe(self, datapipename, commandpipename, lockfile):
        self.lock_pipe(lockfile)
        self.datapipename = datapipename
        self.commandpipename = commandpipename
        fd = os.open(self.datapipename, os.O_RDONLY| os.O_NONBLOCK)
        self.fp = os.fdopen(fd, 'rb')
        self.tk.createfilehandler(self.fp, READABLE, self.pipe_reader)
        self.SV_Status.set('Logging')
        self.is_logging = 1

    def pipe_reader(self, fp, mask):
        try:
            _line = fp.readline()
            if len(_line) == 0:  # Older python/linux: broken pipe.
                                 # Newer version raises IOError.
                raise IOError('broken pipe')
        except IOError:
            self.stop_logging(False)
            return
        line = _line.strip().decode('ascii', 'ignore')
        self.lines = self.lines[-(self.nlines - 1):] + [line]
        self.pingline.set("\n".join(self.lines))
        # Lines are separated by \n, but there is no trailing \n;
        # so we don't have a blank line at the bottom of the message window.

        if line.lower().find('error') > -1:
            self.MP.config(background = 'pink')
            ok = 0
        else:
            self.MP.config(background = 'lightgreen')
            ok = 1
        self.stats.update(ok)
