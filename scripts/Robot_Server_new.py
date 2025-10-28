import os
import time
import json
from xarm.wrapper import XArmAPI

# -----------------------------
# CONFIGURATION
# -----------------------------
ROBOT_IP = "192.168.1.188"
JSON_FILE = "haply_to_xarm.json"
CHECK_INTERVAL = 1.0  # seconds

# -----------------------------
# CONNECT TO ROBOT
# -----------------------------
arm = XArmAPI(ROBOT_IP)
arm.connect()
if not arm.connected:
    raise RuntimeError("Could not connect to xArm!")

print(f"Connected to xArm at {ROBOT_IP}")

# Safe fixed position (X, Y, Z) to rotate in place
x_safe, y_safe, z_safe = 250, 0, 150


def check_if_safe():
    if arm.state == 4 or arm.state == 22:
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
    # Clear any errors and warnings
    arm.clean_error()
    arm.clean_warn()

    # Set the state back to 0 (motion state)
    arm.set_state(state=0)

    # Re-enable the arm's motors
    arm.motion_enable(enable=True)

    # Optional: Reset the arm to a safe position
    arm.reset(wait=True)

    arm.set_position(x=x_safe, y=y_safe, z=z_safe,
                     roll=180, pitch=0, yaw=0, speed=50, wait=True)

# -----------------------------
# HELPER: move robot
# -----------------------------
def move_to_coords(x, y, z):
    """Moves robot to given coordinates (in mm)."""
    try:
        print(f"Moving robot to: x={x}, y={y}, z={z}")
        # Mode 0 = absolute, is_radian=False
        arm.set_position(x=x, y=y, z=z, roll=0, pitch=0, yaw=0,
                                speed=50, mvacc=500, wait=False)

        check_if_safe()

    except Exception as e:
        reset_position()

        print(f"Error moving robot: {e}")

# -----------------------------
# HELPER: watch JSON file
# -----------------------------
def watch_json_file(filepath, interval=1.0):
    """Check file for updates every `interval` seconds."""
    last_mtime = None
    while True:
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            if last_mtime is None or mtime > last_mtime:
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    x, y, z = data["x"], data["y"], data["z"]
                    move_to_coords(x, y, z)
                except Exception as e:
                    print(f"Failed to read/parse {filepath}: {e}")
                last_mtime = mtime
        time.sleep(interval)

# -----------------------------
# MAIN LOOP
# -----------------------------
try:
    print(f"Watching {JSON_FILE} for updates...")
    watch_json_file(JSON_FILE, CHECK_INTERVAL)
except KeyboardInterrupt:
    print("\nShutting down.")
finally:
    arm.disconnect()
