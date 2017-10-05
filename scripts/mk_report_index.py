#!/usr/bin/env python

'''
makes a simple index.html file for daily_report directory
'''
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import os
import time, glob


###

report_dir = '/home/adcp/daily_report'

timestamp = time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime(time.time()))
print(timestamp)

os.chdir(report_dir)

## create the strings for index.html
## (1)
headstr = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <meta content="text/html; charset=ISO-8859-1"
 http-equiv="content-type">
  <title>test</title>
</head>
<body>

'''


# (2)
strlist = ['this file was created on %s' % (timestamp)]
strlist.append('<br>')
strlist.append('<br>')
strlist.append('links to current files:<br>')
strlist.append('<hr style="width: 100%; height: 2px;">')

# system diagnostics
systemlist = ('disk_details.txt', 'disk_files.txt', 'disk_summary.txt',\
              'processes.txt', 'ntp.txt')
#print systemlist
for fname in systemlist:
    strlist.append('<a href="%s">link</a>   to %s<br>' % (fname, fname))
    os.chmod(fname, 0o644)
strlist.append('<hr style="width: 100%; height: 2px;">')

# matfiles
datalist = glob.glob('*.mat')
datalist.sort()
#print datalist
for fname in datalist:
    strlist.append('<a href="%s">link</a>   to %s<br>' % (fname, fname))
    os.chmod(fname, 0o644)
strlist.append('<hr style="width: 100%; height: 2px;">')


# processing
proclist = ['processing.txt']
for ff in glob.glob('*_*.txt'):
    proclist.append(ff)
#print proclist
for fname in proclist:
    if fname not in systemlist:
        strlist.append('<a href="%s">link</a>   to %s<br>' % (fname, fname))
        os.chmod(fname, 0o644)
strlist.append('<hr style="width: 100%; height: 2px;">')

# everything else
filelist= glob.glob('*')
filelist.sort()
#print filelist
for fname in filelist:
    if fname not in datalist and \
           fname not in systemlist and \
           fname not in proclist:
        strlist.append('<a href="%s">link</a>   to %s<br>' % (fname, fname))
        os.chmod(fname, 0o644)
strlist.append('<hr style="width: 100%; height: 2px;">')


strlist.append('<br>')
strlist.append('<br>')



# (3)
tailstr = '''
<br>
<br>
</body>
</html>
'''

index = open('index.html','w')
index.write(headstr)
index.write('\n'.join(strlist))
index.write(tailstr)
index.close()

os.chmod('index.html', 0o644)
