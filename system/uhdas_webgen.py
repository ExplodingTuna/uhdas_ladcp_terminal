#!/usr/bin/env  python
from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

import os, shutil
import string, glob
import subprocess
import sys
from optparse import OptionParser

class SimpleBunch(dict):
    def __init__(self, *args, **kwargs):
        """
        *args* can be dictionaries, bunches, or sequences of
        key,value tuples.  *kwargs* can be used to initialize
        or add key, value pairs.
        """
        dict.__init__(self)
        self.__dict__ = self
        for arg in args:
            self.update(arg)
        self.update(kwargs)


class CommandError(Exception):
    def __init__(self, cmd, status, output):
        msg = "Command '%s' failed with status %d\n" % (cmd, status)
        Exception.__init__(self, msg + output)

from pycurrents.system import logutils
L = logutils.getLogger(__file__)

## TODO -- add verbosity change "info" or "debug"


# requires programs/logging/uhdas_scripts to be on PYTHONPATH
# keys are the same 2-letter abbreviation, eg. 'kk'
from pycurrents.adcp import uhdas_defaults

from pycurrents.adcp.adcp_specs import adcp_longnames

Udef = uhdas_defaults.Uhdas_cfg_base()
Udef.get_defaults()


# The following determines the set and order of the thumbnails.
adcp_plottypes = ['lastens', 'shallow', 'ddaycont', 'latcont', 'loncont',]
# #do all
#beamdiag_plottypes = ['profile', 'timeseries', 'velocity',
#                      'correlation', 'amplitude', scattering]

beamdiag_plottypes = ['scattering', 'velocity'] #beam diagnostics
tsstats_plottypes = ['tsstats',]   #there is only one at present
sci_plottypes = ['ktvecprof',] # science diagnostics (only one at present)

# Thumbnail and full-page plot titles.
adcp_plottitles = {'lastens'    : '5-minute profile',
                'shallow'    : 'vector plot',
                'ddaycont'   : 'contour (time)',
                'latcont'    : 'contour (lat)',
                'loncont'    : 'contour (lon)',
                }

# Thumbnail and full-page plot titles.
beamdiag_plottitles = {'profile'       : 'profile',
                       'timeseries'    : 'timeseries',
                       'velocity'      : 'velocity, m/s',
                       'amplitude'     : 'amplitude',
                       'scattering'    : 'UNCALIBRATED scattering, dB',
                       'correlation'   : 'correlation',
                       }

# Thumbnail and full-page plot titles.
tsstats_plottitles =   {'tsstats'       : '(some) ocean velocity errors',
                       }

# Thumbnail and full-page plot titles.
sci_plottitles =   {'ktvecprof'       : 'speed+direction profile',
                       }

#------------------ templates for figures/*html ---------------------

adcp_figfile_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30">
<title>${inst_uc} ${title}</title></head>
<body>
<img src="./${inst_lc}_${ptype}.png">
<br>
<br>
<br>
</body></html>
'''

beamdiag_figfile_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30">
<title>${inst_uc} ${title}</title></head>
<body>
<img src="./${inst_lc}_beam_${ptype}.png">
<br>
<br>
<br>
</body></html>
'''


tsstats_figfile_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30">
<title>${inst_uc} ${title}</title></head>
<body>
<img src="./${inst_lc}_${ptype}.png">
<br>
<br>
<br>
</body></html>
'''

sci_figfile_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30">
<title>${inst_uc} ${title}</title></head>
<body>
<img src="./${inst_lc}_${ptype}.png">
<br>
<br>
<br>
</body></html>
'''


#------------------ templates for "monitoring" figures --------

## heading correction only, at the moment

att_figfile_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30"><title> ${title}</title></head>
<body>
<img src="./${att_dev}_${hdg_inst}dh.png">
<br>
<br>
</body></html>
'''


att_figfile_thumb_template = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head>
<meta http-equiv="Refresh" content="30"><title> ${title}</title></head>
<body>
<img src="./thumbnails/${att_dev}_${hdg_inst}dh_thumb.png">
<br>
<br>
</body></html>
'''

#----------------- www figure templates ------------------


ttable_head = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>thumbnails</title>
</head>
<body>
<br>
<div style="text-align: center;"><big><span style="font-weight:
bold;"> ADCP Thumbnails</span>
</big></div>
  <a href="../index.html">HOME</a><br><br>
<table
  style="width: 100%; text-align: center;  vertical-align: middle;
background-color: rgb(51, 102, 255);"
  border="1" cellpadding="2" cellspacing="2">
   <tbody>
<!-- PROFILES -->
"""


beamdiag_ttable_head = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>ADCP beam diagnostics</title>
</head>
<body>
<br>
<div style="text-align: center;"><big><span style="font-weight:
bold;"> ADCP Beam diagnostics</span>
</big></div>
  <a href="../index.html">HOME</a><br><br>
<table
  style="width: 100%; text-align: center;  vertical-align: middle;
background-color: rgb(51, 102, 255);"
  border="1" cellpadding="2" cellspacing="2">
   <tbody>
<!-- PROFILES -->
"""

