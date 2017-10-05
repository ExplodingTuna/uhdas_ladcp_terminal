#! /usr/bin/env python
# There is a stub in scripts. This module can lose its executability
# once the transition is made on the ships to using that stub.

"""
GUI for UH ADCP Data Acquisition program

The script can be started with no arguments for normal shipboard
operation, with all control via the gui.

An optional keyword argument can be used to specify the initial
command file to be used.

For unattended startup it can be started with a keyword argument giving
the cruisename, in which case it will start that cruise and begin
logging with no operator action.

This script can be run from an external script, with commands piped
to stdin; this is intended for VOS applications, in which the gui
will still be generated but the external script will use position
and other information to change the configuration, start and stop,
etc.

Alternatively, this script might be modified to launch the control
process, still communicating via a pipe.

Although presently the pipe is sys.__stdin__, this may be changed
to something like a named pipe.

It would be desirable to enable this control without requiring a
separate serial port for navigation information coming to the
controller.  This could be done by switching back and forth between
having the controller reading the port when the system is not
logging, and having it read the rbin file when the system is
logging.

"""

from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import object

from six.moves.tkinter import *
from six.moves import tkinter_messagebox
from six.moves import queue  # Queue in py2, queue in py3
import Pmw
import sys, traceback
import os
import subprocess
import time

import zmq

import logging, logging.handlers
from pycurrents.system import logutils
L = logging.getLogger()
L.setLevel(logging.DEBUG)

formatter = logutils.formatterTLN

logbasename = '/home/adcp/log/DAS_main'

handler = logging.handlers.RotatingFileHandler(logbasename+'.log', 'a',
                                                                100000, 9)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
L.addHandler(handler)

#handler = logging.handlers.TimedRotatingFileHandler(logbasename+'.warn',
#            'midnight', 1, 20)
#handler.setLevel(logging.WARNING)
#handler.setFormatter(formatter)
#L.addHandler(handler)


L.info('Starting DAS.py')


from pycurrents.system import pmwtail
from pycurrents.system.startstop import StartStopControl, ChangedMind
from pycurrents.system.tee import tee

from uhdas.serial.logsubs import Loggers, LoggersStatusFrame
from uhdas.uhdas.cruisesetup import CruiseSetup
from uhdas.uhdas.procsetup import procsetup
from uhdas.uhdas.plotview import ImageMonitor


