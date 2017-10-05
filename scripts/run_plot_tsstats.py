#!/usr/bin/env python

### Specifically for UHDAS underway processing
## proc_cfg.py, uhdas_cfg.py
#
# plot TSERIES_DIFFSTATS from codas processing

## running out of time: additions should include
# copying data to www/figures/data
# making plots; matplotlib if possible
# copying figures to www/figures (or no_figure.png)
# add to thumbnails

from __future__ import print_function
import matplotlib
matplotlib.use('Agg')

import numpy as np
np.seterr(invalid='ignore')

import sys, os
from optparse import OptionParser

from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup

from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.tseries_diffstats import get_data, plot_data, stats_str

# Use a return code to tell repeater whether there was a problem.
retcode = 0


usage = '\n'.join(["usage: %prog -d procdirname  ",
                   " eg.",
                   "  run_plot_tsstats.py   nb150  ",
                   "  run_plot_tsstats.py   os38bb",
                   "",
                   " ==> figures go to web site, text goes to daily_report"])

def write_stats_string(sstr, cid):
    statsfile = os.path.join(cid['daily_dir'], '%s_tsstats.txt' % (cid['procdirname']))
    open(statsfile,'w').write(sstr)

def save_stats_fig(fig, cid):
    pngfile = os.path.join(cid['web_figdir'],
                                 '%s_tsstats' % (cid['procdirname']))
    thumb_pngfile = os.path.join(cid['web_figdir'], 'thumbnails',
                                 '%s_tsstats_thumb' % (cid['procdirname']))
    destlist = [pngfile, thumb_pngfile]
    savepngs(destlist, dpi=[90, 40], fig=fig)


if __name__ == '__main__':

    if len(sys.argv) != 2:
        print(usage)
        sys.exit()

    if '--help' in sys.argv:
        print(usage)
        sys.exit()

    parser = OptionParser()
    (options, args) = parser.parse_args()


    procdirname = args[0]
    # test options
    if procdirname[0:2] not in ('os', 'nb', 'wh', 'bb'):
        LF.error('Use UHDAS processing dir, e.g., nb150, os38bb, os38nb')
        sys.exit(1)

    cruiseinfo = procsetup()
    ## make an instance;  copy of the dictionary for formatting
    cid = cruiseinfo.__dict__.copy()


    # test more
    if procdirname not in cid['procdirnames']:
        LF.error('processing directory %s not available', procdirname)
        sys.exit(2)


    scriptutils.addHandlers(LF, procdirname, 'plot_tsstats')
    LF.info('procdirname: %s', procdirname)


    ## update dictionary for formatting....
    cid['procdirname'] = procdirname

    dbname = os.path.join(cid['procdirbase'], cid['procdirname'], 'adcpdb',
                      cid['dbname'])
    ndays = -1.5
    data = get_data(dbname, ndays=ndays)


    try:
        titlestr = "%s %s" % (cid['cruiseid'], procdirname)
        fig, ax, sd = plot_data(data, titlestr=titlestr)
        save_stats_fig(fig, cid)
    except:
        LF.exception('cannot save timeseries stats figure')


    try:
        sstr = stats_str(sd)
        write_stats_string(sstr, cid)
    except:
        LF.exception('cannot write timeseries stats for daily report')

