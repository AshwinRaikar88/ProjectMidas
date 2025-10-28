# arm_controller.py
from xarm.wrapper import XArmAPI
import socket
import threading
import json
import time

# Connect to xArm
arm = XArmAPI("192.168.1.188")
arm.connect()
arm.motion_enable(True)
arm.set_mode(0)
arm.set_state(0)
time.sleep(1)


def init_robot():
    # Example: move each joint by angle (degrees)
    # joints = [J1, J2, J3, J4, J5, J6]
    arm.set_servo_angle(angle=[0, 0, 0, 0, 0, 0], speed=100, wait=True)
    arm.set_servo_angle(angle=[100, 0, 0, 0, 0, 0], speed=50, wait=True)

    # Get current Cartesian position
    pos = arm.get_position(is_radian=False)  # returns [x, y, z, roll, pitch, yaw]

    x, y, z, roll, pitch, yaw = pos[1]   # pos[0] is error code, pos[1] is coords

    # Cartesian mode
    arm.set_mode(0)
    arm.set_state(0)


# Safe position function
def reset_safe_position():
    print("Resetting arm to safe position...")
    try:
        arm.set_position(x=250, y=0, z=150, roll=180, pitch=0, yaw=0, speed=50, wait=True)
        return False
    except Exception as e:
        print("Failed to reset:", e)

# Safe set_position wrapper
def safe_set_position(x, y, z, roll=180, pitch=0, yaw=0, speed=50):
    try:
        arm.set_position(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw, speed=speed, wait=True)
    except Exception as e:
        print("[ERROR] Motion failed:", e)
        return True

    return False

# TCP server to receive coordinates
# def client_handler(conn, addr):
#     print(f"Connection from {addr}")
#     with conn:
#         while True:
#             data = conn.recv(1024)
#             if not data:
#                 break
#             try:
#                 # Expecting JSON: {"x":..., "y":..., "z":...}
#                 coords = json.loads(data.decode())
#                 x = coords.get("x")
#                 y = coords.get("y")
#                 z = coords.get("z")
#                 print(f"Received: x={x}, y={y}, z={z}")
#                 safe_set_position(x, y, z)
#             except Exception as e:
#                 print("Invalid data received:", e)

def client_handler(conn, addr, reset_flag):
    print(f"Connection from {addr}")
    last_processed_time = 0  # Track last processed timestamp

    with conn:
        while True:
            data = conn.recv(1024)

            if reset_flag:
                reset_flag = reset_safe_position()
                continue

            if not data:
                break


            current_time = time.time()
            if current_time - last_processed_time < 2:
                print("Throttling: Skipping message to avoid overload")
                continue  # Skip processing if within 2 seconds

            try:
                coords = json.loads(data.decode())
                x = coords.get("x")
                y = coords.get("y")
                z = coords.get("z")
                print(f"Received: x={x}, y={y}, z={z}")
                reset_flag = safe_set_position(x, y, z)
                last_processed_time = current_time  # Update timestamp
            except Exception as e:
                print("Invalid data received:", e)


# Start server
HOST = "0.0.0.0"
PORT = 5005
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
reset_flag = False
print(f"Arm controller listening on {HOST}:{PORT}")

init_robot()

server.settimeout(1)  # 1 second
while True:
    try:
        conn, addr = server.accept()
        conn.settimeout(None)
        threading.Thread(target=client_handler, args=(conn, addr, reset_flag), daemon=True).start()
    except socket.timeout:
        continue  # just loop again

