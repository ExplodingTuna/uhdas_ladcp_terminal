'''
Clean up and archive figure files after a cruise.

This must be called with the actual cruise directory
as the only command-line argument; the symlink in /home/adcp
will not suffice, because it may not exist when this is
run.
'''

# JH 2004/01/12


import os, sys, glob, shutil
import logging
logging.basicConfig()
L = logging.getLogger()

def cleanup(cruiseinfo):
    for pname in cruiseinfo.procdirnames:
        pngdir = os.path.join(cruiseinfo.web_pngarchive, pname)
        pngtdir = os.path.join(pngdir, 'thumbnails')
        if os.path.exists(pngdir):
            newdir = os.path.join(cruiseinfo.cruisedir, 'proc', pname, 'png_archive')
            newtdir = os.path.join(newdir, 'thumbnails')
            if not os.path.exists(newdir):
                try:
                    os.mkdir(newdir)
                    os.mkdir(newtdir)
                except:
                    L.exception('could not make directory %s' % (newdir,))

            for new, png in ((newdir, pngdir), (newtdir, pngtdir)):
                if os.path.exists(new):
                    for filename in glob.glob(os.path.join(png, '*png')):
                        try:
                            L.info('copying %s to %s' % (filename, new))
                            shutil.copy2(filename, new)
                            os.remove(filename)
                        except:
                            L.exception('could not copy png_archive file')

                    for filename in glob.glob(os.path.join(pngdir, '*html')):
                        try:
                            L.info('copying %s to %s' % (filename, new))
                            shutil.copy2(filename, new)
                            os.remove(filename)
                        except:
                            L.exception('could not copy png_archive html files')

def main():
    from uhdas.uhdas.procsetup import procsetup
    cruiseinfo = procsetup(cruisedir = sys.argv[1])
    cleanup(cruiseinfo)

