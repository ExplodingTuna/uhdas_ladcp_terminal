# uhdas_ladcp_terminal
Modified version of UHDAS ladcp deployment/recovery terminal

# Installing on Ubunutu 16.04


install six 
"sudo apt-get install python-six"
install future 
"sudo apt-get install python-future"
install Tkinter 
"sudo apt-get install python-tk" 
install pmw 
"sudo apt-get install python-pmw" 
install numpy 
"sudo apt-get install python-numpy"
install UHDAS package
python ./runsetup.py --sudo



# Modifications to UHDAS installation to remove codas and pycurrents dependencies 
modify runsetup.py to remove all codas references
modify setup.py and remove all pycurrents references
copy logutils.py to uhdas/system folder
edit rditerm.py
    change from pycurrents.system import logutils to from uhdas.system import logutils
    modify method "_validated_commands" so that the send script can ignore lines starting with "$" or ";".
    this will allow BBTALK scripts to be read withput causing any errors.
    add Prefix and Cruise Name lables.
    modify "make_filename" method to create a ladcp processing compatible filename
    modify "terminal" class to include suffix and cruiseName in the constructor





