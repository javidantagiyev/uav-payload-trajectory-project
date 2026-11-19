
"""Payload release state from UAV position, velocity and attitude (SI units)."""

from math import radians, sin, cos


def rotation_matrix(roll, pitch, yaw):
    """Return the body-to-ENU rotation matrix for angles in degrees.

    Body frame: x forward, y left, z up. With zero attitude the body axes
    coincide with ENU, so the UAV nose points East. Yaw is measured from
    East, counter-clockwise (towards North). Rotation order is Z-Y-X:
    R = Rz(yaw) * Ry(pitch) * Rx(roll), and R maps body vectors into ENU.

    Returned as three rows: ((r11, r12, r13), (r21, r22, r23), (r31, r32, r33)).
    """
    phi = radians(roll)
    theta = radians(pitch)
    psi = radians(yaw)

    cr, sr = cos(phi), sin(phi)
    cp, sp = cos(theta), sin(theta)
    cy, sy = cos(psi), sin(psi)

    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr)
    )


def rotate(matrix, vector):
    """Multiply a 3x3 matrix by a 3D vector."""
    if len(vector) != 3:
        raise ValueError("Vector must contain exactly 3 values")

    return tuple(
        sum(matrix[i][j] * vector[j] for j in range(3))
        for i in range(3)
    )


def cross(a, b):
    """Return the cross product a x b of two 3D vectors."""
    if len(a) != 3 or len(b) != 3:
        raise ValueError("Vectors must contain exactly 3 values")

    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    )


def release_state(
    uav_position,
    uav_velocity,
    roll=0.0,
    pitch=0.0,
    yaw=0.0,
    mount_offset=(0.0, 0.0, 0.0),
    ejection_velocity=(0.0, 0.0, 0.0),
    angular_rate=(0.0, 0.0, 0.0)
):
    """Return the payload state (x, y, z, vx, vy, vz) at release.

    mount_offset and ejection_velocity are given in the body frame.
    angular_rate is the UAV angular velocity in ENU, rad/s.
    """
    if len(uav_position) != 3 or len(uav_velocity) != 3:
        raise ValueError("UAV position and velocity must contain 3 values")

    if len(mount_offset) != 3 or len(ejection_velocity) != 3:
        raise ValueError("Mount offset and ejection velocity must contain 3 values")

    if len(angular_rate) != 3:
        raise ValueError("Angular rate must contain exactly 3 values")

    matrix = rotation_matrix(roll, pitch, yaw)

    offset = rotate(matrix, mount_offset)
    ejection = rotate(matrix, ejection_velocity)

    # Lever-arm velocity of the mount point caused by UAV rotation.
    lever = cross(angular_rate, offset)

    position = tuple(uav_position[i] + offset[i] for i in range(3))

    velocity = tuple(
        uav_velocity[i] + ejection[i] + lever[i]
        for i in range(3)
    )

    return position + velocity
