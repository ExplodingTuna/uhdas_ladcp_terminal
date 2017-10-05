#!/usr/bin/env python

### Specifically for UHDAS
### Must edit procsetup_onship.py for each particular installation
#
## run autovect (shallow layer, with temperature)
## run autocont (3 days, for contours against time, lon, lat)
##
## reads data from web_datadir
## puts ".eps" web_figdir; converts  "*.eps" to *.png
## changes *.ps  and *.png to 644
#
# J.H 9/2004
#
# NOTES: for wh300, os150, nb150, os75, os38
#        must add logic for other instruments
#

from __future__ import division
from future import standard_library
standard_library.install_hooks()

import sys, os, shutil
from optparse import OptionParser

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from uhdas.system import scriptutils
LF = scriptutils.getLogger()
LF.info('Starting run_3dayplots.py')

from uhdas.uhdas.procsetup import procsetup
from pycurrents.plot.mpltools import savepngs
from pycurrents.plot.html_table import Convention_to_Html

np.seterr(invalid='ignore')


####### get options

usage = '\n'.join(["usage: %prog -d PROCESSING_DIR",
                     "   eg.",
                     "       %prog -d wh300",
                     "       %prog -d wh300 ",
                     "       %prog -d nb150",
                     "       %prog -d os38bb",
                     "       %prog -d os38nb"])
parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
            help="processing directory name, eg. wh300, nb150, os38bb, os38nb")

(options, args) = parser.parse_args()

if options.procdirname == None:
    LF.error('must choose processing directory name')
    sys.exit(1)
procdirname = options.procdirname


if procdirname[0:2] not in ('os', 'nb', 'wh', 'bb'):
    LF.error('Use UHDAS processing dir, e.g., nb150, os38bb, os38nb')
    sys.exit(1)

cruiseinfo = procsetup()
pingtype = cruiseinfo.pingtype[procdirname]

## make an instance;  copy of the dictionary for formatting
cid = cruiseinfo.__dict__.copy()


# test more
if procdirname not in cid['procdirnames']:
    LF.error('processing directory %s not available in this cruise', procdirname)
    sys.exit(1)

scriptutils.addHandlers(LF, procdirname, '3dayplots')


archive_dir = os.path.join(cruiseinfo.web_pngarchive, procdirname)
if not os.path.exists(archive_dir):
    LF.error('%s does not exist\n', archive_dir)
    sys.exit(1)

## new: copy info to /home/data/current_cruise/proc/sonar/png_archive
##      as well as /home/adcp/www/figures/png_archive  5/2012
proc_archive = os.path.join(cruiseinfo.cruisedir,'proc', procdirname, 'png_archive')
cid['proc_archive'] = proc_archive
if not os.path.exists(proc_archive):
    os.mkdir(proc_archive)
    LF.debug('making png_archive dir for %s' %  procdirname)

instname = cruiseinfo.instname[procdirname]
LF.debug('\n'.join(['making 3day plots for %s' %  procdirname,
       'instrument name is %s' % instname,
       'pingtype is %s'  % pingtype]))


## update dictionary for formatting....
cid['procdirname'] = procdirname


filebases = [#'%s_shallow'  % (procdirname,),
            '%s_ddaycont' % (procdirname,),
            '%s_loncont'  % (procdirname,),
            '%s_latcont'  % (procdirname,)]

for filebase in filebases:
    epsfile = '%s.eps' % (filebase)
    pngfile = '%s.png' % (filebase)
    if os.path.exists(epsfile):
        os.remove(epsfile)
    if os.path.exists(pngfile):
        os.remove(pngfile)

###--------------- save 1 day of highres data as ascii -----------------
#  This is for later use when we switch the shore-based plotting
#  to glue together these shorter files.

# for codas database reader
from pycurrents import codas
from pycurrents.adcp.quick_codas import binmaxdepth
from pycurrents.adcp.reader import timegrid_cdb
from pycurrents.adcp import dataplotter
from pycurrents.file.binfile_n import binfile_n


def save_data_sample_db(cid, prefix, dest_dir, ndays):
    if prefix == '_cont':
        dinfo = get_dbinfo(cid, ndays)
        data = get_condata_db(dinfo)
    else:
        dinfo = get_dbinfo(cid, ndays)
        data = get_vecdata_db(dinfo)
#
    xytT = np.zeros((len(data['dday']), 4), dtype=np.float_)
    xytT[:,0] = data['dday']
    xytT[:,1] = data['lon'].filled(np.nan)
    xytT[:,2] = data['lat'].filled(np.nan)
    xytT[:,3] = data['tr_temp'].filled(np.nan)
