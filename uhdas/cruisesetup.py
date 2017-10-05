from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from six.moves.tkinter import *
from six.moves import tkinter_tksimpledialog
from six.moves import tkinter_messagebox
from six import PY3

import Pmw
import os, glob
from subprocess import Popen, PIPE, STDOUT
import stat
import time
import shutil
import subprocess

from string import digits
if PY3:
    from string import ascii_letters as letters
else:
    from string import letters

import logging, logging.handlers
from pycurrents.system import logutils

L = logutils.getLogger(__file__)

L.setLevel(logging.DEBUG)



from pycurrents.system.startstop import StartStopControl, ChangedMind

from uhdas.uhdas.procsetup import CruiseInfo, get_variables
from onship import shipnames


from uhdas.system.repo_summary import HGinfo


# Following are some message strings.  It is easier to
# format them if they are here instead of inside the
# class definition.

# This prompt works best with hard returns. (Entry dialog)
cruiseid_prompt = '''
Enter Cruise ID, e.g.,
%s.  Use only
alphanumeric characters
and underscore; start
with a letter.'''

# This one is better if auto-wrapped by the widget. (Message box)
confirm_start = '''
Setup for a new cruise \
is about to begin.  Configuration \
files will be written and a directory \
tree will be built using the new \
Cruise ID: %s'''


confirm_resume = '''
Directories for Cruise ID %s already exist, \
so it appears that this cruise has been started \
and stopped.  Do you want to resume it?'''


## Following is not used yet; but it would be nice to
## rearrange StartCruise so that it checks for the
## existance of the data directories before proceeding.
confirm_continue = '''
Directories already exist for \
this Cruise ID, %s.  Continue with \
this ID, or Cancel? '''


confirm_end = '''
End the present cruise, %s?
'''

no_cruise = 'None'


class query_cruiseid(tkinter_tksimpledialog._QueryString):
    allowed_chars = digits + letters + '_'

    def validate(self):
        str_ = self.getresult()
        bad = [c for c in str_ if c not in self.allowed_chars]
        if len(bad) > 0:
            tkinter_messagebox.showwarning("Cruise ID entry",
                                     "Only alphanumerics and _ are allowed",
                                      parent = self)
            return 0
        if str_[0] not in letters:
            tkinter_messagebox.showwarning("Cruise ID entry:",
                                     "First character must be a letter.",
                                      parent = self)
            return 0

        self.result = str_
        return 1

def askcruiseid(title, prompt, **kw):
    d = query_cruiseid(*(title, prompt), **kw)
    return d.result

def short_cruiselist(n=4):
    '''
    return list of recent cruise names to aid in cruise name selection
    '''
    flist = glob.glob('/home/data/*')
    flist.sort()
    tdict = dict()
    for d in flist:
        if os.path.isdir(d) and not os.path.islink(d):
            dname = os.path.basename(d)
            tdict[os.path.getctime(d)] = dname
    tsorted = sorted(tdict.keys())
    dirlist=[]
    for t in tsorted:
        if tdict[t] != 'current_cruise':
            dirlist.append(tdict[t])
    return dirlist[-n:]

