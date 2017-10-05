'''
Gathers information relevant to data acquisition and processing.

This module uses three files in /home/adcp/config:
(proc_cfg.py, uhdas_cfg.py, sensor_cfg.py)
and the uhdas.cruisesetup module to
collect and calculate a variety of directories, etc. in an
instance of the procsetup class.

There is some overlap with cruisesetup, as well as differences
in the way they name similar variables, for historical reasons.
'''

from future import standard_library
standard_library.install_hooks()

from future.builtins import zip
from future.builtins import object

import os
import re
import subprocess

from pycurrents.system import logutils, Bunch
L = logutils.getLogger('procsetup')

L.debug('Starting procsetup')

from pycurrents.system.pathdict import PathDict

from onship import shipnames


# Find the script directory, based on location
# of present module:
thispath = os.path.dirname(os.path.abspath(__file__))
_daspath = subprocess.getoutput('which DAS.py')
if _daspath:  # installed or on path
    scriptpath = os.path.dirname(_daspath)
else:         # in place, not on path
    scriptpath = os.path.normpath(os.path.join(thispath, '../scripts'))
L.debug('scriptpath is %s', scriptpath)

# remove reference to programs_path and os.environ.get('CURRENTS_REPO_PATH')
# replaced  scripts/repo_status.py (leveraging 'installed' hg_status.py)

def get_variables(filename):
    '''
    Load a .py file and return a Bunch with its objects.
    Probably we will replace this with inline code, as
    has been done in pycurrents.
    '''
    return Bunch().from_pyfile(filename)

class NoCruiseFound(Exception):
    pass

class CruiseInfo(object):
    '''
    Non-GUI mixin or standalone class and functions
    for organizing and manipulating information about a cruise.

    This is a base class for cruisesetup/CruiseSetup.
    '''
    def __init__(self, homedir = '/home/adcp'):
        self.pd = PathDict()
        self.pd.set('homeD', homedir)
        self.pd.set('homecruiseD', self.pd.homeD, 'cruise')
        self.pd.set('datacruiseD', '/home/data', 'current_cruise')
        self.pd.set('configD', homedir, 'config')
        self.pd.set('cmdD', self.pd.configD, 'cmdfiles')

        self.pd.set('uhdas_cfgF', self.pd.configD, 'uhdas_cfg.py')
        #done?  get rid of references to procsetup_onship.py
        self.onship = get_variables(self.pd.uhdas_cfgF)
        self.pd.set('proc_cfgF', self.pd.configD, 'proc_cfg.py')
        self.onship.update(get_variables(self.pd.proc_cfgF))

        self.pd.set('workD', self.onship['workdir'])
        self.pd.set('flagD', homedir, 'flags')
        self.pd.set('morgueD', homedir, 'morgue')
        self.pd.set('logD', homedir, 'log')
        # Flag file to show other processes when logging is on:
        self.pd.set('is_loggingF', self.pd.flagD, 'DAS.logging')
        #self.pd.set('scriptD', self.pd.homeD, 'scripts')
        self.pd.set('scriptD', scriptpath)
        # Scripts to run when logging starts, stops, etc.:
        self.pd.set('start_loggingF', self.pd.scriptD, 'DAS_while_logging.py')
        self.pd.set('stop_loggingF', self.pd.flagD, 'DAS_while_logging.stop')
        self.pd.set('start_cruiseF', self.pd.scriptD, 'DAS_while_cruise.py')
        self.pd.set('stop_cruiseF', self.pd.flagD, 'DAS_while_cruise.stop')
        # _dir = os.popen('which adcpsect').read()
        # ii = _dir.rfind('/codas3')
        #   codasD was used only in the call to adcptree, which has
        #   its own logic for finding adcp_templates
        # self.pd.set('codasD', _dir[:ii])
