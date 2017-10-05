from __future__ import division
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import object




import os, time, re, string
import numpy as np
from onship import shipnames
from pycurrents.system import Bunch
from pycurrents.system import pathops


def utcnowstr():
    return time.strftime("%Y/%m/%d %H:%M:%S UTC", time.gmtime())

def nowstr():
    return time.strftime("%Y/%m/%d %H:%M:%S HST")

#----------------
class MonitorTable(object):
    def __init__(self, shipkeys):

        self.outfile  = 'uhdas_onships_test.html'

        self.columns = ['letters', 'ship name', 'figures', 'last email', 'cruise name', 'status',
                        'daily report', 'daily email']
        self.linknames = Bunch(figs = 'figs',
                               dir = 'daily_report',
                               email = 'daily_report/shorestatus.txt')

        self.shipkeys = shipkeys
        self.shipkeys.sort()

        #---------  index.html templates ------------------

        self.doc_head = '''
        <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html>
        <head>
           <title>UHDAS monitoring</title>
        </head>
        <body>
        <br>
        <div style="text-align: center;"><big><span style="font-weight:
        bold;"> UHDAS MONITORING: <br> daily figures and status from ships </span>
        </big></div>
        '''

        self.other_links = '''
        <span style="font-weight: bold;">
        More useful information is on these pages:
        </span>

        <ul>
           <li><a href=http://currents.soest.hawaii.edu/uhdas_fromships_static.html> installation details</a> </li>
        </ul>
        '''


        self.ttable_head = '''
        <table  background-color: %s;"
          border="3" cellpadding="2" cellspacing="2">
           <tbody>
        '''

        # specify "shipdir" and "link_source"
        self.weblink = ''' "http://currents.soest.hawaii.edu/uhdas_fromships/${shipdir}/${link_source}" '''

        ## specify 'titlename'
        self.ttable_col_title = '''
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(244, 244, 244);">
        <span style="font-weight: bold;">${titlename}</span><br>
        </td>
        '''

        # specify full http "link_source" and link "name"
        self.ttable_link = '''
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(244, 244, 244);">
             <a href=${link_source}>${name}</a>
             </td>
        '''
        # (pair) specify full http "link_source" and link "name"
        self.ttable_link2 = '''
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(244, 244, 244);">
             <a href=${link_source1}>${name1}</a> ,              <a href=${link_source2}>${name2}</a>
             </td>
        '''

        ## specify "align" (left, center, right) and "text" string
        self.ttable_text = '''
        <td style="text-align: ${align}; vertical-align: middle;
                    background-color: rgb(244, 244, 244);">
                ${text}
             </td>
        '''

        self.ttable_tail = '''
           </tbody>
        </table>
        '''

        self.km_link = '''
         <p>Recent example of at-sea web site for scientists:</p>
           <a href="http://currents.soest.hawaii.edu/uhdas_fromships/kilomoana_atseaweb/index.html">Kilo Moana, 2013</a>
        '''

        self.doc_tail = '''
        </body>
        </html>
        '''


    def lines_with_dates(self,lines):
        '''
        in: list of lines, may contain dates
        out: subset which have dates
        '''
        out=[]
        timepat = r"\b\d{2,4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\b"
        for line in lines:
            matchobj = re.findall(timepat, line)
            if len(matchobj) > 0:
                out.append(line)
        return out

    def time_since_email(self, emailfile=None):
        '''
        read status_str and get
        - time of email generation (from status_str)
        - cruise status
        '''
        now_epoch = time.mktime(time.gmtime())
        secs_since = None
        current_cruise = 'NA'
        status = 'NA'

        if emailfile and os.path.exists(emailfile):
            alllines = open(emailfile,'r').readlines()
            datelines = self.lines_with_dates(alllines)
            ## strong assumption here
            emaildate = datelines[0].strip()
            email_epoch=time.mktime(time.strptime(emaildate, '%Y/%m/%d %H:%M:%S'))
            secs_since =  now_epoch - email_epoch

            for line in alllines[:20]:
                if 'Current cruise' in line:
                    parts = line.split(':')[-1].split()
                    current_cruise = parts[0]
                    if 'is logging' in line:
                        status = 'logging'
                    else:
                        status = '(not logging)'
                else:
                    if 'no cruise set' in line:
                        current_cruise = '(not set)'
                        status = ''
        tbunch = Bunch(secs_since=secs_since,
                     current_cruise=current_cruise,
                     status=status)
        return tbunch

    def format_estr(self, secs):
        if secs is None:
            return 'NA'
        days = secs/86400
        idays = np.floor(days)
        hrs = np.round(24*(days - idays))

        if idays == 0:
            s=  '<pre>%3s  %6dhr</pre>' % (' ', hrs)
        elif idays < 3:
            s = '<pre>%3dd %6dhr</pre>' % (idays, hrs)
        else:
            s = '<pre>%3dd %6s  </pre>' % (idays,' ')

        return s


    def format_str(self, text):
        if text is None:
            text = 'NA'
        tt = '<pre> ' + text + ' </pre>'
        return tt


        #-------------------------------------------------------

    def make_ttable(self):

        linkTS = string.Template(self.ttable_link)
        link2TS = string.Template(self.ttable_link2)
        textTS  = string.Template(self.ttable_text)
        webTS = string.Template(self.weblink)


        tlist = [self.doc_head]
        tlist.append(self.ttable_head % ('rgb(224, 224, 224)',))
        tlist.append(self.other_links)

        #subjects
        tlist.append('  <tr>')
        for title in self.columns:
            tlist.append(textTS.substitute(text=title, align='center'))
        tlist.append('  </tr> ')

        for shipkey in self.shipkeys:
            shipdir = shipnames.shipdirs[shipkey]

            # shipname
            tlist.append(textTS.substitute(text=shipkey, align='left'))
            tlist.append(textTS.substitute(text=shipnames.shipnames[shipkey], align='left'))


            # links: figures, report, email,
            for name in ('figs',):#   'dir', 'email'):
                weblink = webTS.substitute(shipdir=shipnames.shipdirs[shipkey], link_source=self.linknames[name])
                tlist.append(linkTS.substitute(link_source=weblink,  name=name))

            # last email, last tarball
            #
            email_dir = '/home/moli4/users/uhdas/ships/%s/emails' % (shipdir)
            try:
                last_email = pathops.make_filelist(os.path.join(email_dir, '*shorestatus.txt'))[-1]
            except:
                last_email = None
            ebunch = self.time_since_email(last_email)

            tsecstr = self.format_estr(ebunch.secs_since)
            tsecstrNBSP = tsecstr.replace(' ','&nbsp')
            tlist.append(textTS.substitute(text=tsecstrNBSP, align='right'))

            cbunch = Bunch()
            pretext = self.format_str(ebunch.current_cruise)
            cbunch.cruisename = textTS.substitute(text=pretext.replace(' ','&nbsp'), align='right')
            pretext = self.format_str(ebunch.status)
            cbunch.status = textTS.substitute(text=pretext.replace(' ','&nbsp'), align='right')
            tlist.append(cbunch.cruisename)
            tlist.append(cbunch.status)

            # links: figures, report, email,
            for name in ('dir', 'email'):
                weblink = webTS.substitute(shipdir=shipnames.shipdirs[shipkey], link_source=self.linknames[name])
                tlist.append(linkTS.substitute(link_source=weblink,  name=name))
            tlist.append('</tr>')

        tlist.append(self.ttable_tail)
        tlist.append(self.km_link)
        tlist.append('<pre> last_updated %s\n              %s\n</pre>' % (nowstr(), utcnowstr()))
        tlist.append(self.doc_tail)

        self.tlist=tlist
