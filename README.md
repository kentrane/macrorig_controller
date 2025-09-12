# PPFE Macrorig Controller

A Python-based controller software for the PPFE macrorig system, designed for scanning RF beampatterns, but can be modified to measure many other 2D things.

## Overview

This software provides control for the motors, the digitizer and lets you save and plot the data in a grid

## Requirements

- Python
- Required Python packages (see `requirements.txt`)
- NI-DAQmx driver for your operating system (works maybe only on windows and linux)

## Installation
0. Make a new python environment for this, not required but nice

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Install the NI-DAQmx driver:
   ```bash
   python -m nidaqmx installdriver
   ```

## Usage

Run the main controller application:
```bash
python macrorig_control.py
```

The main control file (`macrorig_control.py`) allows you to adjust basic parameters for scanning and data acquisition operations.

## Project Structure

- `macrorig_control.py` - Main control application
- `motor_controller.py` - Motor control
- `ni_daq_reader.py` - NI DAQ interface
- `plotting_utils.py` - Data visualization utilities
- `scan_rig.py` - Everything to do with the scanning is here
- `requirements.txt` - Python dependencies


