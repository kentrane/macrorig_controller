"""
PPFE Macro Rig Controller
Author: Kenneth, based on original script by Stig Jensen
"""

import serial
from serial.tools import list_ports
import time
import numpy as np
from typing import List, Tuple, Optional, Dict
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from ni_daq_reader import NIDAQReader

class MotorController:
    # Hardware identifier for the stepper controller
    act_HWID = 'USB VID:PID=0403:6001 SER=FT4PZ8BBA'
    
    def __init__(self):
        self.connected = False
        self.setup_complete = False
        self.ser: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        if self.connected:
            print("Already connected to stepper controller")
            return True
            
        ports = list_ports.comports()
        print(f"Available ports: {[port.device for port in ports]}")
        for port, desc, hwid in sorted(ports):
            if hwid == self.act_HWID:
                print(f"Found act on {port}: {desc}")
                try:
                    self.ser = serial.Serial(
                        port, 
                        baudrate=9600,
                        bytesize=serial.SEVENBITS,
                        stopbits=serial.STOPBITS_ONE,
                        parity=serial.PARITY_ODD,
                        timeout=5
                    )
                    self.connected = True
                    print("Connected to motor act")
                    return True
                except Exception as e:
                    print(f"Failed to connect to {port}: {e}")
                    
        print("Motor controller not found")
        return False
    
    def disconnect(self) -> None:
        if self.ser:
            self.ser.close()
            self.connected = False
            self.setup_complete = False
    
    def _send_command(self, motor: str, command: str) -> str:
        if not self.connected or not self.ser:
            raise RuntimeError("act not connected")
            
        full_command = f"{motor}{command};"
        self.ser.write(full_command.encode())
        response = self.ser.read_until(b'\r')
        return response.decode('ascii').strip()
    
    def setup_motors(self) -> bool:
        if self.setup_complete:
            print("Motors already set up")
            return True
            
        if not self.connected:
            print("plz connect before setup")
            return False
            
        try:
            # Configure both motors (1=X, 2=Y)
            for motor in ["1", "2"]:
                self._send_command(motor, f'ADDR={motor}')
                self._send_command(motor, 'SON=0')  # Servo off
                self._send_command(motor, 'CT=5000')  # Control time
                self._send_command(motor, 'CS=2000')  # Control speed
                self._send_command(motor, 'AC=1000')  # Acceleration
                self._send_command(motor, 'VM=100')   # Max velocity
                self._send_command(motor, 'VS=10')    # Start velocity
                self._send_command(motor, 'PLS=1')    # Plus limit
                self._send_command(motor, 'NLS=1')    # Minus limit
                self._send_command(motor, 'CB25=1')   # Control bit 25
                self._send_command(motor, 'CB26=1')   # Control bit 26
                self._send_command(motor, 'SON=1')    # Servo on
                self._send_command(motor, 'CB3=1')    # Control bit 3
                self._send_command(motor, 'CB2=1')    # Control bit 2
                self._send_command(motor, 'CON=26.6667')  # Conversion factor
                self._send_command(motor, 'CND2=8')   # Condition 2
                self._send_command(motor, 'CTM2=7')   # Control mode 2
            
            # Additional setup
            self._send_command('', '1AC=5000')  # Motor 1 acceleration
            self._send_command('', '1VM=200')   # Motor 1 velocity
            
            # Home both motors
            for motor in ['1', '2']:
                self._send_command(motor, 'R3=VM')  # Save current velocity
                self._send_command(motor, 'VM=100') # Set homing velocity
                self._send_command(motor, 'SR-')    # Start reverse homing
                self._wait_for_motion_complete(motor)
                self._send_command(motor, 'VM=R3')  # Restore velocity
                self._send_command(motor, 'AP=0')   # Set absolute position to 0
            
            self.setup_complete = True
            print("Motor setup complete")
            return True
            
        except Exception as e:
            print(f"Motor setup not complete, plz fix: {e}")
            return False
    
    def _wait_for_motion_complete(self, motor: str) -> None:
        while True:
            status = self._send_command(motor, 'RS')
            if 'RS=0' in status:  # Motion complete
                break
            time.sleep(0.1) # don't run too fast
    
    def move_to(self, x: float, y: float) -> bool:
        if not self.setup_complete:
            print("Motors not set up")
            return False
            
        try:
            print(f"Moving to x:{x}, y:{y}")
            
            # Move X axis
            self._send_command('1', f'SP={int(x)}')
            self._wait_for_motion_complete('1')
            
            # Move Y axis  
            self._send_command('2', f'SP={int(y)}')
            self._wait_for_motion_complete('2')
            
            return True
            
        except Exception as e:
            print(f"Move failed: {e}")
            return False

