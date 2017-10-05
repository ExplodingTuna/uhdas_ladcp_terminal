#!/usr/bin/env python
'''Send via SMTP a tarred version of the contents of daily_report,
or any subset or single file.  This is designed for compatibility
with daily.py (formerly daily.prl).

If smtp authentication is required, then make a file named
/usr/local/etc/mailparams
that looks like this:

# ---- end of code snippet ----

user = 'adcp'
password = 'whatever'

# ---- end of code snippet ----

The file has to be readable by user adcp, of course. The file
is a snippet of python code, so don't indent the lines.

The rationale for the file location is that it should not be in the
ubuntu system installation area, and it should not be exported.

The file must be present if and only if authentication is
required.

'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()
from future.builtins import object

import smtplib, os
import subprocess
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email import Encoders
## we might want to switch from os.system to subprocess.getstatusoutput
## in mail_tarball

import logging
logging.basicConfig()
L = logging.getLogger('mail_report')

from pycurrents.system import Bunch

class report_mailer(object):
    def __init__(self, server, From, port=None, SSL=False):
        self.server = server
        self.From = From
#
        self.ports_ssl = dict()
        self.ports_ssl[True]  = smtplib.SMTP_SSL_PORT
        self.ports_ssl[False] = smtplib.SMTP_PORT
        self.port = self.ports_ssl[SSL]
        if port is not None:
            self.port = int(port)
#
        self.smtp_ssl=dict()
        self.smtp_ssl[True] = smtplib.SMTP_SSL()
        self.smtp_ssl[False] = smtplib.SMTP()
        self.smtp = self.smtp_ssl[SSL]

    def _login(self):
        try:
            d = Bunch().from_pyfile('/usr/local/etc/mailparams')
            if 'use_ssl' not in list(d.keys()):
                d['use_ssl'] = False
            L.debug('Found mailparams')
        except IOError:
            L.debug('No mailparams found')
            return
        self.smtp.login(d['user'], d['password'])
        # We will let any exceptions propagate up to the
        # next level (daily.py) and be reported there.


    def mail_string(self, to, msg, subject = ''):
        Msg = MIMEText(msg)
        Msg['Subject'] = subject
        Msg['From'] = self.From
        Msg['To'] = ','.join(to)

        if len(self.server) == 0:
            self.smtp.connect()
        else:
            self.smtp.connect(self.server, port=self.port)
        try:
            self._login()
            self.smtp.sendmail(self.From, to, Msg.as_string())
        finally:
            self.smtp.quit()


    def mail_file_contents(self, to, filename):
        L.debug("report_mailer.mail_file_contents: %s %s", to, filename)
        self.mail_string(to, open(filename).read(), filename)


    #----

    def generate_tarball_file(self, source_dir, filelist, tarfilename):
        ''' 
        generate tarfilename with tarball contents from filelist
        '''
        filestring = ' '.join(filelist)
        cmd = "/bin/tar -C %s -czf %s %s" % (source_dir, tarfilename, filestring)
        L.debug(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout_str, stderr_str = p.communicate()
        if stderr_str:
            L.warning(stderr_str)

    def string_from_tarfile(self, tarfilename):
        ''' 
        read file tarfilename and return contents as binary string
        '''
        try:
            bstr = open(tarfilename, 'rb').read()
            return bstr
        except:
            L.warning('could not read tarfile %s' % (tarfilename))

    def generate_tarball_string(self, source_dir, filelist):
        '''
        Generate tar.gz file (return as a string) from filelist in source_dir
        This was the method for sending tarballs before archiving them at sea.
        '''
        filestring = ' '.join(filelist)
        #Strange bug (or feature) in tar: writing to stdout doesn't
        # work well with compression option.  Workaround is to
        # to compress separately.
        cmd = "/bin/tar -C %s -cf - %s | gzip" % (source_dir, filestring)
        L.debug(cmd)
        # very old: os.system; old: commands.getoutput; newer: subprocess
        p=subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        tgz_string, stderr_str=p.communicate()
        if stderr_str:
            L.warning(stderr_str)
        return tgz_string

    def mail_tarball_attachment(self, to, tgz_string, tarfilename=None, subject = ''):
        '''
        tarfilename is what a standard email client will use to save the attachment 
        '''
        if tarfilename is None:
            tarfilename = 'tarfile.tar.gz'

        Msg = MIMEMultipart()
        if subject == '':
            subject = tarfilename
        Msg['Subject'] = subject
        Msg['From'] = self.From
        Msg['To'] = ','.join(to)
        Msg.preamble = 'This is a multi-part message in MIME format.\n'
        #To guarantee the message ends with a newline
        Msg.epilogue = ''

        tgz_msg = MIMEBase('application', 'x-gzip')
        tgz_msg.set_payload(tgz_string)
        Encoders.encode_base64(tgz_msg)
        tgz_msg.add_header('Content-Disposition', 'attachment',
                            filename=tarfilename)
        Msg.attach(tgz_msg)
        ## different syntax if running postfix on the local machine,
        if len(self.server) == 0:
            self.smtp.connect()
        else:
            self.smtp.connect(self.server, port=self.port)
        try:
            self._login()
            self.smtp.sendmail(self.From, to, Msg.as_string())
        finally:
            self.smtp.quit()


from optparse import OptionParser

def main():
    user = subprocess.check_output("whoami", shell=True)
    host= subprocess.check_output("hostname", shell=True)
    def_From = "%s@%s" % (user, ".".join(host.split(".")[1:]))
    print(def_From)
    parser = OptionParser()
    parser.add_option("-s", "--server", dest="server", default="mail")
    parser.add_option("-F", "--From", dest="From", default=def_From)
    parser.add_option("-t", "--tarfilename", dest="tarfilename",
                      default="daily.tar.gz")

    (options, args) = parser.parse_args()

    #RM = report_mailer(options.server, options.From)
    # Maybe a bug in smtplib?  If the report_mailer is
    # instantiated only once, we get an error complaining
    # about lack of HELO if we try to send more than one file.
    To = args[:1]   # This must be a list!
    for arg in args[1:]:
        RM = report_mailer(options.server, options.From)
        if os.path.isdir(arg):
            filelist = os.listdir(arg)
            tgz_string = generate_tarball_string(arg, filelist)
            RM.mail_tarball_attachment(To, arg, filelist, options.tarfilename)
        else:
            RM.mail_file_contents(To, arg)

if __name__ == "__main__":
    main()
