'''
Functions, strings, and instances to facilitate use of the logging module
'''

import logging
import os


def getLogger(fpath=''):
    '''
    Returns a logging.Logger instance, either root or named.

    If a root logger is already configured (with a handler),
    then a named logger is returned; otherwise the root logger
    is configured to simply print messages, and it is returned.

    example, near top of a module:

        log = getLogger(__file__)
        log.info('starting %s', __file__)

    The name argument can be a file path, in which case it is
    stripped down to the base file name without extension.
    '''


    fname = os.path.split(fpath)[1]
    fnamebase = os.path.splitext(fname)[0]

    log = logging.getLogger()
    if log.handlers:
        log = logging.getLogger(fnamebase)
    else:
        logging.basicConfig(format='%(message)s', level=logging.DEBUG)
    return log

formatTLN = '%(asctime)s %(levelname)-8s %(name)-12s %(message)s'
formatterTLN = logging.Formatter(formatTLN)

formatterMinimal = logging.Formatter('%(message)s')

