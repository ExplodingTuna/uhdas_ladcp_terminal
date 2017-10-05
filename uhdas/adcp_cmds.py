"""
Classes for ADCP control commands.

Data structures with instrument-specific command sets.

"""
from __future__ import division
from future.builtins import object

import re

class CommandBase(object):
    '''
    ADCP command validation and conversion.

    A command value can have either of two forms, both strings:
    the 'instrument value', which, when appended to the prefix,
    is the actual command sent to the instrument;
    and the 'displayed value', a more readable version that is
    shown in the GUI.
    '''
    # Initialize attributes that may be set by instances;
    # this avoids pychecker warnings.
    maxval=minval=scale=format=None

    def __init__(self, prefix, title, **kw):
        '''
        prefix is the capital letter code for the command
        title is a string label to be displayed in the gui
        default is our default as a displayed value (string)
        kw are any attributes needed for validation and/or conversion
        '''
        self.prefix = prefix
        self.title = title
        self.update(kw)

    def update(self, kw):
        for key, value in list(kw.items()):
            setattr(self, key, value)

    def make_explanation(self):
        'Generate a short string giving valid range'
        raise NotImplementedError()

    def to_display(self, value):
        'Convert instrument value to displayed value; string -> string'
        raise NotImplementedError(str(value)) # using "value" for pychecker

    def from_display(self, value):
        'Convert displayed value to command value; string -> string'
        raise NotImplementedError(str(value))

    def validate(self, cmd):
        'Return True if instrument value (string) is valid'
        raise NotImplementedError(str(cmd))

    def validate_display(self, cmd):
        'Return True if displayed value (string) is valid'
        raise NotImplementedError(str(cmd))

class CmdOnOff(CommandBase):
    def __init__(self, *args, **kwargs):
        _trans = [('0', 'OFF'), ('1', 'ON')]
        self.trans = kwargs.pop('trans', _trans)
        self.todisp_trans = dict(self.trans)
        self.rtrans = [(a,b) for (b,a) in self.trans]
        self.fromdisp_trans = dict(self.rtrans)
        CommandBase.__init__(self, *args, **kwargs)

    def make_explanation(self):
        return "ON or OFF"

    def validate(self, cmd):
        if cmd in self.trans:
            return True
        return False

    def validate_display(self, cmd):
        if cmd in self.fromdisp_trans:
            return True
        return False

    def from_display(self, cmd):
        return self.fromdisp_trans[cmd]

    def to_display(self, cmd):
        return self.todisp_trans[cmd]

class CmdInt(CommandBase):
    ndigits = None

    def make_explanation(self):
        return '%s to %s' % (self.minval, self.maxval)

    def validate_display(self, cmd):
        try:
            icmd = int(cmd)
        except ValueError:
            return False
        if icmd <= self.maxval and icmd >= self.minval:
            return True
        else:
            return False

    def validate(self, cmd):
        if self.ndigits is not None and len(cmd) != self.ndigits:
            return False
        return self.validate_display(cmd)

    def from_display(self, cmd):
        if self.ndigits is not None:
            nz = self.ndigits - len(cmd)
            return '0' * nz + cmd
        return cmd

    def to_display(self, cmd):
        return str(int(cmd))

class CmdScaledInt(CommandBase):
    'Command uses integer value, but display may be a float'
    ndigits = None

    def make_explanation(self):
        return '%s to %s' % (self.minval, self.maxval)

    def validate(self, cmd):
        if self.ndigits is not None and len(cmd) != self.ndigits:
            return False
        try:
            dcmd = self.to_display(cmd)
        except ValueError:
            return False
        return self.validate_display(dcmd)

    def validate_display(self, cmd):
        try:
            fcmd = float(cmd)
        except ValueError:
            return False
        if (fcmd <= self.maxval and fcmd >= self.minval):
            return True
        return False

    def from_display(self, cmd):
        cmd = str(int(round(float(cmd) * self.scale)))
        if self.ndigits is not None:
            nz = self.ndigits - len(cmd)
            return '0' * nz + cmd
        return cmd

    def to_display(self, cmd):
        return str(float(cmd) / self.scale)

