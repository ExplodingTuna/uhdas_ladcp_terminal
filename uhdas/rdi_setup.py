""" Provide a valid set of commands for an RDI OS or WH Mariner
    or ancient NB.


   2003/12/14 EF

   2005/02/17 EF
      added PS0, LD, LC commands

   2005/03/22 EF
      added WH support; merged in NB support

"""
from future import standard_library
standard_library.install_hooks()

from pycurrents.system.logutils import getLogger

log = getLogger(__file__)


import uhdas.uhdas.adcpsetup as adcpsetup
import uhdas.uhdas.adcp_cmds as cmds

class gui_setup(adcpsetup.gui_setup):
    def __init__(self, parent,
                      default_file = None,
                      instrument = None,  # *must* be supplied
                      config_cmds = None):
        self.instrument = instrument
        instclass = instrument[:2]
        user_commands = cmds.user_command_dict[instrument]
        self.fmt = "%s%s"
        if config_cmds is None:
            config_cmds = list()
        self.config_cmds = config_cmds
        self.pat = cmds.pattern_dict[instclass]
        user_command_list = cmds.user_command_list_dict[instclass]
        file_template = cmds.template_dict[instclass]
        self.default_config_cmds = cmds.default_config_cmds_dict[instclass]
        self.query_cmds = cmds.query_cmds_dict[instclass]
        adcpsetup.gui_setup.__init__(self, parent, default_file,
                       user_commands, user_command_list, file_template)
        self.configure(label_text =
                       'RDI %s Data Collection Parameters' % instrument)
        log.info("Finished gui_setup.__init__")

    def check_for_pingtypes(self, cmdlist):
        ''' Return True if cmdlist includes a nonzero ping command.'''
        for cmd in cmdlist:
            #log.info("checking for ping: %s", cmd)
            if (cmd.find('WP1') >= 0
                or cmd.find('NP1') >= 0
                or cmd.find('BP1') >= 0
                or cmd.find('P00001') >= 0):
                return True
        return False
        # For NB instrument, FH command is BT pings per WT ping, so
        # it is not clear that it can do BT pings alone.
        # Also, the documentation does not say P0000 is valid.
        # Therefore the instrument will be bypassed if we don't see
        # P00001.


if __name__ == '__main__':
    import sys
    from six.moves import tkinter
    root = tkinter.Tk()
    inst = 'os38'
    cmdfile = 'test_os.cmd'
    if len(sys.argv) > 1:
        inst = sys.argv[1]
    if len(sys.argv) > 2:
        cmdfile = sys.argv[2]
    g = gui_setup(root, cmdfile, instrument = inst)
    g.pack()
    root.mainloop()