class CruiseSetup(Pmw.LabeledWidget, CruiseInfo):
    functions = {'make_loggers' : None,
                 'destroy_loggers' : None,
                 'is_logging' : None}
    # Functions will be passed in as a tuple: (name, args, kwargs)

    def __init__(self, parent,
                   homedir = '/home/adcp', functions = None):
        Pmw.LabeledWidget.__init__(self, parent,
                                   labelpos = 'n',
                                   label_text = 'Cruise Setup',
                                   hull_relief = 'ridge',
                                   hull_borderwidth = 2,
                                   label_relief = 'groove',
                                   label_borderwidth = 2)
        self.parent = parent
        if functions:
            self.functions.update(functions)
        CruiseInfo.__init__(self, homedir)

        self.L_cruiseid = self.make_L_cruiseid(self.interior())
        self.L_cruiseid.pack()
        self.C_ss = StartStopControl(self.interior(),
                                      funcs = (self.StartCruise,
                                               self.EndCruise),
                                      names = ('Start Cruise',
                                               'End Cruise'),
                                      orient = 'vertical')
        self.C_ss.pack()


    def init(self):  ## called by createMain in DAS.py
        # Is there a current cruise?
        print("In CruiseSetup.init\n")
        if self.get_underway_cruise_info():
            print("Resuming Cruise")
            self.set_log_handler()
            self.save_hg_info()  #was save_hg_tips
            L.info("Resuming Cruise")
            self.SV_cruiseid.set(self.cruiseid)
            self.C_ss.set_state('started')
            self.run_function('make_loggers')
            if os.path.exists(self.pd.start_cruiseF):
                os.system('%s %s &' % (self.pd.start_cruiseF, 'keep_old'))
        else:
            self.C_ss.set_state('stopped')



    def run_function(self, key):
        f = self.functions[key]
        if f:
            return f[0](*f[1], **f[2])

    def set_log_handler(self):
        logname = os.path.join(self.pd.logD, 'Cruise_%s.log' % self.cruiseid)
        handler = logging.FileHandler(logname, 'a')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logutils.formatterTLN)
        L.addHandler(handler)
        self._handler = handler

    def write_cfg(self, cruiseid, yearbase):
        onship = dict(self.onship)
        onship['shipname'] = shipnames.shipnames[onship['shipkey']]
        onship['yearbase_string'] = str(yearbase)
        onship['cruiseid'] = cruiseid
        onship['uhdas_dir'] = self.pd.baseD
        milist = ['msg_info = ...\n        {']
        for s in self.sensors:
            if s['ext'] != 'raw':
                for m in s['messages']:
                    e = "'%s', '%s',\n         " % (s['subdir'], m)
                    milist.append(e)
        milist.append('        };\n')
        onship['msg_info'] = ''.join(milist)

        ## <snip> do not make cruise_proc.m, cruise_cfg.m
        ## <snip> not using procsetup_onship.py either
        # Make copies of sensor_cfg.py and the replacement pair
        if not os.path.isfile(self.pd.cruise_sensorF):
            shutil.copy(self.pd.sensorF, self.pd.cruise_sensorF)
        if not os.path.isfile(self.pd.cruise_uhdasF):
            shutil.copy(self.pd.uhdas_cfgF, self.pd.cruise_uhdasF)
        if not os.path.isfile(self.pd.cruise_procF):
            f = open(self.pd.cruise_procF, 'w')
            f.write("shipname = '%s'\n" % onship['shipname'])
            f.write("cruiseid = '%s'\n" % cruiseid)
            f.write("yearbase = %s\n" % yearbase)
            f.write("uhdas_dir = '%s'\n" % self.pd.baseD)
            f.write("\n# from proc_cfg.py:\n")
            f.write(open(self.pd.proc_cfgF).read())
            f.close()



    def clean_logdir(self):
        if not os.path.isdir(self.pd.morgueD):
            os.mkdir(self.pd.morgueD)
        t_old = time.time() - 14*86400 # two weeks ago
        for fn in os.listdir(self.pd.logD):
            oldpath = os.path.join(self.pd.logD, fn)
            s = os.stat(oldpath)
            t = s[stat.ST_MTIME]
            if stat.S_ISREG(s[stat.ST_MODE]) and t < t_old:
                newpath = os.path.join(self.pd.morgueD, fn)
                os.rename(oldpath, newpath)



    def save_hg_info(self):
        '''
        print hg source status and install information; leverage new tools
        '''
        tips = []
        try:
            fname = os.path.join(self.pd.logD, 'hg_%s.log' % self.cruiseid)
            HG = HGinfo()
            HG.write_strings_to_file(fname)
        except:
            L.exception('save_hg_info')

    def StartCruise(self, cruisename=None):
        if cruisename is not None:
            cruiseid = cruisename
            auto = True
        else:
            auto = False
            example_crname = shipnames.onship_cruise_strings[
                                                     self.onship['shipkey']]
            previous_cruises = '\n'.join(short_cruiselist()) #last 4 cruises
            prev_prompt = "\nLast 4 cruises:\n%s\n" % (previous_cruises)
            cruiseid = askcruiseid('Start Cruise',
                               cruiseid_prompt%(example_crname) + prev_prompt)
            if cruiseid is None:
                raise ChangedMind
        self.cruiseid = cruiseid

        self.SV_cruiseid.set(self.cruiseid)
        self.set_cruise_dirs()
        # Following is OK if all string variables we
        # extract from cruise_cfg.m are directories we need.
        if os.path.isdir(self.pd.baseD):
            if not auto and not tkinter_messagebox.askokcancel(title = "Resume Cruise",
                  message = confirm_resume % cruiseid):
                self.SV_cruiseid.set(no_cruise)
                raise ChangedMind
            new_cruise = False
        else:
            if not auto and not tkinter_messagebox.askokcancel(title = "Start Cruise",
                  message = confirm_start % cruiseid):
                self.SV_cruiseid.set(no_cruise)
                #os.remove(self.pd.cfgF)  # link made by write_cfg
                raise ChangedMind
            new_cruise = True

        if not new_cruise:
            try:
                d = get_variables(self.pd.cruise_procF)
                self.yearbase = int(d['yearbase'])
                L.info("Initializing yearbase from existing cruise: %d",
                                    self.yearbase)
            except (IOError, KeyError):
                L.exception("Failed to find yearbase")

        if new_cruise or not hasattr(self, 'yearbase'):
            self.yearbase = time.gmtime()[0]
            L.info("Initializing yearbase from current date: %d",
                                    self.yearbase)

        # Here is where the baseD is made for a new cruise:
        if not os.path.exists(self.pd.saveconfigD):
            os.makedirs(self.pd.saveconfigD)
        self.write_cfg(cruiseid, self.yearbase)


        if new_cruise:
            dirs = [self.pd.rawD, self.pd.procD, self.pd.rbinD, self.pd.gbinD,
                     self.pd.logD]
            if self.onship['shipkey'] in ('np', 'lg'):
                dirs.append(self.pd.tsgmetD)
            for _dir in dirs:
                try:
                    os.makedirs(_dir, 0o775)
                except OSError as e:
                    if e.errno != 17:  # 17 is "file exists"
                        raise

            for datatype in self.datatypes:
                D = os.path.join(self.pd.procD, datatype)
                cmd = 'adcptree.py %s -d uhdas' % (D,)
                cmd = cmd + ' --configpath %s' % (self.pd.saveconfigD,)
                cmd = cmd + ' --cruisename %s' % (cruiseid,)
                print(cmd)
                p = Popen(cmd, shell=True, bufsize=-1, stdout=PIPE,
                               stderr=STDOUT, close_fds=True)
                print(p.communicate()[0])
            self.clean_logdir()

        self.set_log_handler()
        self.save_hg_info() # was self.save_hg_tips()
        if new_cruise:
            L.info('StartCruise, new, cruiseid is %s', self.cruiseid)
        else:
            L.info('StartCruise, old, cruiseid is %s', self.cruiseid)

        if os.path.lexists(self.pd.homecruiseD):
            os.remove(self.pd.homecruiseD)
        os.symlink(self.pd.baseD, self.pd.homecruiseD)

        if os.path.lexists(self.pd.datacruiseD):  # /home/data/current_cruise
            os.remove(self.pd.datacruiseD)
        os.symlink(self.cruiseid, self.pd.datacruiseD)

        self.run_function('make_loggers')
        if os.path.exists(self.pd.start_cruiseF):
            if auto:
                auto_opt = 'auto'
            else:
                auto_opt = ''
            os.system('%s %s &' % (self.pd.start_cruiseF, auto_opt))
        print("Start Cruise")

    def EndCruise(self, auto=False):
        if self.run_function('is_logging'):
            if auto:
                self.run_function('stop_logging')
            else:
                tkinter_messagebox.showwarning(title="End Cruise",
                    message="Please stop data logging before ending the cruise.")
                raise ChangedMind
        if not auto and not tkinter_messagebox.askyesno(title = "End Cruise",
                                message = confirm_end % self.SV_cruiseid.get()):
            raise ChangedMind
        ### Debugging version 2004/03/22: for finding interference
        ### between tkMessageBox and tkFileDialog.
        #answer =  tkMessageBox.askyesno(title = "End Cruise",
        #      message = confirm_end % self.SV_cruiseid.get())
        #print "Answer: ", answer
        #if not answer:
        #   raise ChangedMind

        self.run_function('show_log')
        print("Ready to destroy_loggers.")
        self.run_function('destroy_loggers')
        print("After destroy_loggers.")

        # Save the log directory in the data area,
        # so that it will be copied in the final rsync operations
        # at the end of DAS_while_cruise.py.  The config directory
        # is also needed by procsetup to get the yearbase.
        for _dir in [self.pd.savelogD]:
            try:
                os.makedirs(_dir)  ## add mode here and elsewhere
            except:
                pass
        cmd = "cp -au %s/* %s/" % (self.pd.logD, self.pd.savelogD)
        print(cmd)
        os.system(cmd)

        # Remove the symlink as a signal to
        # any processes that may be using it as a flag.
        # (It is better to use an explicit flag file for this.)
        try:
            os.remove(self.pd.homecruiseD)   # symbolic link
        except:
            pass

        # Signal DAS_while_cruise.py to stop, if it is running.
        runflag = os.path.splitext(self.pd.stop_cruiseF)[0] + '.running'
        if os.path.exists(runflag):
            open(self.pd.stop_cruiseF, 'w').close()
        self.SV_cruiseid.set(no_cruise)
        print("End Cruise")
        L.info("EndCruise, cruiseid is %s", self.cruiseid)
        L.removeHandler(self._handler)
        self.run_function('show_control')

    def make_L_cruiseid(self, parent):
        self.SV_cruiseid = StringVar()
        self.SV_cruiseid.set(no_cruise)
        LW = Pmw.LabeledWidget(parent, labelpos = 'w')
        LW.configure(label_text = 'Cruise ID:')

        lab = Label(LW.interior(), textvariable = self.SV_cruiseid)
        lab.pack()
        return LW



if __name__ == "__main__":
    root = Tk()
    CS = CruiseSetup(root)
    CS.pack()
    root.mainloop()
