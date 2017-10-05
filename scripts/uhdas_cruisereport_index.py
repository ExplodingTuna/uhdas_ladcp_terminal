#!/usr/bin/env python
'''
use case:

# remake index.html to have COMMENTs for linking prev,next

for cruise in `\ls | grep RB`
  do
  uhdas_report_generator.py -u $cruise --full_report --remake_index
done

# then make the overall index.html

 uhdas_cruisereport_index.py -rlt "Oleander UHDAS summaries"


'''


from __future__ import print_function

from pycurrents.system import logutils, Bunch
import subprocess

import os, glob

import logging, logging.handlers
from pycurrents.system import logutils
log = logutils.getLogger(__file__)
import argparse


from uhdas.system.uhdas_report_subs import  HTML_page


def make_html_entry(filename, text):
    '''
    return simple link to a file
    '''
    h="<a href='%s' >  %s</a>" % (filename, text)
    return h


def add_links_to_page(indexfile, prev_file=None, next_file=None):
    dots = rel_path(indexfile)
    if prev_file:
        prevlink = make_html_entry(os.path.join(dots, prev_file), '(previous)')
    else:
        prevlink=''
    if next_file:
        nextlink = make_html_entry(os.path.join(dots, next_file), '(next)')
    else:
        nextlink=''
    prev_next_link =  '<br> %s &nbsp &nbsp %s <br><br> \n\n' % (prevlink, nextlink)
    back_to_index = make_html_entry(os.path.join(dots, 'index.html'), '(back to list)')
    #
    lines = open(indexfile, 'rb').read().split('\n')
    for ii in range(len(lines)):
        if 'INDEX_LINKS' in lines[ii]:
            lines[ii] = prev_next_link + '<br>' + back_to_index + '<br>'
    return lines




def rel_path(this_file):
    '''
    construct the relative path from thisfile back to root
    '''
    backdots = []
    if os.path.isdir(os.path.realpath(this_file)):
        dirname = this_file
    else:
        dirname = os.path.split(this_file)[0]
    for part in os.path.relpath(dirname).split(os.sep):
        backdots.append('..')
    return os.sep.join(backdots)


if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description="make a simple index.html for a group of cruise reports")


    parser.add_argument('-t', '--title',
                        default='UHDAS automated cruise reports',
                        help='ship name, or title for index.html')


    parser.add_argument('-p', '--prefix',
                        default='None',
                        help='shipletters: only grab these cruises for index.html')


    parser.add_argument('-r', '--reverse',
                        action='store_true',
                        default=False,
                        help='reverse order of links: oldest at the top')

    parser.add_argument('-l', '--add_links',
                        action='store_true',
                        default=False,
                        help='add links at top and bottom pointing to neighboring index.html.  stores in "index_linked.html"')

    opts = parser.parse_args()

    if opts.prefix is None:
        prefix = '*'
    else:
        prefix = opts.prefix

    ## this only works if all the cruises were named with the same prefix, eg Autopilot.
    cruise_glob1 = '%s*' % (prefix)
    cruise_glob2 = '*/%s*' % (prefix)

    indexes1 = glob.glob(os.path.join(cruise_glob1, 'reports', 'index.html'))
    indexes2 = glob.glob(os.path.join(cruise_glob2, 'reports', 'index.html'))
    indexes = indexes1 + indexes2

    indexes.sort()

    html_list = []
    HP_ = HTML_page(opts.title, report_dir='./')  # dummy

    if opts.add_links:
        log.info('writing %d files with links to prev,next' % (len(indexes)))

    for inum in range(len(indexes)):
        index = indexes[inum]
        parts = index.split(os.sep)
        report_dir = os.path.split(index)[0]
        if len(indexes) > 1:
            if opts.add_links:
                if opts.reverse:
                    step = -1
                else:
                    step = +1
                index_link = os.path.join(report_dir,  "index_links.html")
                if inum  == 0:
                    prev_file = None
                else:
                    prev_file = os.path.join(os.path.split(indexes[inum + step])[0], "index_links.html")
                if inum == len(indexes)-1:
                    next_file = None
                else:
                    next_file = os.path.join(os.path.split(indexes[inum - step])[0], "index_links.html")

                # rewrite index to have links
                i2lines = add_links_to_page(index, prev_file, next_file)
                open(index_link, 'wb').write('\n'.join(i2lines))
            else:
                index_link = index
        else:
            index_link = index

        cruisename = os.path.join(*parts[:-2])

        cmd = 'du -sh %s' % (report_dir)
        proc=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        # every line needs one of these
        HP = HTML_page(cruisename, report_dir=report_dir)
        if len(stderr) == 0:
            size, rdir = stdout.strip().split()
            rtext='&nbsp &nbsp summary report &nbsp  &nbsp  &nbsp (%s) ' % (size)
        else:
            rtext=" summary data report"
        html_list.append(HP.newline + rtext + HP.space + HP.make_html_entry(index_link, cruisename)  )


    if opts.reverse:
        html_list = html_list[::-1]

    hstr = HP_.make_html_index(html_list, opts.title )
    open('index.html', 'wb').write(hstr)
