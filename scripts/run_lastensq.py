#!/usr/bin/env python

### Specifically for UHDAS underway processing
## proc_cfg.py, uhdas_cfg.py, sensor_cfg.py
#
# (1) update gbin files for specified instrument
# (2) do the codas average (load/[*.cmd, *.bin])
# (3) make a last-5minute plot from #2
#
# J.H 9/2004;
# JH jan 2011 python averaging, no matlab engine

from __future__ import division
from future import standard_library
standard_library.install_hooks()

import logging, logging.handlers
import sys, os
from optparse import OptionParser
import time

import numpy as np
np.seterr(invalid='ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Set up the root logger before importing any of our own code.
from uhdas.system import scriptutils
LF = scriptutils.getLogger()

from uhdas.uhdas.procsetup import procsetup

from pycurrents.adcp.quick_adcp import get_processor
from pycurrents.adcp import dataplotter

from pycurrents.adcp.adcp_specs import amp_clim
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.adcp_specs import ping_editparams
from pycurrents.adcp.quick_setup import quickFatalError
from pycurrents.adcp.gbin import Gbinner
from pycurrents.plot.mpltools import savepngs
from pycurrents.system.misc import Cachefile, Bunch
from pycurrents.codas import to_day

# Use a return code to tell repeater whether there was a problem.
retcode = 0


####### get options

usage = '\n'.join(["usage: %prog -d procdirname  ",
         " eg.",
         "  %prog -d nb150  --update_pygbin --averages --plotens_mpl",
         "  %prog -d os38bb --update_pygbin --averages --plotens_mpl --ktsdir",
         "  %prog -d os38bb --plotens_mpl --ktsdir --vecprof"])
parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
       help="processing directory name, eg. nb150, wh300, os38bb, os38nb")

parser.add_option("-q", "--dday_bailout", dest="dday_bailout",
       help="used for simulating incremental processing: quit at this dday")


parser.add_option("--update_pygbin", action="store_true", dest="update_pygbin",
        help="update gbin for this procdirname", default=False)
parser.add_option("-a", "--averages", action="store_true", dest="mk_averages",
        help="make ens* averages for this procdirname", default=False)
parser.add_option("--plotens_mpl", action="store_true", dest="plotens_mpl",
        help="use mpl to plot last 5-minute average for this procdirname",
        default=False)
parser.add_option("--ktsdir", action="store_true", dest="ktsdir",
        help="also make the kts+direction bridge plots for this instrument",
        default=False)
parser.add_option("--kt_vecprof", action="store_true", dest="kt_vecprof",
        help="make 2-panel  vector-profile and surface vector for this instrument",
        default=False)

parser.add_option("--pingwarnN",  dest="pingwarnN",
        help="show a warning on uvamp plot if numpings is less than this",
        default=None)


(options, args) = parser.parse_args()

if not (options.mk_averages or
        options.update_pygbin or
        options.plotens_mpl or
        options.ktsdir  or
        options.vecprof or
        options.kt_vecprof):
    LF.error('''must choose to DO somthing:
            update_pygbin, averages, and/or make some plots (plotens_mpl, ktsdir, vecprof, kt_vecprof)''')
    sys.exit(1)

if options.procdirname == None:
    LF.error('must choose processing directory name')
    sys.exit(1)
procdirname = options.procdirname

## test options
if procdirname[0:2] not in ('os', 'nb', 'wh', 'bb'):
    LF.error('Use UHDAS processing dir, e.g., nb150, os38bb, os38nb')
    sys.exit(1)

scriptutils.addHandlers(LF, procdirname, 'lastensq')

LF.info('procdirname: %s', procdirname)

