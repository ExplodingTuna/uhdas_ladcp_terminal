This directory forms the core logging utilities
for UHDAS.  There are two command-line executables,
  - ser_asc: a general-purpose program to log and timestamp ascii data
  - ser_bin: a program to log binary data output by TRDI ADCPs

Files:
serial_notes.txt (notes about these programs when they were written)
ser_doc.txt (how to use the commandline calls)

These programs are available at the University of Hawaii
"currents" group at http://currents.soest.hawaii.edu/hg
in the directory "uhdas" (go to "serial_c").

These have been tested under GCC linux and OSX.  They use
unix-specific subroutines, so they will not work on Windows.

Examples:

see ser_doc.txt for clues

(1) logging on port ttyUSB0
    yearbase is 2012
    baud 4800
    output directory /home/data/datadir
    prefix test
    flush buffers
    naming convention ("m 1")       '%s%4d_%3d_%5d.%s' % (prefix, yearbase, yearday, seconds_in_day, message)
    suffix (also called "message") 'hdg
    timestamp
    expect checksum
    only log these messages: $HEHDT
    files roll over on the even-numbered hour

    ==> computer clock should be set to UTC
    ==> NOTE yearday is zero-based

    files would be like this:   2012/08/22 = 234

              test2012_234_72000.hdg


$PHTRO,0.48,M,0.43,T*43
$PHLIN,0.000,-0.002,0.006*78
$PHSPD,0.003,0.001,0.004*5B
$PHCMP,4131.43,N,0.00,N*76
$PHINF,30000102*75
$HEHDT,26.156,T*19
$PHTRO,0.50,M,0.44,T*4D
$PHLIN,0.003,-0.002,0.009*74
$PHSPD,0.001,-0.000,0.001*70
$PHCMP,4131.43,N,0.00,N*76

------------------
/usr/local/bin/ser_asc -y 2012 -P ttyn4 -b 9600 -d /home/adcp/tmp -f test -F -m 1 -H 2 -e txt -at

-goes to test2012_044_76251.txt
-all lines
-timestamp preceeds each line
-rolls over at 0000UTC, 0200UTC, 0400UTC, etc

--------------------

/usr/local/bin/ser_asc -y 2012 -P ttyn4 -b 9600 -d /home/adcp/tmp -f test -F -m 3 -H 24 -e txt -a

-all lines
-timestamp preceeds each line
-rolls over at 000UTC
- NOTE: If you start logging again, you *will* overwrite the file.
    Solution -- use a different file naming convention

test2012.044txt

-------
add checksum
only use HEHDT messages

/usr/local/bin/ser_asc -y 2012 -P ttyn4 -b 9600 -d /home/adcp/tmp -f test -F -m 3 -H 24 -e txt -tc '$HEHDT'

-all lines
-timestamp preceeds each line
-rolls over at 000UTC
- NOTE: If you start logging again, you *will* overwrite the file.
    Solution -- use a different file naming convention

test2012.044txt

----------
2012-02-14
All code here was written by Eric Firing, Univ. Hawaii
Additional docs by Julia Hummon, University of Hawaii
----------




