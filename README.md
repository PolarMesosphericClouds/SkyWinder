# SkyWinder
[Python in Heliophysics Community (PyHC)]: https://heliopython.org/

## Overview
SkyWinder is an open-source Python package useful for instrument control, telemetry, and image analysis. It is adapted from software that successfully managed flight control, telemetry, preliminary image analysis, and data visualization for a balloon-borne mission and it has broad uses for mid- and upper-atmosphere science instrumentation including aurora, cloud, and airglow imagers. SkyWinder will save future aeronomy experiments significant time and money, and lowers the barrier to entry in analyzing data hosted in public available repositories.

Our software consists of two distinct parts: the flight and analysis modules. The SkyWinder flight package includes modular distributed flight control including telemetry and subsystem coordination for running mobile aeronomy experiments such as balloon-borne payloads, airplanes, sounding rockets, and suborbital reusable launch vehicles (sRLVs), as well as isolated semi-autonomous ground instruments. The SkyWinder analysis software provides functionality more broadly useful in neutral upper atmosphere dynamics, such as pointing reconstruction, image projection, preliminary image processing, and various image analysis techniques.

## Installation
SkyWinder requires Python 3.9 or newer.

To install `skywinder` on macOS or Linux, open a terminal and run:
```Shell
python -m pip install skywinder
```

## Citing SkyWinder

##Acknowledgments
Development of SkyWinder was supported by the [Python in Heliophysics Community (PyHC)]. SkyWinder was developed from the software that ran on the PMC-Turbo balloon borne experiment, which was supported by NASA.
