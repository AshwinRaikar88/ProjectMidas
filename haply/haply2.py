#!/usr/bin/env python

"""This example demonstrates how to display a haptic ball """

__author__ = "Ashwin Raikar"
__copyright__ = "Copyright 2025, Bionanomics"

import HaplyHardwareAPI
import time
import math

import socket
import json
import keyboard  # pip install keyboard


connected_devices = HaplyHardwareAPI.detect_inverse3s()
com_stream = HaplyHardwareAPI.SerialStream(connected_devices[0])
inverse3 = HaplyHardwareAPI.Inverse3(com_stream)
response_to_wakeup = inverse3.device_wakeup_dict()
print("connected to device {}".format(response_to_wakeup["device_id"]))
start_time = time.perf_counter()
loop_time = 0.001  # 1ms

# loop_time = 5  # 5s
forces = [0, 0, 0]




HOST = "10.3.36.6"  # IP of Script A (xArm server)
PORT = 5005

def send_coordinates(x, y, z):
    try:
        print(f"Sending: x={x}, y={y}, z={z}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            message = json.dumps({"x": x, "y": y, "z": z})
            s.sendall(message.encode())
    except Exception as e:
        print(e)


def force_sphere(sphere_center, sphere_radius, device_position, stiffness):
    distance = math.sqrt(
        sum([(device_position[i] - sphere_center[i])**2 for i in range(3)]))
    if distance > sphere_radius:
        return [0, 0, 0]
    else:
        # Compute the normalised direction of the forces
        direction = [(device_position[i] - sphere_center[i])/sphere_radius
                     for i in range(3)]
        # Compute the force
        force = [direction[i]*(sphere_radius-distance)
                 * stiffness for i in range(3)]

        print(f"position: {device_position}")

        # send_coordinates(180, 0, device_position[2]*100)
        return force


while True:
    position, velocity = inverse3.end_effector_force(forces)
    forces = force_sphere([0, -0.14, 0.2], 0.1, position, stiffness=200)
    # print("position: {}".format(position))

    space_pressed = keyboard.is_pressed("space")
    if space_pressed:
        send_coordinates(180, position[1] * 1000, position[2] * 1000)

    while time.perf_counter() - start_time < loop_time:  # wait for loop time to be reached
        pass
    start_time = time.perf_counter()