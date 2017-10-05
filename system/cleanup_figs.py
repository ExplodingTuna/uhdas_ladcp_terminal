'''
Clean up figures and data when logging starts and stops.

This must be called with the actual cruise directory
as the first command-line argument; the symlink in /home/adcp
will not suffice, because it may not exist when this is
run.

The second argument must be either "not_logging" or "no_figure".
'''


# JH 2004/01/12


import os, sys, glob, shutil
import logging
logging.basicConfig()
L = logging.getLogger()



def cleanup(cruiseinfo, fn_base):
    try:
        for pname in cruiseinfo.procdirnames:
            globstr = os.path.join(cruiseinfo.web_datadir, '%s*.mat' % (pname))
            for filename in glob.glob(globstr):
                os.remove(filename)
            globstr = os.path.join(cruiseinfo.web_datadir, '%s*.asc' % (pname))
            for filename in glob.glob(globstr):
                os.remove(filename)
            globstr = os.path.join(cruiseinfo.web_datadir, '%s*.nc' % (pname))
            for filename in glob.glob(globstr):
                os.remove(filename)
    except:
        L.exception("deleting *.mat, *.asc, *.nc")

    try:
        # overwrite /home/adcp/www/figures/*.png
        nofig = os.path.join(cruiseinfo.html_dir, fn_base + '.png')
        for pname in cruiseinfo.procdirnames:
            globstr = os.path.join(cruiseinfo.web_figdir, '%s*.png' % (pname))
            for filename in glob.glob(globstr):
                shutil.copy(nofig, filename)
                os.chmod(filename, 0o644)  # hmph
        globstr = os.path.join(cruiseinfo.web_figdir, '*dh.png')
        for filename in glob.glob(globstr):
            shutil.copy(nofig, filename)
            os.chmod(filename, 0o644)  # hmph
        for prefix in ('beam', 'kt'):
            globstr = os.path.join(cruiseinfo.web_figdir, '%s*.png' % (prefix,))
            for filename in glob.glob(globstr):
                shutil.copy(nofig, filename)
                os.chmod(filename, 0o644)  # hmph

    except:
        L.exception("overwriting *.png")


    try:
        # (2b) overwrite /home/adcp/www/figures/thumbnails/*.png
        nofig = os.path.join(cruiseinfo.html_dir, fn_base + '_thumb.png')
        for pname in cruiseinfo.procdirnames:
            globstr = os.path.join(cruiseinfo.web_figdir, 'thumbnails',
                                   '%s*.png' % (pname))
            for filename in glob.glob(globstr):
                shutil.copy(nofig, filename)
                os.chmod(filename, 0o644)  # hmph
        globstr = os.path.join(cruiseinfo.web_figdir, 'thumbnails',
                                '*dh_thumb.png')
        for filename in glob.glob(globstr):
            shutil.copy(nofig, filename)
            os.chmod(filename, 0o644)  # hmph
        for prefix in ('beam', 'kt'):
            globstr = os.path.join(cruiseinfo.web_figdir, 'thumbnails',
                                   '%s*.png' % (prefix,))
            for filename in glob.glob(globstr):
                shutil.copy(nofig, filename)
                os.chmod(filename, 0o644)  # hmph
    except:
        L.exception("overwriting _thumb*.png")


def main():
    from uhdas.uhdas.procsetup import procsetup
    cruiseinfo = procsetup(cruisedir = sys.argv[1])
    fn_base = sys.argv[2] # 'not_logging' or 'no_figure'
    cleanup(cruiseinfo, fn_base)

