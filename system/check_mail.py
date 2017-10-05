"""
check_mail.py is a module for shore-based handling of UHDAS emails.

It is normally run from a stub script like this:

--------

#!/usr/bin/env python
from uhdas.system.check_mail import check_mail

pw = '****'

check_mail(server='iniki.soest.hawaii.edu', username='uhdas', pw=pw, fromuser='username')

---------

Because the script contains the password, it should be readable only
by the owner.

If the script is "~uhdas/bin/check_mail_multi.py", then the crontab entry
(owned by the uhdas user) might look like this:

uhdas@moli:(bin)$ crontab -l
SHELL=/bin/bash
*/10  * * * * (date +\%F\ \%T; cd /home/moli4/users/uhdas/bin; . ./bash_env; ./check_mail_multi.py) >> log/checkm.log 2>&1

------------

The corresponding ~uhdas/bin/bash_env might look like this:

-------------

prog=/home/noio/programs

PATH=/usr/local/sbin:\
/usr/local/bin:\
/usr/sbin:\
/usr/bin:\
/sbin:\
/bin:\
$HOME/bin:\
$prog/scripts:\
$prog/codas3/bin/lnx:\
$prog/pycurrents/adcp:\
$prog/pycurrents/plot:\
$prog/pycurrents/system:\
$prog/pycurrents/data/nmea:\
$prog/uhdas/scripts:\
$PATH

PYTHONPATH=$prog:$PYTHONPATH

export PYTHONPATH

export UHDAS_HTMLBASE=/home/moli20/htdocs/uhdas_fromships

---------

In addition to having the stub script and bash_env in ~uhdas/bin,
there needs to be a writeable ~uhdas/log directory.


"""

import imaplib, email, time, os, os.path, re

from onship.shipnames import shipdirs, shipnames, shipkeys
from uhdas.system.process_tarball import process_shorestatus

import logging, logging.handlers
L = logging.getLogger()
L.setLevel(logging.DEBUG)
formatter = logging.Formatter(
      '%(asctime)s %(levelname)-8s %(message)s')

homedir = os.environ['HOME']
logbasename = os.path.join(homedir, 'log', 'check_mail')

handler = logging.handlers.RotatingFileHandler(logbasename, 'a', 100000, 3)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
L.addHandler(handler)

L.info("Starting")

class NothingFound(Exception):
    pass

def shipabbrev(filename):
    pat = re.compile('([a-zA-Z]+)\d+')
    abbrev = pat.match(filename).group(1)
    return abbrev

