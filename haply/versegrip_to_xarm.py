import time
import json
import keyboard  # pip install keyboard
import HaplyHardwareAPI
from HaplyHardwareAPI import SerialStream, Inverse3

# -----------------------------
# CONFIGURATION
# -----------------------------
OUTPUT_FILE = "haply_to_xarm.json"
LOOP_TIME = 0.01  # 10ms loop

# Haply workspace bounds (example in meters)
HAPLY_X_MIN, HAPLY_X_MAX = -0.2, 0.2
HAPLY_Y_MIN, HAPLY_Y_MAX = -0.2, 0.2
HAPLY_Z_MIN, HAPLY_Z_MAX = 0.0, 0.2

# xArm workspace bounds (in mm)
XARM_X_MIN, XARM_X_MAX = 250, 300
XARM_Y_MIN, XARM_Y_MAX = 0, 50
XARM_Z_MIN, XARM_Z_MAX = 100, 150

# -----------------------------
# CONNECT TO HAPLY DEVICE
# -----------------------------
connected_devices = HaplyHardwareAPI.detect_inverse3s()
if not connected_devices:
    raise RuntimeError("No Haply devices detected!")

com_stream = SerialStream(connected_devices[0])
inverse3 = Inverse3(com_stream)
inverse3.device_wakeup_dict()
print(f"Connected to Haply device: {connected_devices[0]}")

# -----------------------------
# HELPER: normalize Haply -> xArm
# -----------------------------
def normalize(value, old_min, old_max, new_min, new_max):
    if old_max - old_min == 0:
        return new_min
    value = max(min(value, old_max), old_min)
    return new_min + (value - old_min) * (new_max - new_min) / (old_max - old_min)

def haply_to_xarm_coords(haply_pos):
    x_h, y_h, z_h = haply_pos
    x = normalize(x_h, HAPLY_X_MIN, HAPLY_X_MAX, XARM_X_MIN, XARM_X_MAX)
    y = normalize(y_h, HAPLY_Y_MIN, HAPLY_Y_MAX, XARM_Y_MIN, XARM_Y_MAX)
    z = normalize(z_h, HAPLY_Z_MIN, HAPLY_Z_MAX, XARM_Z_MIN, XARM_Z_MAX)
    return int(x), int(y), int(z)

# -----------------------------
# MAIN LOOP
# -----------------------------
last_space_state = False
print("Press SPACEBAR to save Haply coordinates to JSON. Press ESC to exit.")

try:
    while True:
        # Poll Haply device
        position, velocity = inverse3.end_effector_force([0, 0, 0])
        haply_pos = position  # [x, y, z] in meters

        mapped = haply_to_xarm_coords(haply_pos)
        print(f"Live Haply: {haply_pos} -> xArm: {mapped}", end="\r")

        # Spacebar pressed → save JSON
        space_pressed = keyboard.is_pressed("space")
        if space_pressed and not last_space_state:
            data = {"x": mapped[0], "y": mapped[1], "z": mapped[2]}
            with open(OUTPUT_FILE, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\nSaved to {OUTPUT_FILE}: {data}")
            time.sleep(0.1)  # debounce

        last_space_state = space_pressed

        if keyboard.is_pressed("esc"):
            print("\nExiting program.")
            break

        time.sleep(LOOP_TIME)

except KeyboardInterrupt:
    print("Interrupted by user.")
finally:
    com_stream.close()