class ScanRig:
    def __init__(self, act: MotorController, daq: Optional[NIDAQReader] = None):
        self.act = act
        self.daq = daq
        self.origin_x = 0
        self.origin_y = 0
        
    def set_origin(self, x: float, y: float) -> None:
        self.origin_x = x
        self.origin_y = y
        print(f"Origin set to ({x}, {y})")
    
    
    def move_to_origin(self) -> bool:
        return self.act.move_to(self.origin_x, self.origin_y)
    
    
    def scan_circle(self, radius: float, step_x: float = 1.0, step_y: float = 1.0) -> List[Tuple[float, float]]:
        coordinates = []
        
        # Generate y-range (reversed due to act setup)
        y_range = -np.arange(-radius, radius + step_y, step_y)
        
        for dy in y_range:
            # Calculate x-range for each y position
            if abs(dy) <= radius:
                x_half_range = radius * np.sqrt(1 - (dy / radius) ** 2)
                x_range = np.arange(-x_half_range, x_half_range + step_x, step_x)
                
                for dx in x_range:
                    coordinates.append((self.origin_x + dx, self.origin_y + dy))
        
        return coordinates
    
    def scan_rectangle(self, width: float, height: float, step_x: float = 1.0, step_y: float = 1.0) -> List[Tuple[float, float]]:
        coordinates = []
        
        # Calculate half dimensions for centering
        half_width = width / 2
        half_height = height / 2
        
        # Generate y-range from top to bottom
        y_steps = np.arange(-half_height, half_height + step_y, step_y)
        
        for i, dy in enumerate(y_steps):
            # Generate x-range  
            x_steps = np.arange(-half_width, half_width + step_x, step_x)
            
            # Alternate scan direction for efficient pattern
            if i % 2 == 1:  # Odd rows: scan right to left
                x_steps = x_steps[::-1]
            
            for dx in x_steps:
                coordinates.append((self.origin_x + dx, self.origin_y + dy))
        
        return coordinates
    
    def execute_scan(self, coordinates: List[Tuple[float, float]], 
                    dwell_time: float = 1.0, 
                    daq_channel: int = 0,
                    acquisition_time: float = 0.1,
                    filter_type: str = "mean",
                    live_plot: bool = False) -> List[Dict]:
        if not coordinates:
            print("No coordinates provided")
            return []
            
        if not self.daq:
            print("ERROR: DAQ not connected. Cannot perform scan without DAQ readings.")
            return []
            
        print(f"Starting scan of {len(coordinates)} points")
        scan_data = []  # Local dataset
        
        # Setup live plotting if requested
        if live_plot:
            plt.ion()  # Interactive mode on
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.set_xlabel('X Position (mm)')
            ax.set_ylabel('Y Position (mm)')
            ax.set_title('Scan Data')
            ax.grid(True, alpha=0.3)
            
            # Plot scan path
            x_path = [coord[0] for coord in coordinates]
            y_path = [coord[1] for coord in coordinates]
            ax.plot(x_path, y_path, 'k--', alpha=0.3, linewidth=1, label='Scan path')
            
            # Initialize empty scatter plot for data points
            scat = ax.scatter([], [], c=[], cmap='viridis', s=50, alpha=0.8)
            ax.legend()
            plt.draw()
        
        first_move = True
        for i, (x, y) in enumerate(coordinates):
            if not self.act.move_to(x, y):
                print(f"Failed to move to position {i}: ({x}, {y})")
                return scan_data  # Return partial data
                
            # Extra settling time for first move
            if first_move:
                time.sleep(2.0)
                first_move = False
            
            time.sleep(dwell_time)
            
            # Take DAQ reading
            try:
                daq_value = self.daq.read_analog_filtered(
                    channel=daq_channel,
                    acquisition_time=acquisition_time,
                    filter_type=filter_type
                )
                print(f"Point {i+1}/{len(coordinates)}: ({x:.1f}, {y:.1f}) -> {daq_value:.4f}V")
            except Exception as e:
                print(f"DAQ read failed at point {i}: {e}")
                return scan_data  # Return partial data on DAQ failure
            
            # Store data point
            data_point = {
                'point_index': i,
                'x': x,
                'y': y,
                'daq_value': daq_value
            }
            scan_data.append(data_point)
            
            # Update live plot if enabled
            if live_plot:
                x_vals = [point['x'] for point in scan_data]
                y_vals = [point['y'] for point in scan_data]
                daq_vals = [point['daq_value'] for point in scan_data]
                
                # Clear and redraw scatter plot with new data
                scat.remove()
                scat = ax.scatter(x_vals, y_vals, c=daq_vals, cmap='viridis', s=50, alpha=0.8)
                
                # Update colorbar on first point or if range changes significantly  
                if i == 0 or (i > 0 and (max(daq_vals) - min(daq_vals)) > 0.1):
                    if hasattr(ax, 'cbar'):
                        ax.cbar.remove()
                    ax.cbar = plt.colorbar(scat, ax=ax, label='DAQ Value (V)')
                
                plt.draw()
                plt.pause(0.01)  # Small pause for plot update
        
        if live_plot:
            plt.ioff()  # Turn off interactive mode
            
        print("Scan completed")
        return scan_data
    
    def test_boundaries(self, width: float, height: float) -> bool:
        half_width = width / 2
        half_height = height / 2
        
        test_points = [
            (self.origin_x, self.origin_y),                    # Center
            (self.origin_x + half_width, self.origin_y),       # Right
            (self.origin_x - half_width, self.origin_y),       # Left  
            (self.origin_x, self.origin_y + half_height),      # Top
            (self.origin_x, self.origin_y - half_height),      # Bottom
        ]
        
        #print("Testing if bro is respecting boundaries:")
        for i, (x, y) in enumerate(test_points):
            print(f"  Point {i+1}: ({x}, {y})")
            #Maybe have some slower speed possible here?
            if not self.act.move_to(x, y):
                return False
            time.sleep(1.5) # wait a bit here
        
        # Test done, now go back to origin
        return self.move_to_origin()
    
    def save_scan_data(self, scan_data: List[Dict], filename: str) -> bool:
        """Save scan data to CSV file"""
        if not scan_data:
            print("No scan data to save")
            return False
            
        try:
            import csv
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['point_index', 'x', 'y', 'daq_value']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(scan_data)
            
            print(f"Scan data saved to {filename}")
            return True
        except Exception as e:
            print(f"Failed to save scan data: {e}")
            return False
    
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