tsstats_ttable_head = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>(some) ADCP velocity errors <br> (EXPERIMENTAL) </br> </title>
</head>
<body>
<br>
<div style="text-align: center;"><big><span style="font-weight:
bold;"> ADCP velocity errors (some)</span>
</big></div>
  <a href="../index.html">HOME</a><br><br>
<table
  style="width: 100%; text-align: center;  vertical-align: middle;
background-color: rgb(51, 102, 255);"
  border="1" cellpadding="2" cellspacing="2">
   <tbody>
<!-- PROFILES -->
"""

ktvecprof_ttable_head = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>Science Diagnostic Plots </br>  (EXPERIMENTAL) </br> </title>
</head>
<body>
<br>
<div style="text-align: center;"><big><span style="font-weight:
bold;"> Science Diagnostic Plots</span>
</big></div>
  <a href="../index.html">HOME</a><br><br>
<table
  style="width: 100%; text-align: center;  vertical-align: middle;
background-color: rgb(51, 102, 255);"
  border="1" cellpadding="2" cellspacing="2">
   <tbody>
<!-- PROFILES -->
"""


#------------

ttable_tail = """
   </tbody>
</table>
</body>
</html>
"""


#----------

ttable_row = '''
       <td style="text-align: center; vertical-align: middle;
background-color: rgb(204, 204, 204);">
       <a target="new_${inst}_${ptype}" href="./${inst}_${ptype}.html">
         <img alt="${inst} ${ptype}"
             src="./thumbnails/${inst}_${ptype}_thumb.png"
style="border: 0px solid ;" align="middle"> </a> <br>
       <span style="font-weight: bold;">${inst} ${title}</span><br>
       </td>
'''


beamdiag_ttable_row = '''
       <td style="text-align: center; vertical-align: middle;
background-color: rgb(204, 204, 204);">
       <a target="${inst}_beam_${ptype}" href="./${inst}_beam_${ptype}.html">
         <img alt="${inst} ${title} "
             src="./thumbnails/${inst}_beam_${ptype}_thumb.png"
style="border: 0px solid ;" align="middle"> </a> <br>
       <span style="font-weight: bold;">${inst} ${title}</span><br>
       </td>
'''

tsstats_ttable_row = '''
       <td style="text-align: center; vertical-align: middle;
background-color: rgb(204, 204, 204);">
       <a target="${inst}_${ptype}" href="./${inst}_${ptype}.html">
         <img alt="${inst} ${title} "
             src="./thumbnails/${inst}_${ptype}_thumb.png"
style="border: 0px solid ;" align="middle"> </a> <br>
       <span style="font-weight: bold;">${inst} ${title}</span><br>
       </td>
'''

ktvecprof_ttable_row = '''
       <td style="text-align: center; vertical-align: middle;
background-color: rgb(204, 204, 204);">
       <a target="${inst}_${ptype}" href="./${inst}_${ptype}.html">
         <img alt="${inst} ${title} "
             src="./thumbnails/${inst}_${ptype}_thumb.png"
style="border: 0px solid ;" align="middle"> </a> <br>
       <span style="font-weight: bold;">${inst} ${title}</span><br>
       </td>
'''


# ------------------ www/simple_figlinks.html templates -----------


sifl_atthead= '''
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>simple figure links</title>
<base target="shownow">
</head>
<body>
<a  target="UHDASHOME" href="index.html">  HOME</a>     <br>
<br>
<hr width="100%"> <br>
Monitoring: click opens a new figure <br><br>

<b> Attitude Devices </b>
  <ul>

'''


sifl_beamblock = '''

<b>Diagnostics</b>:
  <ul>
    <li>
      <a href="figures/beam_diagnostics.html" target="beam_diagnostics">Beams: Scattering, Velocity</a>
    </li>
    <li>
      <a href="figures/tsstats.html" target="velocity_diagnostics">(some) Ocean Velocity Errors</a>
    </li>
  </ul>

  <br>
  <br>

'''

sifl_sciblock = '''

<b>More Science Plots</b>:
  <ul>
    <li>
      <a href="figures/sci.html" target="science_diagnostics">Vector Profile Plots</a>
    </li>
  </ul>

  <br>
  <br>

'''

sifl_bridgeblock = '''
<b>Bridge plots</b>:
  <ul>
    <li>
      surface  vector :
         <ul>
         <li>
              <a href="figures/ktvec_day.html" target="ktvec_day"> day  </a>
         </li>
         <li>
              <a href="figures/ktvec_night.html" target="ktvec_night"> night  </a>
         </li>
         </ul>

    </li>
    <li>
      kts and direction profile:
         <ul>
         <li>
              <a href="figures/ktprof_day.html" target="ktprof_day"> day  </a>
         </li>
         <li>
              <a href="figures/ktprof_night.html" target="ktprof_night"> night  </a>
         </li>
         </ul>
    </li>
    <li> kts E/N + scattering
      <a href="figures/ktprof_amp.html" target="ktprof_amp"> profile  </a>
    </li>
  </ul>

  <br>
'''


