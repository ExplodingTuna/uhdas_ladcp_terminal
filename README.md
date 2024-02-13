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

# uhdas_ladcp_terminal 
![Screenshot_2024-02-02_12-14-13](https://github.com/ExplodingTuna/uhdas_ladcp_terminal/assets/146979376/89f1556b-a4f9-42a2-90c3-bf0fd6c7fd68)

# Installation
This installation guide was tested with Debian Bookworm and python 3. This guide may not work with other Linux distributions or may need some adjustments.

## Install requirements 
Make sure user is part of the dialout group before beggining. 

```bash
sudo usermod -a -G dialout $USER
```
Additionally, install python 3 and lrzsz. If you don't have these installed, the installation process covers this.

## Installing with Debian Bookworm
```bash
sudo apt-get install python3-six python3-future python3-tk python3-pmw python3-numpy
sudo apt-get install lrzsz
cd uhdas_ladcp_terminal/
sudo -E ./install
python3 ./runsetup.py install --sudo
```

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