#--------------
def initialize_dbinfo(cachefile, cdict, comment):
    '''
    initialize 'dbinfo.txt' for quick_adcp.py
    '''
    if os.path.exists(cachefile) is False or (
        os.path.exists(cachefile) is True and
        os.path.getsize(cachefile)==0):

        # first time through; must have these
        for name in ['yearbase', 'sonar']:
            if cdict[name] is None:
                msg = 'must set yearbase and sonar in run_lastensq.py'
                raise quickFatalError(msg)

        init_dict = Bunch(cdict)
        sonar = Sonar(cdict['sonar'])
        for name in ['model', 'frequency', 'pingtype', 'instname']:
            init_dict[name] = getattr(sonar, name)
        dbinfo = Cachefile(cachefile, contents=comment)
        dbinfo.init(init_dict)

#---------------

def now_calc_fig(dest_dir, moretext):
    '''
    make a figure (and thumbnail) with the present computer timestamp
    '''

    flist = ['calctime.png', 'calctime_thumb.png']
    destlist = []
    destlist.append(os.path.join(dest_dir,  flist[0]))
    destlist.append(os.path.join(dest_dir, 'thumbnails', flist[1]))
    ff=plt.figure(figsize=(8,3))
    ax=ff.add_subplot(111)
    tt=time.gmtime()
    dday = to_day(tt[0], tt[0], tt[1], tt[2], tt[3], tt[4], tt[5])
    dataplotter.annotate_last_time(ff, [dday,], tt[0],
                annotate_str = 'last calculation (PC clock)\n%s' % (moretext,),
                       style='middle')
    ax.xaxis.set_ticks([])
    ax.yaxis.set_ticks([])
    ax.set_frame_on(False)
    ff.set_facecolor([226/255., 247/255., 247/255.])
    plt.draw()
    savepngs(destlist, [70,40], ff)

#--------------

