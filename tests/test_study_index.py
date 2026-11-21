"""test experiment session aggregation and duplicate prevention."""

import json

import pytest

from experiments.summarize_stationary_runs import collect


def report(path, left, right):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "inputs_sha256": {"gazebo_truth_csv": left, "px4_local_position_csv": right},
        "counts": {"px4_selected": 234},
        "px4": {"rms_3d_jitter_m": 0.02, "p95_3d_jitter_m": 0.03},
        "gazebo": {"stationary": True},
        "status": "descriptive_only", "clock_alignment": "numeric_overlap_only_not_verified",
    }))


def test_index_separate_runs(tmp_path):
    a = tmp_path / "a" / "stationary_evaluation.json"
    b = tmp_path / "b" / "stationary_evaluation.json"
    report(a, "aa", "bb")
    report(b, "cc", "dd")
    rows = collect([b, a])
    assert len(rows) == 2
    assert rows[0]["session"].endswith("a")
    assert rows[1]["px4_samples"] == 234


def test_reject_duplicate_data(tmp_path):
    a = tmp_path / "a" / "stationary_evaluation.json"
    b = tmp_path / "b" / "stationary_evaluation.json"
    report(a, "aa", "bb")
    report(b, "aa", "bb")
    with pytest.raises(ValueError, match="duplicate"):
        collect([a, b])
