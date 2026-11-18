import pytest

from src.physics.analytical import gravity_impact_time
from src.physics.gravity import gravity_position


def test_horizontal_launch():
    t = gravity_impact_time(19.62)

    position = gravity_position((0, 0, 19.62), (5, 2, 0), t)

    assert t == pytest.approx(2.0)
    assert position == pytest.approx((10, 4, 0))


def test_upward_launch_from_ground():
    t = gravity_impact_time(0, 9.81)

    assert t == pytest.approx(2.0)


def test_invalid_height():
    with pytest.raises(ValueError):
        gravity_impact_time(-1)