def plot_scan_data(scan_data: List[Dict], title: str = "Scan Data") -> None:
    """Plot scan data with DAQ values as color-coded points"""
    if not scan_data:
        print("No scan data to plot")
        return
    
    x_vals = [point['x'] for point in scan_data]
    y_vals = [point['y'] for point in scan_data]
    daq_vals = [point['daq_value'] for point in scan_data]
    
    plt.figure(figsize=(12, 10))
    
    # Create scatter plot with color mapping
    scatter = plt.scatter(x_vals, y_vals, c=daq_vals, cmap='viridis', s=100, alpha=0.8, edgecolors='black', linewidth=0.5)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, label='DAQ Value (V)')
    cbar.ax.tick_params(labelsize=10)
    
    # Plot scan path
    plt.plot(x_vals, y_vals, 'k--', alpha=0.3, linewidth=1, label='Scan path')
    
    # Mark start and end points
    plt.scatter(x_vals[0], y_vals[0], c='red', marker='o', s=150, label='Start', edgecolors='black', linewidth=2)
    plt.scatter(x_vals[-1], y_vals[-1], c='green', marker='s', s=150, label='End', edgecolors='black', linewidth=2)
    
    plt.xlabel('X Position (mm)', fontsize=12)
    plt.ylabel('Y Position (mm)', fontsize=12)
    plt.title(f'{title} - {len(scan_data)} points\nDAQ Range: {min(daq_vals):.4f}V to {max(daq_vals):.4f}V', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.axis('equal')
    plt.tight_layout()
    plt.show()

def plot_scan_coordinates(coordinates: List[Tuple[float, float]], title: str = "Scan Pattern", scan_time: float = None) -> None:
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
    
    if not act.setup_motors():
        print("Motor controller setup failed :( I disconnect now ok?")
        act.disconnect()
        return
    print("Motor controller is setup")
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

    rig.set_origin(904, 620)  # set some origin (x,y)
    
    try:
        rig.move_to_origin()

        scan_pattern = rig.scan_rectangle(width=20, height=15, step_x=2, step_y=2)
        print(f"scan: {len(scan_pattern)} points")
        
        # Calculate estimated scan time
        estimated_time = calculate_scan_time(len(scan_pattern), movement_time=1, dwell_time=0.5)
        print(f"Estimated scan time: {format_time(estimated_time)}")

        # Plot the scan pattern
        plot_scan_coordinates(scan_pattern, "scan pattern", estimated_time)
        
        prompt = input("do the scan? (y/n): ")
        if prompt.lower() == 'y':
            print("doing scan")
            scan_data = rig.execute_scan(scan_pattern, dwell_time=0.5, daq_channel=0, acquisition_time=0.1, live_plot=True)
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