class NBAppShell(Pmw.MegaWidget):
    '''
    Base class for a NoteBook-based GUI.

    This class is based on AppShell.py from
    Grayson's Tkinter programming book.  (Fill in full
    name and title.)

    Note: we are not using everything that this provides.

    '''
    appversion     =  '0.3'
    appname        =  'UHDAS'
    copyright      =  'Copyright 2002-2011, University of Hawaii.'
    contactname    =  'Eric Firing'
    contactemail   =  'efiring@hawaii.edu'

    def __init__(self, **kw):
        optiondefs = (
           ('padx',          1,          Pmw.INITOPT),
           ('pady',          1,          Pmw.INITOPT),
           #('frameWidth',    1,          Pmw.INITOPT),
           #('frameHeight',   1,          Pmw.INITOPT),
           ('errorfile',     'errors.txt',          Pmw.INITOPT))
        self.defineoptions(kw, optiondefs)
        self.errors_to_file(self['errorfile'])
        print(os.popen('uname -nrvm').read())
        self.root = Tk()
        self.initializeTk(self.root)
        Pmw.initialise(self.root)
        self.root.title(self.appname)

        # Make the window big enough so that normally it does not have
        # to be resized, but make sure it fits in whatever screen it
        # is displayed on.
        swidth = self.root.winfo_screenwidth()
        sheight = self.root.winfo_screenheight()
        sw = min(swidth-20, 950)
        sh = min(sheight-20, 700)

        self.root.geometry('%dx%d+10+10' % (sw, sh))
        Pmw.MegaWidget.__init__(self, parent = self.root)

        self.appInit()

        self.__createInterface()

        self._hull.pack(side=TOP, fill=BOTH, expand=YES)

        self.initialiseoptions(NBAppShell)  # Note spelling: s, not z

    def errors_to_file(self, filename):
        self.logfilename = filename
        self.errorfilename = filename + '.err'
        self.errorlog = open(filename, 'w', 1) # 1 for line buffering
        self.errortee = tee(self.errorlog,
                            case_sensitive=False,
                            time_tag = 1)
        self.errortee.add(open(self.errorfilename, 'w', 1),
                          include='Error',
                          exclude='ChangedMind')
        sys.stdout = self.errortee
        sys.stderr = self.errortee
        Pmw.reporterrorstofile(self.errortee)

    def no_tk_errors(self):
        if self.errortee.n > 1:
            self.errortee.remove(1)


    def appInit(self):
        pass


    def initializeTk(self, root):
        root.option_add('*background', 'grey90')
        root.option_add('*foreground', 'black')
        root.option_add('*EntryField.Entry.background', 'white')
        root.option_add('*Entry.background', 'white')
        root.option_add('*MessageBar.Entry.background', 'gray85')
        root.option_add('*Listbox*background', 'white')
        root.option_add('*Listbox*selectBackground', 'dark slate blue')
        root.option_add('*Listbox*selectForeground', 'white')
        root.option_add('*activeBackground', 'yellow')
        root.option_add('*Button.highlightColor', '#FFFF99')
        root.option_add('*Button.highlightThickness', 3)

    def __createAboutBox(self):
        Pmw.aboutversion(self.appversion)
        Pmw.aboutcopyright(self.copyright)
        Pmw.aboutcontact('%s, %s' % (self.contactname, self.contactemail))
        self.about = Pmw.AboutDialog(self._hull,
                                     applicationname = self.appname)
        self.about.withdraw()
        return None

    def showAbout(self):
        self.about.show()
        self.about.focus_set()
    ''' comment
    def __createMenuBar(self):
       # The advantage of the regular menubar is that the
       # help menu can be placed on the right, so that
       # additional menus can be added by later functions.
       self.menuBar = self.createcomponent('menubar', (), None,
                                           Pmw.MenuBar,
                                           (self._hull,)) #,
                                           #hull_relief=RAISED,
                                           #hull_borderwidth=1)
       self.menuBar.pack(fill=X)
       self.menuBar.addmenu('Help', 'About %s' % self.appname, side = 'right')
       self.menuBar.addmenu('File', 'File commands and Quit')

    def createMenuBar(self):
       self.menuBar.addmenuitem('Help', 'command',
                                None,
                                label='About...', command=self.showAbout)

       self.menuBar.addmenuitem('File', 'command', 'Quit this application',
                               label='Quit',
                               command=self.quit)
    ''' # end commment

    def __createNoteBook(self):
        # Create data area where data entry widgets are placed.
        self.noteBook = self.createcomponent('notebook',
                                             (), None,
                                             Pmw.NoteBook, (self._hull,))
        self.noteBook.pack(side=BOTTOM, fill=BOTH, expand=YES,
                           padx=self['padx'], pady=self['pady'])

    def __createStatusArea(self):
        frame = self.createcomponent('statusarea', (), None,
                                      Frame, (self._hull,),
                                      relief = SUNKEN)
        frame.pack(side=TOP, expand=NO, fill=X)
        self.statusArea = frame

    def __createInterface(self):
        #self.__createMenuBar()
        self.__createNoteBook()
        self.__createStatusArea()
        self.__createAboutBox()

        #
        # Create the parts of the interface
        # which can be modified by subclasses
        #
        #self.createMenuBar()
        self.createInterface()

    def createInterface(self):
        pass


### Machinery for optional use of a notebook
class NoteBookFaker(object):
    """
    Mixin for adding the notebook methods we need.
    """
    def add(self, title):
        page = Frame(self.interior())
        page.pack(side=LEFT, anchor=N, fill=BOTH, expand=YES)
        return page

    def selectpage(self, title):
        pass

class FakeNoteBookScrolled(Pmw.ScrolledFrame, NoteBookFaker):
    pass

class FakeNoteBookNonScrolled(Pmw.MegaWidget, NoteBookFaker):
    pass



def _importer(name):
    """
    Import and return module specified in variable *name*.
    """
    mod = __import__(name)
    # This returns only the base, e.g. pycurrents if name is pycurrents.system
    components = name.split('.')
    # Walk out to the end of the chain to get the part we want.
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod

app_quit_query = '''A cruise has been started but not \
stopped.  Do you want to quit the DAS right now anyway?
'''

ADCP_failure_msg = """
ADCP %s startup failed.\
Continue logging other data streams?
"""