#        self.pd.set('programsD', programs_path) #from top of this module
        self.pd.set('sensorF', self.pd.configD, 'sensor_cfg.py')
        sensor_cfg = Bunch().from_pyfile(self.pd.sensorF)
        self.sensors = sensor_cfg['sensors']
        self.ADCPs = sensor_cfg['ADCPs']
        self.common_opts = sensor_cfg['common_opts']
        self.pds = []
        self.datatypes = []
        r = re.compile(r'([a-zA-Z]+)([0-9]+)')
        for ADCP in self.ADCPs:
            pd = PathDict()
            pd.set('cmdF', self.pd.cmdD, ADCP['defaultcmd'])
            self.pds.append(pd)
            self.datatypes.extend(ADCP['datatypes'])
            inst, freq= r.match(ADCP['instrument']).groups()
            ADCP['instclass'] = inst
            ADCP['frequency'] = freq
        self.subdir_messages = self._get_subdir_messages()

    def _get_subdir_messages(self):
        d = {}
        for sensor in self.sensors:
            if sensor['format'] in ('ascii', 'zmq_ascii'):
                d[sensor['subdir']] = sensor['messages']
        return d

    def get_underway_cruise_info(self):
        '''
           If a cruise is underway, get the cruiseid and information
           derived from it, then return True; otherwise, return False.
        '''
        if not os.path.islink(self.pd.homecruiseD):
            return False
        # If a /home/adcp/cruise symlink is present but broken, remove it.
        if not os.path.isdir(self.pd.homecruiseD):    # follows links
            os.remove(self.pd.homecruiseD)
            return False
        self.pd.set('baseD', os.path.realpath(self.pd.homecruiseD))
        cruiseid = os.path.split(self.pd.baseD)[1]
        self.cruiseid = cruiseid
        self.set_cruise_dirs()
        # done?: replace self.read_cfg() with this line, and delete self.read_cfg
        self.yearbase = get_variables(self.pd.cruise_procF)['yearbase']
        return True


    def set_cruise_dirs(self):
        '''Once cruiseid is known, calculate the cruise directories.
        '''
        cruiseid = self.cruiseid
        self.pd.set('baseD', '/home/data', cruiseid)
        self.pd.set('rawD', self.pd.baseD, 'raw')
        self.pd.set('rbinD', self.pd.baseD, 'rbin')
        self.pd.set('gbinD', self.pd.baseD, 'gbin')
        self.pd.set('procD', self.pd.baseD, 'proc')
        self.pd.set('tsgmetD', self.pd.baseD, 'tsgmet')

        for i, pd in enumerate(self.pds):
            pd.set('rawpingD', self.pd.rawD,
                        self.ADCPs[i]['instrument'])
            pd.set('logparamF', pd.rawpingD, 'current.cmd')
        self.pd.set('savelogD', self.pd.rawD, 'log')
        self.pd.set('saveconfigD', self.pd.rawD, 'config')

        self.pd.set('cfgF', self.pd.saveconfigD, cruiseid + '_cfg.m')
        self.pd.set('procF', self.pd.saveconfigD, cruiseid + '_proc.m')

        if 'onshipF' in self.pd.path:
            self.pd.set('pyprocF', self.pd.saveconfigD, 'procsetup_onship.py')
        else:
            self.pd.set('cruise_procF', self.pd.saveconfigD,
                                        cruiseid + '_proc.py')
            self.pd.set('cruise_sensorF', self.pd.saveconfigD,
                                        cruiseid + '_sensor.py')
            self.pd.set('cruise_uhdasF', self.pd.saveconfigD,
                                        cruiseid + '_uhdas.py')