class CmdFloat(CommandBase):
    '''
    For TP command.

    Initialize with a 'format', like '00:%.2f', and a re pattern 'pat' for
    parsing; the pattern must have one group.
    Example for TP:  r'0{0,2}:?(\d+\.?\d+)'

    '''
    def __init__(self, *args, **kwargs):
        self.regex = re.compile(kwargs['pat'])
        CommandBase.__init__(self, *args, **kwargs)

    def make_explanation(self):
        return '%s to %s' % (self.minval, self.maxval)


    def validate(self, cmd):
        try:
            val = float(self.to_display(cmd))
        except (AttributeError, ValueError):
            return False
        if (val <= self.maxval and val >= self.minval):
            return True
        return False

    def validate_display(self, cmd):
        try:
            fcmd = float(cmd)
        except ValueError:
            return False
        if (fcmd <= self.maxval and fcmd >= self.minval):
            return True
        return False

    def from_display(self, cmd):
        return self.format % float(cmd)

    def to_display(self, cmd):
        val = self.regex.match(cmd).groups()[0]
        return val

class Cmd_OS_CX(CommandBase):
    '''
    Special for CX command; probably no point in generalizing it.
    No kwargs needed; everything is built in.
    '''
    regex3 = re.compile(r'(\d),(\d),(\d{1,5})$')
    regex2 = re.compile(r'(\d),(\d)$')

    def make_explanation(self):
        return '[timeout 120-43200]'

    def validate(self, cmd):
        try:
            mo = self.regex3.match(cmd)
            if mo is None:
                mo = self.regex2.match(cmd)
            if mo is None:
                return False
            fields = mo.groups()
        except AttributeError:
            return False
        try:
            nums = [int(x) for x in fields]
            if nums[0] < 0 or nums[0] > 5:
                return False
            if nums[1] < 0 or nums[1] > 4:
                return False
            if len(nums) == 3:
                if nums[2] < 120 or nums[2] > 43200:
                    return False
                if nums[0] == 0 and nums[1] == 0:
                    return False
            return True
        except ValueError:
            return False

    def validate_display(self, cmd):
        return self.validate(cmd)

    def from_display(self, cmd):
        return cmd

    def to_display(self, cmd):
        return cmd

##########################################################

template_boilerplate = '''
#
#   %s configuration file
#   for UHDAS must contain only the commands listed here,
#   although the values may vary.  This file is not
#   necessary; defaults are set in rdi_setup.py,
#   which is called by DAS.py.  Additional commands may
#   be specified in /home/adcp/config/sensor_cfg.py.
#
'''

os_template = template_boilerplate % ("An Ocean Surveyor",)
os_template += '''
# Bottom tracking
%(BP)-10s  # BP0 is off, BP1 is on
%(BX)-10s  # Max search range in decimeters; e.g. BX10000 for 1000 m.

# Narrowband watertrack
%(NP)-10s  # NP0 is off, NP1 is on
%(NN)-10s  # number of cells
%(NS)-10s  # cell size in centimeters; e.g. NS2400 for 24-m cells
%(NF)-10s  # blanking in centimeters; e.g. NF1600 for 16-m cells

# Broadband watertrack
%(WP)-10s  # WP0 is off, WP1 is on
%(WN)-10s  # number of cells
%(WS)-10s  # cell size in centimeters
%(WF)-10s  # blanking in centimeters

# Interval between pings
%(TP)-10s  # e.g., TP00:03.00 for 3 seconds

# Triggering
%(CX)-10s  # in,out[,timeout]

'''

wh_template = template_boilerplate % ("A Workhorse Mariner",)
wh_template += '''
%(BP)-10s   #  Bottom track on (BP1) or off (BP0)
%(BX)-10s   #  BT max search range in decimeters (BX02000 for 200 m)
%(WN)-10s   #  number of cells
%(WS)-10s   #  cell size in centimeters
%(WF)-10s   #  blanking in centimeters
%(TP)-10s   #  ping interval; TP00:00.80 is 0.8 seconds

'''

