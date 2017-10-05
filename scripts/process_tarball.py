#!/usr/bin/env python

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

from uhdas.system.process_tarball import main

if __name__ == '__main__':
    main()