class DasAppShell(NBAppShell):

    n_min_tab = 3                 ### This is probably a temporary location.

    def appInit(self):
        self.cmd_queue = queue.Queue()
        self.in_cmd = None  # will have the command line being run from queue
        self.cycler_id = None


    def maybe_notebook(self, master, scrolled=False,
                                notebook_kw=None, scrolled_kw=None):
        """
        Factory function to return a notebook or a Frame with
        a couple of notebook methods, depending
        on the number of ADCPs being managed.
        """
        if len(self.cruise.ADCPs) >= self.n_min_tab:
            if notebook_kw is None:
                notebook_kw = {}
            return Pmw.NoteBook(master, **notebook_kw)
        if scrolled:
            if scrolled_kw is None:
                scrolled_kw = {}
            return FakeNoteBookScrolled(master, **scrolled_kw)
        return FakeNoteBookNonScrolled(master)

    def createPages(self):
        self.noteBook.add('Control')
        self.noteBook.add('Terminal')
        self.noteBook.add('Monitor')
        self.noteBook.add('5-minPlot')
        self.noteBook.add('ContourPlot')
        self.noteBook.add('VectorPlot')
        self.noteBook.add('BridgePlot')
        self.noteBook.add('HeadingPlot')
        #self.noteBook.add('Info')
        self.noteBook.add('Log')
        self.noteBook.add('Errors')
        self.noteBook.selectpage('Control')

    def createStatus(self):
        pass


    def StartLogging(self, resume = 0, auto=False):
        print("enter StartLogging, resume = ", resume)
        L.info("entering StartLogging, resume = %s, auto = %s", resume, auto)
        if not resume:
            for s in self.setups:
                #ensure setup changes are propagated, even if the
                # mouse was outside the setup window when the change
                # was made
                s.view_commands()

            self.noteBook.selectpage('Terminal')
            self.noteBook.update()
            # Start up the ADCPs
            for i, term in enumerate(self.terms):
                term.select()
                inst = self.cruise.ADCPs[i]['instrument']
                cmdlist = self.setups[i].get_cmdlist()
                cmds = [c for c in cmdlist if not c.endswith('?')]
                L.info("Commands for %s:\n    %s", inst, "\n    ".join(cmds))
                try:
                    enabled = self.setups[i].check_for_pingtypes(cmdlist)
                    self.logs.setEnabled(term.instrument, enabled)
                    if enabled:
                        term.disable_menubar()
                        term.start_binary(cmdlist)

                except:
                    print("term %d ADCP %s startup failure" % (i, inst))
                    traceback.print_exc(file = sys.stdout)
                    if auto:
                        q = True
                    else:
                        q = tkinter_messagebox.askyesno(title="ADCP startup failure",
                                              message=ADCP_failure_msg % inst)
                    term.stop_listening()
                    term.enable_menubar()
                    if not q:
                        # Stop any instruments that have already
                        # been started before the failure.
                        for t in self.terms[:i]:
                            t.select()
                            t.wakeup()
                            t.enable_menubar()

                        raise ChangedMind  # 2004/11/18
                        #return   # Exit the StartLogging procedure.
                        # We hope this will leave us in a useful
                        # situation for debugging.

            # Start the loggers now.
            # We can't start them earlier because they would tie up
            # the serial ports to the ADCP. We could use separate
            # Loggers objects for each ADCP and for all the ancillary
            # instruments, or we could modify the Loggers object so
            # it could handle independent starts and stops; but both
            # of these changes would increase complexity considerably.
            # It would also be good to block the startup of ser_bin
            # when an ADCP is not started.  As it is, ser_bin starts
            # and sends one "good" message to the logger, which doesn't
            # turn back to red until the timeout occurs.

            self.logs.start_logging(time.time())

        # From here down to a few lines from the bottom,
        # everything is done regardless of "resume".
        self.LSF.check()
        self.noteBook.selectpage('Monitor')
        if self.logs.is_logging:
            self.cruise.C_ss.disable()
        for i, setup in enumerate(self.setups):
            setup.present_from_new()  # update the RH column: present params
            setup.write_cmds(self.cruise.pds[i].logparamF)
            print("Updated SVs_present from SVs and wrote cmds", i)
        self.active_procdirnames = procsetup(logging=True).active_procdirnames
        self.createPlotPage('5-minPlot', 'lastens.png')
        self.createPlotPage('ContourPlot', 'ddaycont.png')
        self.createPlotPage('VectorPlot', 'shallow.png')
        self.createMonPlotPage('BridgePlot', 'ktvec_day.png')
        self.createMonPlotPage('HeadingPlot', 'heading.png')


        if not resume:
            open(self.cruise.pd.is_loggingF,'w').close()   # touch the flag file
            if os.path.exists(self.cruise.pd.start_loggingF):
                print("Running %s" % self.cruise.pd.start_loggingF)
                arg = ""
                if auto:
                    arg = "replace"
                os.system('%s %s &' % (self.cruise.pd.start_loggingF, arg))
        print("Exiting StartLogging")
        L.info("Logging started")

    def StopLogging(self, auto=False):
        print("Entering StopLogging")
        L.info("entering StopLogging, auto = %s", auto)
        aborted = self.logs.check_stop_logging(auto=auto)
        if not auto and aborted:
            print("Changed Mind")
            raise ChangedMind
        self.LSF.check()
        self.noteBook.selectpage('Terminal')
        self.noteBook.update()
        for i, term in enumerate(self.terms):
            term.select()
            if self.logs.getEnabled(term.instrument):
                # Ignore exceptions; we don't want lack of communication
                # with the ADCP to block the shutdown process.
                try:
                    term.wakeup()
                except:
                    inst = self.cruise.ADCPs[i]['instrument']
                    print("Wakeup of %s timed out." % inst)
                    L.exception("Wakeup of %s failed.", inst)
            term.enable_menubar()
        self.noteBook.selectpage('Log')
        self.cruise.C_ss.enable()
        try:
            os.remove(self.cruise.pd.is_loggingF)   # remove the flag file
            print("Removed %s" % self.cruise.pd.is_loggingF)
        except:
            print("Failed to remove %s" % self.cruise.pd.is_loggingF)
            L.exception("Failed to remove %s", self.cruise.pd.is_loggingF)
        # Signal DAS_while_logging to quit:
        open(self.cruise.pd.stop_loggingF, 'w').close()
        self.noteBook.selectpage('Control')
        print("Exiting StopLogging")
        L.info("Logging stopped")

    def buildLoggers(self):
        print("Entering buildLoggers")
        if hasattr(self, 'logs'):
            return
        # This function must not be called unless self.cruise
        # has info from a valid _cfg.m
        page = self.noteBook.page('Monitor')
        yearbase = self.cruise.yearbase
        logs = Loggers(yearbase = yearbase, master = page,
                 bindir = '/usr/local/bin') # Create the Loggers object.
        self.logs = logs
        logs.pack()      # here, so a single call to this function does it all

        datadir = self.cruise.pd.rawD

        timeout = 10
        logs.add_list(self.cruise.sensors, self.cruise.common_opts,
                                      datadir, timeout)

        if os.path.exists(self.cruise.pd.is_loggingF):
            for i, setup in enumerate(self.setups):
                setup.read_cmds(self.cruise.pds[i].logparamF)
                # The following may be redundant; it is also called
                # in StartLogging, right before the cmdfile is written.
                setup.present_from_new()  # update the RH column: present params
                print("Read cmds and updated SVs_present from SVs", i)
            for i, term in enumerate(self.terms):
                # No need to use term.select() here.
                cmdlist = self.setups[i].get_cmdlist()
                enabled = self.setups[i].check_for_pingtypes(cmdlist)
                self.logs.setEnabled(term.instrument, enabled)
                if enabled:
                    term.disable_menubar()
            resumed = logs.resume()
            print("resumed is ", resumed)
            if not resumed:
                try:
                    os.remove(self.cruise.pd.is_loggingF)   # remove the flag file
                    print("Removed %s" % self.cruise.pd.is_loggingF)
                except:
                    print("Failed to remove %s" % self.cruise.pd.is_loggingF)
                for term in self.terms:
                    term.enable_menubar()

        if logs.is_logging:
            self.cruise.C_ss.disable()
            self.C_ss.set_started()
        self.C_ss.enable()
        print(">>>> C_ss enabled <<<<<")
        self.LSF = LoggersStatusFrame(master = self.statusArea, logs = logs)
        self.LSF.pack(side = RIGHT, expand = NO, fill = NONE)

        if logs.is_logging:
            self.StartLogging(resume = 1) # to start other processes
        print("Leaving buildLoggers")

    def destroyLoggers(self):
        if not hasattr(self, 'logs'):
            return
        self.LSF.destroy()   # before closing the monitor
        delattr(self, 'LSF')
        self.logs.close_monitor()
        self.C_ss.disable()
        delattr(self, 'logs')

    def is_logging(self):
        if hasattr(self, 'logs'):
            return self.logs.is_logging
        else:
            return False

    def close_all(self):
        still_logging = False
        if self.is_logging():
            try:
                self.StopLogging()
            except ChangedMind:
                still_logging = True
        if not still_logging and self.cruise.C_ss.is_running():
            try:
                self.cruise.EndCruise()
            except ChangedMind:
                # If the cruise is "alive" but logging is stopped,
                # let's stop DAS_while_cruise.py;
                # it can be left running if logging is still
                # running.
                print("Stopping DAS_while_cruise.py")
                open(self.cruise.pd.stop_cruiseF, 'w').close()
        try:
            self.destroyLoggers()
        except:
            pass
        if hasattr(self, 'terms'):
            for term in self.terms:
                term.close_terminal()
        self.no_tk_errors()

    def destroy(self):  # override built-in Pmw function
        '''This function is attached to WM_DELETE_WINDOW.
        '''
        if self.cruise.C_ss.is_running():
            self.noteBook.selectpage('Control')
            q = tkinter_messagebox.askyesno(message = app_quit_query)
            if not q:
                return
            L.info('Cruise is still active')
        self.close_all()
        L.info('Closing DAS GUI')
        Pmw.MegaWidget.destroy(self)
        self.root.quit()

    def shutdown(self):
        """
        Shutdown DAS via remote command.
        """
        L.info("Starting shutdown")
        if self.C_ss.is_running():
            self.C_ss.C_stop(auto=True)
            L.info("shutdown: stopped logging")
        if self.cruise.C_ss.is_running():
            self.cruise.C_ss.C_stop(auto=True)
            L.info("shutdown: ended cruise")
        try:
            self.destroyLoggers()
            L.info("shutdown: loggers destroyed")
        except:
            L.exception("in shutdown")
        if hasattr(self, 'terms'):
            for term in self.terms:
                term.close_terminal()
                L.info("shutdown: closing term %s", term.instrument)
        self.no_tk_errors()
        L.info('Closing DAS GUI by remote command')
        Pmw.MegaWidget.destroy(self)
        self.root.quit()

    def cmd_stop_logging(self):
        """
        Enter a non-pinging state; requires action only if originally pinging.
        """
        L.info("cmd_stop_logging")
        if self.C_ss.is_running():
            self.C_ss.C_stop(auto=True)
            L.info("stopped logging")
        else:
            L.info("No action; not logging.")

    def cmd_stop_cruise(self):
        """
        Enter a waiting state: no logging, no cruise.
        """
        L.info("cmd_stop_cruise")
        if self.C_ss.is_running():
            self.C_ss.C_stop(auto=True)
            L.info("stopped logging")
        if self.cruise.C_ss.is_running():
            self.cruise.C_ss.C_stop(auto=True)
            L.info("ended cruise")
        else:
            L.info("No action; no cruise was set.")

    def cmd_start_cruise(self, cruisename):
        L.info("cmd_start_cruise, cruisename = %s", cruisename)
        if self.C_ss.is_running():
            self.C_ss.C_stop(auto=True)
            L.info("Stopped logging")

        if self.cruise.C_ss.is_running():
            if self.cruise.cruiseid == cruisename:
                L.info("Cruise is already set")
                return

            self.cruise.C_ss.C_stop(auto=True)
            L.info("Ended cruise")

        self.cruise.C_ss.C_start(cruisename=cruisename)
        L.info("Started cruise %s", cruisename)

    def cmd_start_logging(self):
        L.info("cmd_start_logging")
        if not self.cruise.C_ss.is_running():
            L.error("Cannot start logging; no cruise is started")
            return
        if self.C_ss.is_running():
            self.C_ss.C_stop(auto=True)
            L.info("Stopped logging")
        self.C_ss.C_start(auto=True)
        L.info("Started logging")

    def createMain(self):
        # fdict is used to pass functions from this module
        # to the CruiseSetup module.
        fdict = { 'make_loggers' : (self.buildLoggers, (), {}),
                  'destroy_loggers' : (self.destroyLoggers, (), {}),
                  'is_logging' : (self.is_logging, (), {}),
                  'stop_logging' : [None, (), {'auto':True}],  # modify below
                  'show_log' : (self.noteBook.selectpage, ('Log',), {}),
                  'show_control' : (self.noteBook.selectpage, ('Control',), {})}

        page = self.noteBook.page('Control')
        F_outer = Frame(page)
        F_controls = Frame(F_outer,
                            relief = 'ridge', borderwidth = 4)
        self.cruise = CruiseSetup(F_controls, functions = fdict)
        LW = Pmw.LabeledWidget(self.statusArea, labelpos = 'w')
        LW.configure(label_text = 'Cruise ID:')

        L = Label(LW.interior(), textvariable = self.cruise.SV_cruiseid)
        L.pack()
        LW.pack(side = LEFT, expand = NO, fill = NONE)

        F_params = self.maybe_notebook(F_outer, scrolled=True)

        self.setups = []
        i = 0
        for ADCP in self.cruise.ADCPs:
            smod = 'uhdas.uhdas.' + ADCP['setup']

            instpage = F_params.add(ADCP['instrument'])
            if isinstance(F_params, Pmw.ScrolledFrame):
                instframe = Pmw.MegaWidget(instpage)
            else:
                instframe = Pmw.ScrolledFrame(instpage)
            instframe.pack(fill=BOTH, side=LEFT, anchor=N, expand=True)

            setup = _importer(smod).gui_setup(instframe.interior(),
                           default_file = self.cruise.pds[i].cmdF,
                           instrument = ADCP['instrument'],
                           config_cmds = ADCP['commands'])
            self.setups.append(setup)
            i += 1
        self.C_ss = StartStopControl(F_controls,
                                      funcs = (self.StartLogging,
                                               self.StopLogging),
                                      names = ('Start Recording',
                                               'Stop Recording'),
                                      orient = 'vertical',
                                      labelpos = 'n',
                                      hull_relief = 'ridge',
                                      hull_borderwidth = 2,
                                      label_relief = 'groove',
                                      label_borderwidth = 2)
        self.C_ss.configure(label_text = 'Data Recording')
        fdict['stop_logging'][0] = self.C_ss.C_stop

        F_outer.pack(side = TOP, anchor = N, fill = BOTH, expand = YES)
        F_controls.pack(side = LEFT, anchor = N,# fill = Y, expand = NO,
                                      padx = 5)
        F_params.pack(side=LEFT, anchor=N, fill=BOTH, expand=YES)
        for setup in self.setups:
            setup.pack(side = LEFT, anchor = N, padx = 5)
        self.cruise.pack(side = TOP, anchor = N, fill = X, expand = YES, pady = 5)
        self.C_ss.pack(side = TOP, anchor = N, fill = X, expand = YES, pady = 5)



        page = self.noteBook.page('Terminal')
        F_terms = self.maybe_notebook(page, scrolled=False)
                    #scrolled=True,
                    #scrolled_kw=dict(vscrollmode='none'))
        F_terms.pack(side=LEFT, anchor=N, expand=True, fill=BOTH)
        (path, name) = os.path.split(self['errorfile'])
        self.terms = []
        # ADCPs must be at the top of the sensor list.
        for i, ADCP in enumerate(self.cruise.ADCPs):
            inst = ADCP['instrument']
            device = self.cruise.sensors[i]['device']
            tmod = 'uhdas.serial.' + ADCP['terminal']
            termpage = F_terms.add(inst)
            term = _importer(tmod).terminal(
                              device = '/dev/' + device, master = termpage,
                              standalone = 0,
                              baud = ADCP['wakeup_baud'],
                              cmd_filename = self.cruise.pds[i].cmdF,
                              instrument=inst,
                              baud2=self.cruise.sensors[i]['baud'])

            # Patch in a method to show the notebook page:
            def _display_page(inst=inst):
                F_terms.selectpage(inst)
            term.select = _display_page

            termlog = os.path.join(path, 'term' + inst + name)
            term.begin_save(filename = termlog)
            term.display.Text.configure(width = 65, height = 30)
            term.Frame.pack_forget()
            term.Frame.pack(side = LEFT, expand = YES, fill = BOTH)
            self.terms.append(term)
        self.cruise.init() # must be after making C_ss and term
        if not self.cruise.C_ss.is_running():
            self.C_ss.disable()

        page = self.noteBook.page('Log')
        Tail = pmwtail.tail(page, self.logfilename)
        Tail.pack()
        page = self.noteBook.page('Errors')
        Tail = pmwtail.tail(page, self.errorfilename)
        Tail.pack()

    def createPlotPage(self, name, file_suffix):
        page = self.noteBook.page(name)
        for w in list(page.children.values()):
            w.destroy()
        NB = Pmw.NoteBook(page)
        NB.pack(fill = BOTH, expand = YES)
        for datatype in self.active_procdirnames:
            subpage = NB.add(datatype)
            filename = '/home/adcp/www/figures/%s_%s' % (datatype, file_suffix)
            IM = ImageMonitor(subpage, file = filename)
            IM.pack()

    def createMonPlotPage(self, name, fname):
        page = self.noteBook.page(name)
        filename = '/home/adcp/www/figures/%s' % (fname,)
        IM = ImageMonitor(page, file = filename)
        IM.pack()


    def createHdgPlotPage(self, name):
        page = self.noteBook.page(name)
        filename = '/home/adcp/www/figures/heading.png'
        IM = ImageMonitor(page, file = filename)
        IM.pack()


    def createInterface(self):
        NBAppShell.createInterface(self)
        self.createPages()
        self.createMain()
        self.createStatus()   # must follow createMain
        self.noteBook.setnaturalsize(pageNames = ['Control','Terminal'])
        self.root.protocol("WM_DELETE_WINDOW", self.destroy)

    def load_cmdfiles(self, cmdfile):
        """
        *cmdfile* is from a command-line option of the form

            'os75:os75_shallow.cmd,wh300:wh300_shallow.cmd'

        This is to facilitate autonomous operation.
        """
        records = cmdfile.split(',')
        setupd = dict([(s.instrument, s) for s in self.setups])
        for rec in records:
            inst, fname = rec.split(':')
            fpath = os.path.join(self.cruise.pd.cmdD, fname)
            L.info("Commands for %s to be loaded from %s", inst, fpath)
            setupd[inst].read_cmds(fpath) # logs success or failure


    def command_reader(self, fp, mask):
        """
        Read commands from file object *fp*.
        This will typically be piped via stdin.
        Commands are put on a queue, not executed immediately.
        This is intended as a callback for the tk filehandler.
        """
        try:
            line = fp.readline().strip()
            self.cmd_queue.put(line)
            L.info("command_reader: Read command line: %s", line)
        except:
            L.exception("command_reader: failed")

    def command_runner(self):
        """
        Execute commands read from cmd_queue.
        """
        try:
            line = self.cmd_queue.get(False)  # don't block
        except queue.Empty:
            return

        if self.in_cmd is not None:
            self.cmd_queue.put(line)  # to be tried again later
            L.debug("waiting for completion of %s", self.in_cmd)
            return

        self.command_runner_core(line)

    def command_runner_core(self, line):

        try:
            self.in_cmd = line
            if "stop_cruise" in line or "end_cruise" in line:
                self.cmd_stop_cruise()
                L.info("Cruise ended by command_runner")
            elif "stop_logging" in line:
                self.cmd_stop_logging()
                L.info("Logging ended by command_runner")
            elif "start_cruise" in line:
                try:
                    cruisename = line.split()[1]
                except:
                    L.exception("Failed to find cruisename in line <%s>", line)
                    return
                self.cmd_start_cruise(cruisename=cruisename)
                L.info("Cruise %s started by command_runner", cruisename)
            elif "start_logging" in line:
                self.cmd_start_logging()
                L.info("Logging started by command_runner")
            elif "cmdfile" in line:
                try:
                    inst_filename = line.split()[1]
                except:
                    L.exception("Failed to find cmdfile(s) in line <%s>", line)
                    return
                self.load_cmdfiles(inst_filename)
                L.info("cmdfile loaded by command_runner")
            elif "quit" in line:
                self.command_cycler(quit=True)
                self.shutdown()
            else:
                L.warn("Unexpected input to command_runner: <%s>", line)
                #print("Unexpected input to command_runner: <%s>", line,
                #      file=sys.__stdout__)
        except:
            L.exception("command_runner failed")
        else:
            L.info("command_runner: completed")
        finally:
            self.in_cmd = None

    def command_cycler(self, quit=False):
        """
        Check for commands from zmq, if used; and process a command
        from the queue, if present.
        """
        if quit:
            self.root.after_cancel(self.cycler_id)
            return
        if self.zmq_sock:
            self.check_zmq()
        else:
            self.command_runner()
        self.cycler_id = self.root.after(1000, self.command_cycler)

    def check_zmq(self):
        try:
            line = self.zmq_sock.recv_string(zmq.NOBLOCK)
        except zmq.ZMQError:
            return

        L.info("read line from zmq: %s", line)
        count = 100
        while self.in_cmd is not None and count > 0:
            if count == 100:
                L.Warn("in check_zmq, waiting for %s", self.in_cmd)
            self.root.after(100)  # 0.1 s
            self.root.update_idletasks()
            count -= 1
        if count == 0:
            L.Error("timeout in check_zmq, waiting for %s", self.in_cmd)
            self.zmq_sock.send_string('ERROR')
        self.command_runner_core(line)
        self.zmq_sock.send_string('OK')

    def list_commands(self):
        commands = [
                    "start_cruise <cruisename>",
                    "end_cruise",
                    "start_logging",
                    "stop_logging",
                    "cmdfile <inst:cmd_fname.cmd>",
                    "quit"]
        return commands

    def connect_stdin(self):
        """
        Make a tk filehandler for reading commands from stdin.
        """
        self.root.tk.createfilehandler(sys.__stdin__,
                                            READABLE,
                                            self.command_reader)
        self.command_cycler()  # checks the queue every second

    def check_timeout(self):
        """
        At 5-sec intervals, check to see whether the system is logging
        but the time since the last good input from an enabled ADCP
        exceeds the specified timeout.  If so, stop and restart
        logging, under the assumption that perhaps a power glitch
        to the ADCP stopped its data transmissions.
        """
        if self.is_logging() and self.timeout_id is not None:
            now = time.time()
            for term in self.terms:
                inst = term.instrument
                if not self.logs.getEnabled(inst):
                    continue
                dt = now - self.logs.LogWinDict[inst].stats.LastGoodTime
                if dt > self.timeout:
                    self.restart_logging(dt)
        if self.timeout_id is None:
            check_interval = (5 + self.timeout) * 1000
        else:
            check_interval = 5000
        self.timeout_id = self.root.after(int(check_interval),
                                          self.check_timeout)

    def restart_logging(self, dt):
        self.C_ss.C_stop(auto=True)
        L.info("Logging ended after timeout, dt = %s", dt)
        self.C_ss.C_start(auto=True)
        L.info("Logging restarted after timeout")


    def run(self, cruisename=None,
                  cmdfile=None,
                  read_stdin=False,
                  zmq_addr=None,
                  timeout=None,
                  quit=False,
                  endcruise=False,
                  **kw):
        self.pack()

        if quit:
            self.shutdown()
            L.info("Quit via command-line option.")
            return

        if cruisename is not None or cmdfile is not None:
            self.update()
            if self.C_ss.is_running():
                self.C_ss.C_stop(auto=True)
            if cruisename is not None:
                self.update()
                if self.cruise.C_ss.is_running():
                    self.cruise.C_ss.C_stop(auto=True)
                self.update()
                self.cruise.C_ss.C_start(cruisename=cruisename)
            if cmdfile is not None:
                try:
                    self.load_cmdfiles(cmdfile)
                except:
                    L.exception("processing %s failed", cmdfile)
                    print("processing %s failed; using defaults" % cmdfile,
                          file=sys.__stdout__)
                    # Note: load_cmdfiles normally logs its errors
                    # and moves on, so the "print" above is not
                    # effective.  Fixing this would require changes
                    # in about the next 2 levels up the stack.
            if not self.cruise.C_ss.is_running():
                L.error("No active cruise, so cannot start logging")
                print("No active cruise, so cannot start logging",
                      file=sys.__stdout__)
                return
            self.C_ss.C_start(auto=True)

        if endcruise:
            self.update()
            self.cmd_stop_cruise()
            self.update()

        if timeout is not None:
            self.timeout = timeout
            self.timeout_id = None
            self.check_timeout() # starts timer cycle

        if read_stdin:
            self.root.after_idle(self.connect_stdin)
            print("Reading commands from stdin", file=sys.__stdout__)
            print("Available commands are:\n",
                  "\n".join(self.list_commands()),
                  "\n",
                  file=sys.__stdout__)

        if zmq_addr:
            print("zmq address is: %s" % zmq_addr)
            zmq_context = zmq.Context()
            self.zmq_sock = zmq_context.socket(zmq.REP)
            self.zmq_sock.bind(zmq_addr)
            self.root.after_idle(self.command_cycler)
        else:
            self.zmq_sock = None
            zmq_context = None

        print("About to run mainloop")
        self.mainloop()
        print("mainloop ended")

        # The destruction should be automatic, but let's make
        # it explicit.
        if zmq_context is not None:
            zmq_context.destroy(0)

        if read_stdin:
            self.root.tk.deletefilehandler(sys.__stdin__)
        # Not sure whether the following helps, but I don't think
        # it can do any harm.  It's probably not necessary at all.
        try:
            self.root.after_cancel(self.timeout_id)
        except:
            pass