def check_mail(server=None, username=None, pw=None, ssl=True, fromuser=None):
    tarballtuples = []
    emailtuples = []
    if ssl:
        imap = imaplib.IMAP4_SSL
    else:
        imap = imaplib.IMAP

    if fromuser is None:
        raise ValueError('must specify FROM username expected in email message')

    timestamp = time.strftime('%Y-%j-%H%M', time.gmtime(time.time()))
    try:
        M = imap(server)
        M.login(username, pw)

        # Any messages waiting?
        M.select()
        status, data = M.search(None, 'ALL')
        allmsgnums = data[0].split()
        nmsgs = len(allmsgnums)
        L.info('timestamp: %s', (timestamp,))
        L.info("%d messages found", nmsgs)
        if nmsgs == 0:
            raise NothingFound()

        ## ----------
        ## find tarball and 'shore status' emails

        # Find the tarballs
        tarstatus, tardata = M.search(None, 'FROM', "%s" % (fromuser,),
                                       '(SUBJECT "tarball")')
        L.debug("tarball search result: %s", str(tardata))
        tarmsgnums = tardata[0].split()
        L.info("%d tarball messages found", len(tarmsgnums))
        if len(tarmsgnums) > 0:
            # Download all tarball messages
            tarstatus, tardata = M.fetch(','.join(tarmsgnums), '(RFC822)')
        total_emails = len(tarmsgnums)


        # Find the shorestatus emails
        shorestatus, shoredata = M.search(None, 'FROM', "%s" % (fromuser,),
                                       '(SUBJECT "ADCP shore status")')
        L.debug("shorestatus search result: %s", str(shoredata))
        shoremsgnums = shoredata[0].split()
        L.info("%d shore status messages found", len(shoremsgnums))

        if len(shoremsgnums) > 0:
            # Download all shore status messages
            shorestatus, shoredata = M.fetch(','.join(shoremsgnums), '(RFC822)')
        total_emails += len(shoremsgnums)

        if total_emails == 0:
            raise NothingFound()
        #============
        ## deal with tarballs
        msgstrings=[]
        if len(tarmsgnums) > 0:
            msgstrings = [m[1] for m in tardata[::2]]
        for imsg, msgstring in enumerate(msgstrings):
            msg = email.message_from_string(msgstring)
            for part in msg.walk():
                ct = part.get_content_type()
                L.debug('Content type: %s', ct)
                if (ct == 'application/x-gzip'
                                  or ct == 'application/octet-stream'):
                    filename = part.get_filename(None)
                    if filename is None:
                        L.warn('No filename. Trying the next part',)
                        continue
                    L.debug('Filename: %s', filename)
                    shipkey = shipabbrev(filename)

                    if shipkey not in shipdirs:
                        L.warn('Ship abbrev %s not found in shipdirs', shipkey)
                        continue
                    shipdir = os.path.join(os.environ['HOME'],
                                            'ships',
                                            shipdirs[shipkey])
                    shiptardir = os.path.join(shipdir, 'tarfiles')

                    for dir in (shipdir, shiptardir):
                        if not os.path.isdir(dir):
                            os.mkdir(dir)

                    # to make outgoing email attachments "secure", send as ".uhdas"
                    basename, suffix = os.path.splitext(filename)
                    if suffix == '.uhdas':
                        filename = basename + ".tar.gz"
                    tarpath = os.path.join(shiptardir, filename)
                    open(tarpath, 'w').write(part.get_payload(decode=True))
                    L.info('wrote tarball: %s', tarpath)
                    tarballtuples.append((shipkey, tarpath))
                    try:
                        M.store(tarmsgnums[imsg], "+FLAGS", "(\Deleted)")
                    except:
                        L.error('Trying to delete index %d, msg %d',
                                        imsg, tarmsgnums[imsg], exc_info=True)

        # deal with the shore status
        # IF there is email, it will write shorestatus
        msgstrings=[]
        if len(shoremsgnums) > 0:
            msgstrings = [m[1] for m in shoredata[::2]]
        msgstrings = [m[1] for m in shoredata[::2]]
        for imsg, msgstring in enumerate(msgstrings):
            msg = email.message_from_string(msgstring)
            for part in msg.walk():
                ct = part.get_content_type()
                L.debug('Content type: %s', ct)
                if (ct == 'text/plain'):
                    shipkey = None
                    for skey in shipkeys:
                        if shipnames[skey] in msg['Subject']:
                            shipkey = skey
                    if shipkey is None:
                        L.info('skipping %s', msg['Subject'])
                        continue
                    if shipkey not in shipdirs:
                        L.warn('Ship abbrev %s not found in shipdirs', shipkey)
                        continue
                    shipdir = os.path.join(os.environ['HOME'],
                                            'ships',
                                            shipdirs[shipkey])
                    ship_emaildir = os.path.join(shipdir, 'emails')
                    for dir in (shipdir, ship_emaildir):
                        if not os.path.isdir(dir):
                            os.mkdir(dir)
                            L.info('making new email dir %s', ship_emaildir)
                    filename= timestamp + '_shorestatus.txt'
                    emailpath = os.path.join(ship_emaildir, filename)
                    open(emailpath, 'w').write(part.get_payload(decode=True))
                    L.info('wrote shore status email: %s', emailpath)
                    emailtuples.append((shipkey, emailpath))
                    try:
                        M.store(shoremsgnums[imsg], "+FLAGS", "(\Deleted)")
                    except:
                        L.error('Trying to delete index %d, msg %d',
                                        imsg, shoremsgnums[imsg], exc_info=True)

    except NothingFound:
        pass
    except:
        L.exception("Outer try block")

    M.close()
    M.logout()

    for tarballtuple in tarballtuples:
        L.info('processing tarball: %s %s' % tarballtuple)
        os.system('process_tarball.py %s %s' % tarballtuple)

    L.info('processing shore status emails: %s ' % str(emailtuples))
    passed, failed = process_shorestatus(emailtuples)
    L.info('shore status: %d passed, %d failed' % (len(passed), len(failed)))

    L.info("Exiting")
