#!/usr/bin/env python

### Specifically for UHDAS
### Must edit proc_setup.py for each particular installation
#
# run quick_adcp.py for the inferred processing directory (or directories)
#
# J.H 9/2004
#
# NOTES: covers wh300, nb150, os75, os38 installations.
#        must add logic for other instruments
#


from __future__ import division
from future.builtins import zip
import sys, os, shutil
from optparse import OptionParser

from uhdas.system import scriptutils

LF = scriptutils.getLogger()

LF.info('Starting run_quick.py')

import matplotlib
matplotlib.use('Agg')

from pycurrents.adcp.quick_adcp import quick_adcp
from pycurrents.codas import to_datestring

from uhdas.uhdas.procsetup import procsetup

# Jan 2011 -- stripping out matlab from live processing

####### get options

usage = '\n'.join(["usage: %prog  -d procdirname",
                     "   eg.",
                     "       %prog -d nb150 ",
                     "       %prog -d wh300 ",
                     "       %prog -d os38bb",
                     "       %prog -d os38nb"])



parser = OptionParser(usage)
parser.add_option("-d",  "--procdirname", dest="procdirname",
      help="processing directory name, eg. nb150, wh300, os38bb, os38nb")

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

scriptutils.addHandlers(LF, procdirname, 'quick')

instname = cruiseinfo.instname[procdirname]
pingtype = cruiseinfo.pingtype[procdirname]


## update dictionary for formatting
ldict = {}
ldict['ens_len']         = cruiseinfo.enslength[procdirname]
ldict['yearbase']        = cruiseinfo.yearbase
ldict['configtype']      = 'python'
ldict['cruisename']      = cruiseinfo.cruiseid
ldict['dbname']          = cruiseinfo.dbname
ldict['sonar']           =  procdirname

if instname in cruiseinfo.max_search_depth.keys():
    max_search_depth  = max_search_depth=cruiseinfo.max_search_depth[instname]
    # this is preferred
if procdirname in cruiseinfo.max_search_depth.keys():
    max_search_depth  = max_search_depth=cruiseinfo.max_search_depth[procdirname]

ldict['max_search_depthstr'] = '--max_search_depth  %s' % (max_search_depth)

ldict['gbinstr']='#--update_gbin  ## python gbins: run by "run_lastensq.py" at sea'


try:
    ldict['xducer_dx'] = cruiseinfo.xducer_dx[instname]
    ldict['xducer_dy'] = cruiseinfo.xducer_dy[instname]
    ldict['xducerxy_str'] = '\n'.join([
              '#offset between transducer and gps, applied in at-sea processing',
              '# NOTE : read special instructions to change offsets',
              '#        diagnostics in cal/watertrk/guess_xducerxy.out',
              '# parameters used: ',
              '    --xducer_dx %d  ' % (ldict['xducer_dx']),
              '    --xducer_dy %d  ' % (ldict['xducer_dy']),
              ])
except:
    ldict['xducerxy_str'] = '# xducer_dx, xducer_dy not set'

ldict['tpb']                 = cid['top_plotbin'][procdirname]

if options.procdirname not in cid['procdirnames']:
    LF.error('processing directory %s not available in this cruise', procdirname)
    sys.exit(1)

## at-sea processing: if hcorr_inst is there, we want to apply it.
if cruiseinfo.hcorr_inst:
    ldict['ping_headcorr_str'] = '--ping_headcorr'
else:
    ldict['ping_headcorr_str'] = '## no heading correction device, so not using "--ping_headcorr"'


fullprocdir = os.path.join("/home/data/%s/proc" % \
                 (cruiseinfo.cruiseid), procdirname)
os.chdir(fullprocdir)

ldict['fullprocdir'] = fullprocdir

cntparts = ["--yearbase    %(yearbase)d",   #yearbase will be an integer
            "--cruisename  %(cruisename)s",
            "--configtype  %(configtype)s",
            "--sonar       %(sonar)s",
            "--dbname      %(dbname)s",
            "--datatype    uhdas ",
            "--cfgpath     %(fullprocdir)s/config ",
            "--ens_len     %(ens_len)s ",
            "%(gbinstr)s ",
            "%(xducerxy_str)s ",
            "## see config/%(cruisename)s_proc.py for other settings",
            "--skip_avg  ##  see above  ",
            "%(max_search_depthstr)s ",
            "%(ping_headcorr_str)s ",
            "--proc_engine python",
            "--refuv_smoothwin 3",
            "--incremental",
            "--find_pflags",
            "--top_plotbin  %(tpb)d",
            "--auto"]


cntparts.append("\n")

cntfile_string = "\n".join(cntparts) % ldict

## write out the control file in tmp and the processing directory
cntfile_tmp = os.path.join(cruiseinfo.workdir, '%s_qpy.cnt' % (procdirname))
cntfile_proc = os.path.join(fullprocdir, '%s_qpy.cnt' % (procdirname))

LF.debug('about to write control file parameters to %s\n', cntfile_string)

open(cntfile_tmp,'w').write(cntfile_string)
open(cntfile_proc,'w').write(cntfile_string)

try:
    quick_adcp(['--cntfile', cntfile_proc])
except:
    LF.exception('running quick_adcp')
    sys.exit(2)

## copy hcorr plot to web page     ## this could be in run_3dayplots.py
nofig = os.path.join(cruiseinfo.html_dir, 'no_figure.png')
thumb_nofig = os.path.join(cruiseinfo.html_dir, 'no_figure_thumb.png')

