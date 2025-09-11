import nidaqmx
from nidaqmx.constants import AcquisitionType, TerminalConfiguration
import numpy as np
from typing import List, Optional, Union, Dict
import time

class NIDAQReader:
    def __init__(self, device_name: str = "Dev1"):
        self.device_name = device_name
        self.task: Optional[nidaqmx.Task] = None
        self._sample_rate = 1000.0
        self._buffer_size = 1000
        
    def connect(self) -> bool:
        try:
            system = nidaqmx.system.System.local()
            devices = [device.name for device in system.devices]
            
            if self.device_name not in devices:
                print(f"Device {self.device_name} not found. Available: {devices}")
                return False
                
            print(f"Connected to {self.device_name}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def read_analog_single(self, channel: Union[int, str], 
                          acquisition_time: float = 0.1,
                          filter_samples: int = 10,
                          terminal_config: TerminalConfiguration = TerminalConfiguration.RSE) -> float:
        
        if isinstance(channel, int):
            channel_name = f"{self.device_name}/ai{channel}"
        else:
            channel_name = channel
            
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    channel_name,
                    terminal_config=terminal_config,
                    min_val=-10.0,
                    max_val=10.0
                )
                
                samples_to_read = max(filter_samples, int(self._sample_rate * acquisition_time))
                task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate,
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=samples_to_read
                )
                
                data = task.read(number_of_samples_per_channel=samples_to_read)
                
                if isinstance(data, list):
                    filtered_data = np.array(data)
                else:
                    filtered_data = np.array([data])
                
                return float(np.mean(filtered_data))
                
        except Exception as e:
            print(f"Read error on {channel_name}: {e}")
            return 0.0
    
    def read_analog_multiple(self, channels: List[Union[int, str]], 
                           acquisition_time: float = 0.1,
                           filter_samples: int = 10,
                           terminal_config: TerminalConfiguration = TerminalConfiguration.RSE) -> List[float]:
        
        channel_names = []
        for ch in channels:
            if isinstance(ch, int):
                channel_names.append(f"{self.device_name}/ai{ch}")
            else:
                channel_names.append(ch)
        
        try:
            with nidaqmx.Task() as task:
                for ch_name in channel_names:
                    task.ai_channels.add_ai_voltage_chan(
                        ch_name,
                        terminal_config=terminal_config,
                        min_val=-10.0,
                        max_val=10.0
                    )
                
                samples_to_read = max(filter_samples, int(self._sample_rate * acquisition_time))
                task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate,
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=samples_to_read
                )
                
                data = task.read(number_of_samples_per_channel=samples_to_read)
                
                if len(channel_names) == 1:
                    return [float(np.mean(data))]
                
                results = []
                for ch_data in data:
                    results.append(float(np.mean(ch_data)))
                
                return results
                
        except Exception as e:
            print(f"Multi-channel read error: {e}")
            return [0.0] * len(channels)
    
    def read_single_sample(self, channel: Union[int, str],
                         terminal_config: TerminalConfiguration = TerminalConfiguration.RSE) -> float:
        
        if isinstance(channel, int):
            channel_name = f"{self.device_name}/ai{channel}"
        else:
            channel_name = channel
            
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    channel_name,
                    terminal_config=terminal_config,
                    min_val=-10.0,
                    max_val=10.0
                )
                
                data = task.read()
                return float(data)
                
        except Exception as e:
            print(f"Single sample read error on {channel_name}: {e}")
            return 0.0
    
    def read_analog_filtered(self, channel: Union[int, str],
                           acquisition_time: float = 1.0,
                           filter_type: str = "mean",
                           terminal_config: TerminalConfiguration = TerminalConfiguration.RSE) -> float:
        
        if isinstance(channel, int):
            channel_name = f"{self.device_name}/ai{channel}"
        else:
            channel_name = channel
            
        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(
                    channel_name,
                    terminal_config=terminal_config,
                    min_val=-10.0,
                    max_val=10.0
                )
                
                samples_to_read = int(self._sample_rate * acquisition_time)
                task.timing.cfg_samp_clk_timing(
                    rate=self._sample_rate,
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=samples_to_read
                )
                
                data = task.read(number_of_samples_per_channel=samples_to_read)
                data_array = np.array(data)
                
                if filter_type == "mean":  # Average of all samples
                    return float(np.mean(data_array))
                elif filter_type == "median":  # Middle value, reduces outlier impact
                    return float(np.median(data_array))
                elif filter_type == "rms":  # Root mean square, useful for AC signals
                    return float(np.sqrt(np.mean(data_array**2)))
                elif filter_type == "std_filtered":  # Removes outliers beyond 2 std dev
                    mean_val = np.mean(data_array)
                    std_val = np.std(data_array)
                    filtered = data_array[np.abs(data_array - mean_val) < 2 * std_val]
                    return float(np.mean(filtered)) if len(filtered) > 0 else float(mean_val)
                else:
                    return float(np.mean(data_array))
                    
        except Exception as e:
            print(f"Filtered read error on {channel_name}: {e}")
            return 0.0
    
    def set_sample_rate(self, rate: float) -> None:
        self._sample_rate = max(1, min(rate, 250000))  # USB-6001 max rate
    
    def get_sample_rate(self) -> float:
        return self._sample_rate
    
    def close(self) -> None:
        if self.task:
            self.task.close()
            self.task = None

def create_daq_reader(device_name: str = "Dev1") -> NIDAQReader:
    reader = NIDAQReader(device_name)
    if reader.connect():
        return reader
    else:
        raise ConnectionError(f"Failed to connect to {device_name}")

def main():
    try:
        daq = create_daq_reader()

        print("NI USB DAQ Reader Test - Press Ctrl+C to stop")
        daq.set_sample_rate(1000)
        while True:
            
            # Read AI2 as differential input
            ai2_read = daq.read_single_sample(2, terminal_config=TerminalConfiguration.DIFF)
            print(f"AI2 (DIFF): {ai2_read:.4f}V")
            print("-" * 40)
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'daq' in locals():
            daq.close()

if __name__ == "__main__":
    main()