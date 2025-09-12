"""
Scan Rig class for PPFE Macro Rig
Handles scanning patterns and data acquisition
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional, Dict
from motor_controller import MotorController
from ni_daq_reader import NIDAQReader
from nidaqmx.constants import TerminalConfiguration


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
        fig = None
        ax = None
        mesh = None
        Xi = None
        Yi = None
        Zi = None
        current_pos_scatter = None
        completed_scatter = None
        if live_plot:
            plt.ion()  # Interactive mode on
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Pre-calculate plot bounds from all coordinates
            all_x = [coord[0] for coord in coordinates]
            all_y = [coord[1] for coord in coordinates]
            x_min, x_max = min(all_x), max(all_x)
            y_min, y_max = min(all_y), max(all_y)
            
            # Add small margin to bounds
            x_margin = (x_max - x_min) * 0.05 if x_max != x_min else 1
            y_margin = (y_max - y_min) * 0.05 if y_max != y_min else 1
            x_min -= x_margin
            x_max += x_margin
            y_min -= y_margin
            y_max += y_margin
            
            # Create fixed grid for interpolation
            grid_res = min(50, max(20, len(coordinates) // 2))
            xi = np.linspace(x_min, x_max, grid_res)
            yi = np.linspace(y_min, y_max, grid_res)
            Xi, Yi = np.meshgrid(xi, yi)
            
            # Initialize with NaN values (will show as transparent/empty)
            Zi = np.full_like(Xi, np.nan)
            
            # Setup plot with fixed bounds
            ax.set_xlabel('X Position (mm)')
            ax.set_ylabel('Y Position (mm)')
            ax.set_title(f'Beam Pattern (0/{len(coordinates)} points)')
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            ax.invert_yaxis()  # Invert Y-axis to match physical coordinates
            ax.grid(True, alpha=0.3)
            
            # Create initial empty pcolormesh
            mesh = ax.pcolormesh(Xi, Yi, Zi, cmap='plasma', shading='nearest', alpha=0.8)
            cbar = plt.colorbar(mesh, ax=ax, label='DAQ Value (V)')
            
            # Show planned scan points as light gray dots
            ax.scatter(all_x, all_y, c='lightgray', s=30, alpha=0.5, label='Planned points')
            ax.legend(loc='upper right')
            
            plt.tight_layout()
            plt.draw()
            plt.pause(0.01)
        
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
                    filter_type=filter_type,
                    terminal_config=TerminalConfiguration.DIFF
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
            if live_plot and fig is not None and ax is not None and mesh is not None:
                try:
                    # Update title
                    ax.set_title(f'Beam Pattern ({len(scan_data)}/{len(coordinates)} points)')
                    
                    # Update the interpolated data if we have enough points
                    if len(scan_data) >= 3:
                        from scipy.interpolate import griddata
                        
                        x_vals = [point['x'] for point in scan_data]
                        y_vals = [point['y'] for point in scan_data]
                        daq_vals = [point['daq_value'] for point in scan_data]
                        
                        # Interpolate current data onto the fixed grid
                        Zi_new = griddata(
                            (x_vals, y_vals), daq_vals, (Xi, Yi), 
                            method='linear', fill_value=np.nan
                        )
                        
                        # Update the mesh data
                        mesh.set_array(Zi_new.ravel())
                        
                        # Update colorbar limits based on current data
                        vmin, vmax = min(daq_vals), max(daq_vals)
                        mesh.set_clim(vmin, vmax)
                    
                    # Add current scan position as a red dot
                    if current_pos_scatter is not None:
                        current_pos_scatter.remove()
                    current_pos_scatter = ax.scatter([x], [y], c='red', s=100, marker='x', 
                                                      linewidths=3, label='Current position')
                    
                    # Add completed points as white dots (only recent ones to avoid clutter)
                    if len(scan_data) > 0:
                        recent_points = scan_data[-min(10, len(scan_data)):]  # Show last 10 points
                        recent_x = [point['x'] for point in recent_points]
                        recent_y = [point['y'] for point in recent_points]
                        
                        if completed_scatter is not None:
                            completed_scatter.remove()
                        completed_scatter = ax.scatter(recent_x, recent_y, c='white', s=20, 
                                                        alpha=0.9, edgecolors='black', linewidth=0.8,
                                                        label='Recent points')
                    
                    plt.draw()
                    plt.pause(0.01)  # Shorter pause for smoother updates
                    
                except Exception as e:
                    print(f"Live plot update failed: {e}")
        
        if live_plot:
            print("Live plot will remain open. Close the plot window manually when done.")
            # Keep interactive mode on and ensure plot stays visible
            plt.show(block=False)
            # Add a final draw to ensure plot is fully rendered
            plt.draw()
            plt.pause(0.1)  # Small pause to ensure plot is visible
            
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