filebase = 'hcorr_plot'
pngfile =  '%s.png' % (filebase)
fullpngfile = os.path.join(fullprocdir, 'cal', 'rotate', pngfile)
destfile = os.path.join(cruiseinfo.web_figdir,
                        '%s_%s' % (procdirname, pngfile))

thumb_pngfile =  '%s_thumb.png' % (filebase)
fullthumb_pngfile = os.path.join(fullprocdir,  'cal', 'rotate', thumb_pngfile)
thumb_destfile = os.path.join(cruiseinfo.web_figdir, 'thumbnails',
                              '%s_%s'  % (procdirname, thumb_pngfile))


if os.path.exists(fullpngfile) and  os.path.exists(fullthumb_pngfile) :
    ## copy files
    shutil.copy(fullpngfile, destfile)
    LF.info('copying %s to %s' % (fullpngfile, destfile))
    shutil.copy(fullthumb_pngfile, thumb_destfile)
    LF.info('copying %s to %s' % (fullthumb_pngfile, thumb_destfile))

else:
    shutil.copy(nofig, destfile)
    LF.info('copying NOFIG to %s' % (destfile))
    shutil.copy(thumb_nofig, thumb_destfile)
    LF.info('copying NOFIG to %s' % (thumb_destfile))

os.chmod(destfile, 0o644)
######## end  of copy hcorr plots


###
# Copy mat files to www/data as "nb150_cont_xy", "os38bb_cont_xy", etc
for matvar in ("uv", "xy"):
    for v1, v2 in (('contour', 'cont'), ('vector', 'vect')):
        matfile = os.path.join(v1, '%s_%s.mat' % (v1, matvar))
        LF.debug('matfile is %s',matfile)

        if os.path.exists(matfile):
            destfile= os.path.join(cruiseinfo.web_datadir,
                                   '%s_%s_%s.mat' %  (procdirname, v2, matvar))
            try:
                shutil.copy2(matfile, destfile)
                LF.info('copying %s to %s\n', matfile, destfile)
                os.chmod(destfile, 0o644)
            except:
                LF.exception('cannot copy file %s to %s\n', matfile, destfile)
                sys.exit(3)

# also copy the temperature file
temfile = os.path.join('edit', '%s.tem' % (cruiseinfo.dbname))
if os.path.exists(temfile):
    destfile = os.path.join(cruiseinfo.web_datadir,
                            '%s_temp.asc' % (procdirname))
    LF.debug('about to copy file %s to %s\n', temfile, destfile)

    try:
        shutil.copy2(temfile, destfile)
        os.chmod(destfile, 0o644)
        LF.info('copying %s to %s' % (temfile, destfile))
    except:
        LF.exception('cannot copy file %s to %s\n', temfile, destfile)


# make netcdf file
try:
    from pycurrents.adcp.adcp_nc import make_nc_short
    fulldbname =  os.path.join(cruiseinfo.procdirbase,
                               procdirname,
                               'adcpdb/%s' % (cruiseinfo.dbname))
    ncfile = os.path.join(cruiseinfo.procdirbase,
                               procdirname,
                               'contour/%s.nc' % (procdirname))
    make_nc_short(fulldbname, ncfile, cruiseinfo.cruiseid, procdirname)

    if os.path.exists(ncfile):
        destfile = os.path.join(cruiseinfo.web_datadir,
                                '%s.nc' % (procdirname))
        LF.debug('about to copy netcdf file %s to %s\n', ncfile, destfile)

        try:
            shutil.copy2(ncfile, destfile)
            os.chmod(destfile, 0o644)
            LF.info('copying %s to %s' % (temfile, destfile))
        except:
            LF.exception('cannot copy file %s to %s\n', ncfile, destfile)
except:
    LF.exception('cannot make %s netcdf file\n', procdirname)



# generate some recent ping statistics
try:
    fulldbname =  os.path.join(cruiseinfo.procdirbase,
                               procdirname,
                               'adcpdb/%s' % (cruiseinfo.dbname))

    from pycurrents.codas import DB, get_profiles

    numens = 12 #one hour

    db = DB(fulldbname)
    ancil2 = db.get_variable('ANCILLARY_1')
    numpings = ancil2['pgs_sample'][-numens:]
    config1 = db.get_variable('CONFIGURATION_1')
    ens_len = config1['avg_interval'][-numens:]
    data = get_profiles(fulldbname, ddrange=-300*numens/86400.)

    yearbase = data.yearbase
    ds=[]
    for dday in data.dday[-numens:]:
        ds.append(to_datestring(yearbase, dday))

    ss = []
    ss.append('%s recent ping statistics' % (procdirname))
    for x_ddaystring,x_enslen,x_numpings in zip(ds, ens_len, numpings):
        x_secperping = x_enslen/float(x_numpings)
        ss.append('(%s) ens = %d sec, %d pings, (%3.2f sec/ping)' % (
                 x_ddaystring, x_enslen, x_numpings, x_secperping))

    ss.append('')


    try:
        destfile = os.path.join(cruiseinfo.daily_dir,
                                '%s_pingstats.txt' % (procdirname))
        open(destfile,'w').write('\n'.join(ss))

        os.chmod(destfile, 0o644)
        LF.info('generating pingstats for %s' % (procdirname))
    except:
        LF.exception('cannot generate  %s pingstats\n', procdirname)

except:
    LF.exception('cannot make %s pingstats file\n', procdirname)



LF.info('Ending quick_adcp.py')