from pycurrents.system.pmw_process import SingleFunction

class DAS(SingleFunction):
    def run(self, **kw):
        t = self.start_time
        ts = "log%4d_%03d_%05d.txt" % (t[0], t[7]-1,
                                t[5] + 60 * (t[4] + 60 * t[3]))
        das = DasAppShell(errorfile = os.path.join('/home/adcp/log', ts))
        das.run(**kw)



def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("", "--endcruise",
                      dest="endcruise",
                      action="store_true",
                      help="Don't resume; end any existing cruise")

    parser.add_option("-c",  "--cruisename",
                      dest="cruisename",
                      default="",
                      help="Start pinging with this cruise name.\n")
    parser.add_option("",  "--cmdfile",
                      dest="cmdfile",
                      default="",
                      help="e.g. 'os75:os75_shallow.cmd,wh300:wh300_shallow.cmd'")
    parser.add_option("", "--read_stdin",
                        action="store_true",
                        dest="read_stdin",
                        help="read commands from stdin")
    parser.add_option("-z", "--zmq_req_rep",
                      dest="zmq_addr",
                      help="Use zmq request-reply address with autopilot",)
    parser.add_option("", "--timeout",
                        dest="timeout",
                        type="float",
                        help="timeout in seconds for restarting logging")
    parser.add_option("", "--quit",
                        dest="quit",
                        action="store_true",
                        help="Quit logging and end cruise")

    (options, args) = parser.parse_args()

    DASkw = dict(flagdir='/home/adcp/flags')  # for DAS initialization
    runkw = dict()                            # for DAS.run()
    if options.cruisename:
        DASkw['action'] = 'replace'
        runkw['cruisename'] = options.cruisename
    if options.cmdfile:
        DASkw['action'] = 'replace'
        runkw['cmdfile'] = options.cmdfile
    if options.read_stdin:
        DASkw['action'] = 'replace'
        runkw['read_stdin'] = options.read_stdin
    if options.zmq_addr:
        DASkw['action'] = 'replace'
        runkw['zmq_addr'] = options.zmq_addr
    if options.timeout:
        DASkw['action'] = 'replace'
        runkw['timeout'] = options.timeout
    if options.quit:
        DASkw['action'] = 'replace'
        runkw['quit'] = options.quit
    if options.endcruise:
        DASkw['action'] = 'replace'
        runkw['endcruise'] = True

    DASkw['kwargs'] = runkw

    display = os.environ.get("DISPLAY", None)
    if display is None:
        L.error("Environment DISPLAY variable is not set")
        print("ABORT: Environment DISPLAY variable is not set")
        print("HINT: For remote display, try:")
        print("   export DISPLAY=:0.0")
        sys.exit(-1)
    elif display == "":
        L.error("Environment DISPLAY variable is empty")
        print("ABORT: Environment DISPLAY variable is empty")
        print("HINT: For remote display, try:")
        print("   export DISPLAY=:0.0")
        sys.exit(-1)
    else:
        L.info("DISPLAY is %s", display)

    bad = subprocess.call(['/usr/bin/xinput', '--list'],
                         stdout=open('/dev/null', 'w'))
    if bad:
        L.error("Can't connect to DISPLAY %s", display)
        print("ABORT: Can't connect to DISPLAY %s" % display)
        sys.exit(-1)

    DAS(**DASkw).start()

if __name__ == '__main__':
    main()
