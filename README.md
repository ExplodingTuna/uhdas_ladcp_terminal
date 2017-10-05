# uhdas_ladcp_terminal
Modified version of UHDAS ladcp deployment/recovery terminal

# Installing on Ubunutu 16.04


install six</br>
"sudo apt-get install python-six"</br>
install future</br>
"sudo apt-get install python-future"</br>
install Tkinter</br>
"sudo apt-get install python-tk"</br> 
install pmw</br>
"sudo apt-get install python-pmw"</br> 
install numpy</br>
"sudo apt-get install python-numpy"</br>
install UHDAS package</br>
python ./runsetup.py --sudo</br>



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





