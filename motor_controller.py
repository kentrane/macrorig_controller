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
        self.serial_connection: Optional[serial.Serial] = None
        self.home_x: float = 0.0
        self.home_y: float = 0.0

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
                    self.serial_connection = serial.Serial(
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
        if self.serial_connection:
            self.serial_connection.close()
            self.connected = False
            self.setup_complete = False

    def _send_command(self, motor: str, command: str) -> str:
        if not self.connected or not self.serial_connection:
            raise RuntimeError("Motor controller not connected")

        full_command = f"{motor}{command};"
        self.serial_connection.write(full_command.encode())
        response = self.serial_connection.read_until(b'\r')
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
                    self._home_single_motor(motor, homing_velocity=100)
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

    def _home_single_motor(self, motor: str, homing_velocity: int = 100) -> None:
        """Home a single motor and set its position to 0"""
        self._send_command(motor, 'R3=VM')  # Save current velocity
        self._send_command(motor, f'VM={homing_velocity}')  # Set homing velocity
        self._send_command(motor, 'SR-')  # Start reverse homing
        self._wait_for_motion_complete(motor)
        self._send_command(motor, 'VM=R3')  # Restore velocity
        self._send_command(motor, 'AP=0')  # Set absolute position to 0

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
                self._home_single_motor(motor, homing_velocity=100)
            print("Motors homed successfully")
            return True
        except Exception as e:
            print(f"Homing failed: {e}")
            return False

    def get_position(self) -> tuple[float, float]:
        """Get current position of both motors (x, y)"""
        if not self.setup_complete:
            raise RuntimeError("Motors not set up")

        try:
            # Query absolute position for both motors
            x_response = self._send_command('1', 'AP?')
            y_response = self._send_command('2', 'AP?')

            # Parse responses (format: "AP=value")
            x_pos = float(x_response.split('=')[1])
            y_pos = float(y_response.split('=')[1])

            return (x_pos, y_pos)
        except Exception as e:
            print(f"Failed to get position: {e}")
            return (0.0, 0.0)

    def move_x(self, x: float) -> bool:
        """Move only the X axis to specified position"""
        if not self.setup_complete:
            print("Motors not set up")
            return False

        try:
            print(f"Moving X axis to {x}")
            self._send_command('1', f'SP={round(x)}')
            self._wait_for_motion_complete('1')
            return True
        except Exception as e:
            print(f"X move failed: {e}")
            return False

    def move_y(self, y: float) -> bool:
        """Move only the Y axis to specified position"""
        if not self.setup_complete:
            print("Motors not set up")
            return False

        try:
            print(f"Moving Y axis to {y}")
            self._send_command('2', f'SP={round(y)}')
            self._wait_for_motion_complete('2')
            return True
        except Exception as e:
            print(f"Y move failed: {e}")
            return False

    def set_home_position(self, x: float = None, y: float = None) -> bool:
        """Set current position or specified position as custom home

        Args:
            x: X coordinate for home (if None, uses current position)
            y: Y coordinate for home (if None, uses current position)
        """
        if not self.setup_complete:
            print("Motors not set up")
            return False

        try:
            if x is None or y is None:
                # Use current position
                current_x, current_y = self.get_position()
                self.home_x = x if x is not None else current_x
                self.home_y = y if y is not None else current_y
            else:
                self.home_x = x
                self.home_y = y

            print(f"Home position set to X={self.home_x}, Y={self.home_y}")
            return True
        except Exception as e:
            print(f"Failed to set home position: {e}")
            return False

    def return_to_home(self) -> bool:
        """Return to the saved custom home position"""
        if not self.setup_complete:
            print("Motors not set up")
            return False

        print(f"Returning to home position (X={self.home_x}, Y={self.home_y})")
        return self.move_to(self.home_x, self.home_y)

    def interactive_mode(self) -> None:
        """Start interactive manual control mode"""
        if not self.setup_complete:
            print("Motors not set up - please run setup_motors() first")
            return

        print("\n" + "="*60)
        print("MANUAL MOTOR CONTROL MODE")
        print("="*60)

        while True:
            try:
                # Show current position
                x, y = self.get_position()
                print(f"\nCurrent Position: X={x:.2f}, Y={y:.2f}")
                print(f"Home Position: X={self.home_x:.2f}, Y={self.home_y:.2f}")
                print("\nCommands:")
                print("  1. Move to coordinates (x,y)")
                print("  2. Move X axis only")
                print("  3. Move Y axis only")
                print("  4. Set current position as home")
                print("  5. Set specific home position")
                print("  6. Return to home")
                print("  7. Home motors (find physical home)")
                print("  8. Get current position")
                print("  9. Exit interactive mode")

                choice = input("\nEnter command number: ").strip()

                if choice == '1':
                    coords = input("Enter coordinates as 'x,y': ").strip()
                    try:
                        x_str, y_str = coords.split(',')
                        x_val = float(x_str.strip())
                        y_val = float(y_str.strip())
                        self.move_to(x_val, y_val)
                    except ValueError:
                        print("Invalid format. Use: x,y (e.g., 100,200)")

                elif choice == '2':
                    x_input = input("Enter X position: ").strip()
                    try:
                        self.move_x(float(x_input))
                    except ValueError:
                        print("Invalid number")

                elif choice == '3':
                    y_input = input("Enter Y position: ").strip()
                    try:
                        self.move_y(float(y_input))
                    except ValueError:
                        print("Invalid number")

                elif choice == '4':
                    self.set_home_position()

                elif choice == '5':
                    coords = input("Enter home coordinates as 'x,y': ").strip()
                    try:
                        x_str, y_str = coords.split(',')
                        x_val = float(x_str.strip())
                        y_val = float(y_str.strip())
                        self.set_home_position(x_val, y_val)
                    except ValueError:
                        print("Invalid format. Use: x,y (e.g., 100,200)")

                elif choice == '6':
                    self.return_to_home()

                elif choice == '7':
                    confirm = input("This will home motors to physical limits. Continue? (y/n): ")
                    if confirm.lower() == 'y':
                        self.home_motors()
                        # Update home position to 0,0 after physical homing
                        self.home_x = 0.0
                        self.home_y = 0.0

                elif choice == '8':
                    x, y = self.get_position()
                    print(f"Current position: X={x:.2f}, Y={y:.2f}")

                elif choice == '9':
                    print("Exiting interactive mode...")
                    break

                else:
                    print("Invalid choice. Please enter 1-9.")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Exiting interactive mode...")
                break
            except Exception as e:
                print(f"Error: {e}")

        print("="*60)
