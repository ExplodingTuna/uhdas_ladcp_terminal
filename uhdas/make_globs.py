
import os.path

def make_rbin_glob(instrument, message, base_dir):
    g = os.path.join(base_dir, instrument,
                      '.'.join(('*', message, 'rbin')))
    return g

def make_rbin_globs(sensors, available_messages, base_dir):
    '''Make glob patterns for available messages.

    sensors: list from sensor_cfg.py
    available_messages: list of suitable  rbins; may
       include more messages than are actually in sensor_cfg.py
    base_dir: typically /home/adcp/cruise.

    Returns a list of the messages in both sensors and
    available_messages, in the order of the latter, and
    two dictionaries, both with message as the key.
    The first contains *lists* of glob patterns, the second
    contains matching *lists* of instruments.  Most lists will
    have only a single element; the exception will be for the gps
    message
    '''
    globdict = dict()
    instrumentdict = dict()
    messages = list()
    for sensor in [s for s in sensors if 'messages' in s]:
        for msg in [m for m in available_messages if m in sensor['messages']]:
            g = os.path.join(base_dir, sensor['subdir'],
                              '.'.join(('*', msg, 'rbin')))
            if msg in globdict:
                globdict[msg].append(g)
                instrumentdict[msg].append(sensor['subdir'])
            else:
                globdict[msg] = [g]
                instrumentdict[msg] = [sensor['subdir']]
    messages = [m for m in available_messages if m in globdict]
    return messages, globdict, instrumentdict


def make_raw_globs(ADCPs, sensors, base_dir, glob_pat):
    '''Make glob patterns for available ADCP files
    in subdirectories of 'raw'.  glob_pat will usually
    be '*.raw' or '*.raw.log'.  base_dir is the 'raw'
    subdirectory itself.  Unlike the rbin case, globdict
    returns a glob, not a list of globs.  We are assuming
    there will never be two identical instruments.
    '''
    instruments = list()
    globdict = dict()
    for ADCP in ADCPs:
        instrument = (ADCP['instrument']) # e.g., 'os38'
        s = [s for s in sensors if s['instrument'] == instrument]
        sensor = s[0]  # should be the only element, of course
        g = os.path.join(base_dir, sensor['subdir'], glob_pat)
        globdict[instrument] = g
        instruments.append(instrument)
    return instruments, globdict
