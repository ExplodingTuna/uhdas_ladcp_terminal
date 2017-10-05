""" Provide a framework for parsing and displaying ADCP
    configurations.  Subclassing is required for specific
    instruments.


   2003/12/14 EF

"""
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

from six.moves.tkinter import *
import Pmw
#import tkFileDialog, tkMessageBox
from six.moves import tkinter_filedialog # Workaround: tkFileDialog seems to clobber tkMessageBox
import re, os.path

from pycurrents.system.logutils import getLogger

log = getLogger(__file__)

import uhdas.uhdas.adcp_cmds as adcp_cmds # only for CmdOnOff special case

pady = 3  # vertical spacing for entries

unrecognized_command = """
Error: unrecognized command in file %s, in line '%s'. \
The file will not be used. """


class gui_setup(Pmw.LabeledWidget):
    def __init__(self, parent,
                      default_file = None,
                      user_commands = None,
                      user_command_list = None,
                      file_template = None
                      ):
        Pmw.LabeledWidget.__init__(self, parent,
                                   labelpos = 'n',
                                   label_text = 'Data Collection Parameters',
                                   hull_relief = 'ridge',
                                   hull_borderwidth = 2,
                                   label_relief = 'groove',
                                   label_borderwidth = 2)
        self.default_file = default_file
        self.user_commands = user_commands
        self.user_command_list = user_command_list
        self.file_template = file_template
        self.all_commands = user_commands
        self.parent = parent
        self.value_changed = 1  # flag: 1 to update command display
        self.BT_CB = None  # placeholder for checkbox
        self.entries = {} # New
        self.SVs = {}     # New
        self.SVs_present = {}
        self.EG = self.make_entry_grid(self.user_command_list)
        self.EG.pack() # Add options.
        self.cmd_dict = self.dict_from_defaults()
        self.SVs_from_dict(self.SVs, self.cmd_dict)
        log.info("Loading SVs from defaults in adcpsetup.gui_setup.__init__.")
        self.default_cmd_dict = self.cmd_dict.copy()
        self.BB = self.add_buttons()
        self.BB.pack(side = LEFT) # Add options
        self.VC_SV = StringVar()
        self.VC = self.add_command_view()
        self.VC.pack(side = RIGHT)
        self.view_commands()
        self.bind('<Leave>', self.view_commands)


    def dict_from_file(self, filename):
        R = re.compile(self.pat)
        cmds = {}
        if not os.path.exists(filename):
            log.error('Error: file %s not found',  filename)
            print("Error: file %s not found" % filename)
            return {}
            # This is a workaround for a bug found on manini,
            # 2008/11/13, with Ubuntu 8.10, in which trying
            # to open a nonexistent file *here* causes a
            # segfault.  It has something to do with exception
            # raising/catching.
        try:
            lines = open(filename).readlines()
        except:
            log.exception("reading %s", filename)
            return {}
        lines = [l.strip() for l in lines if len(l) > 2]
        for line in lines:
            # explicitly throwing away comments; probably unnecessary
            line = line.split('#', 2)[0]
            line = line.split(';', 2)[0]
            line = line.strip()
            if len(line) < 3:
                continue
            try:
                key, val = R.search(line).groups()
                key = key.upper()
                cmd = self.user_commands[key]
                cmds[key] = cmd.to_display(val)
            except (AttributeError, KeyError, ValueError):
                log.error('Error: unrecognized_command %s in file %s', line, filename)
                print('Error: unrecognized_command %s in file %s' % (line, filename))
                return  {}
        if self.validate_dict(cmds):
            return cmds
        else:
            log.error('Error: validation of commands from file %s failed', filename)
            print('Error: validation of commands from file %s failed' % filename)
            return {}

    def dict_from_commands(self, c):
        ''' c is a dictionary like user_commands '''
        cmds = {}
        for key in c:
            cmds[key] = c[key].default
        return cmds

    def dict_from_SVs(self, SVs):
        cmds = {}
        for key in list(SVs.keys()):
            cmds[key] = SVs[key].get()
        return cmds

    def SVs_from_dict(self, SVs, d):
        for key, value in list(d.items()):
            SVs[key].set(value)

    def dict_from_defaults(self):
        cmds = self.dict_from_commands(self.all_commands)
        if self.default_file:
            try:
                cmds.update(self.dict_from_file(self.default_file))
            except IOError:
                msg = 'Default command file %s is missing or inaccessible.\n'
                msg += 'Continuing with programmed defaults.'
                Pmw.MessageDialog(
                           title = "Getting Commands",
                           message_text = msg % self.default_file,
                           buttons = ("OK",),
                           defaultbutton = 0)    #.activate()
                           # activate() segfaults on jaunty
        return cmds

    def list_from_dict(self, d):
        'Return a list of strings in instrument format'
        L = []
        # list in the order they are shown on the screen
        for key in self.user_command_list:
            cmd = self.user_commands[key]
            L.append(key + cmd.from_display(d[key]))
        return L

    def string_from_dict_and_template(self, d, template):
        'Return single string with commands in instrument format'
        d1 = dict()
        for key in self.user_command_list:
            cmd = self.user_commands[key]
            d1[key] = key + cmd.from_display(d[key])
        return template % d1

    def view_commands(self, event = None):  # So it can be bound to an event.
        if self.value_changed:
            self.cmd_dict.update(self.dict_from_SVs(self.SVs))
            L = self.list_from_dict(self.cmd_dict)
            msg = "\n".join(L)
            self.VC_SV.set(msg)
            self.value_changed = 0


    def modified(self, event = None):
        self.value_changed = 1
        self.view_commands()

    def make_onoff_entry(self, parent, irow, cmd):  # propagate back to os
        cmdobj = self.user_commands[cmd]
        L = Label(parent, text = cmdobj.title)
        L.grid(column = 0, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        L = Label(parent, text = "ON or OFF")
        L.grid(column = 1, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        SV = StringVar()
        SV.set(cmdobj.default)  # new with this version?  Right way to init?
        CB = Checkbutton(parent,
              onvalue = 'ON',
              offvalue = 'OFF',
              variable = SV,
              textvariable = SV,
              width = 4,
              background = 'red', #< Color of the whole button,
                                  # and of indicator when not selected
              disabledforeground = 'black', #< text when disabled
              activebackground = 'light blue',   # no effect when disabled
              activeforeground = 'magenta',   # no effect when disabled
              selectcolor = 'green',        #< middle of button when selected
              indicatoron = 0               #< 0: the whole thing is the indicator
              )
        CB.bind('<ButtonRelease>', self.modified)

        CB.grid(column = 2, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        self.SVs[cmd] = SV
        self.SVs_present[cmd] = StringVar()
        L = Label(parent, width = 4,
                    textvariable = self.SVs_present[cmd],
                    bg = 'light green',
                    relief = 'raised')
        L.grid(column = 3, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        # Note: nothing goes in self.entries, and the cmdobj is not saved.
        # Validation is inherent in the widget.

    def make_numeric_entry(self, parent, irow, cmd, width=4):
        cmdobj = self.user_commands[cmd]
        L = Label(parent, text = cmdobj.title)
        L.grid(column = 0, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        L = Label(parent, text =cmdobj.make_explanation())
        L.grid(column = 1, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        SV = StringVar()
        SV.set(cmdobj.default)
        self.SVs[cmd] = SV
        E = Entry(parent,
                  textvariable = SV,
                  width = width,
                  bg = 'white')
        E.grid(column = 2, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        E.bind('<KeyRelease>', self.validate)
        E.bind('<Leave>', self.view_commands)
        E.cmd = cmdobj  # Note potential name confusion
        self.entries[cmd] = E
        SV = StringVar()
        self.SVs_present[cmd] = SV
        L = Label(parent, width = width,
                    textvariable = SV,
                    bg = 'light green',
                    relief = 'raised')
        L.grid(column = 3, row = irow, padx = 10, pady = pady, sticky = 'nsew')

    def make_entry_grid(self, cmdlist):
        parent = Frame(self.interior())
        # Row 0: Titles
        irow = 0
        L = Label(parent, text = 'Command')
        L.grid(column = 0, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        L = Label(parent, text = 'Range')
        L.grid(column = 1, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        L = Label(parent, text = 'New')
        L.grid(column = 2, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        L = Label(parent, text = 'Present')
        L.grid(column = 3, row = irow, padx = 10, pady = pady, sticky = 'nsew')
        for cmd in cmdlist:
            cmdobj = self.user_commands[cmd]
            irow += 1
            if isinstance(cmdobj, adcp_cmds.CmdOnOff):
                self.make_onoff_entry(parent, irow, cmd)
            else:
                self.make_numeric_entry(parent, irow, cmd, width=7)
        return parent # the Frame in which the grid sits

    def add_buttons(self):
        BB = Pmw.ButtonBox(self.interior(),
                           #labelpos = 'n',  # need labelpos to have a border
                           #frame_borderwidth = 2,
                           #frame_relief = 'groove',
                           orient = 'vertical',
                           hull_relief = 'sunken',
                           hull_borderwidth = 2)
        BB.add('Restore Defaults', command = self.restore_defaults)
        BB.add('Load File', command = self.ask_load_file)
        BB.add('Save File', command = self.ask_save_file)
        BB.alignbuttons(when = 'later')
        return BB


    def add_command_view(self):
        VC = Pmw.LabeledWidget(self.interior(),
                               labelpos = 'n',
                               label_text = 'Commands',
                               hull_borderwidth = 2,
                               hull_relief = 'groove')
        L = Label(VC.interior(), textvariable = self.VC_SV,
                               borderwidth = 2,
                               relief = 'sunken',
                               height = 12,
                               width = 20,
                               justify = 'left')
        L.pack()
        return VC


    def validate(self, event):   # bound to events
        E = event.widget
        if E.cmd.validate_display(E.get()):
            E.configure(bg = 'white')
        else:
            E.configure(bg = 'pink')
        self.value_changed = 1

    def validate_all(self):      # check all new entries
        ok = 1
        for E in list(self.entries.values()):
            if E.cmd.validate_display(E.get()):
                E.configure(bg = 'white')
            else:
                E.configure(bg = 'pink')
                ok = 0
        return ok

    def validate_dict(self, d):   # check a new dictionary
        # This seems a bit more convoluted than necessary;
        # do we need to go through self.entries?
        for key, E in list(self.entries.items()):
            if key in d:
                if not E.cmd.validate_display(d[key]):
                    log.error("Error: %s %s is out of range\n", key, d[key])
                    print("Error: %s %s is out of range\n" % (key, d[key]))
                    return 0
        unrecognized = [k for k in d if k not in self.all_commands]
        if len(unrecognized):
            log.error("Error: unrecognized commands %s", unrecognized)
            print("Error: unrecognized commands %s" % unrecognized)
            return 0
        return 1


    def present_from_new(self):  # part of starting logging
        for cmd in self.user_command_list:
            self.SVs_present[cmd].set(self.SVs[cmd].get())

    def ask_load_file(self):
        if self.default_file:
            dir = os.path.dirname(self.default_file)
        else:
            dir = './'

        fd = tkinter_filedialog.LoadFileDialog(self.parent,
                                               title="Load Command File")
        fn = fd.go(dir_or_file=dir, pattern='*.cmd')
        #### tkFileDialog clobbers tkMessageBox.askyesno, so we use
        #### a work-alike, above.
        #fn = tkFileDialog.askopenfilename(initialfile = name,
        #               initialdir = dir,
        #               filetypes = (('Command', '*.cmd'), ('All', '*')),
        #               parent = self.parent,
        #               title = 'Load Command File')
        if fn:
            self.read_cmds(fn)

    def ask_save_file(self):
        if self.default_file:
            dir, name = os.path.split(self.default_file)
        else:
            dir = './'
        name = 'new.cmd'

        fd = tkinter_filedialog.SaveFileDialog(self.parent, title = "Save Command File")
        fn = fd.go(dir_or_file = dir, default = name,
                       pattern = '*.cmd', key='cmdsave')
        #### tkFileDialog clobbers tkMessageBox.askyesno, so we use
        #### a work-alike, above.
        #fn = tkFileDialog.askopenfilename(initialfile = name,
        #               initialdir = dir,
        #               filetypes = (('Command', '*.cmd'), ('All', '*')),
        #               parent = self.parent,
        #               title = 'Load Command File')
        if not fn: return
        s = self.string_from_dict_and_template(self.cmd_dict, self.file_template)
        open(fn, 'w').write(s)


    def read_cmds(self, filename):
        D = self.dict_from_file(filename)   # returns {} on failure
        if D:
            self.cmd_dict.update(D)
            self.SVs_from_dict(self.SVs, self.cmd_dict)
            self.modified()
            log.info("Loaded commands from %s", filename)
        else:
            log.warn("Failed to load commands from %s", filename)

    def write_cmds(self, filename):
        L = self.list_from_dict(self.cmd_dict)
        msg = "\n".join(L) + "\n"
        open(filename, 'w').write(msg)

    def restore_defaults(self):
        self.SVs_from_dict(self.SVs, self.default_cmd_dict)
        self.modified()


    def get_cmdlist(self):
        cmdlist = self.default_config_cmds[:] # slice to return a copy!
        cmdlist += list(self.config_cmds)
        cmdlist += self.list_from_dict(self.cmd_dict)
        cmdlist += self.query_cmds
        return cmdlist