#
    out_base = os.path.join(dest_dir, cid['procdirname']+prefix)
    binfile_n(out_base+'_xytT.bin', mode='w',
                columns=['dday', 'lon', 'lat', 'T']).write(xytT)
    dep = data['dep']

    if len(dep) == 0:
        dep = [0.0,]

    zYR = np.zeros((len(dep), 2), dtype=np.float_)
    zYR[:,0] = dep
    zYR[0,1] = data['yearbase']
    binfile_n(out_base+'_zYR.bin', mode='w',
                columns=['zc', 'yearbase']).write(zYR)
#

    if len(data['u']) == 0:
        data['u'] = 0.0*data['dday']
        data['v'] = 0.0*data['dday']

    u = (data['u']*100).astype(np.int16).filled(32767)
    v = (data['v']*100).astype(np.int16).filled(32767)
    np.save(out_base+'_u', u)
    np.save(out_base+'_v', v)


###--------------- vector figure and files-----------------------------------

def get_dbinfo(cid, ndays=-1.5):
    '''get_dbinfo(cid)
       returns dictionary with keys
            - 'deltaz'   (about 2* nominal resolution)
            - 'zstart'   (uses top_plotbin)
            - 'data'     last ndays of data, flags applied
    '''
    dbname = os.path.join(cid['procdirbase'], cid['procdirname'], 'adcpdb',
                      cid['dbname'])
    dinfo = {}
    #
    # vertical grid size for contouring
    zsteps = {'bb600'   : 2,
              'wh300'   : 2,
              'wh600'   : 2,
              'wh1200'  : 2,
              'bb300'   : 2,
              'bb150'   : 5,
              'os150bb' : 4,
              'os150nb' : 8,
              'nb150'   : 15,
              'nb300'   : 4,
              'hr140'   : 10,
              'os75bb'  : 10,
              'os75nb'  : 20,
              'hr50'    : 20,
              'os38bb'  : 20,
              'os38nb'  : 30}
    dinfo['deltaz'] = zsteps[cid['procdirname']]
    dinfo['zstart'] = binmaxdepth(dbname,
                                    cid['top_plotbin'][cid['procdirname']])

    data = codas.get_profiles(dbname, ndays=ndays, nbins=128)
    nbins = np.max(data.lgb)

    if nbins > 0:
        dinfo['data'] = codas.get_profiles(dbname, ndays=ndays, nbins=nbins)
    else:
        dinfo['data'] = data
    return dinfo

##--------


def get_vecdata_db(dinfo, deltat=1/24.): # 1 hour, roughly 6 bins
    gdata = timegrid_cdb(dinfo['data'], deltat=deltat,
                         deltaz=2*dinfo['deltaz'])
    return gdata


def vecplot(dinfo, procdirname, dest_dir, dest_suffix, cruiseid, deltat=1/24.):
    destfile = os.path.join(dest_dir, procdirname+dest_suffix+'.png')
    thumb_destfile = os.path.join(dest_dir, 'thumbnails',
                                    procdirname+dest_suffix+'_thumb.png')
    destlist = [destfile, thumb_destfile]
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    dataplotter.vecplot(dinfo['data'],
        refbins = [1,2,3,4], # will average everything it can find
        deltaz = dinfo['deltaz'],
        deltat = deltat,
        ax=ax)
    fig.text(.5,.95,'%s %s' % (cruiseid, procdirname),ha='center')
    dataplotter.annotate_last_time(ax.figure, dinfo['data']['dday'],
                       dinfo['data']['yearbase'],
                       annotate_str = '%s: last time ' % (procdirname,))

    #ax.figure.set_facecolor([1,0,.3])

    savepngs(destlist, dpi=[90, 40], fig=fig)
    plt.close(fig)
    for d in destlist:
        os.chmod(destfile, 0o644)
    return destlist ,int(np.floor(max(dinfo['data']['dday'])))

##--------

def get_condata_db(dinfo, deltat=.25/24): #15 minutes, roughly 2 bins
    gdata = timegrid_cdb(dinfo['data'],  deltat=deltat,
                                         deltaz=dinfo['deltaz'])
    return gdata

