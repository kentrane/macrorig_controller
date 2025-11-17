import time
import numpy as np
from datetime import datetime
from motor_controller import MotorController
from scan_rig import ScanRig
from ni_daq_reader import NIDAQReader


def main():
    # Initialize hardware
    motor_controller = MotorController()
    if not motor_controller.connect():
        print("Failed to connect to motor controller")
        print("Check cable connections")
        return
    print("Connected to motor controller")

    if not motor_controller.setup_motors(home_motors=True):
        print("Motor controller setup failed - disconnecting")
        motor_controller.disconnect()
        return
    print("Motor controller setup complete")

    # Uncomment the next line if you want to manually home motors now:
    # motor_controller.home_motors()

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

    rig = ScanRig(motor_controller, daq)

    # Ask user what they want to do
    print("\n" + "="*60)
    print("MACRORIG CONTROLLER")
    print("="*60)
    print("\nOptions:")
    print("  1. Interactive manual control mode")
    print("  2. Run automated scan")
    choice = input("\nSelect option (1 or 2): ").strip()

    try:
        if choice == '1':
            # Enter interactive manual control mode
            motor_controller.interactive_mode()

        elif choice == '2':
            # Run automated scan
            rig.set_origin(600, 600)  # Set origin position (x, y)
            rig.move_to_origin()

            scan_pattern = rig.scan_rectangle(width=100, height=100, step_x=5, step_y=5)
            print(f"Scan pattern: {len(scan_pattern)} points")
            prompt = input("Start scan? (y/n): ")
            if prompt.lower() == 'y':
                print("Starting scan...")
                scan_data = rig.execute_scan(scan_pattern, dwell_time=0, daq_channel=2,
                                            acquisition_time=0.05, live_plot=True)
            else:
                print("Scan cancelled")

            # Return to origin after scan
            rig.move_to_origin()

        else:
            print("Invalid option selected")

    finally:
        motor_controller.disconnect()
        print("\nComplete!")


if __name__ == "__main__":
    main()