sifl_att_link = '''
<li>
  ${inst}-${hdg_inst} comparison <br>
  <a  href="figures/${inst}_${hdg_inst}dh_thumb.html" target = "${inst}_att_thumbnail">
   (thumbnail) </a>
  <br>

  <br>
  <a  href="figures/${inst}_${hdg_inst}dh.html" target = "${inst}_att_plot">
  <img alt="${inst}-${hdg_inst} heading comparison"
  src="figures/thumbnails/${inst}_${hdg_inst}dh_thumb.png"></a>
  <br>
</li>
'''

sifl_thumbhead = '''
</ul>

<br>
<hr width="100%"> <br>
<br>
Click shows figures on the right:
<br><br>
<a  href="figures/thumbnails.html" >  all thumbnails </a>
<br>
'''


sifl_row = '''
<li><a  href="figures/${inst}_${ptype}.html"> ${title} </a>  <br></li>
'''

sifl_tail = '''
</body>
</html>
'''


#----------------- www/data/index.html templates ------------------


data_index = '''
<html>
<head>
   <title>ADCP data: web links</title>
</head>
<body>
<center><b><font size="+2">Processed ADCP DATA links<br>
</font></b></center>
<br>
<a href="../index.html">HOME</a><br>
<br>

ADCP data from CODAS processing are shared via web link
in two forms: Matlab files and NetCDF files.
The Matlab files are the same files used to make the
web plots seen on the UHDAS at-sea web site.  They are
averaged in space and time for plotting purposes.  The
NetCDF files contain more variables and retain the
native CODAS processed data resolution.  <br><br>

The following links will take you to: <br>
     <ul>
       <li> <a href="matlab_data.html">Matlab files </a>
                    (averaged for vector and contour plots) </li>
       <li> <a href="netcdf_data.html">NetCDF files </a>
                    (CODAS data: every bin, every profile </li>
     </ul>

If you want every bin and every profile in matlab format, read
the instructions for <a href="../index.html">UHDAS+CODAS at sea</a>.
<br>

</body>
</html>
'''

###  matlab (adcpsect output)


datamat_head = '''

<html>
<head>
   <title>ADCP data (matlab)</title>
</head>
<body>
<center><b><font size="+1">ADCP data, matlab format<br>
</font></b></center>
<br>


These files are created by a program called "adcpsect".
Adcpsect can be configured to extract velocity data
with a variety of averaging in horizontal and vertical.
The actual vertical averaging used depends on instrument,
ship, and frequency.

In general, data from active instrument+pingtype combinations
will be updated approximately every 15 minutes, available below.

<br><br>

Matlab output is a pair of files, eg
<b> contour_uv.mat, contour_xy.mat </b>.
<a href="adcpsect_output.txt"> This link </a> 
describes how to read the two files.


Downloading binary files can vary between browsers (and even
browser
versions). Several things to try are: <br>
<ol>
   <li> Explorer
     <ul>
       <li> left-click (then save) </li>
     </ul>
   </li>
   <li>Thunderbird (Netscape, Mozilla): </li>
   <ul>
     <li> left-click (if you see the binary data on your screen, try
"save as" using "source" </li>
     <li> shift and left-click (it should bring up a dialog to save the file) </li>
     <li> right-click (it should bring up a dialog to save the file) </li>
   </ul>
</ol>


<br>

'''

#----------

datamat_block = '''
<hr width="100%"><br>
Matlab files for the ${inst_long_name}:
<br>

<br>
<br>


<table style="text-align: left; width: 100%; height: 115px;" border="1"
  cellpadding="2" cellspacing="2">
   <tbody>
     <tr>
       <td style="vertical-align: top; text-align: center;"><span
style="font-weight: bold;">data description</span><br>
       </td>
       <td style="vertical-align: top; text-align: center;"><span
style="font-weight: bold;">matlab file<br>
(part 1)</span><br>
       </td>
       <td style="vertical-align: top; text-align: center;"><span
style="font-weight: bold;">matlab file <br>
(part 2)</span><br>
       </td>
     </tr>
     <tr>
       <td style="vertical-align: top; text-align: center;">
         ${inst_uc} <br> 15minute averages, medium resolution (few bins)
       </td>
       <td style="vertical-align: top; text-align: center;"><a href="
        ${inst_lc}_cont_xy.mat">time and depth</a>
       </td>
       <td style="vertical-align: top; text-align: center;"><a href="
        ${inst_lc}_cont_uv.mat">velocity</a></td>
     </tr>
     <tr>
       <td style="vertical-align: top; text-align: center;">
        ${inst_uc} <br> 1-hour averages, coarse resolution (20-50m)
       </td>
       <td style="vertical-align: top; text-align: center;">
        <a href="${inst_lc}_vect_xy.mat">time and depth</a>
       </td>
       <td style="vertical-align: top; text-align: center;">
         <a href="${inst_lc}_vect_uv.mat">velocity</a></td>
     </tr>
   </tbody>
</table>
'''