# presently same as WH except for boilerplate title
bb_template = template_boilerplate % ("A Broadband",)
bb_template += '''
%(BP)-10s   #  Bottom track on (BP1) or off (BP0)
%(BX)-10s   #  BT max search range in decimeters (BX02000 for 200 m)
%(WN)-10s   #  number of cells
%(WS)-10s   #  cell size in centimeters
%(WF)-10s   #  blanking in centimeters
%(TP)-10s   #  ping interval; TP00:00.80 is 0.8 seconds

'''

nb_template = template_boilerplate % ("A Narrowband",)
nb_template += '''
#   The Narrowband requires *exactly* the number of digits
#   given in the examples.

%(I)-10s   # Pulse length in meters; I08 is 8-m pulse
%(J)-10s   # Blanking in decimeters; e.g., J08 for 8-m blank
%(L)-10s   # base-2 log of cell length in meters; L3 is 8-m cell
%(Q)-10s   # Number of cells, e.g. Q050 for 50 cells
%(FH)-10s  # Bottom Track: FH00255 is off, FH00001 is on

'''

template_dict = {'os' : os_template,
                 'wh' : wh_template,
                 'bb' : bb_template,
                 'nb' : nb_template}


default_config_cmds_dict = {'os' : ['CR1',
                                    'WD 111 00 0000',
                                    'ND 111 00 0000'],
                            'wh' : ['CR1',
                                    'CL0',
                                    'WD 111 000 000',
                                    #'WB0',
                                    #'WV550',
                                    'TE00:00:00.00',
                                    #'TP00:01.00',
                                    'CF11110',
                                    'EX00000',
                                    'EZ1011101'
                                    ],
                            # bb presently same as wh
                            'bb' : ['CR1',
                                    'WD 111 000 000',
                                    #'WB0',
                                    #'WV550',
                                    'TE00:00:00.00',
                                    #'TP00:01.00',
                                    'CF11110',
                                    'EX00000',
                                    'EZ1011101'
                                    ],
                            'nb' : ['Z',
                                    'B009001',
                                    'E0004020099',
                                    'P00001']
                           }

query_cmds_dict = {'os' : ['B?', 'N?', 'W?', 'E?', 'C?', 'T?',
                            'PS0'],
              #              'PS0', 'LD', 'LC'],
                   'wh' : ['B?', 'W?', 'E?', 'C?', 'T?', 'PS0'],
                   'bb' : ['B?', 'W?', 'E?', 'C?', 'T?', 'PS0'],
                   'nb' : ['?', 'F?']
                  }


OS38params = {
    'NS': {'default': '24', 'minval':16, 'maxval':64},
    'NF': {'default': '16', 'minval':4, 'maxval':90},
    'WS': {'default': '12', 'minval':8, 'maxval':64},
    'WF': {'default': '16', 'minval':4, 'maxval':90},
    'BX': {'default': '1000', 'minval':100, 'maxval':2000},
    'TP': {'default': '3.0', 'minval':0, 'maxval':6},
    }

OS75params = {
    'NS': {'default': '16', 'minval':8, 'maxval':32},
    'NF': {'default': '8', 'minval':4, 'maxval':90},
    'WS': {'default': '8', 'minval':4, 'maxval':32},
    'WF': {'default': '8', 'minval':4, 'maxval':90},
    'BX': {'default': '1000', 'minval':100, 'maxval':1500},
    'TP': {'default': '1.8', 'minval':0, 'maxval':6},
    }

OS150params = {
    'NS': {'default': '8', 'minval':4, 'maxval':16},
    'NF': {'default': '4', 'minval':2, 'maxval':90},
    'WS': {'default': '4', 'minval':2, 'maxval':16},
    'WF': {'default': '4', 'minval':2, 'maxval':90},
    'BX': {'default': '500', 'minval':50, 'maxval':700},
    'TP': {'default': '1.1', 'minval':0, 'maxval':6},
    }

OSparams = {38: OS38params,
            75: OS75params,
            150: OS150params
           }

WH300params = {
    'WS': {'default': '2', 'minval':2, 'maxval':16},
    'WF': {'default': '2', 'minval':2, 'maxval':16},
    'BX': {'default': '200', 'minval':10, 'maxval':200},
    'TP': {'default': '0.8', 'minval':0, 'maxval':6},
    }

