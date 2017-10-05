'''
Script for processing the tarballs mailed home by UHDAS
systems.  Companion script check_mail.py downloads the
email and unpacks the attachments.

This script makes vector and contour plots and puts
them in a directory tree that we serve via http. The base
directory for this must be supplied on the command line
or as an environment variable, UHDAS_HTMLBASE.  Normal
procedure is to set this in bash_env, which is sourced
by .bashrc, and must be explicitly sourced by the command
line specified to cron.

This script can also be used to reprocess the most recent
tarfile in all ship directories; this is to facilitate
development of the plotting routines.


run as

process_tarball.py shipletters tarball
'''

## also contains function to process shore status email

import sys, time, os, os.path, glob, shutil
from optparse import OptionParser

usage = '\n'.join(['Run from $HOME.',
                   '',
                   'usage: '
                   ''
                   'python process_tarball.py shipletters tarballpath',
                   'python process_tarball.py [options]',
                   'eg: ',
                   'cd; python process_tarball.py --all_ships',
                   ])

import logging, logging.handlers
L = logging.getLogger()
L.setLevel(logging.DEBUG)
formatter = logging.Formatter(
      '%(asctime)s %(levelname)-8s %(name)-12s %(message)s')

homedir = os.environ['HOME']
try:
    logbasename = os.path.join(homedir, 'log', 'tar')
except:
    raise IOError(usage)

handler = logging.handlers.RotatingFileHandler(logbasename, 'a', 100000, 3)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
L.addHandler(handler)

## ---new, for python plotting
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pycurrents.adcp.dataplotter as adp
from pycurrents.adcp import reader
from pycurrents.plot.mpltools import savepngs
##-------------

from uhdas.system import tarball_web

from onship import shipnames

def get_cruisename(emailfile):
    if os.path.exists(emailfile):
        alllines = open(emailfile,'r').readlines()
        status = "unknown"
        current_cruise = "not determined"
        for line in alllines[:20]:
            if 'Current cruise' in line:
                parts = line.split(':')[-1].split()
                current_cruise = parts[0]
                if 'is logging' in line:
                    status = 'logging'
                else:
                    status = '(not logging)'
    return current_cruise, status


#-------------
def process_shorestatus(emailtuples):
    '''
    tuple is ((shipkey, emailpath),(shipkey, emailpath),(shipkey, emailpath),)
    '''
    try:
        htmlbase = os.environ['UHDAS_HTMLBASE']
    except KeyError:
        L.exception("htmlbase not specified")
    passed=[]
    failed=[]
    for  shipkey, emailpath in emailtuples:
        htmlshipdir = os.path.join(htmlbase, shipnames.shipdirs[shipkey])
        reportdir = os.path.join(htmlshipdir, 'daily_report')
        try:
            alllines=open(emailpath,'r').readlines()   # skip To, From, Subject
            lines = []
            for line in alllines:
                ok = True
                for header in ['@', 'Original', 'Subject', 'Date', 'From', 'To']:
                    if header in line:
                        ok = False
                if ok:
                    lines.append(line)
            open(os.path.join(reportdir, 'shorestatus.txt'),'w').write(''.join(lines))
            passed.append(emailpath)
        except:
            failed.append(emailpath)
            pass
    return passed, failed