###  netcdf

data_netcdf_head = '''

<html>
<head>
   <title>ADCP data (NetCDF)</title>
</head>
<body>
<center><b><font size="+1">ADCP data, NetCDF format<br>
</font></b></center>
<br>

These files contain every bin and every profile from the CODAS
processed data.
<br>

Downloading binary files can vary between browsers (and even
browser
versions). Several things to try are: <br>
<ol>
   <li> Explorer
     <ul>
       <li> left-click (then save) </li>
     </ul>
   </li>
   <li>Thunderbird (Netscape, Mozilla): </li>
   <ul>
     <li> left-click (if you see the binary data on your screen, try
"save as" using "source" </li>
     <li> shift and left-click (it should bring up a dialog to save the file) </li>
     <li> right-click (it should bring up a dialog to save the file) </li>
   </ul>
</ol>

<br>

Information about the variables stored can be
found  <a href="../programs/adcp_doc/adcp_access/netcdf_output.html">
here</a>.

<br>

'''

data_netcdf_block = '''

<li>
 ${inst_long_name}  <a href="${inst_lc}.nc"> netcdf file</a>
</li>
'''


#-----------  index.html for the www page  -----------------

# this has four substitutions:
# "shipname" (in index_body)
# "instructions"
# "access_str" and "policy_str"
#
wi_top = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
        <title>UHDAS ADCP web page</title>
</head>

<body>
<table border="0" width="760" cellspacing="0" cellpadding="4">

<!--  -->
<!-- Row 1 is the icon and the title -->
<!-- image is 138,108 w,h ; 160,120 makes it fit about right but loses resolution-->
<!--  -->


<tr>
<td align="center" width="200" bgcolor="#CBF5F6">
  <a  target="ADCP_instruct"><img alt="uhdas logo" src="adcpicon.png"
   id="UHDAS_logo" width="138" height="108"></a>
</td>

<td align="center" width="560" bgcolor="#CBF5F6">
<h1> ${shipname}<br> UHDAS and ADCP </h1>
</td>

</tr>


<!--  -->
<!-- Row 2 is link list and the table that contains most of the text -->
<!--  -->

<tr>

<td valign="top" bgcolor="#CBF5F6" width="200" align="left">
<!--  -->



<h3>Quick Links:<br></h3>
<a href="figures_wframes.html" target="framefigs">Figures (live) </a><br>
<a href="figures/png_archive">Figures (archive) </a><br>
<a href="data/index.html" target="dataweb">Data (web) </a><br>
<br>


<h3>Documentation:</h3>
<!--  -->
<a href="programs/adcp_doc/UHDAS_atsea/index.html" >UHDAS at sea</a> <br>
<a href="programs/adcp_doc/adcp_access/index.html" >ADCP data tools</a> <br>
<br>
complete
<br>
<a href="programs/adcp_doc/index.html" target="rtfm">CODAS+UHDAS</a> <br>

<h3>Technical:</h3>
<a href="${instructionstr}" target="instructions">ADCP Instructions</a><br>
<a href="ADCP_checklist.html" target="DefaultChecklist">ADCP Checklist</a><br>
<a href="programs/adcp_doc/UHDAS_techdoc/Atsea_Monitoring/index.html" target="monitoring">What to Monitor</a><br>
<a href="programs/adcp_doc/Troubleshooting/index.html" target="troubleshooting">Troubleshooting</a><br>
<a href="configs" target="settings">Settings</a> <br>
<!--  -->


<!--  -->
</td>

<td  width="560">
<!--  -->
<!-- The main text of the page is in the following table -->
<!--  -->

'''


#------

wi_tail = '''
<hr width="100%"> <br>
<a href="mailto:uhdas@hawaii.edu"> UHDAS support </a><br>
<hr width="100%"> <br>

</td>  <!-- end of text -->
</tr>  <!-- end of second row-->
</table>


</body>
</html>
'''


#------

c_header = '''
  -------------------------------------------------------
  -----------------  DOCUMENTATION ----------------------
  -------------------------------------------------------
  -------------------------------------------------------
  ---------------  This is an anotated copy -------------
  --------------- of the original file  -----------------
            ${cdir}/${fname}
  -------------------------------------------------------
  ---------------- If you need to make any --------------
  ----------------- configuration changes, --------------
  --------------- make a copy of the original, ----------
  ----------------- then edit the real copy -------------
  -------------------------------------------------------
  ----------------- (carefully, of course) --------------
  -------------------------------------------------------
  '''

cdir_indextop = '''

.. ......................................
.. UHDAS/CODAS restructured text document
.. ......................................

UHDAS Settings
---------------

**processing configuration files**

- ADCP and serial port setup (includes "EA"): `sensor_cfg.py <sensor_cfg.py.txt>`_.
- UHDAS processing configuration file used: `proc_cfg.py <proc_cfg.py.txt>`_.

**acquisition configuration files**

