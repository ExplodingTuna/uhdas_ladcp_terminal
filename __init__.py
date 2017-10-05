"""
University of Hawaii shipboard ADCP data acquisition system.

This package depends on the pycurrents and onship packages.
It provides the core control and logging code, together with
a more general serial terminal capability, and a specialization
for communicating with lowered ADCPs.
"""
from future import standard_library
standard_library.install_hooks()


