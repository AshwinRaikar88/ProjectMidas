from xarm.wrapper import XArmAPI
import time
import math

# Connect to the xArm
arm = XArmAPI("192.168.1.188")
arm.connect()
print("Connected:", arm.connected)

# Enable motion and set to Cartesian control
arm.motion_enable(True)
arm.set_mode(0)   # 0 = position control (Cartesian)
arm.set_state(0)  # 0 = ready
time.sleep(1)

# Safe fixed position (X, Y, Z) to rotate in place
x_safe, y_safe, z_safe = 250, 0, 150


def check_if_safe():
    if arm.state == 4:
        print("xArm is in a stop state (state 4), attempting to recover...")

        # Clear any errors and warnings
        arm.clean_error()
        arm.clean_warn()

        # Set the state back to 0 (motion state)
        arm.set_state(state=0)

        # Re-enable the arm's motors
        arm.motion_enable(enable=True)

        # Optional: Reset the arm to a safe position
        arm.reset(wait=True)

        print("xArm has been recovered. You can now send new motion commands.")
        return 0
    else:
        return 1


def reset_position():
    arm.set_position(x=x_safe, y=y_safe, z=z_safe,
                     roll=180, pitch=0, yaw=0, speed=50, wait=True)
# Rotation function
def rotate_axis(axis='roll', steps=36, delay=0.2):
    """
    Rotate the end-effector 360° around a single axis.
    axis: 'roll', 'pitch', or 'yaw'
    steps: number of increments (360/steps = degrees per step)
    delay: seconds between movements
    """
    for i in range(steps + 1):
        proceed_flag = check_if_safe()
        if proceed_flag:
            angle = i * (360 / steps)  # current rotation
            roll, pitch, yaw = 180, 0, 0  # default orientation

            if axis == 'roll':
                roll = angle
            elif axis == 'pitch':
                pitch = angle
            elif axis == 'yaw':
                yaw = angle
            else:
                raise ValueError("Axis must be 'roll', 'pitch', or 'yaw'")

            arm.set_position(x=x_safe, y=y_safe, z=z_safe,
                             roll=roll, pitch=pitch, yaw=yaw,
                             speed=50, wait=True)
            time.sleep(delay)

# Rotate around roll
# print("Rotating around roll...")
# rotate_axis('roll')
#
# # Rotate around pitch
# print("Rotating around pitch...")
# rotate_axis('pitch')
#
# # Rotate around yaw
# print("Rotating around yaw...")
# rotate_axis('yaw')

reset_position()

print("Rotation demo complete!")