WH600params = {
    'WS': {'default': '1', 'minval':1, 'maxval':8},
    'WF': {'default': '1', 'minval':1, 'maxval':8},
    'BX': {'default': '50', 'minval':5, 'maxval':125},
    'TP': {'default': '0.7', 'minval':0, 'maxval':3},
    }

WH1200params = {
    'WS': {'default': '0.5', 'minval':.25, 'maxval':2},
    'WF': {'default': '0.5', 'minval':.5, 'maxval':2},
    'BX': {'default': '20', 'minval':1, 'maxval':45},
    'TP': {'default': '0.6', 'minval':0, 'maxval':2},
    }

WHparams = {300: WH300params,
            600: WH300params,
            1200: WH1200params,
            }

# presently same as WH
BB150params = {
    'WS': {'default': '4', 'minval':2, 'maxval':8},
    'WF': {'default': '4', 'minval':2, 'maxval':16},
    'BX': {'default': '300', 'minval':10, 'maxval':500},
    'TP': {'default': '1.1', 'minval':0, 'maxval':6},
    }

BB300params = {
    'WS': {'default': '2', 'minval':2, 'maxval':8},
    'WF': {'default': '2', 'minval':1, 'maxval':16},
    'BX': {'default': '200', 'minval':10, 'maxval':200},
    'TP': {'default': '0.8', 'minval':0, 'maxval':6},
    }

BB600params = {
    'WS': {'default': '1', 'minval':1, 'maxval':4},
    'WF': {'default': '1', 'minval':1, 'maxval':8},
    'BX': {'default': '100', 'minval':10, 'maxval':100},
    'TP': {'default': '0.7', 'minval':0, 'maxval':3},
    }

BBparams = {150: BB150params,
            300: BB300params,
            600: BB600params,
            }



TP_pat = r'0{0,2}:?(\d+\.?\d+)'

def make_OS_command_dict(freq):
    commands = [
        CmdOnOff('NP', 'Narrowband Mode', default='ON'),
        CmdOnOff('WP', 'Broadband Mode', default='ON'),
        CmdOnOff('BP', 'Bottom Track', default='OFF'),
        CmdInt('NN', 'NB Number of Bins', default='60', minval=5, maxval=128),
        CmdInt('WN', 'BB Number of Bins', default='80', minval=5, maxval=128),
        Cmd_OS_CX('CX', 'Trigger in,out[,timeout]', default='0,0'),
        # The following need freq-specific parameters:
        CmdScaledInt('NS', 'NB Bin Length (m)', scale=100),
        CmdScaledInt('NF', 'NB Blanking (m)', scale=100),
        CmdScaledInt('WS', 'BB Bin Length (m)', scale=100),
        CmdScaledInt('WF', 'BB Blanking (m)', scale=100),
        CmdScaledInt('BX', 'BT max depth (m)', scale=10),
        CmdFloat('TP', 'TP min ping time (s)', format= '00:%05.2f',
                                         pat=TP_pat),
        ]
    comdict = dict([(c.prefix, c) for c in commands])
    params = OSparams[freq]
    for key, value in list(params.items()):
        comdict[key].update(value)
    return comdict


def make_WH_command_dict(freq):
    commands = [
        CmdOnOff('WP', 'Water Profile', default='ON'),
        CmdOnOff('BP', 'Bottom Track', default='OFF'),
        CmdInt('WN', 'Number of Bins', default='70', minval=5, maxval=128),
            # WB could display 'Narrow', 'Broad'
        CmdInt('WB', 'Bandwidth', default='0', minval=0, maxval=1),
            # Long term, we may want to make the following change with WB;
            # but it is not trivial.
        CmdInt('WV', 'Ambiguity (cm/s)', default='550', minval=100, maxval=700),
        # The following need freq-specific parameters:
        CmdScaledInt('WS', 'Bin Length (m)', scale=100),
        CmdScaledInt('WF', 'Blanking (m)', scale=100),
        CmdScaledInt('BX', 'BT max depth (m)', scale=10),
        CmdFloat('TP', 'TP min ping time (s)', format= '00:%05.2f',
                                         pat=TP_pat),
        ]
    comdict = dict([(c.prefix, c) for c in commands])
    params = WHparams[freq]
    for key, value in list(params.items()):
        comdict[key].update(value)
    return comdict


