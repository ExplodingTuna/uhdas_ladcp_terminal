'''
Functions to consolidate common functionality in scripts that
are run as separate processes by DAS_while_logging.
'''

import os
import logging, logging.handlers
from pycurrents.system import logutils

def getLogger():
    '''
    Provide an initial root logger instance.

    Call this near the top of the script, before importing
    any pycurrents modules.

    This function cleans the slate by deleting any existing
    root handlers; normally there should not be any, so this
    is to prevent unexpected behavior if a pycurrents module
    or other module initializing the logging module is called
    before this function.

    See addHandlers for the second step in setting up logging.

    '''
    LF = logging.getLogger()
    for h in LF.handlers:
        LF.removeHandler(h)
    LF.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logutils.formatterMinimal)
    LF.addHandler(handler)
    return LF


def addHandlers(LF, procdirname, logname):
    '''
    Add handlers once procdirname is known.

    procdirname can be any short string to identify the instrument the
    script is working with.

    One handler prints everything into a file that is overwritten
    on each run; the second prints warnings in longer-lived files.
    '''
    logfilebase = os.path.join('/home/adcp/log', logname)
    logfile = '%s_%s.log' % (logfilebase, procdirname)
    handler = logging.FileHandler(logfile, 'w')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logutils.formatterTLN)
    LF.addHandler(handler)

    logfile = '%s_%s.warn' % (logfilebase, procdirname)
    handler = logging.handlers.TimedRotatingFileHandler(logfile,
                    'midnight', 1, 30)
    handler.setLevel(logging.WARN)
    handler.setFormatter(logutils.formatterTLN)
    LF.addHandler(handler)
