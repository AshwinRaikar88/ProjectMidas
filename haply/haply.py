#!/usr/bin/env python

"""This example demonstrates how to display a haptic ball """

__author__ = "Antoine Weill--Duflos"
__copyright__ = "Copyright 2023, HaplyRobotics"

import HaplyHardwareAPI
import time
import math
connected_devices = HaplyHardwareAPI.detect_inverse3s()
com_stream = HaplyHardwareAPI.SerialStream(connected_devices[0])
inverse3 = HaplyHardwareAPI.Inverse3(com_stream)
response_to_wakeup = inverse3.device_wakeup_dict()
print("connected to device {}".format(response_to_wakeup["device_id"]))
start_time = time.perf_counter()
loop_time = 0.001  # 1ms
forces = [0, 0, 0]


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
        return force


def force_sphere_inner(sphere_center, sphere_radius, device_position, stiffness):
    """
    Computes a force that pushes the end-effector out of a sphere.
    The force is applied only when the end-effector is inside the sphere.

    Args:
        sphere_center (list): A list of 3 floats representing the [x, y, z] center of the sphere.
        sphere_radius (float): The radius of the sphere.
        device_position (list): A list of 3 floats representing the [x, y, z] position of the device.
        stiffness (float): The stiffness coefficient for the force.

    Returns:
        list: A list of 3 floats representing the [Fx, Fy, Fz] forces to apply.
    """
    # Calculate the Euclidean distance from the sphere's center to the end-effector
    distance = math.sqrt(
        sum([(device_position[i] - sphere_center[i]) ** 2 for i in range(3)]))

    # Check if the end-effector is inside the sphere's radius
    if distance > sphere_radius:
        # Compute the normalized direction of the forces
        # We use a small epsilon to avoid division by zero if distance is 0
        direction = [(device_position[i] - sphere_center[i]) / (distance + 1e-6)
                     for i in range(3)]

        # Compute the force. The force magnitude is proportional to how deep
        # the end-effector is inside the sphere (sphere_radius - distance)
        force = [direction[i] * (sphere_radius - distance) * stiffness
                 for i in range(3)]

        return force
    else:
        # No force is applied when the end-effector is outside the sphere
        return [0, 0, 0]

def force_cube(cube_center, cube_size, device_position, stiffness):
    """
    Computes a force that pushes the end-effector back into a cube.
    The force is applied only when the end-effector is outside the cube.

    Args:
        cube_center (list): A list of 3 floats representing the [x, y, z] center of the cube.
        cube_size (list): A list of 3 floats representing the [x, y, z] dimensions of the cube.
        device_position (list): A list of 3 floats representing the [x, y, z] position of the device.
        stiffness (float): The stiffness coefficient for the force.

    Returns:
        list: A list of 3 floats representing the [Fx, Fy, Fz] forces to apply.
    """
    forces = [0, 0, 0]

    # Calculate the half-sizes of the cube
    half_size = [s / 2 for s in cube_size]

    # Calculate the min and max coordinates of the cube
    cube_min = [cube_center[i] - half_size[i] for i in range(3)]
    cube_max = [cube_center[i] + half_size[i] for i in range(3)]

    # Check if the device is outside the cube and calculate the force
    for i in range(3):
        if device_position[i] < cube_min[i]:
            # Push back along the negative direction
            forces[i] = (cube_min[i] - device_position[i]) * stiffness
        elif device_position[i] > cube_max[i]:
            # Push back along the positive direction
            forces[i] = (cube_max[i] - device_position[i]) * stiffness

    return forces


def damping_force(velocity, damping_coefficient):
    """
    Calculates a damping force proportional to the velocity.
    The force acts in the opposite direction of the velocity.

    Args:
        velocity (list): A list of 3 floats representing the [vx, vy, vz] velocity of the device.
        damping_coefficient (float): The coefficient that determines the "thickness" of the medium.

    Returns:
        list: A list of 3 floats representing the [Fx, Fy, Fz] forces to apply.
    """
    # The force is the negative of the velocity multiplied by the damping coefficient
    # F = -c * v
    forces = [-v * damping_coefficient for v in velocity]

    return forces


while True:
    position, velocity = inverse3.end_effector_force(forces)
    forces = force_sphere([0, -0.14, 0.2], 0.08, position, stiffness=100)

    forces = force_sphere_inner([0, -0.14, 0.2], 0.08, position, stiffness=800)

    # Define the cube properties
    cube_center = [0, -0.14, 0.2]  # Same center as the sphere

    # For a cube of 8cm radius, the side is 16cm.
    sq_cm = 0.20
    cube_size = [sq_cm, sq_cm, sq_cm]
    stiffness = 80

    # forces = force_cube(cube_center, cube_size, position, stiffness)

    # print("position: {}".format(position))
    while time.perf_counter() - start_time < loop_time:  # wait for loop time to be reached
        pass
    start_time = time.perf_counter()