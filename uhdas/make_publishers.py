#!/usr/bin/env python
'''
Read sensor_cfg.py and read the "monitors" section.
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()


from pycurrents.system import Bunch

def modify_sensors_and_publishers(sensors, publishers):
    '''
    sensors: list of dictionaries with sensor information, from sensor_cfg.py
    publishers: dictionary of overrides for zmq publishers (keyed by subdir)

    purpose:
      modify sensors to subscribe to publishers; fill out publisher info
    '''
    sensor_dict = dict((x['subdir'], x) for x in sensors)
    publish_dict = dict((x['subdir'], x) for x in publishers)
#
    for subdir in publish_dict.keys():
        sensor = sensor_dict[subdir]
        # for zmq_publisher, fill in values
        publisher = publish_dict[subdir]
        for name in ['baud', 'subdir', 'ext', 'strings', 'messages']:
            publisher[name] = sensor[name]
        publisher['in_device'] = sensor['device']
        publisher['format'] = 'zmq_ascii'
        publisher['opt'] = ''
#
    for subdir in publish_dict.keys():
        # for sensor to become subscriber, modify in place
        subscriber = sensor_dict[subdir]
        publisher = publish_dict[subdir]
        # overrides
        subscriber['format'] = publisher['format']
        subscriber['opt'] = publisher['opt']
        subscriber['device'] = publisher['pub_addr']







