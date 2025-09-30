"""Motor Controller class for PPFE Macro Rig - handles stepper motor communication and control."""

import serial
from serial.tools import list_ports
import time
from typing import Optional


class MotorController:
    """Controls stepper motors for the PPFE Macro Rig."""

    # Hardware identifier for the stepper controller
    ACTUATOR_HWID = 'USB VID:PID=0403:6001 SER=FT4PZ8BBA'

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
            if hwid == self.ACTUATOR_HWID:
                print(f"Found actuator on {port}: {desc}")
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
                    print("Connected to motor controller")
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
            raise RuntimeError("Motor controller not connected")

        full_command = f"{motor}{command};"
        self.ser.write(full_command.encode())
        response = self.ser.read_until(b'\r')
        return response.decode('ascii').strip()

    def setup_motors(self, home_motors: bool = False) -> bool:
        if self.setup_complete:
            print("Motors already set up")
            return True

        if not self.connected:
            print("Please connect before setup")
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

            # Home both motors (optional)
            if home_motors:
                print("Homing motors...")
                for motor in ['1', '2']:
                    self._send_command(motor, 'R3=VM')  # Save current velocity
                    self._send_command(motor, 'VM=100') # Set homing velocity
                    self._send_command(motor, 'SR-')    # Start reverse homing
                    self._wait_for_motion_complete(motor)
                    self._send_command(motor, 'VM=R3')  # Restore velocity
                    self._send_command(motor, 'AP=0')   # Set absolute position to 0
                print("Motors homed successfully")
            else:
                print("Skipping motor homing (home_motors=False)")

            self.setup_complete = True
            print("Motor setup complete")
            return True

        except Exception as e:
            print(f"Motor setup failed: {e}")
            return False

    def _wait_for_motion_complete(self, motor: str) -> None:
        while True:
            status = self._send_command(motor, 'RS')
            if 'RS=0' in status:  # Motion complete
                break
            time.sleep(0.1)  # Poll interval

    def move_to(self, x: float, y: float) -> bool:
        if not self.setup_complete:
            print("Motors not set up")
            return False

        try:
            print(f"Moving to x:{x}, y:{y}")

            # Move X axis
            self._send_command('1', f'SP={round(x)}')
            self._wait_for_motion_complete('1')

            # Move Y axis
            self._send_command('2', f'SP={round(y)}')
            self._wait_for_motion_complete('2')

            return True

        except Exception as e:
            print(f"Move failed: {e}")
            return False

    def home_motors(self) -> bool:
        """Manually home both motors and set position to 0"""
        if not self.connected:
            print("Not connected to motor controller")
            return False

        try:
            print("Homing motors...")
            for motor in ['1', '2']:
                self._send_command(motor, 'R3=VM')  # Save current velocity
                self._send_command(motor, 'VM=100') # Set homing velocity
                self._send_command(motor, 'SR-')    # Start reverse homing
                self._wait_for_motion_complete(motor)
                self._send_command(motor, 'VM=R3')  # Restore velocity
                self._send_command(motor, 'AP=0')   # Set absolute position to 0
            print("Motors homed successfully")
            return True
        except Exception as e:
            print(f"Homing failed: {e}")
            return False
