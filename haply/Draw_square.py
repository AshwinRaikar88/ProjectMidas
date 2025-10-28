from xarm.wrapper import XArmAPI
import time

# Connect to robot
arm = XArmAPI('192.168.1.188')
arm.connect()

# Enable motion
arm.motion_enable(True)
arm.set_mode(0)   # position control
arm.set_state(0)
time.sleep(1)

# Square parameters
z = 150       # fixed height (mm)
roll, pitch, yaw = 180, 0, 0
speed = 100

# Starting corner (bottom-left of square)
x0, y0 = 100, 100
size = 100  # square side length (mm)

# Define corners (in XY plane)
square_points = [
    (x0, y0, z),               # bottom-left
    (x0+size, y0, z),          # bottom-right
    (x0+size, y0+size, z),     # top-right
    (x0, y0+size, z),          # top-left
    (x0, y0, z)                # back to start
]

# Move through each corner
while(True):
    for (x, y, z) in square_points:
        arm.set_position(x=x, y=y, z=z,
                         roll=roll, pitch=pitch, yaw=yaw,
                         speed=speed, wait=True)
        time.sleep(0.1)  # small pause
