"""publication-readable simulation screening figures; never claim physical validation."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.physics.environmental_evaluation import load_trajectory

LABELS = {"x_m": "East position (m)", "y_m": "North position (m)",
          "z_m": "Height (m)"}


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _base_ax(title, y):
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.set_title(title)
    ax.set_xlabel("Elapsed simulation time (s)")
    ax.set_ylabel(y)
    ax.grid(alpha=0.3)
    return fig, ax


def plot_case(case_row, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    signals = [load_trajectory(r["path"]) for r in case_row["runs"]]
    if not signals:
        return []
    files = []
    for k in ("x_m", "y_m", "z_m"):
        for view in ("full", "early"):
            fig, ax = _base_ax(f"{case_row['id']} | {LABELS[k]} | {view} view", LABELS[k])
            for i, data in enumerate(signals):
                t = data["time_s"]
                end = min(0.4, float(t[-1])) if view == "early" else float(t[-1])
                keep = t <= end + 1e-8
                ax.plot(t[keep], data[k][keep], lw=1.15, alpha=0.65,
                        label=f"run {case_row['runs'][i]['repeat_index']:03d}")
            ax.legend(ncol=min(5, len(signals)), fontsize=8, loc="best")
            ax.set_xlim(left=0, right=end)
            path = out / f"{k}_{view}.png"
            _save(fig, path)
            files.append(path)

    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    for i, data in enumerate(signals):
        ax.plot(data["x_m"], data["y_m"], label=f"run {case_row['runs'][i]['repeat_index']:03d}",
                lw=1.25, alpha=0.75)
    ax.scatter([signals[0]["x_m"][0]], [signals[0]["y_m"][0]], marker="o", s=45, label="start")
    ax.set_title(f"{case_row['id']} | horizontal path (entire run)")
    ax.set_xlabel("East position (m)")
    ax.set_ylabel("North position (m)")
    ax.axis("equal")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    xy_path = out / "horizontal_path.png"
    _save(fig, xy_path)
    files.append(xy_path)

    if len(signals) >= 2:
        end = min(float(d["time_s"][-1]) for d in signals)
        grid = np.linspace(0, end, 400)
        fig, ax = _base_ax(f"{case_row['id']} | repeat variability (descriptive)",
                           "East displacement from first sample (m)")
        shifted = np.array([np.interp(grid, d["time_s"], d["x_m"] - d["x_m"][0]) for d in signals])
        avg = shifted.mean(axis=0)
        std = shifted.std(axis=0, ddof=1)
        ax.plot(grid, avg, label="mean over repeated runs", linewidth=1.8)
        ax.fill_between(grid, avg - std, avg + std, alpha=0.20,
                        label="± 1 sample SD (not a confidence interval)")
        ax.legend(fontsize=9)
        path = out / "repeat_variability.png"
        _save(fig, path)
        files.append(path)

    # diagnostic only: a fit can measure effective acceleration, not isolate gravity.
    cutoffs = [0.12, 0.18, 0.24, 0.30]
    from src.physics.simtime_analysis import effective_z_acceleration
    figures = []
    for d in signals:
        vals = [effective_z_acceleration(d, h) for h in cutoffs]
        figures.append([v["g_effective_m_s2"] if v else float("nan") for v in vals])
    if np.isfinite(figures).any():
        fig, ax = plt.subplots(figsize=(9.0, 4.8))
        for i, values in enumerate(figures):
            ax.plot(cutoffs, values, "o-", label=f"run {case_row['runs'][i]['repeat_index']:03d}")
        ax.axhline(float(case_row["parameters"]["gravity_m_s2"]), ls="--", lw=1.2,
                   label="world gravity setting (reference, not a measurement)")
        ax.set(title=f"{case_row['id']} | early quadratic-fit sensitivity",
               xlabel="Fit-window length (s)", ylabel="Effective downward acceleration from z fit (m/s²)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        path = out / "effective_acceleration_diagnostic.png"
        _save(fig, path)
        files.append(path)
    return files


def plot_overview(report, output):
    output = Path(output)
    cases = [r for r in report["cases"] if r["status"] == "evaluated" and
             r.get("aggregate", {}).get("probe_available")]
    if not cases:
        return []
    values = [(r["id"], r["aggregate"]["probe_shift_east_m"],
               r["aggregate"]["probe_shift_north_m"]) for r in cases]
    fig, ax = plt.subplots(figsize=(max(9, .52*len(values)), 5.8))
    idx = np.arange(len(values))
    w = 0.37
    ax.bar(idx-w/2, [v[1]["mean"]*1000 for v in values], width=w, label="East shift")
    ax.bar(idx+w/2, [v[2]["mean"]*1000 for v in values], width=w, label="North shift")
    ax.set(xticks=idx, xticklabels=[v[0] for v in values],
           ylabel="Signed displacement from initial position at 0.2 s (mm)",
           title="Controlled scenario comparison | Gazebo odometry")
    ax.tick_params(axis="x", labelrotation=55)
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(0, lw=1)
    ax.legend()
    path = output / "wind_response_0p2s.png"
    _save(fig, path)
    return [path]
