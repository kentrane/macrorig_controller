import time
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
from motor_controller import MotorController
from ni_daq_reader import NIDAQReader
from nidaqmx.constants import TerminalConfiguration
from data_saver import DataSaver


class ScanRig:
    def __init__(self, act, daq=None):
        self.act = act
        self.daq = daq
        self.origin_x = 0
        self.origin_y = 0
        
    def set_origin(self, x, y):
        self.origin_x = x
        self.origin_y = y
        print(f"Origin set to ({x}, {y})")

    def move_to_origin(self):
        return self.act.move_to(self.origin_x, self.origin_y)

    def scan_circle(self, radius, step_x=1.0, step_y=1.0):
        coordinates = []
        y_range = -np.arange(-radius, radius + step_y, step_y)
        
        for dy in y_range:
            if abs(dy) <= radius:
                x_half_range = radius * np.sqrt(1 - (dy / radius) ** 2)
                x_range = np.arange(-x_half_range, x_half_range + step_x, step_x)
                for dx in x_range:
                    coordinates.append((self.origin_x + dx, self.origin_y + dy))
        return coordinates

    def scan_rectangle(self, width, height, step_x=1.0, step_y=1.0):
        coordinates = []
        half_width = width / 2
        half_height = height / 2
        y_steps = np.arange(-half_height, half_height + step_y, step_y)
        
        for i, dy in enumerate(y_steps):
            x_steps = np.arange(-half_width, half_width + step_x, step_x)
            if i % 2 == 1:
                x_steps = x_steps[::-1]
            for dx in x_steps:
                coordinates.append((self.origin_x + dx, self.origin_y + dy))
        return coordinates

    def execute_scan(self, coordinates, dwell_time=1.0, daq_channel=0, 
                    acquisition_time=0.1, filter_type="mean", live_plot=False, 
                    save_formats=None, auto_save=True):
        if not coordinates:
            print("No coordinates provided")
            return []

        if not self.daq:
            print("ERROR: DAQ not connected. Cannot perform scan without DAQ readings.")
            return []

        print(f"Starting scan of {len(coordinates)} points")
        scan_data = []
        
        data_saver = None
        if auto_save:
            save_formats = save_formats or ['csv', 'tdms']
            os.makedirs('data', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_filename = f"data/scan_data_{timestamp}"
            data_saver = DataSaver(save_filename, save_formats)
            
            scan_metadata = {
                'total_planned_points': len(coordinates),
                'dwell_time_seconds': dwell_time,
                'daq_channel': daq_channel,
                'acquisition_time_seconds': acquisition_time,
                'filter_type': filter_type,
                'origin_x': self.origin_x,
                'origin_y': self.origin_y
            }
            data_saver.start_scan(scan_metadata)
            print(f"Auto-saving data to: {save_filename}")

        # Setup live plotting if requested
        fig = None
        ax = None
        mesh = None
        Xi = None
        Yi = None
        Zi = None
        current_pos_scatter = None
        last_plot_update = 0
        plot_update_interval = 0.5  # Update plot every 0.5 seconds max
        if live_plot:
            plt.ion()  # Interactive mode on
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Configure matplotlib for better performance
            plt.rcParams['figure.facecolor'] = 'white'
            plt.rcParams['axes.facecolor'] = 'white'
            
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
            mesh = ax.pcolormesh(Xi, Yi, Zi, cmap='plasma', shading='nearest', alpha=0.95)
            plt.colorbar(mesh, ax=ax, label='DAQ Value (V)')
            
            # Show planned scan points as light gray dots
            ax.scatter(all_x, all_y, c='lightgray', s=10, alpha=0.2, label='Planned points')
            ax.legend(loc='upper right')
            
            plt.tight_layout()
            
            # Fix window behavior - prevent always on top
            if fig.canvas.manager is not None:
                try:
                    # Try to set window properties to prevent always-on-top behavior
                    manager = fig.canvas.manager
                    if hasattr(manager, 'window'):
                        window = getattr(manager, 'window')
                        if hasattr(window, 'wm_attributes'):
                            window.wm_attributes('-topmost', False)
                except Exception:
                    pass  # Ignore if not supported on this platform
            
            # Initial draw with minimal pause
            fig.canvas.draw_idle()
            fig.canvas.flush_events()

        for i, (x, y) in enumerate(coordinates):
            if not self.act.move_to(x, y):
                print(f"Failed to move to position {i}: ({x}, {y})")
                if data_saver:
                    data_saver.finish_scan({'scan_completion_status': 'failed_movement'})
                return scan_data

            if i == 0:
                time.sleep(1.0)
            time.sleep(dwell_time)

            try:
                daq_value = self.daq.read_analog_filtered(
                    channel=daq_channel,
                    acquisition_time=acquisition_time,
                    filter_type=filter_type,
                    terminal_config=TerminalConfiguration.DIFF
                )
                print(f"Point {i+1}/{len(coordinates)}: ({x:.1f}, {y:.1f}) -> {daq_value:.4f}V", end="")
            except Exception as e:
                print(f"DAQ read failed at point {i}: {e}")
                if data_saver:
                    data_saver.finish_scan({'scan_completion_status': 'failed_daq_read'})
                return scan_data

            data_point = {
                'point_index': i,
                'x': x,
                'y': y,
                'daq_value': daq_value,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat()
            }
            scan_data.append(data_point)

            if data_saver:
                data_saver.add_data_point(data_point)

            if live_plot and fig and ax and i % 5 == 0:
                try:
                    ax.set_title(f'Beam Pattern ({len(scan_data)}/{len(coordinates)} points)')
                    if len(scan_data) >= 3:
                        from scipy.interpolate import griddata
                        x_vals = [point['x'] for point in scan_data]
                        y_vals = [point['y'] for point in scan_data]
                        daq_vals = [point['daq_value'] for point in scan_data]
                        
                        if max(x_vals) - min(x_vals) > 1e-6 and max(y_vals) - min(y_vals) > 1e-6:
                            try:
                                Zi_new = griddata((x_vals, y_vals), daq_vals, (Xi, Yi), 
                                                method='linear', fill_value=np.nan)
                                mesh.set_array(Zi_new.ravel())
                                mesh.set_clim(min(daq_vals), max(daq_vals))
                            except Exception:
                                pass

                    ax.scatter([x], [y], c='red', s=100, marker='x')
                    fig.canvas.draw_idle()
                    fig.canvas.flush_events()
                except Exception as e:
                    print(f"Plot update failed: {e}")

        if live_plot and ax:
            ax.set_title(f'Beam Pattern - SCAN COMPLETE ({len(scan_data)} points)')
            if len(scan_data) >= 3 and mesh:
                from scipy.interpolate import griddata
                x_vals = [point['x'] for point in scan_data]
                y_vals = [point['y'] for point in scan_data]
                daq_vals = [point['daq_value'] for point in scan_data]
                
                Zi_final = griddata((x_vals, y_vals), daq_vals, (Xi, Yi), 
                                  method='linear', fill_value=np.nan)
                mesh.set_array(Zi_final.ravel())
                mesh.set_clim(min(daq_vals), max(daq_vals))

            if fig:
                fig.canvas.draw_idle()
                fig.canvas.flush_events()

        if data_saver:
            final_metadata = {
                'actual_points_collected': len(scan_data),
                'scan_completion_status': 'completed' if len(scan_data) == len(coordinates) else 'partial'
            }
            data_saver.finish_scan(final_metadata)

        print("Scan completed")
        return scan_data
