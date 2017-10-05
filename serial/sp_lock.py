
'''
sp_lock.py

Lock file management for serial ports; but very little is
specific to serial ports, so it would make sense to
generalize it for other locks and improve the error handling.

EF

'''
from __future__ import print_function

import os

lock_dir = '/var/lock'

pid = 0  # global, for reporting.

class LockFailure(Exception):
    pass

class LockedError(Exception):
    ''' An unexpected active lock file was found. '''
    locked_by = ('', 'this process', 'another running process')
    def __init__(self, status, device):
        Exception.__init__(self, status, device)
        print(LockedError.__doc__)
        print('The lock file is %s.' % lock_file(device))
        print('Lock is owned by %s, with pid = %d.' % (
                           LockedError.locked_by[status],
                           pid))



def lock_file(device):
    fn = 'LCK..%s' % os.path.split(device)[1]
    return os.path.join(lock_dir, fn)

def is_locked(device):
    ''' Returns 0 if not locked, (or was locked by a dead process)
                1 if locked by this process,
                2 if locked by another running process
    '''
    fn = lock_file(device)
    if not os.access(fn, os.F_OK):
        return 0  # File does not exist; not locked.

    line = open(fn).readline()     # Let these raise default exceptions for now.
    field = line.split()[0]
    global pid
    pid = int(field.strip())

    try:
        os.kill(pid, 0)
    except OSError:
        # Process is dead; delete the lock file.
        try:
            os.remove(fn)  # raise default exception for now
        except OSError as e:
            print(e)
        return 0
    if pid == os.getpid():
        return 1
    else:
        return 2

def check_lock(device):
    status = is_locked(device)
    if status:
        raise LockedError(status, device)

def lock_port(device):
    check_lock(device)
    pid = os.getpid()
    fn = lock_file(device)
    open(fn, 'w', 0o775).write('%d' % pid)

def unlock_port(device):
    try:
        os.remove(lock_file(device))
    except:
        pass
