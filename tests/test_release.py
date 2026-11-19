
import pytest

from src.physics.release import (
    rotation_matrix,
    rotate,
    cross,
    release_state
)


def test_zero_attitude_is_identity():
    matrix = rotation_matrix(0, 0, 0)

    assert rotate(matrix, (1, 2, 3)) == pytest.approx((1, 2, 3))


def test_yaw_90_turns_forward_to_north():
    matrix = rotation_matrix(0, 0, 90)

    assert rotate(matrix, (1, 0, 0)) == pytest.approx((0, 1, 0))
    assert rotate(matrix, (0, 1, 0)) == pytest.approx((-1, 0, 0))


def test_positive_pitch_lowers_nose():
    matrix = rotation_matrix(0, 90, 0)

    assert rotate(matrix, (1, 0, 0)) == pytest.approx((0, 0, -1))


def test_positive_roll_lifts_left_side():
    matrix = rotation_matrix(90, 0, 0)

    assert rotate(matrix, (0, 1, 0)) == pytest.approx((0, 0, 1))


def test_rotation_keeps_length():
    matrix = rotation_matrix(20, -15, 130)
    vector = rotate(matrix, (3, 4, 12))

    assert sum(value ** 2 for value in vector) == pytest.approx(169)


def test_cross_product():
    assert cross((1, 0, 0), (0, 1, 0)) == (0, 0, 1)
    assert cross((0, 1, 0), (1, 0, 0)) == (0, 0, -1)


def test_zero_attitude_release():
    state = release_state(
        (10, 20, 100),
        (15, 0, 0),
        mount_offset=(0, 0, -0.5),
        ejection_velocity=(0, 0, -1)
    )

    assert state == pytest.approx((10, 20, 99.5, 15, 0, -1))


def test_yaw_rotates_mount_offset_and_ejection():
    state = release_state(
        (0, 0, 50),
        (0, 0, 0),
        yaw=90,
        mount_offset=(1, 0, 0),
        ejection_velocity=(2, 0, 0)
    )

    assert state == pytest.approx((0, 1, 50, 0, 2, 0))


def test_lever_arm_velocity():
    # Yaw rate 1 rad/s with the mount 2 m ahead adds 2 m/s towards North.
    state = release_state(
        (0, 0, 50),
        (10, 0, 0),
        mount_offset=(2, 0, 0),
        angular_rate=(0, 0, 1)
    )

    assert state == pytest.approx((2, 0, 50, 10, 2, 0))


def test_invalid_uav_position():
    with pytest.raises(ValueError):
        release_state((0, 0), (0, 0, 0))


def test_invalid_mount_offset():
    with pytest.raises(ValueError):
        release_state((0, 0, 0), (0, 0, 0), mount_offset=(0, 0))


def test_invalid_angular_rate():
    with pytest.raises(ValueError):
        release_state((0, 0, 0), (0, 0, 0), angular_rate=(0, 0, 0, 0))


def test_invalid_rotate_vector():
    with pytest.raises(ValueError):
        rotate(rotation_matrix(0, 0, 0), (1, 2))


def test_invalid_cross_vector():
    with pytest.raises(ValueError):
        cross((1, 0), (0, 1, 0))
