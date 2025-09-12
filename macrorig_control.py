import time
import numpy as np
from datetime import datetime
from motor_controller import MotorController
from scan_rig import ScanRig
from ni_daq_reader import NIDAQReader


def main():
    # Initialize hardware
    act = MotorController()
    if not act.connect():
        print("I try to connect, but it no want")
        print("maybe check the cables")
        return
    print("Connected to motor controller :)")
    
    if not act.setup_motors(home_motors=True):
        print("Motor controller setup failed :( I disconnect now ok?")
        act.disconnect()
        return
    print("Motor controller is setup")
    
    # Uncomment the next line if you want to manually home motors now:
    # act.home_motors()
    
    daq = None
    try:
        daq = NIDAQReader()
        if daq.connect():
            print("DAQ connected")
        else:
            print("DAQ connection failed, continuing without DAQ")
            daq = None
    except Exception as e:
        print(f"DAQ initialization failed: {e}")
        daq = None
    
    rig = ScanRig(act, daq)

    rig.set_origin(600, 600)  # set some origin (x,y)
    
    try:
        rig.move_to_origin()

        scan_pattern = rig.scan_rectangle(width=100, height=100, step_x=5, step_y=5)
        print(f"scan: {len(scan_pattern)} points")
        prompt = input("do the scan? (y/n): ")
        if prompt.lower() == 'y':
            print("doing scan")
            scan_data = rig.execute_scan(scan_pattern, dwell_time=0, daq_channel=2, acquisition_time=0.05, live_plot=True)
        else: 
            print("okokok, no scan")
        
        
    finally:
        rig.move_to_origin()
        act.disconnect()
        print("\nfini!")


if __name__ == "__main__":
    main()