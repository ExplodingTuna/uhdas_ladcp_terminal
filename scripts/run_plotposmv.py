#!/usr/bin/env python

'''
specialty posmv plotter: nhours back from now, plot every posmv acc_heading

   run_plotposmv.py [-n HOURS]

'''
from __future__ import division

import os, glob, shutil
from optparse import OptionParser

import numpy as np
import matplotlib as mpl
mpl.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from uhdas.system import scriptutils
LF = scriptutils.getLogger()
LF.info('Starting run_plotposmv.py')

from uhdas.uhdas.procsetup import procsetup

from pycurrents.file.binfile_n import BinfileSet
from pycurrents.plot.mpltools import savepngs


cruiseinfo = procsetup()
## make an instance;  copy of the dictionary for formatting
cid = cruiseinfo.__dict__.copy()



def get_pmv(uhdasdir, att_dev=None, nhours=2):
    '''
    return last nhours of posmv rbin data
    (or choose a different device with pmv messages)
    '''
    #
    uhdasdir = '/home/data/current_cruise'
    globstr= os.path.join(uhdasdir, 'rbin', att_dev, '*pmv.rbin')
    filelist = glob.glob(globstr)
    if len(filelist) == 0:
        LF.critical('no files found with %s' % (globstr))
        return None
    filelist.sort()
    nfiles = int(nhours // 2 + 1)
    pmv = BinfileSet(filelist[-nfiles:], cname='u_dday')
    last_dday = pmv.ends[pmv.cname][-1]
    pmv.set_range([last_dday - nhours / 24.0, last_dday])
    return pmv


def plot_posmv(pmv, head_acc_cutoff=0.2):
    graybox= dict(boxstyle="round", ec=(.2,.2,.2), fc=(.5,.5,.5),alpha=.2)
    fig,ax=plt.subplots(nrows=3, sharex=True)
#   make the file smaller
    plt.rc(('lines','text'), antialiased=False)
    aa=ax[0]
    aa.plot(pmv.dday, pmv.acc_heading,'r.-')
    aa.set_ylim(0,60)
    aa.xaxis.set_visible(False)
    # zoom on 2 hours, under 10 units
    #  top plot
    pp= np.ma.masked_where(pmv.acc_heading > 10, pmv.acc_heading)
    aa.plot(pmv.dday, pp,'k.')
    aa.text(.05,.85,'all', size=10, color='r', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    aa.text(.05,.05,'zoom below', size=10, color='k', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    # second plot
    aa=ax[1]
    aa.plot(pmv.dday, pmv.acc_heading,'k.-')
    aa.set_ylim(0,10)
    aa.xaxis.set_visible(False)
    aa.text(.05,.05,'zoom below', size=12, color='m', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    aa.text(.05,.85,'zoomed', size=12, color='k', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    ## zoom on 2deg
    pp= np.ma.masked_where(pp > 2, pp)
    aa.plot(pmv.dday, pp,'m.')
    #bottom plot
    aa=ax[2]
    aa.plot(pmv.dday, pmv.acc_heading,'m.-')
    aa.set_ylim(0,2)
    aa.text(.05,.85,'zoomed', size=14, color='m', weight='bold',
             bbox=graybox, transform=aa.transAxes)
#
    pp= np.ma.masked_where(pp > head_acc_cutoff, pp)
    aa.plot(pmv.dday, pp,'c.')
#
    aa.text(.05,.05,'good', size=10, color='c', weight='bold',
             bbox=graybox, transform=aa.transAxes)
    ax[0].set_title('POSMV "heading accuracy"')
#
    ax[-1].set_xlabel('decimal day')
    ax[-1].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))

#
    return fig


if __name__ == '__main__':

    parser = OptionParser()


    parser.add_option("-n", "--nhours", dest="nhours",
                      default = 1.5,
                      help="plot last N hours")

    parser.add_option("-d", "--device", dest="att_dev",
                      default = 'posmv',
                      help="choose 'posmv' or other pmv device")

    (options, args) = parser.parse_args()

    figdir = cruiseinfo.web_figdir
    thumbdir = os.path.join(figdir, 'thumbnails')

    outfilebase = '%s_qc' % (options.att_dev)
    tbase = outfilebase + '_thumb'

    if cruiseinfo.cruiseid:
        pmv = get_pmv(cruiseinfo.cruisedir,
                      att_dev=options.att_dev,
                      nhours = float(options.nhours))
        if pmv is not None:
            fig=plot_posmv(pmv)
            fig.text(.5,.95, '%s %s quality' % (cruiseinfo.cruiseid,  options.att_dev),
                      ha='center')

            destlist=[os.path.join(figdir, outfilebase),
                      os.path.join(thumbdir, tbase)]
            savepngs(destlist, dpi=[90, 40], fig=fig)
            plt.close(fig)

            shutil.copy(os.path.join(figdir, outfilebase+'.png'), cruiseinfo.daily_dir)



