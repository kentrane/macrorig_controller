"""
PPFE Macro Rig Plotting Utilities
Standalone plotting functions for scan data visualization
"""
from typing import List, Dict, Tuple, Optional
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata


def load_scan_data_from_csv(filepath):
    """Load scan data from CSV file into list of dicts"""
    scan_data = []
    with open(filepath, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            scan_data.append({
                'point_index': int(row['point_index']),
                'x': float(row['x']),
                'y': float(row['y']),
                'daq_value': float(row['daq_value'])
            })
    print(f"Loaded {len(scan_data)} data points from {filepath}")
    return scan_data


def plot_scan_data_pcolormesh(scan_data, title="Scan Data", figsize=(12, 10), cmap='plasma', grid_resolution=50):
    """Plot scan data as pcolormesh or scatter if few points"""
    x_vals = [point['x'] for point in scan_data]
    y_vals = [point['y'] for point in scan_data]
    daq_vals = [point['daq_value'] for point in scan_data]

    fig, ax = plt.subplots(figsize=figsize)

    if len(scan_data) >= 4:
        grid_res = min(grid_resolution, len(scan_data) * 2)
        xi = np.linspace(min(x_vals), max(x_vals), grid_res)
        yi = np.linspace(min(y_vals), max(y_vals), grid_res)
        Xi, Yi = np.meshgrid(xi, yi)

        # Interpolate data onto regular grid
        Zi = griddata((x_vals, y_vals), daq_vals, (Xi, Yi), method='nearest', fill_value=0)

        # Create pcolormesh
        mesh = ax.pcolormesh(Xi, Yi, Zi, cmap=cmap, shading='nearest', alpha=0.8)

        # Add colorbar
        cbar = plt.colorbar(mesh, ax=ax, label='DAQ Value (V)')
        cbar.ax.tick_params(labelsize=10)
    else:
        scatter = ax.scatter(x_vals, y_vals, c=daq_vals, cmap=cmap, s=100,
                             alpha=0.8, edgecolors='black', linewidth=0.5)
        cbar = plt.colorbar(scatter, ax=ax, label='DAQ Value (V)')
        cbar.ax.tick_params(labelsize=10)

    ax.set_xlabel('X Position (mm)', fontsize=12)
    ax.set_ylabel('Y Position (mm)', fontsize=12)
    ax.set_title(f'{title} - {len(scan_data)} points\n'
                 f'DAQ Range: {min(daq_vals):.4f}V to {max(daq_vals):.4f}V', fontsize=14)
    ax.invert_yaxis()  # Match physical coordinates
    ax.axis('equal')
    plt.tight_layout()
    plt.show()



def format_time(seconds):
    """Convert from just seconds to more readable format"""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    if minutes > 0:
        return f"{minutes}:{secs:02d}"
    return f"{secs}s"



if __name__ == "__main__":
    scan_data = load_scan_data_from_csv('scan_data_250912_15_11_42.csv')
    plot_scan_data_pcolormesh(scan_data, title="some readings")
