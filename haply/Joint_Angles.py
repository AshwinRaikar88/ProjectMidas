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

# Example: move each joint by angle (degrees)
# joints = [J1, J2, J3, J4, J5, J6]
arm.set_servo_angle(angle=[0, 0, 0, 0, 0, 0], speed=100, wait=True)
arm.set_servo_angle(angle=[100, 0, 0, 0, 0, 0], speed=50, wait=True)

# Get current Cartesian position
pos = arm.get_position(is_radian=False)  # returns [x, y, z, roll, pitch, yaw]

x, y, z, roll, pitch, yaw = pos[1]   # pos[0] is error code, pos[1] is coords

# Force Y = 200
DEFAULT_Y_POS = 200

# Example: move along X (e.g., +50 mm)
x += 0
start_time = time.time()
arm.set_position(x=x, y=DEFAULT_Y_POS, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=100, wait=True)
end_time = time.time()

print(f"Move duration: {end_time - start_time:.2f} seconds")

# Example: move along Z (e.g., +30 mm up)
z += 30

start_time = time.time()
arm.set_position(x=x, y=DEFAULT_Y_POS, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=100, wait=True)
end_time = time.time()

# in mm
delta_x = 60

avg_time = []
for i in range(1, 6):
    x+=delta_x
    start_time = time.time()
    arm.set_position(x=x, y=DEFAULT_Y_POS, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=100, wait=True)
    end_time = time.time()

    duration = end_time - start_time
    avg_time.append(duration)

    print(f"{i} Move duration: {duration:.2f} seconds")

avg_time = sum(avg_time) / len(avg_time)
print(f"Average Move duration: {avg_time:.2f} seconds")

avg_time = []
for i in range(1, 6):
    x-=delta_x
    start_time = time.time()
    arm.set_position(x=x, y=DEFAULT_Y_POS, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=100, wait=True)
    end_time = time.time()

    duration = end_time - start_time
    avg_time.append(duration)
    print(f"{i} Move duration: {duration:.2f} seconds")

avg_time = sum(avg_time) / len(avg_time)


print(f"Average Move duration: {avg_time:.2f} seconds")