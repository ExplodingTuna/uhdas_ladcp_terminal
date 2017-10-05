#!/usr/bin/env  python

from __future__ import print_function
from optparse import OptionParser
import string, os, sys

from pycurrents.adcp.uhdasconfig import Proc_Gen, Sensor_Gen, Uhdas_Gen
from pycurrents.adcp.uhdasconfig import get_configs, compare_cfg
from pycurrents.adcp import uhdas_defaults

from uhdas.uhdas.uhdasconfig import Cmdfile_Gen
import commands


class CommandError(Exception):
    def __init__(self, cmd, status, output):
        msg = "Command '%s' failed with status %d\n" % (cmd, status)
        Exception.__init__(self, msg + output)

#---------
def make_configdir(configdir):
    if os.path.exists(configdir):
        print('config dir %s exists, exiting' % (configdir))
        sys.exit()
    try:
        os.makedirs(configdir)
    except:
        print('cannot make directory %s' % (configdir))

#########


if __name__ == "__main__":
    icnf = None
    if '--shipinfo' in sys.argv:
        icnf = sys.argv.index('--shipinfo')
    elif '-p' in sys.argv:
        icnf = sys.argv.index('-p')

    if icnf is None:
        from  onship import shipnames
    else:
        shipinfo = sys.argv[icnf+1]
        mod = __import__(shipinfo)
        shipnames = getattr(mod, 'shipnames')

    qsletters=[]
    for k in shipnames.shipletters:
        qsletters.append("'%s'" % k)
    shipletters=string.join(qsletters,', ')

    usage = string.join(["\n\nusage for UH-managed ships:",
         "  ",
         " generate and (sort of) test sensor_cfg defaults:",
         "      uhdas_config_gen.py -s ka ",
         " generate and write:",
         "      uhdas_config_gen.py  -s ka --new newconfig ",
         " generate and compare; do not write (no dest)",
         "      uhdas_config_gen.py  -s ka --old config",
         " generate, compare, and write:",
         "      uhdas_config_gen.py  -s ka --new newconfig --old config",
         " ",
         " Usage for homebrewed collection of ships: ",
         " same as above, but add the following option (python module):",
         "     --shipinfo shipinfo  # or '-p shipinfo' ",
         " where 'shipinfo' has these files, ",
         " (consistent with the syntax in the 'onship' repository):",
         "     proc_defaults.py",
         "     uhdas_defaults.py",
         "     sensor_cfgs/XX_sensor_cfg.py  #XX is ship letters",
         " and  shipnames.py, consistent with pycurrents/adcp/shipnames.py",
         " ",
         "   choose one ship abbreviation from:",
         shipletters,
         "",
         "",
         ],
         '\n')

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)


    parser.add_option("-n",  "--new", dest="newconfig",
       default=None,
       help="create a new uhdas configuration directory")

    parser.add_option("-o",  "--old", dest="oldconfig",
       default=None,
       help="compare with original uhdas configuration directory")

    parser.add_option("-s",  "--shipkey", dest="shipkey",
       default=None,
       help="ship abbreviation")

    parser.add_option("-p",  "--shipinfo", dest="shipinfo",
       default=None,
       help="directory with ship configuration (compatible with 'onship')")


    ## NOTE you cannot choose "--shipinfo onship" because
    ## shipnames.py is in pycurrents/adcp
    ## see pycurrents/adcp/uhdas_defaults for more info.

    (options, args) = parser.parse_args()

    if not options.shipkey:
        print(usage)
        raise IOError('MUST specify ship letters')

    newconfig = options.newconfig
    oldconfig   = options.oldconfig
    shipkey   = options.shipkey

    # make new directory
    if newconfig:
        make_configdir(newconfig)


    # make proc_cfg.py
    P=Proc_Gen(shipkey=shipkey, shipinfo=options.shipinfo)

    if newconfig:
        procfile = os.path.join(newconfig, 'proc_cfg.py')
        P.write(procfile)
    # make uhdas_cfg.py
    U=Uhdas_Gen(shipkey=shipkey, shipinfo = options.shipinfo)
    if newconfig:
        uhdasfile = os.path.join(newconfig, 'uhdas_cfg.py')
        U.write(uhdasfile)


    S=Sensor_Gen(shipkey=shipkey, shipinfo=options.shipinfo)

    print('------- sensor_cfg.py (commentary) ----------')
    S.check_vals()
    if newconfig:
        sensorfile = os.path.join(newconfig, 'sensor_cfg.py')
        S.write(sensorfile)

    # compare with original
    if oldconfig :
        if not os.path.exists(oldconfig):
            print('oldconfig "%s" does not exist for comparison' % (oldconfig))
            sys.exit()
        else:
            osensor, oproc = get_configs(oldconfig)
            print('\n------- proc_cfg.py (differences) ----------')
            compare_cfg(oproc, P.pdict, exclude = list(U.pdict.keys()))
            print('------- uhdas_cfg.py (differences) ----------')
            compare_cfg(oproc, U.pdict, exclude = list(P.pdict.keys()))
            print('------- sensor_cfg.py (differences) ----------')
            print('\nADCPS')
            compare_cfg(osensor.adcpdict, S.adcpdict)
            print('\nserial logging sensors')
            compare_cfg(osensor.sensordict, S.sensordict)

    # make instrument cmd files
    CG=Cmdfile_Gen(shipkey,
                   shipinfo=options.shipinfo)

    if oldconfig and os.path.exists(oldconfig):
        CG.compare_all_dicts(os.path.join(oldconfig, 'cmdfiles'))

    if newconfig:
        # write bash_paths
        f=open(os.path.join(newconfig, 'bash_paths'),'w')
        f.write(uhdas_defaults.bash_paths)
        f.close()
        # write cmd files
        newcmd_dir = os.path.join(newconfig, 'cmdfiles')
        CG.write_cmd(newcmd_dir)  # puts files here
        # write some readme's
        f=open(os.path.join(newconfig, 'README.txt'),'w')
        f.write(uhdas_defaults.config_readme)
        f.close()
        f=open(os.path.join(newcmd_dir, 'README.txt'),'w')
        f.write(uhdas_defaults.cmd_readme)
        f.close

        f=open(os.path.join(newconfig, '.hgignore'),'w')
        f.write(uhdas_defaults.hgignore)
        f.close()

        # repositorize it
        cmdlist = ['cd %s' % (newconfig),
                   'hg init',
                   'hg addremove',
                   'hg commit -u adcp -m "new repository"',
                   'cd ..',
                   ]
        longcmd = ';'.join(cmdlist)
        #
        print('\nAbout to make Mercurial repository...\n')
        status, output = commands.getstatusoutput(longcmd)
        if status:
            outlist.append(status)
            print('failed to make mercurial repository (%s)' % (newconfig))
            print(output)
        else:
            print('ran these commands')
            print('\n     '.join(cmdlist))
