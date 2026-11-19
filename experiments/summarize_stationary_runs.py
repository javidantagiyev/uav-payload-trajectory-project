"""index independently analyzed simulation sessions without pooling raw samples."""

import argparse
import csv
import json
from pathlib import Path


COLUMNS = (
    "session", "model", "status", "px4_samples", "rms_3d_jitter_m",
    "p95_3d_jitter_m", "gazebo_stationary", "quality_checked",
    "clock_alignment", "source_hash_prefix",
)


def collect(paths):
    """summarize per-session reports while rejecting duplicated source inputs."""
    records = []
    seen = set()
    for path in sorted(map(Path, paths)):
        obj = json.loads(path.read_text(encoding="utf-8"))
        required = ("inputs_sha256", "counts", "px4", "gazebo", "status", "clock_alignment")
        if any(key not in obj for key in required):
            raise ValueError(f"not a stationary evaluation report: {path}")
        hashes = obj["inputs_sha256"]
        if "gazebo_truth_csv" not in hashes or "px4_local_position_csv" not in hashes:
            raise ValueError(f"report lacks source hashes: {path}")
        identity = (hashes["gazebo_truth_csv"], hashes["px4_local_position_csv"])
        if identity in seen:
            raise ValueError(f"duplicate input recording in {path}")
        seen.add(identity)
        records.append({
            "session": str(path.parent),
            "model": str(obj.get("model", "unknown")),
            "status": str(obj["status"]),
            "px4_samples": int(obj["counts"]["px4_selected"]),
            "rms_3d_jitter_m": float(obj["px4"]["rms_3d_jitter_m"]),
            "p95_3d_jitter_m": float(obj["px4"]["p95_3d_jitter_m"]),
            "gazebo_stationary": bool(obj["gazebo"]["stationary"]),
            "quality_checked": bool(obj.get("quality_history_checked", False)),
            "clock_alignment": obj["clock_alignment"],
            "source_hash_prefix": hashes["gazebo_truth_csv"][:12],
        })
    if not records:
        raise ValueError("no analysis reports found")
    return records


def main():
    parser = argparse.ArgumentParser(description="index stationary experiment reports")
    parser.add_argument("reports", nargs="+", type=Path,
                        help="one stationary_evaluation.json per independent session")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = collect(args.reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"indexed {len(rows)} independent sessions in {args.output}")


if __name__ == "__main__":
    main()
