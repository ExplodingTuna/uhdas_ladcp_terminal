'''
one-stop shopping for uhdas processing (data locations) and some defaults.

used by uhdas/scripts/uhdas_config_gen.py
'''
from __future__ import print_function
from future.builtins import object

import os, sys, glob
import re

from pycurrents.system import logutils
log = logutils.getLogger(__file__)


from pycurrents.adcp import uhdas_defaults
from pycurrents.adcp.uhdas_defaults import codas_adcps, get_shipnames

# for Cmdfile_Gen
try:
    import uhdas.uhdas.adcp_cmds as rdi
except ImportError:
    # This is for compatibility with older uhdas directory.
    try:
        import undas.uhdas.commands as rdi
    except ImportError:
        import uhdas.uhdas.rdi_setup as rdi
    import warnings
    warnings.warn("Update your uhdas repo.")

#---------------------------------------------------

## from onship/cmd_defaults.py


pattern_dict = {'os' : r"([&a-zA-Z]+)\s*(\S*)",
                'wh' : r"([&a-zA-Z]+)\s*(\S*)",
                'nb' : r"([&A-Z]+)(\d*)"}       # Upper case only.

class Cmdfile_Gen(object):
    '''
    overrides from uhdas_cmdoverrides applied
    strings (for printing) are stored in attribute cmdstrs,
                  filename (base) are keys (eg 'os75_default')
    dict with UHDAS-style values stored in attribute string_dict
                  (defaults only)
    if cmddir is provided, write standard default files to that dir.


    usage:
    CG=Cmdfile_Gen('kn')
    CG.compare_all_dicts('/home/adcp/config/cmdfiles')

    CG.write_cmd('newcmddir')  # puts files here

    '''

    def __init__(self, shipkey=None, shipinfo=None):

        shipnames = get_shipnames(shipinfo=shipinfo)
        self.shipnames = shipnames
        self.shipkey = shipkey

        # dictionaries, key=adcp
        self.user_dicts = dict()  # values are CommandBase
        self.user_cmdlist_dict = dict() #ordered list of keys
        # fill
        self.adcps = self.shipnames.onship_adcps[self.shipkey]
        for adcp in self.adcps:
            self.user_dicts[adcp] = rdi.user_command_dict[adcp]
            inst = adcp[:2]
            self.user_cmdlist_dict[adcp] = rdi.user_command_list_dict[inst]

        # dictionaries
        self.string_disp_dicts = dict() # as displayed
        self.string_dicts = dict() # feed to cmdstr
        self.string_adcp_dict = dict() # hold adcp type
        self.cmdstrs = dict()   #printable strings for file: key=fnamebase

        Udef = uhdas_defaults.Uhdas_cmdfile_defaults(shipkey=self.shipkey,
                                    shipinfo=shipinfo)

        self.ship_overrides = Udef.defaults

        # make sure overrides are reasonable
        self._test_overrides()

        if self.badcount == 0:
            for adcp in self.adcps:
                string_dict, disp_dict = self._make_userdict_withstrings(adcp)
                #stores for printing in self.cmdstrs[filenamebase]
                # stores for comparison in self.string_dicts[filenamebase]
                self._gen_cmdfile(string_dict, disp_dict, adcp)
            #
        else:
            print('badcount  is', self.badcount)
            print('could not generate strings: check syntax in cmd_defaults.py')


    #-------------
    def _test_overrides(self):
        self.badcount = 0

        for adcp in self.adcps:
            if adcp in self.ship_overrides.keys():
                overrides = self.ship_overrides[adcp]
                for kk in overrides.keys():
                    cmd = self.user_dicts[adcp][kk]
                    if not cmd.validate_display(overrides[kk]):
                        print('failed to validate ', kk, overrides[kk])
                        self.badcount += 1
                        print('ship  adcp  command  default override')
                        print('%2s   %4s     %s       %s      %s' % (
                               self.shipkey, adcp, kk,
                                      str(cmd.default), str(overrides[kk])))

    #--------
    def _make_userdict_withstrings(self, adcp):
        '''
        implement UHDAS overrides, return dict with string values
        values are human-readable (as per UHDAS gui)
        '''
        for a in self.ship_overrides.keys():
            if a not in codas_adcps:
                print('WARNING: invalid instrument "%s" for cmd overrides' % (a))
                print('%s not in ' % (a), codas_adcps)
                sys.exit()

        string_dict = dict()
        disp_dict = dict()
        user_dict = self.user_dicts[adcp]
        # replace all values with string
        for kk in self.user_cmdlist_dict[adcp]:
            cmd = user_dict[kk]
            string_dict[kk] = cmd.from_display(cmd.default)
            disp_dict[kk]   = cmd.to_display(cmd.from_display(cmd.default))
        if adcp in self.ship_overrides:
            overrides = self.ship_overrides[adcp]
            for kk in overrides.keys():
                cmd = user_dict[kk]
                string_dict[kk] = user_dict[kk].from_display(overrides[kk])
                disp_dict[kk]   = cmd.to_display(cmd.from_display(overrides[kk]))

        return string_dict, disp_dict


    #-------------
    def _gen_cmdfile(self, s_dict, d_dict, adcp):
        #                 string_dict , disp_dict
        file_template =rdi.template_dict[adcp[:2]]
        user_command_list = rdi.user_command_list_dict[adcp[:2]]
        if adcp[:2] == 'os':
            overrides = dict(interleaved     =  {'WP' : 'ON', 'NP' : 'ON'},
                             default         =  {'WP' : 'ON', 'NP' : 'ON'},
                             lowres_deep     =  {'WP' : 'OFF','NP' : 'ON'},
                             highres_shallow =  {'WP' : 'ON', 'NP' : 'OFF'})
        else:
            overrides = dict()
        overrides['default'] = {}
        #
        for fname in overrides.keys():
            user_dict = self.user_dicts[adcp].copy()
            string_dict = s_dict.copy()
            disp_dict = d_dict.copy()
            override = overrides[fname]
            for kk in override.keys():
                string_dict[kk]= user_dict[kk].from_display(override[kk])
                disp_dict[kk]= override[kk]
            # prepend keys
            d1 = dict()
            for kk in user_command_list:
                d1[kk] = kk + string_dict[kk]
            # store printable strings here, with key = file prefix
            fnamebase = '%s_%s' % (adcp, fname)
            self.cmdstrs[fnamebase] = file_template % d1
            self.string_dicts[fnamebase] = d1.copy()
            self.string_disp_dicts[fnamebase] = disp_dict.copy()
            self.string_adcp_dict[fnamebase]  = adcp

    #--------
    def write_cmd(self, cmddir):
        if os.path.exists(cmddir):
            print('directory %s exists.  will not write files' % (cmddir))
        else:
            os.makedirs(cmddir)
            for fbase in self.cmdstrs.keys():
                outfile = os.path.join(cmddir, fbase+'.cmd')
                open(outfile, 'w').write(self.cmdstrs[fbase])
            print('\nfiles in %s:' % (cmddir))
            filelist = glob.glob(os.path.join(cmddir, '*cmd'))
            filelist.sort()
            print('\n'.join(filelist))

    #==========================
    ## now these are for reading existing files to compare with defaults

    def _read_cmdfiles_from_dir(self, dirname, globstr='*.cmd'):
        filelist=glob.glob(os.path.join(dirname, globstr))
        filelist.sort()
        self.strdicts_from_dir = dict()
        for fname in filelist:
            fnamebase = os.path.splitext(os.path.basename(fname))[0]
            try:
                self.strdicts_from_dir[fnamebase] = self._dict_from_file(fname)
            except:
                self.strdicts_from_dir[fnamebase] = None
                print('cannot get commands from %s' % (fname))


    #--------
    def _dict_from_file(self, filename):
        # we need to make the CommandBase but won't be using the frequency
        cmds = {}
        if not os.path.exists(filename):
            #log.error('Error: file %s not found',  filename)
            print("Error: file %s not found" % filename)
            return {}
            # This is a workaround for a bug found on manini,
            # 2008/11/13, with Ubuntu 8.10, in which trying
            # to open a nonexistent file *here* causes a
            # segfault.  It has something to do with exception
            # raising/catching.

        # try to guess ADCP type
        # low budget:
        lines = open(filename).readlines()
        lines = [l.strip() for l in lines if len(l) > 2]
        adcp = self._adcp_from_file(filename, lines)
        user_dict = rdi.user_command_dict[adcp]
        R = re.compile(pattern_dict[adcp[:2]])
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
                cmd = user_dict[key]
                cmds[key] = cmd.to_display(val)
            except (AttributeError, KeyError, ValueError):
                print('Error: unrecognized_command %s in %s file %s' % (
                                   line, adcp, os.path.basename(filename)))
                return  {}
        return cmds

    #--------
    def compare_dicts(self, from_repo, from_file, adcp):
        user_dict = rdi.user_command_dict[adcp]
        for kk in user_dict.keys():
            if kk not in from_repo:
                print('     %s : missing          (from onship)' % (kk))
            if kk not in from_file:
                print('     %s :          missing from file' % (kk))
            else:
                v1 = from_repo[kk]
                v2 = from_file[kk]
                if v1!=v2:
                    print('     %s : %5s  %5s' % (kk, str(v1), str(v2)))


    #--------
    def compare_all_dicts(self, dirname, globstr='*.cmd'):
        self._read_cmdfiles_from_dir(dirname, globstr=globstr)
        local_keys = list(self.string_disp_dicts.keys())
        other_keys = list(self.strdicts_from_dir.keys())

        unrelated_adcps = []
        for a in codas_adcps:
            if a not in self.adcps:
                unrelated_adcps.append(a)

        common = []
        local_only = []
        dir_unrelated = []
        dir_plausible = []

        for kk in local_keys:
            if kk in other_keys:
                common.append(kk)
            else:
                local_only.append(kk)

        for kk in other_keys:
            if kk not in common:
                parts = kk.split('_')
                if parts[0] in unrelated_adcps:
                    dir_unrelated.append(kk)
                else:
                    dir_plausible.append(kk)

        if len(dir_unrelated) > 0:
            print("\nonly in dir, probably unrelated:\n")
            print(', '.join(dir_unrelated))
            print("\n\nFiles of interest: (only in dir):\n ",'\n  '.join(dir_plausible))

        if len(local_only) > 0:
            print("\nonly from onship:\n", '\n  '.join(local_only))
            print("\n  diffs:\n")

        print('\ncomparison for %s' % (dirname))
        for kk in common:
            print('------------------------------------')
            print('   diffs: onship, from file "%s.cmd"' % (kk))
            self.compare_dicts(self.string_disp_dicts[kk], #from repo
                               self.strdicts_from_dir[kk], #from file
                               self.string_adcp_dict[kk])

    #----------
    def _adcp_from_file(self,full_fname, lines):
        '''
        try to determine the adcp type from a cmd file
        frequency is hardwired; this is just to get our hands on
               the conversion methods
        '''
        alltxt = ''.join(lines)
        adcp = None
        fname = os.path.basename(full_fname)
        fpart = fname.split('_')[0]
        if fpart in codas_adcps:
            adcp = fpart
            if adcp in self.adcps:
                print('adcp %5s from filename (%s)' % (adcp, fname))
        else:
            if 'FH00' in alltxt:
                adcp = 'nb150'
            elif 'NP' in alltxt:
                adcp='os75'
            else:
                adcp = 'wh300'
            print('adcp %5s from contents (%s)' % (adcp, os.path.basename(fname)))
        return adcp