'''

cdir_link = '''
- default ${instname} commands: `${instname}_default.cmd <${instname}_default.cmd.txt>`_
'''



#-----------------------------------------

def make_www_index(webcore, website, shipinfo, shipname, shortname):

    cmd = 'rsync -auxl --exclude=calibrations --exclude=Checks_and_Instructions --exclude=index_bodies %s/ %s ' % (webcore, website)
    L.info('about to run:\n%s' % (cmd))
    status, output = subprocess.getstatusoutput(cmd)
    if status != 0:
        raise CommandError(cmd, status, output)

    startdir = os.getcwd()
    if os.path.exists(website):
        os.chdir(website)
        os.symlink('/home/currents/programs', 'programs')
        for tfile in glob.glob('*.txt'):
            # rst2html.py was older (tarball); rst2html is newer (package)
            tbase, ext = os.path.splitext(tfile)
            cmd = 'rst2html.py -r3  %s.txt > %s.html' % (tbase, tbase)
            L.info('about to run:\n%s' % (cmd,))
            status, output = subprocess.getstatusoutput(cmd)
            if status != 0:
                cmd = 'rst2html -r3  %s.txt > %s.html' % (tbase, tbase)
                L.info('about to run:\n%s' % (cmd,))
                status, output = subprocess.getstatusoutput(cmd)
                if status != 0:
                    raise CommandError(cmd, status, output)
        os.chdir(startdir)

    s = string.Template(wi_top)
    tlist = [s.substitute(shipname=shipname,
                instructionstr = get_instructionstr(shortname, shipinfo),
                policy_str = os.path.join('programs/adcp_doc/UHDAS_techdoc',
                      get_policy_str(shortname)))]

    fname_body = os.path.join(webcore, 'index_bodies',
                  'index_body_%s.html' % (shortname))
    wi_body = open(fname_body,'r').read()

    tlist.append(wi_body)
    tlist.append(wi_tail)
    index_fname = os.path.join(website, 'index.html')
#    L.debug('generating %s', index_fname)
    open(index_fname, 'w').write('\n'.join(tlist))


def get_instructionstr(shortname, shipinfo):
    if shortname == 'lmgould':
        pathname = 'programs/%s/wwwcore/Checks_and_Instructions'
        filename = 'ADCP_instructions_lmgould.html'
    elif shortname == 'nbpalmer':
        pathname = 'programs/%s/wwwcore/Checks_and_Instructions'
        filename = 'ADCP_instructions_nbpalmer.html'
    else:
        pathname = 'programs/%s/wwwcore/Checks_and_Instructions'
        filename = 'ADCP_instructions.html'
    fname = os.path.join(pathname % (shipinfo), filename)
    return fname

def get_policy_str(shortname):
#    if shortname in ('lmgould', 'nbpalmer'):
#        filename = 'polar_datapolicy.html'
#    else:
#        filename = 'unols_datapolicy.html'
    return 'unols_datapolicy.html'

def copy_checklist(website, shortname, shipinfo):
    wwwcore  = os.path.join(website,'programs',shipinfo,'wwwcore')

    srcdir = os.path.join(wwwcore, 'Checks_and_Instructions/')

    filename = 'ADCP_checklist_%s.html' % (shortname,)
    srcfile = os.path.join(srcdir,filename)
    tofile = os.path.join(website,'ADCP_checklist.html')
    if os.path.exists(srcfile):
        cmd = 'cp -p %s %s ' % (srcfile, tofile)
    else:
        filename = 'ADCP_checklist.html'
        srcfile = os.path.join(srcdir,filename)
        tofile = os.path.join(website,'ADCP_checklist.html')
        cmd = 'cp -p %s %s ' % (srcfile, tofile)

    L.info('copying ADCP %s checklist from %s' % (shortname, srcfile))

    status, output = subprocess.getstatusoutput(cmd)
    if status != 0:
        raise CommandError(cmd, status, output)

def make_png_archivetree(website, instpings):
    try:
        # "figures" directory already works; add these subdirs
        os.makedirs(os.path.join(website, 'figures', 'png_archive'))
        os.makedirs(os.path.join(website, 'figures', 'thumbnails'))
    except OSError:
        pass
    for instname in instpings:
        try:
            os.mkdir(os.path.join(website, 'figures','png_archive', instname))
        except OSError:
            pass

def make_simplefiglinks(website, instpings, att_dev,
                                    beamstats=[], hdg_inst=None):
    ''' make_simplefiglinks(website, instpings, attitude_devices)
        NOTE: the third argument is either a list of devices
        the last (optional) is for beam statistics (OS only)
        '''

    # sifl = Simple FigLinks
    fname = os.path.join(website, 'simple_figlinks.html')
    slist = [sifl_atthead,]

    # attitude plots
    s = string.Template(sifl_att_link)
    for hcorrdev in att_dev:
#        L.debug('adding %s to simplefiglinks', hcorrdev)
        slist.append(s.substitute(inst=hcorrdev, hdg_inst=hdg_inst))
    if len(att_dev) > 0:
        slist.append('</ul>\n\n')

    # bridge plots
    slist.append(sifl_bridgeblock)

    # beam statistics, if requested (from "atsea" settings, if used)
    if len(beamstats) > 0:
        slist.append(sifl_beamblock)

    slist.append(sifl_sciblock)

    ## take out links on the bottom left
#    L.debug('generating %s', fname)
    open(fname, 'w').write('\n'.join(slist))


def make_ttable(website, instpings):
    figdir = os.path.join(website, 'figures')
    fname = os.path.join(figdir, 'thumbnails.html')
#    L.debug('generating %s', fname)
    s = string.Template(ttable_row)
    tlist = [ttable_head]
    for ptype in adcp_plottypes:
        title = adcp_plottitles[ptype]
        tlist.append('<tr>')
        for inst in instpings:
            tlist.append(s.substitute(inst=inst, ptype=ptype, title=title))
        tlist.append('</tr>')
    tlist.append(ttable_tail)
    open(fname, 'w').write('\n'.join(tlist))


def make_beamdiag_ttable(website, instpings):
    figdir = os.path.join(website, 'figures')
    fname = os.path.join(figdir, 'beam_diagnostics.html')
#    L.debug('generating %s', fname)
    s = string.Template(beamdiag_ttable_row)
    beamdiag_tlist = [beamdiag_ttable_head]
    for ptype in beamdiag_plottypes:
        title = beamdiag_plottitles[ptype]
        beamdiag_tlist.append('<tr>')

#        L.debug('ptype=%s', ptype)
#        L.debug('title=%s', title)

        for inst in instpings:
#            L.debug('inst=%s', inst)
            beamdiag_tlist.append(s.substitute(inst=inst,
                                           ptype=ptype, title=title))
        beamdiag_tlist.append('</tr>')
    beamdiag_tlist.append(ttable_tail)
    open(fname, 'w').write('\n'.join(beamdiag_tlist))



def make_tsstats_ttable(website, instpings):
    figdir = os.path.join(website, 'figures')
    fname = os.path.join(figdir, 'tsstats.html')
#    L.debug('generating %s', fname)
    s = string.Template(tsstats_ttable_row)
    tsstats_tlist = [tsstats_ttable_head]
    for ptype in tsstats_plottypes:
        title = tsstats_plottitles[ptype]
        tsstats_tlist.append('<tr>')

#        L.debug('ptype=%s', ptype)
#        L.debug('title=%s', title)

        for inst in instpings:
#            L.debug('inst=%s', inst)
            tsstats_tlist.append(s.substitute(inst=inst,
                                           ptype=ptype, title=title))
        tsstats_tlist.append('</tr>')
    tsstats_tlist.append(ttable_tail)
    open(fname, 'w').write('\n'.join(tsstats_tlist))



def make_sci_ttable(website, instpings):  #science diagnostics
    figdir = os.path.join(website, 'figures')
    fname = os.path.join(figdir, 'sci.html')
#    L.debug('generating %s', fname)
    s = string.Template(ktvecprof_ttable_row)
    sci_tlist = [ktvecprof_ttable_head]
    for ptype in sci_plottypes:
        title = sci_plottitles[ptype]
        sci_tlist.append('<tr>')

#        L.debug('ptype=%s', ptype)
#        L.debug('title=%s', title)

        for inst in instpings:
#            L.debug('inst=%s', inst)
            sci_tlist.append(s.substitute(inst=inst,
                                           ptype=ptype, title=title))
        sci_tlist.append('</tr>')
    sci_tlist.append(ttable_tail)
    open(fname, 'w').write('\n'.join(sci_tlist))


def make_adcp_figshells(website, instpings):
    figdir = os.path.join(website, 'figures')
    s = string.Template(adcp_figfile_template)
    for inst in instpings:
        for ptype, title in adcp_plottitles.items():
            fname = "%s_%s.html" % (inst, ptype)
            dest = os.path.join(figdir, fname)
            h = s.substitute(inst_lc=inst,
                         inst_uc=inst.upper(),
                         ptype=ptype,
                         title=title)
            open(dest, 'w').write(h)

def make_beamdiag_figshells(website, instpings):
    figdir = os.path.join(website, 'figures')
    s = string.Template(beamdiag_figfile_template)
    for inst in instpings:
        for ptype, title in beamdiag_plottitles.items():
            fname = "%s_beam_%s.html" % (inst, ptype)
            dest = os.path.join(figdir, fname)
            h = s.substitute(inst_lc=inst,
                         inst_uc=inst.upper(),
                         ptype=ptype,
                         title=title)
            open(dest, 'w').write(h)


def make_tsstats_figshells(website, instpings):
    figdir = os.path.join(website, 'figures')
    s = string.Template(tsstats_figfile_template)
    for inst in instpings:
        for ptype, title in tsstats_plottitles.items():
            fname = "%s_%s.html" % (inst, ptype)
            dest = os.path.join(figdir, fname)
            h = s.substitute(inst_lc=inst,
                         inst_uc=inst.upper(),
                         ptype=ptype,
                         title=title)
            open(dest, 'w').write(h)


def make_sci_figshells(website, instpings):
    figdir = os.path.join(website, 'figures')
    s = string.Template(sci_figfile_template)
    for inst in instpings:
        for ptype, title in sci_plottitles.items():
            fname = "%s_%s.html" % (inst, ptype)
            dest = os.path.join(figdir, fname)
            h = s.substitute(inst_lc=inst,
                         inst_uc=inst.upper(),
                         ptype=ptype,
                         title=title)
            open(dest, 'w').write(h)


def make_attitude_figshell(website, att_dev, hdg_inst):
    figdir = os.path.join(website, 'figures')
    s = string.Template(att_figfile_template)
    for hcorr_inst in att_dev:
        title = hcorr_inst
        h = s.substitute(att_dev=hcorr_inst, title=title, hdg_inst=hdg_inst)
        fname = "%s_%sdh.html" % (hcorr_inst,hdg_inst)
#        L.debug('generating %s', fname)
        dest = os.path.join(figdir, fname)
        open(dest, 'w').write(h)
    # same thing for thumbnails
    s = string.Template(att_figfile_thumb_template)
    for hcorr_inst in att_dev:
        title = hcorr_inst
        h = s.substitute(att_dev=hcorr_inst, title=title, hdg_inst=hdg_inst)
        fname = "%s_%sdh_thumb.html" % (hcorr_inst,hdg_inst)
#        L.debug('generating %s', fname)
        dest = os.path.join(figdir, fname)
        open(dest, 'w').write(h)


def make_data_index(website, instpings):
    datadir = os.path.join(website, 'data')
    # instructions, plus links to adcpsect and netcdf output
    fname = os.path.join(datadir, 'index.html')
    open(fname, 'w').write(data_index)

    fname = os.path.join(datadir, 'matlab_data.html')
#    L.debug('generating %s', fname)
    dlist = [datamat_head]
    s=string.Template(datamat_block)
    for inst in instpings:
        ss = s.substitute(inst_long_name = adcp_longnames[inst],
                          inst_uc=inst.upper(),
                          inst_lc = inst)
        dlist.append(ss)
    dlist.append('</body></html>')
    open(fname, 'w').write('\n'.join(dlist))

    fname = os.path.join(datadir, 'netcdf_data.html')
#    L.debug('generating %s', fname)
    dlist = [data_netcdf_head]
    dlist.append('<ul><br>')
    s=string.Template(data_netcdf_block)
    for inst in instpings:
        ss = s.substitute(inst_long_name = adcp_longnames[inst],
                          inst_lc = inst)
        dlist.append(ss)
    dlist.append('</ul><br>')
    dlist.append('</body></html>')
    open(fname, 'w').write('\n'.join(dlist))


def copy_configs(webcore, website, instnames, shortname):
    configdir =os.path.join(website, 'configs')
    fname = os.path.join(configdir, 'index.html')
#    L.debug('generating %s', fname)
    files = ['proc_cfg.py', 'sensor_cfg.py']
    cdir = '/home/adcp/config'
    for fname in files:
        L.info('copying %s to %s' % (os.path.join(cdir,fname),
                                    os.path.join(configdir,fname+'.txt')))
        try:
            shutil.copy2(os.path.join(cdir,fname), os.path.join(configdir,fname+'.txt'))
        except:
            raise
    ## get relevant default cmd files config/cmdfiles
    cdir = '/home/adcp/config/cmdfiles'
    for instname in instnames:
        fname = '%s_default.cmd' % (instname,)
        L.info('copying %s to %s' % (os.path.join(cdir,fname),
                                    os.path.join(configdir,fname+'.txt')))
        try:
            shutil.copy2(os.path.join(cdir,fname), os.path.join(configdir,fname+'.txt'))
        except:
            L.exception('could not copy '+os.path.join(configdir,fname+'.txt'))
            raise

    ## get relevant default cmd files config/cmdfiles
    ddir = '../daily_report'
    fname = 'cals.txt'
    try:
        os.symlink(os.path.join(ddir,fname),
                   os.path.join(website, 'daily_cals.txt'))
    except:
        raise

    ## build index.html
    clist = [cdir_indextop]
    s = string.Template(cdir_link)
    for instname in instnames:
        clist.append(s.substitute(instname = instname))
    rstfile = os.path.join(website,'configs', 'index.rst')
    OF = open(rstfile,'w')
    OF.write('\n'.join(clist))
    OF.close()

    htmlconfigfile = os.path.join(website,'configs', 'index.html')
    cmd = 'rst2html %s > %s' % (rstfile, htmlconfigfile)
    status, output = subprocess.getstatusoutput(cmd)
    if status != 0:
        raise CommandError(cmd, status, output)


def make_rsthtml(rstfilelist):
    for fname in rstfilelist:
        basename = os.path.splitext(fname)[0]
        # rst2html.py was older (tarball); rst2html is newer (package)
        cmd = 'rst2html.py -r3 %s.rst > %s.html' % (basename, basename)
        status, output = subprocess.getstatusoutput(cmd)
        if status != 0:
            cmd = 'rst2html -r3 %s.rst > %s.html' % (basename, basename)
            status, output = subprocess.getstatusoutput(cmd)
            if status != 0:
                raise CommandError(cmd, status, output)

#########

def main():
    icnf = None
    if '--shipinfo' in sys.argv:
        icnf = sys.argv.index('--shipinfo')
    elif '-p' in sys.argv:
        icnf = sys.argv.index('-p')
    if icnf is None:
        shipinfo = 'onship'
        from  onship import shipnames
    else:
        shipinfo = sys.argv[icnf+1]
        mod = __import__(shipinfo)
        shipnames = getattr(mod, 'shipnames')

    qsletters=[]
    for k in shipnames.shipletters:
        qsletters.append("'%s'" % k)
    shipletters=string.join(qsletters,', ')
    usage = string.join(["\n\nusage:",
             "  ",
             " uhdas_webgen.py  -w www -s ka ",
             " uhdas_webgen.py  --website www --shipkey ka",
             "   default template is 'PROGRAMS/onship/wwwcore'",
             "   default website is 'www'",
             "   MUST specify 'shipkey' ",
             "   ",
             " to use a python module with ship information, use:",
             " --shipinfo shipinfo # or '-p shipinfo' ",
             " and appropriate ship letters.",
             "   then default template is 'PROGRAMS/xxx/wwwcore'",
             "   (where xxx is specified using --shipinfo)",
             "   choose one ship abbreviation from:",
             shipletters,
             ],
            '\n')

    if len(sys.argv) == 1:
        print(usage)
        sys.exit()

    parser = OptionParser(usage)

    parser.add_option("-w",  "--website", dest="website",
       default='www',
       help="uhdas web site")

    parser.add_option("-s",  "--shipkey", dest="shipkey",
       help="ship abbreviation")

    parser.add_option("-p",  "--shipinfo", dest="shipinfo",
       default=None,
       help="python module with ship configuration (compatible with 'onship')")


    (options, args) = parser.parse_args()

    if options.website is None:
        options.website = 'www'

    if not options.shipkey:
        print(usage)
        raise IOError('MUST specify ship letters')

    # already got shipnames

    # get shipnames and proc_defaults
    if options.shipinfo is None:
        import onship
        from onship import proc_defaults
        wwwcore =  os.path.join(os.path.dirname(onship.__file__),'wwwcore')
    else:
        # get from another directory
        mod = __import__(shipinfo)    # eg onship
        proc_defaults = mod.proc_defaults
        wwwcore =  os.path.join(os.path.dirname(mod.__file__),'wwwcore')


    # instruments and pingtypes.  This is the order of the the web site columns
    instpings=[]
    instnames=[]

    L.info('shipkey is %s' % (options.shipkey,))

    for inst in list(proc_defaults.h_align[options.shipkey].keys()):
        instnames.append(inst)
        if inst[:2] != 'os':
            instpings.append(inst)
        else:
            instpings.append(inst + 'bb')
            instpings.append(inst + 'nb')

    shipname  = shipnames.shipnames[options.shipkey]
    shortname = shipnames.shipdirs[options.shipkey]
    hdg_inst  = proc_defaults.hdg_inst_msgs[options.shipkey][0][0]
    att_dev   = []
    for inst_msg in proc_defaults.hdg_inst_msgs[options.shipkey][1:]:
        if inst_msg[0] != hdg_inst:
            att_dev.append(inst_msg[0])
    beamstats = Udef.defaults['beamstats'] # might want to move this

    if os.path.exists(options.website):
        print('web site %s exists, exiting' % (options.website))
        sys.exit()

    print('web page for ', shipname)
    print('found instruments: ', instnames)
    print('found sonars (instping): ', instpings)
    print('found attitude devices: ', att_dev)

    ##----- core web site and info  --------
    make_www_index(wwwcore, options.website, shipinfo, shipname, shortname)
    copy_checklist(options.website, shortname, shipinfo)

    copy_configs(wwwcore, options.website, instnames, shortname)

    ##----- figures and data --------
    make_png_archivetree(options.website, instpings)

    make_adcp_figshells(options.website, instpings)
    make_attitude_figshell(options.website, att_dev, hdg_inst)
    make_beamdiag_figshells(options.website, instpings)
    make_tsstats_figshells(options.website, instpings)
    make_sci_figshells(options.website, instpings)

    ## these are replicated in DAS_while_logging.py, so any additions
    ##   to the collection of plots should be replicated there
    make_ttable(options.website, instpings)
    make_simplefiglinks(options.website, instpings, att_dev,
                        beamstats=beamstats, hdg_inst=hdg_inst)
    make_beamdiag_ttable(options.website, instpings)
    make_tsstats_ttable(options.website, instpings)
    make_sci_ttable(options.website, instpings)

    make_data_index(options.website, instpings)

#   # none at the moment; should convert calibrations
