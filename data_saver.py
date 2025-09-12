import time
import csv
from datetime import datetime
import numpy as np
try:
    from nptdms import TdmsWriter, RootObject, GroupObject, ChannelObject
    TDMS_AVAILABLE = True
except ImportError:
    TDMS_AVAILABLE = False
    print("Warning: npTDMS not available. TDMS saving will be disabled.")
except Exception as e:
    TDMS_AVAILABLE = False
    print(f"Warning: TDMS library has compatibility issues: {e}. TDMS saving will be disabled.")


class DataSaver:
    def __init__(self, base_filename, save_formats=None):
        self.base_filename = base_filename
        self.save_formats = save_formats or ['csv', 'tdms']
        self.scan_data = []
        self.metadata = {}
        self.scan_start_time = None
        self.scan_end_time = None
        self.is_scan_active = False
        
        # TDMS streaming writer
        self.tdms_writer = None
        self.tdms_file = None
        self.tdms_initialized = False
        
    def start_scan(self, metadata=None):
        self.scan_start_time = datetime.now()
        self.scan_data = []
        self.metadata = metadata or {}
        self.is_scan_active = True
        
        # Add automatic metadata
        self.metadata.update({
            'scan_start_time': self.scan_start_time.isoformat(),
            'scan_start_timestamp': time.time()
        })
        
        print(f"Starting scan data collection: {self.base_filename}")
        
        # Initialize TDMS streaming writer if requested
        if 'tdms' in self.save_formats and TDMS_AVAILABLE:
            self._initialize_tdms_writer()
    
    def _initialize_tdms_writer(self):
        """Initialize TDMS streaming writer"""
        if not TDMS_AVAILABLE:
            return
            
        tdms_filename = f"{self.base_filename}.tdms"
        
        try:
            # Open TDMS file for streaming writes
            self.tdms_file = open(tdms_filename, 'wb')
            self.tdms_writer = TdmsWriter(self.tdms_file)
            
            # Write initial segment with metadata and structure
            root_object = RootObject(properties=self.metadata)
            group_object = GroupObject("ScanData", properties={
                'description': 'Scan data from PPFE Macro Rig',
                'channels': 4
            })
            
            # Create empty initial channels to establish structure
            point_index_channel = ChannelObject("ScanData", "PointIndex", np.array([], dtype=np.int32))
            x_position_channel = ChannelObject("ScanData", "XPosition", np.array([], dtype=np.float64))
            y_position_channel = ChannelObject("ScanData", "YPosition", np.array([], dtype=np.float64))
            daq_value_channel = ChannelObject("ScanData", "DAQValue", np.array([], dtype=np.float64))
            
            # Write initial segment with metadata
            self.tdms_writer.write_segment([
                root_object,
                group_object,
                point_index_channel,
                x_position_channel,
                y_position_channel,
                daq_value_channel
            ])
            
            self.tdms_initialized = True
            print(f"TDMS streaming writer initialized: {tdms_filename}")
            
        except Exception as e:
            print(f"Failed to initialize TDMS streaming writer: {e}")
            if self.tdms_writer:
                self.tdms_writer.close()
                self.tdms_writer = None
            if self.tdms_file:
                self.tdms_file.close()
                self.tdms_file = None
            # Remove 'tdms' from save_formats if it fails
            if 'tdms' in self.save_formats:
                self.save_formats.remove('tdms')
    
    
    def add_data_point(self, point_data):
        if not self.is_scan_active:
            print("Warning: Scan not started. Call start_scan() first.")
            return
            
        # Add timestamp to data point
        point_data['timestamp'] = time.time()
        point_data['datetime'] = datetime.now().isoformat()
        
        self.scan_data.append(point_data)
        
        # Save to CSV immediately (append mode)
        if 'csv' in self.save_formats:
            self._append_to_csv(point_data)
            
        # Write to TDMS immediately (streaming)
        if 'tdms' in self.save_formats and self.tdms_initialized and self.tdms_writer:
            self._append_to_tdms_stream(point_data)
            
        print(f"Data point {len(self.scan_data)} saved")
    
    def _append_to_csv(self, point_data):
        csv_filename = f"{self.base_filename}.csv"
        
        try:
            # Check if file exists to determine if header is needed
            file_exists = False
            try:
                with open(csv_filename, 'r'):
                    file_exists = True
            except FileNotFoundError:
                pass
                
            with open(csv_filename, 'a', newline='') as csvfile:
                # Define field order
                fieldnames = ['point_index', 'x', 'y', 'daq_value', 'timestamp', 'datetime']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header if new file
                if not file_exists:
                    writer.writeheader()
                    
                # Write data point
                writer.writerow(point_data)
                
        except Exception as e:
            print(f"Failed to append to CSV: {e}")
    
    def _append_to_tdms_stream(self, point_data):
        if not self.tdms_writer or not self.tdms_initialized:
            return
            
        try:
            # Create data arrays for single point
            point_index_data = np.array([point_data['point_index']], dtype=np.int32)
            x_data = np.array([point_data['x']], dtype=np.float64)
            y_data = np.array([point_data['y']], dtype=np.float64)
            daq_data = np.array([point_data['daq_value']], dtype=np.float64)
            
            # Create channel objects with single data point
            point_index_channel = ChannelObject("ScanData", "PointIndex", point_index_data)
            x_position_channel = ChannelObject("ScanData", "XPosition", x_data)
            y_position_channel = ChannelObject("ScanData", "YPosition", y_data)
            daq_value_channel = ChannelObject("ScanData", "DAQValue", daq_data)
            
            # Write segment with this data point
            self.tdms_writer.write_segment([
                point_index_channel,
                x_position_channel,
                y_position_channel,
                daq_value_channel
            ])
            
        except Exception as e:
            print(f"Failed to append to TDMS stream: {e}")
            # Disable TDMS if streaming fails
            self.tdms_initialized = False
            if 'tdms' in self.save_formats:
                self.save_formats.remove('tdms')
    
    def finish_scan(self, additional_metadata=None):
        if not self.is_scan_active:
            return
            
        self.scan_end_time = datetime.now()
        self.is_scan_active = False
        
        # Update metadata
        scan_duration = (self.scan_end_time - self.scan_start_time).total_seconds()
        self.metadata.update({
            'scan_end_time': self.scan_end_time.isoformat(),
            'scan_end_timestamp': time.time(),
            'scan_duration_seconds': scan_duration,
            'total_data_points': len(self.scan_data),
            'points_per_second': len(self.scan_data) / scan_duration if scan_duration > 0 else 0
        })
        
        if additional_metadata:
            self.metadata.update(additional_metadata)
        
        # Close TDMS streaming writer
        if self.tdms_writer and self.tdms_initialized:
            try:
                # Write final metadata update as properties
                if additional_metadata:
                    final_root_object = RootObject(properties=self.metadata)
                    self.tdms_writer.write_segment([final_root_object])
                
                self.tdms_writer.close()
                self.tdms_writer = None
                print(f"TDMS streaming file closed with {len(self.scan_data)} points")
            except Exception as e:
                print(f"Error closing TDMS streaming writer: {e}")
            finally:
                if self.tdms_file:
                    self.tdms_file.close()
                    self.tdms_file = None
                self.tdms_initialized = False
        
        # Write metadata to separate file
        self._save_metadata()
        
        print(f"Scan completed: {len(self.scan_data)} points in {scan_duration:.1f} seconds")
    
    def _save_metadata(self):
        metadata_filename = f"{self.base_filename}_metadata.json"
        
        try:
            import json
            with open(metadata_filename, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            print(f"Metadata saved to {metadata_filename}")
        except Exception as e:
            print(f"Failed to save metadata: {e}")
    
    def get_scan_data(self):
        return self.scan_data.copy()
    
    def get_metadata(self):
        return self.metadata.copy()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure files are properly closed"""
        if self.is_scan_active:
            self.finish_scan()
        
        # Ensure TDMS writer is closed even if finish_scan wasn't called
        if self.tdms_writer:
            try:
                self.tdms_writer.close()
            except:
                pass
            self.tdms_writer = None
        if self.tdms_file:
            try:
                self.tdms_file.close()
            except:
                pass
            self.tdms_file = None