class procsetup(object):
    '''
    Provide info about ship, cruise, instruments as instance attributes.

    '''
    def __init__(self, cruisedir = None, logging = False):
        '''
        - set cruisedir = '' to get info valid when not logging.
        - logging is set to True by DAS_while_logging; otherwise it
             remains False.
        '''

        # New style: no procsetup_onship.py
        p = "/home/adcp/config/uhdas_cfg.py"
        self.__dict__.update(get_variables(p))
        p = "/home/adcp/config/proc_cfg.py"
        self.__dict__.update(get_variables(p))

        # procsetup_onship.py or uhdas_cfg.py must have a shipkey variable;
        # this should be identical to the shipabbrev variable in sensor_cfg.py
        self.shipname = shipnames.shipnames[self.shipkey]
        self.shipdir = shipnames.shipdirs[self.shipkey]

        sensor_cfg = '/home/adcp/config/sensor_cfg.py'
        self.__dict__.update(get_variables(sensor_cfg))

        ## shorthand for:
        ## all instruments in hdg_inst_msgs except primary heading ("hdg_inst")
        ## used in DAS_while_logging.py and uhdas_webgen.py
        if not hasattr(self.__dict__, 'attitude_devices'):
            self.attitude_devices = []
            for hdg_inst, hdg_msg in self.hdg_inst_msgs:
                if hdg_inst != self.hdg_inst:
                    self.attitude_devices.append(hdg_inst)

        self.CI = CruiseInfo()
        if self.CI.get_underway_cruise_info():  #returns True if a cruise is
                                                # underway;
            if logging:
                self.active_procdirnames = self.get_active_procdirnames()
        # CI now has quite complete path information that can replace some
        # of what follows.
        self.dbname = 'a_' + self.shipabbrev  # from sensor_cfg.py
        p = os.path.split(__file__)[0]
        p = os.path.split(p)[0]
        self.progdir = os.path.split(p)[0]
        self.adcphome = '/home/adcp'
        self.cruiseid = None  # initialize, so it is None unless changed.
        self.cruisedir = cruisedir

        if not cruisedir:
            cruiselink = os.path.join(self.adcphome, 'cruise')
            # get the actual path linked to cruiselink
            if os.path.exists(cruiselink):
                self.cruisedir = os.readlink(cruiselink)
        if self.cruisedir:
            self.cruiseid = os.path.split(self.cruisedir)[1]   # for titles
        elif self.cruisedir is not '':
            raise NoCruiseFound


        ## get these whether there is a cruise or not
        self.et_emailfile = '/home/adcp/config/et_email_body'
        self.daily_dir = '/home/adcp/daily_report'
        self.flag_dir = '/home/adcp/flags'
        self.html_dir = '/home/adcp/www'
        self.web_datadir    = os.path.join(self.html_dir, 'data')
        # root of figures (current and archived)
        self.web_figdir     = os.path.join(self.html_dir, 'figures')
        # archive png here (by instrument name)
        self.web_pngarchive = os.path.join(self.html_dir,'figures', 'png_archive')


        ## get these only if there is a known cruisedir
        if self.cruisedir:
            ## get processing directories if they exist
            self.procdirbase = os.path.join(self.cruisedir, 'proc')
            #initialize a list of database paths eminating from procdirbase
            # use as a test later
            procdirnames = []
            tmpdirs = os.listdir(self.procdirbase)
            for tmpdir in tmpdirs:
                dbpath = os.path.join(self.procdirbase, tmpdir, 'adcpdb')
                if os.path.exists(dbpath):
                    procdirnames.append(tmpdir)

            self.procdirnames = procdirnames

            # make archive directories if necessary
            for name in procdirnames:
                dirname = os.path.join(self.web_pngarchive, name)
                if not os.path.exists(dirname):
                    L.info('making figure archive directory %s:' % (dirname,))
                    os.makedirs(dirname)

            ################## deduce some info #######################
            self.yearbase = get_variables(self.CI.pd.cruise_procF)['yearbase']

            ## get instrument class, ping type by parsing procdirnames
            ## e.g., (nb150, os38bb, os38nb)
            self.instclass = {}     #os, nb, bb
            self.pingtype  = {}     #nb, bb
            self.frequency = {}     #38, 150...
            self.instname  = {}     #os38, nb150
            default_ping = {'nb':'nb', 'wh':'bb', 'bb':'bb'}
            r = re.compile(r'([a-zA-Z]+)([0-9]+)([a-zA-Z]*)')
            # self.procdirnames has the same members as self.CI.datatypes
            for name in procdirnames:
                inst, freq, ping = r.match(name).groups()
                self.instclass[name] = inst
                self.frequency[name] = int(freq)
                self.instname[name] = inst+freq
                if ping:
                    self.pingtype[name] = ping
                else:
                    self.pingtype[name] = default_ping[inst]

    def get_active_procdirnames(self):
        activelist = []
        for pd, ADCP in zip(self.CI.pds, self.CI.ADCPs):
            if ADCP['instclass'] == 'os':
                try:
                    cmds = open(pd.logparamF).read()
                    if cmds.find('WP1') >= 0:
                        activelist.append(ADCP['instrument'] + 'bb')
                    if cmds.find('NP1') >= 0:
                        activelist.append(ADCP['instrument'] + 'nb')
                except:
                    L.warn("Can't read %s" % (pd.logparamF,))
            elif ADCP['instclass'] in ('wh', 'bb'):
                try:
                    cmds = open(pd.logparamF).read()
                    if cmds.find('WP1') >= 0:
                        activelist.append(ADCP['instrument'])
                except:
                    L.warn("Can't read %s" % (pd.logparamF,))
            else:
                activelist.append(ADCP['instrument'])
        return activelist
        # Regenerating the procdirnames as above seems less than
        # ideal, but it should be OK until some other instrument
        # or pingtype comes along.

