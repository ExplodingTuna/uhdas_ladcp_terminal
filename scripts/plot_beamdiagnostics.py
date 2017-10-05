#!/usr/bin/env python
'''
First cut at making diagnostic plots for beam-wise information
Specifically for UHDAS underway processing; uses procsetup_onship.py
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

from optparse import OptionParser
import sys, os, shutil
from uhdas.uhdas.procsetup import procsetup

# Set up the root logger before importing any of our own code.
from uhdas.system import scriptutils
LF = scriptutils.getLogger()
from pycurrents.adcp.adcp_specs import Sonar

####### get options

usage = '\n'.join(["usage: %prog  -d procdirname  -p all [--savefigs] [--webcopy] ",
         "   eg.",
         "       plot_beamdiagnostics.py -d nb150  --savefigs",
         "       plot_beamdiagnostics.py -d os75nb  -p velocity",
         "                                                             ",
         "            switch   : defaults   [options]:",
         "           -------     -------    --------------",
         "      [-p]  plottype : all        ['all' ,  'velocity',",
         "                                            'scattering',",
         "                                            'amplitude',",
         "                                            'correlation'],",
         "      [-m]  minutes   : 90        integer>0",
         "      [-d]  procdirname : None    ['wh300', 'os75bb',...]",
         "            savefigs : False      [True, False]",
         "            webcopy  : False      [(only if 'live')]",
         "                             " ])

parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
                  help="processing directory name, eg. nb150, os75nb")

parser.add_option("-m",  "--minutes", dest="minutes",
                  help="number of minutes to plot")

parser.add_option("--savefigs", action="store_true", dest="savefigs",
                  help="make png files",
                  default = False)

parser.add_option("--webcopy", action="store_true", dest="webcopy",
                  help="copy to uhdas web location (use with 'adcp')",
                  default = False)

parser.add_option("-p",  "--plottype", dest="plottype",
                  help='\n'.join(["plots to make: ",
                                  "'all','scattering'",
                                  "'velocity', 'amplitude', 'correlation' "]),
                  default='all')


(options, args) = parser.parse_args()

if options.minutes is None:
    options.minutes = 90

if options.procdirname == None:
    print(usage)
    LF.error('ERROR must choose processing directory name')
    sys.exit(1)
procdirname = options.procdirname

all_plottypes = [ 'velocity', 'amplitude', 'scattering', 'correlation']

if options.plottype in all_plottypes:
    makeplots = [options.plottype,]
elif options.plottype != 'all':
    print(usage)
    LF.error("ERROR  'plottype' choice incorrect")
    sys.exit(1)
if options.plottype == 'all':
    makeplots = all_plottypes

## test options
if procdirname[0:2] not in ('os', 'nb', 'wh', 'bb'):
    LF.error('Use UHDAS processing dir, e.g., nb150, os38bb, os38nb')
    sys.exit(1)



def copyfig(fnames, figdir):
    '''
    specific to UHDAS live
    '''
    shutil.copy(fnames[0], figdir)
    shutil.copy(fnames[1], os.path.join(figdir, 'thumbnails'))


## proceed
import matplotlib
if options.savefigs == True:
    matplotlib.use('Agg')
else:
    import matplotlib.pylab as plt
from pycurrents.adcp.adcp_diagnostics import BeamDiagnostics


# current cruise

cruiseinfo = procsetup()

## a hack:
if options.procdirname[:2] == 'wh':
    beamangle=20
else:
    beamangle=30

sonar=Sonar(options.procdirname)

BD = BeamDiagnostics(cruiseinfo.cruisedir, sonar=options.procdirname,
                     ducerdepth=cruiseinfo.ducer_depth[sonar.instname],
                     beamangle=int(beamangle))


for plottype in makeplots:
    outfiles = BD.get_plot_recent(plottype, minutes=int(options.minutes),
                                  savefigs=options.savefigs)
    if options.savefigs and options.webcopy:
        copyfig(outfiles, cruiseinfo.web_figdir)


if options.savefigs is False:
    plt.show()
