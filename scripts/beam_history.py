#!/usr/bin/env python

'''
First cut at making diagnostic plots for beam-wise information
 -- historical plots, last 24 files.
Specifically for UHDAS underway processing
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

from optparse import OptionParser
import sys, os, shutil

import numpy as np
np.seterr(invalid='ignore')

# Set up the root logger before importing any of our own code.
from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup

from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.system import pathops


####### get options

usage = '\n'.join(["usage: beam_history.py  -d procdirname  -p all [--savefigs] [--webcopy]  ",
         "   eg.",
                   "   beam_history.py -d nb150  --savefigs",
         "             beam_history.py -d os75nb  -p vel",
         "                                                             ",
         "            switch   : defaults[options]:",
         "           -------     -------- --------------",
         "     [-p] --plottype : all     ['all', 'cor', 'vel']",
         "     [-d] --procdirname : None ['wh300', 'nb150', 'os75bb',...]",
         "     [-c] --cruisedir: None    [(for source 'adcp')]",
         "          --savefigs : False   [True, False]",
         "          --printstats: False  [stdout, or file (for source 'live')]",
         "          --webcopy  : False   [(for source 'live')]",
         "                             " ])

parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
                  help=" instrument + pingtype, eg. nb150, wh300, os75nb")

parser.add_option("-c",  "--cruisedir", dest="cruisedir",
                  help="cruise directory (has 'raw' subdirectory in it)",
                  default = None)

parser.add_option("--savefigs", action="store_true", dest="savefigs",
                  help="make png files",
                  default = False)

parser.add_option("--webcopy", action="store_true", dest="webcopy",
                  help="copy to uhdas web location (use with 'adcp')",
                  default = False)

parser.add_option("--printstats", action="store_true", dest="printstats",
                  help="print stats (to stdout, or to daily_report, if 'live'",
                  default = False)

parser.add_option("-p",  "--plottype", dest="plottype",
                  help="plots to make, 'all', 'cor', 'vel''",
                  default='all')


(options, args) = parser.parse_args()



if options.procdirname == None:
    print(usage)
    LF.error('ERROR must choose processing directory name')
    sys.exit(1)
procdirname = options.procdirname

makeplots = ['cor', 'vel']
if options.plottype in makeplots:
    makeplots = [options.plottype,]
elif options.plottype != 'all':
    print(usage)
    LF.error("ERROR  'plottype' choice incorrect")
    sys.exit(1)


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



def copy_to_archive(dlist, daynum, png_archivedir):
    for pngfile in dlist[0::2]:
        fpath, fname = os.path.split(pngfile)
        froot, fext  = os.path.splitext(fname)
        dday_filename = os.path.join(png_archivedir,
                                    '%03d_%s%s' % (daynum, froot, fext))

        if os.path.exists(dday_filename):
            os.remove(dday_filename)
        shutil.copy2(pngfile,  dday_filename)
        os.chmod(dday_filename, 0o644)
        LF.debug('copying %s to %s' % (pngfile, dday_filename))


## proceed
import matplotlib
if options.savefigs == True:
    matplotlib.use('Agg')

from pycurrents.adcp.adcp_diagnostics import BeamDiagnostics
from pycurrents.plot.mpltools import savepngs

cruiseinfo = procsetup()


if options.cruisedir is None:
    BD = BeamDiagnostics(cruiseinfo.cruisedir,
                         sonar=options.procdirname,
                         get_plot_recent=False)
else:
    BD = BeamDiagnostics(options.cruisedir,
                         sonar=options.procdirname,
                         get_plot_recent=False)

sonar=Sonar(options.procdirname)

filelist=pathops.make_filelist(os.path.join(BD.cruisedir,
                                            'raw', sonar.instname, '*raw'))

if len(filelist) == 0:
    raise ValueError('no *.raw files in %s' % (BD.cruisedir,))


stats_dict = BD.beam_stats_byfile(filelist, yearbase=cruiseinfo.yearbase)
daynum= np.floor(stats_dict['enddd'][-1])


if 'cor' in makeplots:
    BD.plot_corstats_byfile(stats_dict)

    if options.savefigs:
        outfilebase = '%s_cor_history' % (procdirname,)
        outfiles = [outfilebase+'.png',
                    outfilebase+'_thumb.png']
        savepngs(outfiles , [90, 40], BD.cor_fig )
        LF.debug('Made beam history: %s', outfiles)
        if options.webcopy:
            webdir = cruiseinfo.web_figdir
            copyfig(outfiles, webdir)
            png_archivedir = os.path.join(webdir, 'png_archive', procdirname)
            copy_to_archive(outfiles, daynum, png_archivedir)


if 'vel' in makeplots:
    BD.plot_velPG_byfile(stats_dict)

    if options.savefigs:
        outfilebase = '%s_bin_history' % (procdirname,)
        outfiles = [outfilebase+'.png',
                    outfilebase+'_thumb.png']
        savepngs(outfiles , [90, 40], BD.velPG_fig)
        print('saving file to %s' % (outfiles[0],))
        if options.webcopy:
            webdir = cruiseinfo.web_figdir
            copyfig(outfiles, webdir)
            png_archivedir = os.path.join(webdir, 'png_archive', procdirname)
            copy_to_archive(outfiles, daynum, png_archivedir)

if options.savefigs is False:
    import matplotlib.pylab as plt
    plt.show()


if options.printstats is True:
    statsfile = os.path.join( cruiseinfo.daily_dir,
                                  procdirname+'_stats.txt')

    stats_dict = BD.beam_stats_byfile(filelist, maxnum = 12)
    #shallow
    header, s1list = BD.stats_strings(stats_dict, beamnum=1, binnum=5)
    header, s2list = BD.stats_strings(stats_dict, beamnum=2, binnum=5)
    header, s3list = BD.stats_strings(stats_dict, beamnum=3, binnum=5)
    header, s4list = BD.stats_strings(stats_dict, beamnum=4, binnum=5)
    #deep
    header, d1list = BD.stats_strings(stats_dict, beamnum=1, binnum=-5)
    header, d2list = BD.stats_strings(stats_dict, beamnum=2, binnum=-5)
    header, d3list = BD.stats_strings(stats_dict, beamnum=3, binnum=-5)
    header, d4list = BD.stats_strings(stats_dict, beamnum=4, binnum=-5)


    strlist = ['# ' + procdirname]
    strlist.append(header)

    for ii in np.arange(len(stats_dict['enddd'])):
        strlist.append(s1list[ii]) #shallow, beam 1,2,3,4
        strlist.append(s2list[ii])
        strlist.append(s3list[ii])
        strlist.append(s4list[ii])
        strlist.append(d1list[ii]) # deep, beam 1,2,3,4
        strlist.append(d2list[ii])
        strlist.append(d3list[ii])
        strlist.append(d4list[ii])
    statsstr = '\n'.join(strlist)

    if statsfile is None:
        print(statsstr)
    else:
        open(statsfile,'w').write(statsstr)
        LF.info('wrote stats to %s' % (statsfile,))
