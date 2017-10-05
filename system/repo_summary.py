'''
Special Classe for repo_summary.py, to let it be run from PROGRAMS directory
If run in the root PROGRAMS directory for all the repos, the imports are local.
Is there a way around that?
'''
from __future__ import print_function
from __future__ import absolute_import

from future import standard_library
standard_library.install_hooks()
#from future.builtins import object
from importlib import import_module

import os, subprocess, time, glob, stat, datetime


class HGinfo(object):
    '''
    class consolidating methods to give summaries about mercurial repositories
    '''

    def __init__(self):
        '''
        HG = GHinfo(dirname)
        for r in HG.repolist:
            print(HG.assemble_strings(r,show_installed=True, short=True))
        '''
        self.uhdas_repolist = ['adcp_srcdoc', 'codas3', 'pycurrents',
                               'uhdas', 'onship', 'onship_private', 'pytide', 'scripts']


    #----
    def get_all_repos(self, dirname=None):
        if dirname is None:
            dirname = os.getcwd()

        rlist = []
        for fd in glob.glob(os.path.join(dirname,'*')):
            if os.path.isdir(os.path.join(fd,'.hg')):
                rlist.append(fd)
        rlist.sort()
        self.repolist = rlist

    def get_uhdas_repos(self, dirname='/home/currents/programs'):
        self.repolist=[]
        for r in self.uhdas_repolist:
            self.repolist.append(os.path.join(dirname, r))


    def diff(self, nlines=60, repodir='/home/adcp/config'):
        '''
        Nlines of "diff"
        '''
        if not os.path.exists(os.path.join(repodir, '.hg')):
            return('%s: not repositorized!' % (reponame))

        cmd = 'hg diff -R %s' % (repodir)

        lines = subprocess.getoutput(cmd).split('\n')[-nlines:]

        outstr = '-------- ' + cmd + ' --------' +  '\n'.join(lines) + '\n'
        return outstr


    def get_install_str(self, reponame=None):
        '''
        return hg_status.installed attribute, if it exists
        NOTE: hg_status.py is written in the SOURCE as well as INSTALLED location.
        When run in PROGRAMS directory, local copy is reported in source location
            otherwise the installed copy is reported, but since they are the same
            that is OK.
        '''
        if reponame is None:
            return ''
        rbase = os.path.split(reponame)[-1]
        if rbase == 'codas3':
            rlist=[]
            for cmd in ['which codas_prefix', 'codas_prefix']:
                rlist.append(subprocess.getoutput(cmd))
            return '\n'.join(rlist)
        # now for the rest:
        if os.path.exists(os.path.join(reponame,'hg_status.py')):
            try:
                hgstatus = import_module(rbase + '.hg_status')
                return hgstatus.installed
            except:
                ss =  '%s: failed to import hg_status, not "installed?' % (rbase)
                return ss
        else:
            return '%s: hg_status.py does not exist. not "installed?"' % (rbase)



    def summary(self, reponame, greplines=('changeset', 'date','summary')):
        '''
        summarize info about a repo using
                tip (these lines: changeset, date, summary)
                status

        '''
        repo = os.path.normpath(reponame)
        outlist=[]
        ## tip
        tcmd = 'hg tip -R %s' % (repo)
        lines = subprocess.getoutput(tcmd).split('\n')

        tlist = []
        for line in lines:
            for name in greplines:
                if name in line[:10]:
                    tlist.append(line)

        ## status
        scmd = 'hg status -R %s' % (repo)
        slist = subprocess.getoutput(scmd).split('\n')

        outlist = ['\n========= %s ================' % (repo),
                   '\n ---- REPO status -------',
                   '\n'.join(tlist)]
        if len(slist[0]) > 0:
            outlist.append('==>repo changed')
            outlist.append('\n'.join(slist))
        return '\n'.join(outlist)


    def short_summary(self, reponame):
        '''
        hg id -bint
        '''
        repo = os.path.normpath(reponame)
        ## tip
        formatlen=[15,6,8,5] # rev, num, 'default', 'tip'
        tcmd = 'hg id -bint -R %s' % (repo)
        parts = subprocess.getoutput(tcmd).split()
        pieces = ['%-17s' % (os.path.basename(repo)),]
        for ii, part in enumerate(parts):
            formatstr = '%%-%ds' % (formatlen[ii])
            pieces.append(formatstr % (part))
        return ''.join(pieces)


    def assemble_strings(self, reponame, show_installed=False, short=False):
        '''
        assemble strings from various hg commands for source repo,
        as well as docstring in "hg_status.py"
        '''
        ## called by repo_status and daily.py (using system_summary)
        outlist=[]
        if short:
            outlist.append(self.short_summary(reponame))
        else:
            outlist.append(self.summary(reponame))

        if show_installed:
            outlist.append('\n ---- INSTALL status (hg_status.installed) ---- ')
            installstr = self.get_install_str(reponame)
            outlist.append(installstr)
        return '\n'.join(outlist)


    def write_strings_to_file(self, fname):
        '''
        initialize repolist first
        meant for DAS.py, which is managing stdout
        '''
        self.get_uhdas_repos()
        tips=[]
        for r in self.repolist:
            tips.append(self.assemble_strings(r, show_installed=True))
        tips.append('\n')
        open(fname, 'w').write('\n'.join(tips))