try:   ## try/except for the entire body of the script
    cruiseinfo = procsetup()

    instname =  cruiseinfo.instname[procdirname]

    cid = Bunch(cruiseinfo.__dict__.copy())
    ## make an instance;  copy of the dictionary for formatting

    if options.update_pygbin:
        LF.debug('Updating pygbin files for %s', procdirname)
        gbindirbase = os.path.join(cruiseinfo.cruisedir, 'gbin')

        if hasattr(cruiseinfo, 'acc_heading_cutoff'):
            rbin_edit_params=dict(acc_heading_cutoff=cruiseinfo.acc_heading_cutoff)
        else:
            rbin_edit_params = {}
        gb = Gbinner(cruisedir=cruiseinfo.cruisedir,
                     sonar=procdirname,
                     config=cruiseinfo,
                     gbin = gbindirbase,
                     timeinst = cruiseinfo.pos_inst,
                     msg = cruiseinfo.pos_msg,
                     rbin_edit_params=rbin_edit_params )

        gb(update=True)

    # test more
    if procdirname not in cid['procdirnames']:
        LF.error('processing directory %s not available in this cruise',
                                                                procdirname)
        sys.exit(1)
    ## local dictionary for formatting  (use vars() instead???)
    ldict = {}
    ldict['proc_engine']     = 'python'
    ldict['sonar']           = procdirname
    ldict['yearbase']        = cruiseinfo.yearbase
    ldict['cruisename']      = cruiseinfo.cruiseid

    ldict['progdir']         = cid['progdir']
    ldict['verbose']         = 1
    ldict['ens_len']         = cruiseinfo.enslength[procdirname]

    # phasing this out:
    if instname in cid.max_search_depth.keys():
        ldict['max_search_depth']  = max_search_depth=cid.max_search_depth[instname]
    # this is preferred
    if procdirname in cid.max_search_depth.keys():
        ldict['max_search_depth']  = max_search_depth=cid.max_search_depth[procdirname]

    sonar = Sonar(procdirname)

    ldict['cfgpath']=os.path.join(cruiseinfo.procdirbase, procdirname, 'config')
    ldict['loaddir']=os.path.join(cruiseinfo.procdirbase, procdirname, 'load')

    # if proc_cfg.py has pgmin for procdirname, use that.
    try:
        ldict['pgmin'] = cid.pgmin[procdirname]
    except:
        pass


    #adding badbeam 2012/07
    # if proc_cfg.py has badbeam for procdirname, use that.
    try:
        badbeam = cid.badbeam[procdirname] # beam 1,2,3,4
    except:
        badbeam = None
    if badbeam is None:
        ibadbeam = None
    else:
        ibadbeam = badbeam - 1  #zero-based


    ## adding new parameters 2012/10/31

    try:
        # for printing q_py.cnt
        ldict['xducer_dx'] = cid.xducer_dx[instname]
        ldict['xducer_dy'] = cid.xducer_dy[instname]
        # for Pingavg
        xducerxy = (ldict['xducer_dx'] ,ldict['xducer_dy'])
    except:
        ldict['xducer_dx'] = None
        ldict['xducer_dy'] = None
        # for Pingavg
        xducerxy = None
    fixfile = '%s.gps' % (cruiseinfo.dbname)


    if options.dday_bailout is None:
        ldict['dday_bailout'] = None
    else:
        ldict['dday_bailout'] = float(options.dday_bailout)


    #Bridge plots:
    # matplotlib
    kts_dir_plot = False

    if options.ktsdir:
        kts_dir_plot = True #for Ensplot mpl plot

        ## still have to deal with matlab
        ## these values don't exist in procsetup_onship.py any more
        ## fix this chunk later; use defaults at the moment
        ldict['kt_vec_instrument'] = cid.instname[procdirname]
        ldict['kt_vec_depthstr'] =  '[50, 100]'
        ldict['kt_prof_depthstr'] =  '[0 400]'
        ldict['kt_vec_pingtype']  = cid.pingtype[procdirname]

    ldict['logfile'] = '%s_lastensq.stdout' %(procdirname,)

    ###########################################################

    proc = get_processor(ldict, warn=False)

    ###########################################################
    ## (1) update gbin files for instrument

    #######################################################
    ## (2) grab load_uhblk_tmp from quick_subs.py, and run it

    have_newdata = True  #if not told to make averages,
                         # pretend we do have new data
    if options.mk_averages:

        LF.debug('Make averages')

        LF.debug("Using Pingavg")
        from pycurrents.adcp.pingavg import Pingavg
        from pycurrents.adcp.uhdasfile import UHDAS_Tree


        soundspeed = cid.soundspeed[procdirname]
        calculate = (soundspeed == "calculate")

        instname = cid.instname[procdirname]

        if cid.hcorr_inst  == '':
            hcorr = None
        else:
            hcorr = [cid.hcorr_inst, cid.hcorr_msg, cid.hcorr_gap_fill]
        params = dict(tr_depth=cid.ducer_depth[instname],
                        head_align=cid.h_align[instname],
                        hbest=[cid.hdg_inst, cid.hdg_msg],
                        velscale=dict(scale=cid.scalefactor[procdirname],
                                      calculate=calculate,
                                      salinity=cid.salinity[procdirname],
                                      soundspeed=soundspeed)
                        )
        if hcorr:
            params['hcorr']=hcorr

        ## establish defaults; override
        edit_params = ping_editparams(sonar.instname)
        edit_params['max_search_depth'] = ldict['max_search_depth']
        dirs = UHDAS_Tree(cid.cruisedir, procdirname)

        pavg = Pingavg(datadir=dirs.rawsonar,
                        gbinsonar=dirs.gbinsonar,
                        loaddir=dirs.procsonarpath("load"),
                        calrotdir=dirs.procsonarpath("cal", "rotate"),
                        sonar=procdirname,
                        edit_params=edit_params,
                        ens_len=cid.enslength[procdirname],
                        ibadbeam = ibadbeam,
                        params=params,
                        xducerxy=xducerxy,
                        yearbase=cid.yearbase,
                        update=True,
                        )

        have_newdata = pavg.run()

        # write the beam angle...
        cachefile=dirs.procsonarpath('dbinfo.txt')
        cdict =      {'beamangle': pavg.beam_angle,
                      'sonar'    : procdirname,
                      'yearbase' : cruiseinfo.yearbase,
                      'cruisename' : cruiseinfo.cruiseid,
                      'fixfile'  : fixfile}
        if cid.hcorr_inst:
            cdict['hcorr_inst'] = cid.hcorr_inst
        else:
            cdict['hcorr_inst'] = None

        initialize_dbinfo(cachefile, cdict,
                     comment='CODAS quick_adcp.py info')

        LF.debug("Finished Pingavg; made %d averages",
                                         have_newdata)

    #######################################################
    ## (3) lastens and kt_vec plots:

    if have_newdata and (options.plotens_mpl or options.ktsdir or options.vecprof or options.kt_vecprof):
        ## should have already tested that one of the plots was requested

        LF.debug('about to make mpl last ens plot for %s\n', procdirname)
        from pycurrents.adcp.ensplot import Ensplot
        fn = os.path.join(cid.workdir, '%s_plotens_mpl.stdout' % (procdirname,))
        handler = logging.FileHandler(fn, 'w')
        handler.setLevel(logging.DEBUG)
        LF.addHandler(handler)

        read_fcn = 'npz_lastens'

        try:
            #Instantiate
            E = Ensplot(basename = 'lastens',
                    path = os.path.join('/home/adcp/cruise/proc',
                                        procdirname,'load'),
                        top_plotbin = cid.top_plotbin[procdirname],
                        procdirname = '%s' % (procdirname,),
                        pingwarnN = options.pingwarnN,
                        climdict = {'amp':amp_clim[procdirname[:2]],
                                    'vel':None, 'pg':[0,100]},
                        colorscheme='day',
                        timeout = 2* cruiseinfo.enslength[procdirname],
                        read_fcn = read_fcn,
                        altdirs = ['/home/adcp/www/figures', 
                                   '/home/adcp/www/figures/thumbnails'],
                        verbose = True)

            ## then make the plots
            # plot lastens
            # this one gets m/s on the main science web page, and kts in the diagnostics (bridge plots)
            if options.plotens_mpl:
                E.scalefactor = 'm/s'
                E(plotname = 'ampuvpg')
                outfilebase = '%s_lastens' % (procdirname,)
                E.save_fig(outfilebase, fig=E.fig1)

                E.scalefactor = 'kts'
                E(plotname = 'ampuvpg')
                outfilebase = 'ktprof_amp_lastens'
                E.save_fig(outfilebase, fig=E.fig1)

            # add vertical profile of kts/dir arrows "kt_vecprof"
            if options.kt_vecprof:
                E(plotname = 'kt_vecprof', zbin=4) #colorscheme='day'
                outfilebase = '%s_ktvecprof' % (procdirname,)
                E.save_fig(outfilebase, fig=E.fig5)

            # add lastens plot in kts
            if options.ktsdir:
                E.scalefactor='kts'

                for colorscheme in ('day','night'):
                    E.colorscheme=colorscheme
                    E.set_colors(E.colorscheme)
                    E(plotname = 'ktvec')

                    outfilebase = 'ktprof_%s' % (colorscheme,)
                    E.save_fig(outfilebase, fig=E.fig2)

                    outfilebase = 'ktvec_%s' % (colorscheme,)
                    E.save_fig(outfilebase, fig=E.fig3)

                # add text string for SCS and NOAA ships (by request)
                kts_textfile = '/home/adcp/www/figures/ktvec.txt'
                open(kts_textfile,'w').write(E.kts_text + '\n')

            LF.removeHandler(handler)
        except:
            retcode += 8
            raise

    LF.info('Finished run_lastensq for procdir %s', procdirname)
except:
    LF.exception('In body of run_lastensq.py')
    retcode += 16


try:
    now_calc_fig(cruiseinfo.web_figdir,  '\n(%s %s)\n\n' % (procdirname, 'profile plots'))
except:
    LF.exception('cannot make "last_calc" fig in lastens \n')


sys.exit(retcode)
