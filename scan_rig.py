import time
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
from scipy.interpolate import griddata
from motor_controller import MotorController
from ni_daq_reader import NIDAQReader
from nidaqmx.constants import TerminalConfiguration
from data_saver import DataSaver


class ScanRig:
    def __init__(self, motor_controller, daq=None):
        self.motor_controller = motor_controller
        self.daq = daq
        self.origin_x = 0
        self.origin_y = 0
        
    def set_origin(self, x, y):
        self.origin_x = x
        self.origin_y = y
        print(f"Origin set to ({x}, {y})")

    def move_to_origin(self):
        return self.motor_controller.move_to(self.origin_x, self.origin_y)

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

    def _setup_live_plot(self, coordinates):
        """Setup live plotting display"""
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
        grid_resolution = min(50, max(20, len(coordinates) // 2))
        grid_x = np.linspace(x_min, x_max, grid_resolution)
        grid_y = np.linspace(y_min, y_max, grid_resolution)
        grid_x_mesh, grid_y_mesh = np.meshgrid(grid_x, grid_y)

        # Initialize with NaN values (will show as transparent/empty)
        grid_values = np.full_like(grid_x_mesh, np.nan)

        # Setup plot with fixed bounds
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')
        ax.set_title(f'Beam Pattern (0/{len(coordinates)} points)')
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.invert_yaxis()  # Invert Y-axis to match physical coordinates
        ax.grid(True, alpha=0.3)

        # Create initial empty pcolormesh
        mesh = ax.pcolormesh(grid_x_mesh, grid_y_mesh, grid_values,
                            cmap='plasma', shading='nearest', alpha=0.95)
        plt.colorbar(mesh, ax=ax, label='DAQ Value (V)')

        # Show planned scan points as light gray dots
        ax.scatter(all_x, all_y, c='lightgray', s=10, alpha=0.2, label='Planned points')
        ax.legend(loc='upper right')

        plt.tight_layout()

        # Fix window behavior - prevent always on top
        if fig.canvas.manager is not None:
            try:
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

        return {
            'fig': fig,
            'ax': ax,
            'mesh': mesh,
            'grid_x_mesh': grid_x_mesh,
            'grid_y_mesh': grid_y_mesh
        }

    def _update_live_plot(self, plot_objects, scan_data, current_x, current_y, total_points):
        """Update the live plot with current scan data"""
        try:
            ax = plot_objects['ax']
            mesh = plot_objects['mesh']
            grid_x_mesh = plot_objects['grid_x_mesh']
            grid_y_mesh = plot_objects['grid_y_mesh']

            ax.set_title(f'Beam Pattern ({len(scan_data)}/{total_points} points)')

            if len(scan_data) >= 3:
                x_vals = [point['x'] for point in scan_data]
                y_vals = [point['y'] for point in scan_data]
                daq_vals = [point['daq_value'] for point in scan_data]

                if max(x_vals) - min(x_vals) > 1e-6 and max(y_vals) - min(y_vals) > 1e-6:
                    try:
                        grid_values_new = griddata((x_vals, y_vals), daq_vals,
                                                   (grid_x_mesh, grid_y_mesh),
                                                   method='linear', fill_value=np.nan)
                        mesh.set_array(grid_values_new.ravel())
                        mesh.set_clim(min(daq_vals), max(daq_vals))
                    except Exception:
                        pass

            ax.scatter([current_x], [current_y], c='red', s=100, marker='x')
            plot_objects['fig'].canvas.draw_idle()
            plot_objects['fig'].canvas.flush_events()
        except Exception as e:
            print(f"Plot update failed: {e}")

    def _finalize_live_plot(self, plot_objects, scan_data):
        """Finalize the live plot with complete scan data"""
        try:
            ax = plot_objects['ax']
            mesh = plot_objects['mesh']
            grid_x_mesh = plot_objects['grid_x_mesh']
            grid_y_mesh = plot_objects['grid_y_mesh']

            ax.set_title(f'Beam Pattern - SCAN COMPLETE ({len(scan_data)} points)')

            if len(scan_data) >= 3 and mesh:
                x_vals = [point['x'] for point in scan_data]
                y_vals = [point['y'] for point in scan_data]
                daq_vals = [point['daq_value'] for point in scan_data]

                grid_values_final = griddata((x_vals, y_vals), daq_vals,
                                            (grid_x_mesh, grid_y_mesh),
                                            method='linear', fill_value=np.nan)
                mesh.set_array(grid_values_final.ravel())
                mesh.set_clim(min(daq_vals), max(daq_vals))

            plot_objects['fig'].canvas.draw_idle()
            plot_objects['fig'].canvas.flush_events()
        except Exception as e:
            print(f"Plot finalization failed: {e}")

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
        plot_objects = None
        if live_plot:
            plot_objects = self._setup_live_plot(coordinates)

        for i, (x, y) in enumerate(coordinates):
            if not self.motor_controller.move_to(x, y):
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

            # Update live plot every 5 points
            if plot_objects and i % 5 == 0:
                self._update_live_plot(plot_objects, scan_data, x, y, len(coordinates))

        # Finalize live plot
        if plot_objects:
            self._finalize_live_plot(plot_objects, scan_data)

        if data_saver:
            final_metadata = {
                'actual_points_collected': len(scan_data),
                'scan_completion_status': 'completed' if len(scan_data) == len(coordinates) else 'partial'
            }
            data_saver.finish_scan(final_metadata)

        print("Scan completed")
        return scan_data
