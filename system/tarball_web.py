# components to generate currents.soest.hawaii.edu
#      index.html for each ship


import string

from pycurrents.system import Bunch
from pycurrents.adcp import adcp_specs
from pycurrents.adcp.adcp_specs import adcp_plotlist

from onship import shipnames


## ttable is "thumbnail table"

#shipname eg "Kilo Moana"
# institution eg "University of Hawaii"
ttable_head = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
   <meta  http-equiv="Refresh" content="120">
   <title>${shipname} UHDAS at-sea data snippet</title>
</head>
<body>
<br>
<div style="text-align: center;"><big><span style="font-weight:
bold;"> ${shipname} UHDAS figures</span>
</big></div>

<br><br>

<div style="margin-left: 10em;margin-right: 10em;">
These plots were generated at the University of Hawaii from data sent
daily by email from the ${institution} ship <b>${shipname}</b>.
Every 15-30min, a computer dedicated to ADCP data aquisition
and processing updates a CODAS
database by fully processing single-ping data from the RD Instruments
ADCPs on board.
A daily email to UH contains status updates for the computer system,
data acquisition, archiving, processing, and plotting, and a sample of
data. Samples of recent
data are shown below (if no figure is available, the ship is probably
in port)
</div>

<br>
<br>
<br>

<table
  style="width: 100%; text-align: center;  vertical-align: middle;
  background-color: rgb(204, 204, 204)";
  border="1" cellpadding="2" cellspacing="2">
   <tbody>
<!-- PROFILES -->
"""

res_comment = Bunch(
     high = '1 day, high resolution',
     low =  '3 days, low resolution',
)

# 'low', 'high' refer to the target link
reslink = Bunch(
     high=  '''<br><a href="indexH.html">${comment}</a><br><br>''',
     low = '''<br><a href="index.html">${comment}</a><br><br>''',
)

restitle = '''<br><br>
     <div style="text-align: center;"><big>
     <span style="font-weight: bold;"> ${comment}</span>
     <br><br>'''


homelink = '<br><a href="%s">UHDAS at-sea table of ships</a><br><br>' % (
    'http://currents.soest.hawaii.edu/uhdas_fromships.html')



# long_sonarname eg "os75 narrowband mode"
ttitlerow = '''
   <td style="vertical-align: top; text-align: center;">
    ${long_sonarname}<br>
      </td>
  '''

# sonar eg 'os75nb', 'wh300'
# plottype eg 'vect', 'cont'
# resolution is '' or 'H'
ttable_row = '''
       <td style="text-align: center; vertical-align: middle;
                 background-color: rgb(204, 204, 204);"
                 href="./${sonar}_${plottype}${resolution}.png">
                 <img alt="${sonar} ${plottype}"
                 src="./${sonar}_${plottype}_thumb${resolution}.png"
       style="border: 0px solid ;" align="middle"> </a> <br>
       </td>
'''


ttable_tail = """
   </tbody>
</table>
</body>
</html>
"""


def sort_sonarlist(sonarlist):
    '''
    sonarlist may just be a list of model+freq+pingtype
    '''
    sdict=Bunch()
    for s in sonarlist:
        sdict[adcp_plotlist.index(s)] = s
    kk = list(sdict.keys())
    kk.sort()
#
    slist=[]
    for k in kk:
        slist.append(sdict[k])
    return slist


def html_str(sonarlist, shipkey, resolution):
    shipname=shipnames.shipnames[shipkey]
    institution=shipnames.institutions[shipkey]
    plottypes = ('vect', 'cont')
    slist=[]
    # "s" will get recycled
    s = string.Template(ttable_head)
    header = s.substitute(shipname=shipname,
                          institution=institution)
    slist.append(header)
    if len(sonarlist) == 0:
        slist.append('<br><br> NO SONARS LOGGING <br><br>')
    else:
        if resolution == 'H':
            s=string.Template(reslink['low'])
            slist.append(s.substitute(comment=res_comment['low']))

            slist.append(homelink)

            s=string.Template(restitle)
            slist.append(s.substitute(comment=res_comment['high']))
        else:
            s=string.Template(reslink['high'])
            slist.append(s.substitute(comment=res_comment['high']))

            slist.append(homelink)

            s=string.Template(restitle)
            slist.append(s.substitute(comment=res_comment['low']))
    #

    #
    st = string.Template(ttitlerow)
    sr = string.Template(ttable_row)
    #
    slist.append('<tr>')

    sorted_sonarlist=sort_sonarlist(sonarlist)

    for instping in sorted_sonarlist:
        title = st.substitute(
            long_sonarname=adcp_specs.adcp_longnames[instping])
        slist.append(title)
    slist.append('</tr>')
    #
    for ptype in plottypes:
        slist.append('<tr>')
        for instping in sorted_sonarlist:
            slist.append(sr.substitute(sonar=instping,
                                       plottype=ptype,
                                       resolution=resolution))
        slist.append('</tr>')
    #
    slist.append(ttable_tail)
    return '\n'.join(slist)


