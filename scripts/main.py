from xarm.wrapper import XArmAPI
import time

# Connect to the robot (replace with your robot IP)
arm = XArmAPI('192.168.1.188')
arm.connect()

print("Connected:", arm.connected)

# Enable motion
arm.motion_enable(enable=True)
arm.set_mode(0)   # 0 = position control mode
arm.set_state(0)  # 0 = ready
time.sleep(1)

# Cartesian mode
arm.set_mode(0)
arm.set_state(0)

# 1️⃣ Move above object
arm.set_position(x=250, y=0, z=150, roll=180, pitch=0, yaw=0, speed=100, wait=True)

# 2️⃣ Lower to pick
arm.set_position(x=250, y=0, z=50, roll=180, pitch=0, yaw=0, speed=50, wait=True)

# 4️⃣ Lift object
arm.set_position(x=250, y=0, z=150, roll=180, pitch=0, yaw=0, speed=100, wait=True)

# 5️⃣ Move to place location
arm.set_position(x=500, y=50, z=150, roll=180, pitch=0, yaw=0, speed=100, wait=True)
arm.set_position(x=300, y=50, z=50, roll=180, pitch=0, yaw=0, speed=50, wait=True)

# 7️⃣ Return home
arm.set_position(x=250, y=0, z=200, roll=180, pitch=0, yaw=0, speed=100, wait=True)