def conplots(data, procdirname, dest_dir, dest_suffix, cruiseid):
    dday = data['dday']
    lat = data['lat']
    lon = data['lon']

    if len(data['dep']) == 0:
        data['dep']=[0.0,]
    if len(data['u']) == 0:
        data['u'] = 0.0*dday
        data['v'] = 0.0*dday

    ng = min(100, len(lat))
    xgrids = {}
    xgrids['dday'] = None
    xgrids['lat'] = np.linspace(lat.min(), lat.max(), ng)
    xgrids['lon'] = np.linspace(lon.min(), lon.max(), ng)
    dgrids = {}
    dgrids['dday'] = None
    dgrids['lat'] = dgrids['lon'] = data['dep'][:]

    xlims = {}
    xlims['dday'] = None
    xlims['lat'] = [min(xgrids['lat']), max(xgrids['lat'])]
    xlims['lon'] = [min(xgrids['lon']), max(xgrids['lon'])]

    dlist = []


    for xvar, xgrid in xgrids.items():
        fn = ''.join([procdirname, '_%scont'%xvar, dest_suffix, '.png'])
        destfile = os.path.join(dest_dir, fn)
        fn = ''.join([procdirname, '_%scont'%xvar, dest_suffix, '_thumb.png'])
        thumb_destfile = os.path.join(dest_dir, 'thumbnails', fn)
        destlist = [destfile, thumb_destfile]

        adp = dataplotter.ADataPlotter(data, zname='uv', x=xvar, y='dep',
                             xlim=xlims[xvar],
                             ylim=[data['dep'][-1], 0])
        adp.cuvplot(title_base=procdirname,
                            xout=xgrid, yout=dgrids[xvar])

        #adp.cuv_fig.set_facecolor([1,0,.3])
        adp.cuv_fig.text(.05,.98,'%s %s' % (cruiseid, procdirname), ha='left')


        dataplotter.annotate_last_time(adp.cuv_fig, data['dday'],
                                       data['yearbase'],
                         annotate_str = '%s: last time ' % (procdirname,))

        adp.save(destlist, dpi=[90, 40])
        dlist.extend(destlist)

    for d in dlist:
        os.chmod(destfile, 0o644)
    return dlist ,int(np.floor(max(dday)))


def copy_to_archive(dlist, daynum, arch_name='web'):
    for pngfile in dlist[0::2]:
        fpath, fname = os.path.split(pngfile)
        froot, fext  = os.path.splitext(fname)
        if arch_name == 'web':
            arch_dir = os.path.join(cid['web_pngarchive'], procdirname)
        elif arch_name == 'proc':
            arch_dir = cid['proc_archive']
        else:
            LF.exception('arch_name %s not supported' % (arch_name))
        dday_filename = os.path.join(arch_dir,  '%03d_%s%s' % (daynum, froot, fext))

        if os.path.exists(dday_filename):
            os.remove(dday_filename)
        shutil.copy2(pngfile,  dday_filename)
        os.chmod(dday_filename, 0o644)
        LF.debug('copying %s to %s' % (pngfile, dday_filename))


#-------------------

try:
    save_data_sample_db(cid, '_cont', cruiseinfo.daily_dir, -1.2)
    save_data_sample_db(cid, '_vect', cruiseinfo.daily_dir, -3.0)
except:
    LF.exception('cannot write codasdb data samples for daily_report')

#-----------
## for plots, get 1.5 days
dinfo = get_dbinfo(cid, ndays=-1.5)

try:
    # now 30min between vectors
    dlist, daynum = vecplot(dinfo, procdirname, cruiseinfo.web_figdir,
                            '_shallow', cruiseinfo.cruiseid, deltat=0.5/24)
    LF.debug('Made vecplots: %s', dlist)
    copy_to_archive(dlist, daynum, arch_name='web')
    copy_to_archive(dlist, daynum, arch_name='proc')

except:
    LF.exception('cannot make 3-day shallow plot\n')
    # do not exit; try contour plots


#-------------

try:
    data = get_condata_db(dinfo)
    dlist, daynum = conplots(data, procdirname, cruiseinfo.web_figdir,'', cruiseinfo.cruiseid)
    LF.debug('Made conplots: %s', dlist)
    copy_to_archive(dlist, daynum, arch_name='web')
    copy_to_archive(dlist, daynum, arch_name='proc')
except:
    LF.exception('cannot make 3-day contour plots\n')


#--------------
for arch_name in [archive_dir, proc_archive]:
    try:
        Convention_to_Html(figdir = arch_name,
                       convention = 'uhdas',
                       columns = ['shallow','ddaycont','latcont','loncont'],
                       verbose = False)
    except:
        LF.exception('cannot make index.html\n')
