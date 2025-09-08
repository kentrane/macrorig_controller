"""
PPFE Macro Rig Controller
Author: Kenneth, based on script by Stig Jensen
"""

import serial
from serial.tools import list_ports
import time
import numpy as np
from typing import List, Tuple, Optional


class MotorActuator:
    """Controls XY positioning motors via serial communication."""
    
    # Hardware identifier for the actuator controller
    act_HWID = 'USB VID:PID=0403:6001 SER=FT4PZ8BBA'
    
    def __init__(self):
        self.connected = False
        self.setup_complete = False
        self.ser: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """Connect to the motor actuator via serial port."""
        if self.connected:
            print("Already connected to actuator controller")
            return True
            
        ports = list_ports.comports()
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
                    
        print("Motor act not found")
        return False
    
    def disconnect(self) -> None:
        """Disconnect from motor act."""
        if self.ser:
            self.ser.close()
            self.connected = False
            self.setup_complete = False
    
    def _send_command(self, motor: str, command: str) -> str:
        """Send command to specific motor and return response."""
        if not self.connected or not self.ser:
            raise RuntimeError("act not connected")
            
        full_command = f"{motor}{command};"
        self.ser.write(full_command.encode())
        response = self.ser.read_until(b'\r')
        return response.decode('ascii').strip()
    
    def setup_motors(self) -> bool:
        """Initialize both X and Y motors with required parameters."""
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
        """Wait until specified motor completes motion."""
        while True:
            status = self._send_command(motor, 'RS')
            if 'RS=0' in status:  # Motion complete
                break
            time.sleep(0.1) # don't run too fast
    
    def move_to(self, x: float, y: float) -> bool:
        """Move to absolute XY coordinates in mm."""
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
    """High-level scanning operations for the macro rig."""
    
    def __init__(self, act: MotorAct):
        self.act = act
        self.origin_x = 0
        self.origin_y = 0
        
    def set_origin(self, x: float, y: float) -> None:
        """Set the center point for scanning operations."""
        self.origin_x = x
        self.origin_y = y
        print(f"Origin set to ({x}, {y})")
    
    
    def move_to_origin(self) -> bool:
        """Move act to the defined origin point."""
        return self.act.move_to(self.origin_x, self.origin_y)
    
    
    def scan_line_h(self, half_length: float, step_size: float = 1.0) -> List[Tuple[float, float]]:
        """
        Generate coordinates for horizontal line scan.
        
        Args:
            half_length: Distance from center to each end
            step_size: Step size in mm
            
        Returns:
            List of (x, y) coordinates relative to origin
        """
        steps = np.arange(-half_length, half_length + step_size, step_size)
        return [(self.origin_x + step, self.origin_y) for step in steps]
    
    def scan_line_v(self, half_length: float, step_size: float = 1.0) -> List[Tuple[float, float]]:
        """
        Generate coordinates for vertical line scan.
        
        Args:
            half_length: Distance from center to each end  
            step_size: Step size in mm
            
        Returns:
            List of (x, y) coordinates relative to origin
        """
        steps = np.arange(-half_length, half_length + step_size, step_size)
        return [(self.origin_x, self.origin_y + step) for step in steps]
    
    def scan_circle(self, radius: float, step_x: float = 1.0, step_y: float = 1.0) -> List[Tuple[float, float]]:
        """
        Generate coordinates for circular scan pattern.
        
        Args:
            radius: Radius of circle in mm
            step_x: X-axis step size in mm
            step_y: Y-axis step size in mm
            
        Returns:
            List of (x, y) coordinates within circular boundary
        """
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
        """
        Generate coordinates for rectangular scan pattern.
        
        Args:
            width: Total width of rectangle in mm
            height: Total height of rectangle in mm  
            step_x: Step size in X direction in mm
            step_y: Step size in Y direction in mm
            
        Returns:
            List of (x, y) coordinates in raster scan pattern
        """
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
    
    def scan_square(self, size: float, step_size: float = 1.0) -> List[Tuple[float, float]]:
        """
        Generate coordinates for square scan pattern.
        
        Args:
            size: Side length of square in mm
            step_size: Step size in mm for both X and Y
            
        Returns:
            List of (x, y) coordinates in scan pattern
        """
        return self.scan_rectangle(size, size, step_size, step_size)
    
    def execute_scan(self, coordinates: List[Tuple[float, float]], 
                    dwell_time: float = 1.0) -> bool:
        """
        Execute a scan by moving to each coordinate.
        
        Args:
            coordinates: List of (x, y) positions to visit
            dwell_time: Time to wait at each position in seconds
            
        Returns:
            True if scan completed successfully
        """
        if not coordinates:
            print("No coordinates provided")
            return False
            
        print(f"Starting scan of {len(coordinates)} points")
        
        first_move = True
        for i, (x, y) in enumerate(coordinates):
            if not self.act.move_to(x, y):
                print(f"Failed to move to position {i}: ({x}, {y})")
                return False
                
            # Extra settling time for first move
            if first_move:
                time.sleep(2.0)
                first_move = False
            
            time.sleep(dwell_time)
        
        print("Scan completed")
        return True
    
    def test_boundaries(self, width: float, height: float) -> bool:
        """Test movement to rectangular scan boundaries.
        
        Args:
            width: Width of test rectangle in mm
            height: Height of test rectangle in mm
        """
        half_width = width / 2
        half_height = height / 2
        
        test_points = [
            (self.origin_x, self.origin_y),                    # Center
            (self.origin_x + half_width, self.origin_y),       # Right
            (self.origin_x - half_width, self.origin_y),       # Left  
            (self.origin_x, self.origin_y + half_height),      # Top
            (self.origin_x, self.origin_y - half_height),      # Bottom
        ]
        
        print("Testing boundary movements:")
        for i, (x, y) in enumerate(test_points):
            print(f"  Point {i+1}: ({x}, {y})")
            if not self.act.move_to(x, y):
                return False
            time.sleep(1.5)
        
        # Return to origin
        return self.move_to_origin()


def main():
    """Example usage of the macro rig controller."""
    
    # Initialize hardware
    act = MotorAct()
    if not act.connect():
        return
    
    if not act.setup_motors():
        act.disconnect()
        return
    
    # Initialize scanning system
    rig = ScanRig(act)
    rig.set_origin(904, 620)  # Example origin
    
    try:
        # Test basic movements
        print("Testing basic movements...")
        rig.move_to_origin()
        rig.test_boundaries(width=20, height=15)  # Test 20x15mm area
        
        # Horizontal line scan
        h_coords = rig.scan_line_h(half_length=10, step_size=2)
        print(f"Horizontal line: {len(h_coords)} points")
        
        # Rectangular scan (20mm x 15mm)
        rect_coords = rig.scan_rectangle(width=20, height=15, step_x=2, step_y=1.5)
        print(f"Rectangle scan: {len(rect_coords)} points")
        
        # Square scan (20mm x 20mm)
        square_coords = rig.scan_square(size=20, step_size=2)
        print(f"Square scan: {len(square_coords)} points")
        
        # Circular scan (radius=10mm)
        circle_coords = rig.scan_circle(radius=10, step_x=2, step_y=2)
        print(f"Circular scan: {len(circle_coords)} points")
        
        # Execute a small test scan
        print("\nExecuting test horizontal scan...")
        test_coords = rig.scan_line_h(half_length=5, step_size=1)
        rig.execute_scan(test_coords, dwell_time=0.5)
        
    finally:
        rig.move_to_origin()
        act.disconnect()
        print("\nfini!")


if __name__ == "__main__":
    main()