# presently same as WH
def make_BB_command_dict(freq):
    commands = [
        CmdOnOff('WP', 'Water Profile', default='ON'),
        CmdOnOff('BP', 'Bottom Track', default='OFF'),
        CmdInt('WN', 'Number of Bins', default='70', minval=5, maxval=128),
        CmdInt('WB', 'Bandwidth', default='0', minval=0, maxval=1),
            # Long term, we may want to make the following change with WB;
            # but it is not trivial.
        CmdInt('WV', 'Ambiguity (cm/s)', default='550', minval=100, maxval=700),
        # The following need freq-specific parameters:
        CmdScaledInt('WS', 'Bin Length (m)', scale=100),
        CmdScaledInt('WF', 'Blanking (m)', scale=100),
        CmdScaledInt('BX', 'BT max depth (m)', scale=10),
        CmdFloat('TP', 'TP min ping time (s)', format= '00:%05.2f',
                                         pat=TP_pat),
        ]
    comdict = dict([(c.prefix, c) for c in commands])
    params = BBparams[freq]
    for key, value in list(params.items()):
        comdict[key].update(value)
    return comdict


def make_NB_command_dict(freq):
    if freq == 150:
        Length='3'; Pulse='8'; Blank='8'
    elif freq == 300:
        Length = '2'; Pulse = '4'; Blank = '4'
    else:
        raise ValueError('frequency %d not known' % (freq))
    commands = [
        CmdOnOff('P', 'Pinging', default='ON',
                        trans=[('00000', 'OFF'), ('00001', 'ON')]),
                        # 00000 is a dummy value; it will never be
                        # sent to the instrument.
        CmdOnOff('FH', 'Bottom Track', default='OFF',
                            trans=[('00255', 'OFF'), ('00001', 'ON')]),
        CmdInt('Q', 'Number of Bins', default='60',
                            minval=5, maxval=128, ndigits=3),
        CmdInt('L', 'log2 of Bin Length (m)', default=Length,
                            minval=2, maxval=4, ndigits=1),
        CmdInt('I', 'Pulse Length (m)', default=Pulse,
                            minval=4, maxval=16, ndigits=2),
        CmdScaledInt('J', 'Blanking (m)', default=Blank, scale=10,
                            minval=4, maxval=16, ndigits=3),
        ]
    comdict = dict([(c.prefix, c) for c in commands])
    return comdict


user_command_dict = {
   'os38'  : make_OS_command_dict(38),
   'os75'  : make_OS_command_dict(75),
   'os150' : make_OS_command_dict(150),
   'wh300' : make_WH_command_dict(300),
   'wh600' : make_WH_command_dict(600),
   'wh1200': make_WH_command_dict(1200),
   'bb150' : make_BB_command_dict(150),
   'bb300' : make_BB_command_dict(300),
   'bb600' : make_BB_command_dict(600),
   'nb150' : make_NB_command_dict(150),
   'nb300' : make_NB_command_dict(300)
   }


# We need this list to establish the display order.
os_user_command_list = ['NP', 'NN', 'NS', 'NF',
                        'WP', 'WN', 'WS', 'WF', 'BP', 'BX', 'TP', 'CX']
wh_user_command_list = [ 'WP', 'WN', 'WS', 'WF', 'BP', 'BX', 'WB', 'WV', 'TP']
bb_user_command_list = [ 'WP', 'WN', 'WS', 'WF', 'BP', 'BX', 'WB', 'WV', 'TP']
nb_user_command_list = ['P', 'Q', 'L', 'I', 'J', 'FH']
user_command_list_dict = {'os': os_user_command_list,
                          'wh': wh_user_command_list,
                          'bb': bb_user_command_list,
                          'nb': nb_user_command_list}


pattern_dict = {'os' : r"([&a-zA-Z]+)\s*(\S*)",
                'wh' : r"([&a-zA-Z]+)\s*(\S*)",
                'bb' : r"([&a-zA-Z]+)\s*(\S*)",
                'nb' : r"([&A-Z]+)(\d*)"}       # Upper case only.




