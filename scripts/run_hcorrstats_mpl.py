#!/usr/bin/env python

### Specifically for UHDAS underway processing
## procsetuponship.py
## CRUISEID_cfg.m, CRUISEID_proc.m, CRUISEID_disp.m
#
# get statistics from recent attitude data; run plots


## running out of time: additions should include
# copying data to www/figures/data
# making plots; matplotlib if possible
# copying figures to www/figures (or no_figure.png)
# add to thumbnails

from __future__ import division
from __future__ import print_function
import matplotlib
matplotlib.use('Agg')

import numpy as np
np.seterr(invalid='ignore')

import sys, os, shutil
from optparse import OptionParser

from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup
from pycurrents.adcp.attitude import AttitudeDiagnostics, Hcorr
from pycurrents.adcp.uhdasconfig import UhdasConfig

## make an instance;  copy of the dictionary for formatting
cruiseinfo = procsetup()
cid = cruiseinfo.__dict__.copy()

qc_kw = {}
for name in ('maxrms', 'maxbms',
             'acc_heading_cutoff',
             'acc_roll_cutoff',
             'gams_cutoff'):
    kk =  list(cid.keys())
    if name in kk:
        qc_kw[name] = cid[name]


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
hcorr_inst = options.hcorr_inst
hdg_inst = cruiseinfo.hdg_inst

outfilebase = '%s_%sdh'   % (hcorr_inst, hdg_inst)
statfile = '%s_stats.txt'   % (outfilebase)
pngfile =  './%s.png'       % (outfilebase)
png_generic = 'heading.png' # generic name, for gui to look at
png_thumb ='./%s_thumb.png' % (outfilebase)


rel=True
plot_startdd = -4/24.
stats_startdd  = -1.
stats_winsecs = 300.


# this is for at-sea processing, so we can assume a correctly-configured
## proc_cfg.py and uhdas_cfg.py exist

hdict = {}
for inst_msg in cruiseinfo.hdg_inst_msgs:
    hdict[inst_msg[0]] = inst_msg[1]

hcorr_msg = hdict[hcorr_inst]


uhdas_cfg = UhdasConfig(cfgpath='/home/adcp/config',
                        configtype='pyproc',
                        sonar=cruiseinfo.procdirnames[0],
                        uhdas_dir=cruiseinfo.cruisedir,
                        cruisename = cruiseinfo.cruiseid,
                        yearbase=cruiseinfo.yearbase)

uhdas_cfg.hcorr = [hcorr_inst,  hcorr_msg, 0]

#######################################################
## (1) plot figure

if options.plotdh:
    LF.info('about to plot figure for %s\n', hcorr_inst)

        # used to plot the file the statistics were made from;
        # now plot 4 hrs of raw
    try:
        hdg_inst = uhdas_cfg.gbin_params['hdg_inst']
        titlestring = "%s: (%s-%s) statistics" % (cruiseid, hdg_inst, hcorr_inst)

        cname='u_dday'

        AD = AttitudeDiagnostics(uhdas_cfg=uhdas_cfg,  hcorr_inst=hcorr_inst)
        msg = AD.get_rbins(cname=cname, ddrange=plot_startdd, qc_kw = qc_kw)
        if len(msg) > 0:
            print(msg)
            raise IOError(msg)

        AD.grid_att()
        AD.plot_hcorr(titlestring=titlestring,
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

    winsecs = 300.

    LF.info('about to print stats for %s\n', hcorr_inst)

    try:

        cname='u_dday'
        HH = Hcorr(uhdas_cfg=uhdas_cfg, hcorr_inst=hcorr_inst)
        msg = HH.get_rbins(cname=cname, ddrange=stats_startdd)
#        if len(msg) > 0:
#            #print msg
#            #LF.warning('%s, trying %s' % (msg, cname))
#            cname='u_dday'
#            msg = HH.get_rbins(cname=cname, ddrange=stats_startdd)
#            if len(msg) > 0:
#                print msg
#                raise IOError(msg)
#            else:
#                stats_msg = 'using u_dday'


        if len(msg) > 0:
            print(msg)
            raise IOError(msg)

        HH.grid_att()
        HH.hcorr_stats(winsecs=winsecs)

        if len(HH.dh) == 0:
            slist = ['no %s data\n' % (hcorr_inst,)]
        elif HH.ensnumgood == 0:
            slist = ['no good %s data out of %d (%dsec) ensembles\n' % (
                    hcorr_inst,  HH.ensnumtotal,
                    np.round(winsecs))]
        else:

            slist = HH.print_stats_summary()
            slist.append('')

        ## copy files
        statsfile = '%s_%s_pystats.txt' % (hcorr_inst,
                                           HH.uhdas_cfg.gbin_params['hdg_inst'])
        dailyfile = os.path.join(cruiseinfo.daily_dir, statsfile)

        open(dailyfile,'w').write('\n'.join(slist))
        open(statsfile,'w').write('\n'.join(slist))

    except:
        LF.exception('could not get %s stats\n' % (hcorr_inst,))


LF.info('Finished run_hcorrstats.py')
