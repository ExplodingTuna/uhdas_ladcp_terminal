# uhdas_ladcp_terminal
Modified version of UHDAS ladcp deployment/recovery terminal



Disclaimer
==========
This repository is a scientific product and is not official communication of the National Oceanic and
Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is
provided on an ‘as is’ basis and the user assumes responsibility for its use. Any claims against the Department of
Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed
by all applicable Federal law. Any reference to specific commercial products, processes, or services by service
mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or
favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a
DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by
DOC or the United States Government.

# Installing on Ubunutu 16.04 && 18.04

Install requirements
```bash
sudo apt-get install python-six \
python-future \
python-tk \
python-pmw \
python-numpy
```
install UHDAS package
```bash
python ./runsetup.py --sudo
```

# Installing on Debian with python 3

Install requirements 
'''bash
sudo apt-get install python3-six python3-future python3-tk python3-pmw python3-numpy
'''

# Modifications to UHDAS installation to remove codas and pycurrents dependencies 
modify runsetup.py to remove all codas references</br>
modify setup.py and remove all pycurrents references</br>
copy logutils.py to uhdas/system folder</br>
edit rditerm.py</br>
    change from pycurrents.system import logutils to from uhdas.system import logutils</br>
    modify method "_validated_commands" so that the send script can ignore lines starting with "$" or ";".</br>
    this will allow BBTALK scripts to be read withput causing any errors.</br>
    add Prefix and Cruise Name lables.</br>
    modify "make_filename" method to create a ladcp processing compatible filename</br>
    modify "terminal" class to include suffix and cruiseName in the constructor</br>





