# coordinate_sender.py
import socket
import json
import time

HOST = "10.3.36.6"  # IP of Script A (xArm server)
PORT = 5005

def send_coordinates(x, y, z):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        message = json.dumps({"x": x, "y": y, "z": z})
        s.sendall(message.encode())

# Example usage
coords_list = [
    (250, 0, 150),
    (250, 50, 100),
    (300, 0, 120)
]

for x, y, z in coords_list:
    print(f"Sending: x={x}, y={y}, z={z}")
    send_coordinates(x, y, z)
    time.sleep(2)  # wait 2 seconds between commands
