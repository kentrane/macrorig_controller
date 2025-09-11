"""
PPFE Macro Rig Controller
Author: Kenneth, based on original script by Stig Jensen
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict
import matplotlib.pyplot as plt
from motor_controller import MotorController
from scan_rig import ScanRig
from ni_daq_reader import NIDAQReader
from plotting_utils import plot_scan_data_pcolormesh


#Calculates scan time in seconds based on number of points, movement time per point, and dwell time per point
def calculate_scan_time(num_points: int, movement_time: float, dwell_time: float) -> float:
    return num_points * movement_time + num_points * dwell_time

#Formats time in seconds to a more readable format (H:MM:SS or M:SS or SSs)
def format_time(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    elif minutes > 0:
        return f"{minutes}:{secs:02d}"
    else:
        return f"{secs}s"


def plot_scan_data(scan_data: List[Dict], title: str = "Scan Data", use_pcolormesh: bool = True) -> None:
    """Plot scan data using plotting utilities - wrapper for backward compatibility"""
    plot_scan_data_pcolormesh(scan_data, title=title)

def plot_scan_coordinates(coordinates: List[Tuple[float, float]], title: str = "Scan Pattern", scan_time: Optional[float] = None) -> None:
    x_coords = [coord[0] for coord in coordinates]
    y_coords = [coord[1] for coord in coordinates]
    plt.figure(figsize=(10, 8))
    plt.plot(x_coords, y_coords, 'm--', alpha=0.5, linewidth=1, label='Scan path')
    plt.scatter(x_coords, y_coords, c=range(len(coordinates)), label='Scan points')
    plt.scatter(x_coords[0], y_coords[0], c='red', marker='o', label='Start')
    plt.scatter(x_coords[-1], y_coords[-1], c='green', marker='s', label='End')
    
    plt.xlabel('X Position (mm)')
    plt.ylabel('Y Position (mm)')
    title_text = f'{title} - {len(coordinates)} points'
    if scan_time is not None:
        title_text += f' (Est. {format_time(scan_time)})'
    plt.title(title_text)
    plt.grid(True, alpha=0.3)
    plt.gca().invert_yaxis()  # Invert Y-axis to match physical coordinates
    plt.legend()
    plt.axis('equal')
    plt.tight_layout()
    plt.show()


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

        scan_pattern = rig.scan_rectangle(width=50, height=50, step_x=5, step_y=5)
        print(f"scan: {len(scan_pattern)} points")
        
        # Calculate estimated scan time
        estimated_time = calculate_scan_time(len(scan_pattern), movement_time=1, dwell_time=0.5)
        print(f"Estimated scan time: {format_time(estimated_time)}")

        # Plot the scan pattern
        #plot_scan_coordinates(scan_pattern, "scan pattern", estimated_time)
        
        prompt = input("do the scan? (y/n): ")
        if prompt.lower() == 'y':
            print("doing scan")
            scan_data = rig.execute_scan(scan_pattern, dwell_time=0.5, daq_channel=2, acquisition_time=0.1, live_plot=True)
            if scan_data:
                rig.save_scan_data(scan_data, f"scan_data_{int(time.time())}.csv")
                #plot_scan_data(scan_data, "Completed Scan Results")
        else: 
            print("okokok, no scan")
        
        
    finally:
        rig.move_to_origin()
        act.disconnect()
        print("\nfini!")


if __name__ == "__main__":
    main()