#!/usr/bin/env python

### Specifically for UHDAS underway processing
## proc_cfg.py, uhdas_cfg.py
#
# get statistics from recent attitude data; run plots


## running out of time: additions should include
# copying data to www/figures/data
# making plots; matplotlib if possible
# copying figures to www/figures (or no_figure.png)
# add to thumbnails

from __future__ import division
import matplotlib
matplotlib.use('Agg')

import numpy as np
np.seterr(invalid='ignore')

import sys, os, shutil, glob
from optparse import OptionParser

from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup
from pycurrents.adcp.hbin_diagnostics import HbinDiagnostics

## make an instance;  copy of the dictionary for formatting
cruiseinfo = procsetup()
cid = cruiseinfo.__dict__.copy()

####### get options

usage = '\n'.join(["usage: %prog --hcorr_inst instrument --plotdh --printstats  ",
         "   eg.",
         "       %prog --hcorr_inst posmv  --plotdh --printstats"])
parser = OptionParser(usage)
parser.add_option("",  "--hcorr_inst", dest="hcorr_inst",
       help="heading correction device, 'posmv', 'ashtech', 'seapath'")

## plotting options
parser.add_option("", "--plotdh", action="store_true", dest="plotdh",
        help="extract raw data and plot", default=False)

## statistics
parser.add_option("", "--printstats", action="store_true", dest="printstats",
        help="extract data and print statistics", default=False)

(options, args) = parser.parse_args()

if not (options.hcorr_inst):
    LF.error('must choose a heading device')
    sys.exit(1)

scriptutils.addHandlers(LF, options.hcorr_inst, 'hcorrstats')

LF.info('Starting run_hcorrstats.py')

cruiseid = cruiseinfo.cruiseid
hdict = {}
for inst_msg in cruiseinfo.hdg_inst_msgs:
    hdict[inst_msg[0]] = inst_msg[1]
hcorr_inst = options.hcorr_inst
hdg_inst = cruiseinfo.hdg_inst
hcorr_msg = hdict[hcorr_inst]
hdg_msg = hdict[hdg_inst]
hdg_inst_msg = '_'.join([hdg_inst, hdg_msg])
hcorr_inst_msg =  '_'.join([hcorr_inst, hcorr_msg])
if options.hcorr_inst == cruiseinfo.hcorr_inst:
    hcorr_gap_fill = cruiseinfo.hcorr_gap_fill
else:
    hcorr_gap_fill = 0.0
gbin = os.path.join(cruiseinfo.cruisedir, 'gbin')
yearbase = cruiseinfo.yearbase

outfilebase = '%s_%sdh'   % (hcorr_inst, hdg_inst)
statfile = '%s_stats.txt'   % (outfilebase)
pngfile =  './%s.png'       % (outfilebase)
png_generic = 'heading.png' # generic name, for gui to look at
png_thumb ='./%s_thumb.png' % (outfilebase)

if len(glob.glob(os.path.join(gbin, 'heading','*.hbin'))) == 0:
    LF.info('no hbin files for run_hcorrstats.py')
    sys.exit()

#######################################################
## (1) plot figure

if options.plotdh:
    LF.info('about to plot figure for %s\n', hcorr_inst)

        # used to plot the file the statistics were made from;
        # now plot 4 hrs of raw
    try:
        titlestring = "%s: (%s-%s) statistics" % (cruiseid, hcorr_inst, hdg_inst)
        H=HbinDiagnostics(gbin=gbin,
                          yearbase=yearbase)

        H.get_segment(-4/24.)
        H.get_hcorr(hdg_inst_msg, hcorr_inst_msg)
        H.plot_hcorr(titlestring=titlestring,
                     hcorr_gap_fill = hcorr_gap_fill,
                     outfilename=[pngfile, png_generic, png_thumb],
                     dpi=[70, 70, 30])

        ## copy files
        destfile = os.path.join(cruiseinfo.web_figdir, pngfile)
        dest_generic = os.path.join(cruiseinfo.web_figdir, png_generic)
        thumb_destfile = os.path.join(cruiseinfo.web_figdir,
                                      'thumbnails', png_thumb)

        shutil.copy(png_generic, dest_generic)
        LF.info('copying %s to %s\n' % (pngfile, dest_generic))
        shutil.copy(pngfile, destfile)
        LF.info('copying %s to %s\n' % (pngfile, destfile))
        shutil.copy(png_thumb, thumb_destfile)
        LF.info('copying %s to %s\n' % (png_thumb, thumb_destfile))

    except:
        destfile = os.path.join(cruiseinfo.web_figdir, 'no_figure.png')
        dest_generic = os.path.join(cruiseinfo.web_figdir, 'no_figure.png')
        thumb_destfile = os.path.join(cruiseinfo.web_figdir,
                                  'thumbnails', 'no_figure_thumb.png')

        shutil.copy(pngfile, destfile)
        shutil.copy(pngfile, dest_generic)
        shutil.copy(png_thumb, thumb_destfile)

        LF.exception('could not make heading correction plot')


#######################################################
## (2) print statistics (for daily_report)

if options.printstats:
    LF.info('about to print stats for %s\n', hcorr_inst)

    try:

        H=HbinDiagnostics(gbin=gbin,
                          yearbase=yearbase)
        winsecs=300 #statistics window
        H.get_segment(-1) #1 day
        H.get_hcorr(hdg_inst_msg, hcorr_inst_msg)
        H.hcorr_stats(winsecs=winsecs)

        if len(H.dh) == 0:
            slist = ['no %s data\n' % (hcorr_inst,)]
        elif H.ensnumgood == 0:
            slist = ['no good %s data out of %d (%dsec) ensembles\n' % (
                    hcorr_inst,  H.ensnumtotal,
                    np.round(winsecs))]
        else:

            slist = H.print_stats_summary()
            slist.append('')

        ## copy files
        statsfile = '%s_%s_pystats.txt' % (hcorr_inst, hdg_inst)
        dailyfile = os.path.join(cruiseinfo.daily_dir, statsfile)

        open(dailyfile,'w').write('\n'.join(slist))
        open(statsfile,'w').write('\n'.join(slist))

    except:
        LF.exception('could not get %s stats\n' % (hcorr_inst,))


LF.info('Finished run_hcorrstats.py')
