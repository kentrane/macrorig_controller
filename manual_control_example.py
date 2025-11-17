"""
Example script demonstrating manual motor control features.

This script shows how to use the new manual control methods added to MotorController.
"""

from motor_controller import MotorController


def example_manual_control():
    """Example demonstrating all manual control features"""

    # Initialize and connect to motor controller
    controller = MotorController()

    if not controller.connect():
        print("Failed to connect to motor controller")
        return

    # Setup motors (optionally home them)
    if not controller.setup_motors(home_motors=True):
        print("Failed to setup motors")
        controller.disconnect()
        return

    print("\n" + "="*60)
    print("MANUAL CONTROL EXAMPLES")
    print("="*60)

    # Example 1: Get current position
    print("\n1. Getting current position:")
    x, y = controller.get_position()
    print(f"   Current position: X={x}, Y={y}")

    # Example 2: Move to specific coordinates
    print("\n2. Moving to coordinates (100, 150):")
    controller.move_to(100, 150)

    # Example 3: Move individual axes
    print("\n3. Moving only X axis to 200:")
    controller.move_x(200)

    print("\n4. Moving only Y axis to 250:")
    controller.move_y(250)

    # Example 4: Set current position as home
    print("\n5. Setting current position as custom home:")
    controller.set_home_position()

    # Example 5: Move somewhere else
    print("\n6. Moving to (500, 600):")
    controller.move_to(500, 600)

    # Example 6: Return to custom home
    print("\n7. Returning to home position:")
    controller.return_to_home()

    # Example 7: Set specific home position
    print("\n8. Setting home to (300, 300) without moving:")
    controller.set_home_position(300, 300)

    # Cleanup
    controller.disconnect()
    print("\nExamples complete!")


def interactive_control():
    """Start interactive control mode"""

    # Initialize and connect to motor controller
    controller = MotorController()

    if not controller.connect():
        print("Failed to connect to motor controller")
        return

    # Setup motors (optionally home them)
    if not controller.setup_motors(home_motors=True):
        print("Failed to setup motors")
        controller.disconnect()
        return

    # Enter interactive mode - this provides a menu-driven interface
    controller.interactive_mode()

    # Cleanup
    controller.disconnect()


if __name__ == "__main__":
    import sys

    print("Manual Motor Control Examples")
    print("1. Run example sequence")
    print("2. Interactive control mode")

    choice = input("\nSelect option (1 or 2): ").strip()

    if choice == '1':
        example_manual_control()
    elif choice == '2':
        interactive_control()
    else:
        print("Invalid option")