def main():
    shipkeys = dict([(value, key) for key, value in shipnames.shipdirs.items()])

    parser = OptionParser(usage)
    parser.add_option("-H", "--htmlbase", dest="htmlbase",
                  help="base directory for UHDAS shore web")
    parser.add_option("--all_ships", dest="all_ships", action="store_true",
                  help="redo last tarfile for all ships. run from uhdas $HOME")
    options, args = parser.parse_args()

    if options.htmlbase:
        htmlbase = options.htmlbase
    else:
        try:
            htmlbase = os.environ['UHDAS_HTMLBASE']
        except KeyError:
            L.error("htmlbase must be given as an option or via environment")
            sys.exit(-1)
    if not os.path.isdir(htmlbase):
        os.mkdir(htmlbase)

    if options.all_ships:
        arglist = []
        dirs = os.listdir('ships')
        for dir in dirs:
            tfd = os.path.join('ships', dir, 'tarfiles')
            if os.path.isdir(tfd):
                tf = glob.glob(os.path.join(tfd, '*.tar.gz'))
                tf.sort()
                arglist.append((shipkeys[dir], tf[-1]))
        L.debug("arglist: %s", arglist)
    else:
        arglist = [args]

    startdir = os.getcwd()
    for args in arglist:
        L.info("Starting, args = %s", args)
        timestamp = time.strftime('%Y-%j-%H%M', time.gmtime(time.time()))
        shipkey, tarfile = args
        shipname = shipnames.shipnames[shipkey]

        homeshipdir = os.path.join(homedir, 'ships', shipnames.shipdirs[shipkey])
        workdir = os.path.join(homeshipdir, 'working')
        archivedir = os.path.join(homeshipdir, 'png_archive')
        htmlshipdir = os.path.join(htmlbase, shipnames.shipdirs[shipkey])
        reportdir = os.path.join(htmlshipdir, 'daily_report')
        htmldir = os.path.join(htmlshipdir, 'figs')
        for dir in (homeshipdir, workdir, htmlshipdir, reportdir, htmldir, archivedir):
            if not os.path.isdir(dir):
                os.mkdir(dir)

        # clear out working directory
        cmd = '/bin/rm -f %(workdir)s/*' % vars()
        L.debug(cmd)
        os.system(cmd)

        # extract tarball into working directory
        cmd = 'tar -C %(workdir)s -xzf %(tarfile)s' % vars()
        L.debug(cmd)
        os.system(cmd)

        # clear out old png files from web page
        cmd = '/bin/rm -f %(htmldir)s/*.png' % vars()   # do not remove the index.html
        L.debug(cmd)
        os.system(cmd)

        # clear out old files from report dor
        cmd = '/bin/rm -f %(reportdir)s/*' % vars()
        L.debug(cmd)
        os.system(cmd)

        # extract specific files into report dir: first all txt files
        cmd = 'tar --wildcards -C %(reportdir)s -xzf %(tarfile)s \*.txt' % vars()
        L.debug(cmd)
        os.system(cmd)

        # extract specific files into report dir: all png files (so far, only posmv*png)
        cmd = 'tar --wildcards -C %(reportdir)s -xzf %(tarfile)s \*.png' % vars()
        L.debug(cmd)
        os.system(cmd)

        #then extract other specific files
        cmd = 'tar -C %(reportdir)s -xzf %(tarfile)s proc_cfg.py' % vars()
        L.debug(cmd)
        os.system(cmd)
        cmd = 'tar -C %(reportdir)s -xzf %(tarfile)s sensor_cfg.py' % vars()
        L.debug(cmd)
        os.system(cmd)




        os.chdir(workdir)

        #2012/08/15: I think all ships are using *vect_u.npy now
        vecubins = glob.glob('*vect_u.bin')
        vecunpys = glob.glob('*vect_u.npy')
        if vecunpys:
            using_npy = True
            sonars = [v.split('_')[0] for v in vecunpys]
        else:
            using_npy = False
            sonars = [v.split('_')[0] for v in vecubins]
        L.debug('using_npy is %s, procbase list: %s', using_npy, sonars)

        for res in ['','H']:
            h=tarball_web.html_str(sonars, shipkey, res)
            if res == 'H':
                open(os.path.join(htmldir, 'indexH.html'),'w').write(h)
            else:
                open(os.path.join(htmldir, 'index.html'),'w').write(h)

        # get email text
        email_textfiles = (os.path.join(workdir, 'shorestatus.txt'),
                           os.path.join(workdir, 'status_str.txt'))
        if os.path.exists(email_textfiles[0]):
            cruisename, cstatus = get_cruisename(email_textfiles[0])
        elif os.path.exists(email_textfiles[1]):
            cruisename, cstatus = get_cruisename(email_textfiles[1])
        else:
            cruisename = "OLD CRUISE"
            cstatus = "unknown"
        L.info("cruisename is %s" % (cruisename))

        for procbase in sonars:
            for res in ['', 'H']: # original, Hires (1 day)
                L.info('procbase is %s', procbase)
                if res == 'H':
                    L.info('processing Hires data')
                try:
                    vect_image = procbase+'_vect'+res+'.png'
                    cont_image = procbase+'_cont'+res+'.png'
                    html_vect_image = os.path.join(htmldir, vect_image)
                    html_cont_image = os.path.join(htmldir, cont_image)
                    ## thumbnails
                    vect_thumb_image = procbase+'_vect_thumb'+res+'.png'
                    cont_thumb_image = procbase+'_cont_thumb'+res+'.png'
                    html_vect_thumb_image = os.path.join(htmldir, vect_thumb_image)
                    html_cont_thumb_image = os.path.join(htmldir, cont_thumb_image)


                    ## new, Oct 29 2007 ----------
                    if res=='H':
                        datafile=procbase+'_cont'
                    else:
                        datafile=procbase+'_vect'
                    data  =  reader.get_adata(datafile, read_fcn='uvztbin')
                    topofig = plt.figure()
                    ax = topofig.add_subplot(1,1,1)
                    adp.simple_vecplot(data, ax=ax) # top bin, no regrid
                    topofig.text(.5,.96, procbase, ha='center')
                    topofig.text(.05,.96, cruisename, ha='left')
                    adp.annotate_last_time(ax.figure, data['dday'],
                              data['yearbase'],
                              annotate_str = '%s: last time ' % (procbase,))

                    savenames = ['vect'+res, 'vect_thumb'+res]
                    dpi = [120, 60]
                    savepngs(savenames, dpi=dpi, fig=topofig)
                    plt.close(topofig)

                    dpuv = adp.ADataPlotter(data, zname = 'uv', x='dday', y='dep',
                              cmapname='ob_vel',
                              yearbase = time.localtime()[0],
                              ylim = [data['dep'][-1], 0])

                    dpuv.cuvplot(title_base = procbase, nxticks=None,
                                 major_minor=(.5,.1))
                    adp.annotate_last_time(dpuv.cuv_fig, data['dday'],
                              data['yearbase'],
                              annotate_str = '%s: last time ' % (procbase,))

                    dpuv.cuv_fig.text(.02,.03, cruisename, ha='left')

                    savenames = ['cont'+res, 'cont_thumb'+res]
                    dpuv.save(savenames, dpi=dpi)
                    plt.close(dpuv.cuv_fig)
                    ## -------------------

                    ## vector -- fullsize png
                    dest = os.path.join(archivedir,
                              timestamp + procbase +'_vect'+res+'.png')
                    shutil.copyfile('vect'+res+'.png', dest)


                    ## contour -- fullsize png
                    dest = os.path.join(archivedir,
                              timestamp + procbase +'_cont'+res+'.png')
                    shutil.copyfile('cont'+res+'.png', dest)

                    try:
                        os.remove(html_vect_image)
                        os.remove(html_cont_image)
                    except:
                        pass
                    shutil.copyfile('vect'+res+'.png', html_vect_image)
                    os.chmod(html_vect_image, 0o664)
                    shutil.copyfile('cont'+res+'.png', html_cont_image)
                    os.chmod(html_cont_image, 0o664)
                    L.debug('copied vector and contour images to %s and %s',
                               html_vect_image, html_cont_image)

                    ## do not copy to archive (worthless, as presently implemented)

                    try:
                        os.remove(html_vect_thumb_image)
                        os.remove(html_cont_thumb_image)
                    except:
                        pass
                    shutil.copyfile('vect_thumb'+res+'.png',
                                    html_vect_thumb_image)
                    os.chmod(html_vect_image, 0o664)
                    shutil.copyfile('cont_thumb'+res+'.png',
                                    html_cont_thumb_image)
                    os.chmod(html_cont_image, 0o664)
                except:
                    L.exception('processing %s', procbase)
                    ##raise  ## temporary, while debugging


        # remove processing of *_stats.txt


        os.chdir(startdir)

    L.info("Exiting")

