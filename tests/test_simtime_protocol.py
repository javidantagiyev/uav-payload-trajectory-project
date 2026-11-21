"""6f timestamp window must not confuse wall time and simulation time."""

import pytest

from src.physics.simtime_protocol import SimTimeWindow
from src.physics.simulator_io import RigidBodySample


def item(t):
    return RigidBodySample(t, (0, 0, 2), (1, 0, 0, 0),
                           (0, 0, 0), (0, 0, 0))


def test_complete_from_simulation_timestamps():
    window = SimTimeWindow(.20, 100)
    for i in range(22):
        window.ingest(item(i * .01))
    result = window.report()
    assert result["status"] == "sim_time_window_captured"
    assert result["recorded_sim_duration_s"] == pytest.approx(.20)
    assert result["samples"] == 21


def test_incomplete_even_if_wall_timeout():
    window = SimTimeWindow(1, 100)
    for i in range(22):
        window.ingest(item(i * .01))
    assert window.report(wall_timeout=True)["status"] == "wall_timeout_before_sim_duration"


def test_nonmonotonic_sample_is_rejected():
    window = SimTimeWindow(.5, 100)
    window.ingest(item(0))
    window.ingest(item(.01))
    window.ingest(item(.01))
    assert window.rejected == 1
    assert window.report()["status"] == "incomplete"


def test_late_first_sample_rejected():
    window = SimTimeWindow(.5, 100, start_limit_s=.05)
    window.ingest(item(.20))
    assert "first_sample_late" in window.report()["failure"]


def test_large_gap_is_not_accepted():
    window = SimTimeWindow(.5, 100)
    window.ingest(item(0))
    window.ingest(item(.01))
    window.ingest(item(.1))
    assert "sample_gap_exceeded" in window.report()["failure"]


def test_bad_or_overlarge_sample_request():
    with pytest.raises(ValueError, match="max_samples"):
        SimTimeWindow(180, 500)
    with pytest.raises(ValueError):
        SimTimeWindow(0, 100)


def test_invalid_sample_doesnt_fabricate_success():
    window = SimTimeWindow(.2, 100)
    invalid = RigidBodySample(0, (float("nan"), 0, 1), (1,0,0,0), (0,0,0), (0,0,0))
    window.ingest(invalid)
    assert window.rejected == 1
    assert not window.samples
