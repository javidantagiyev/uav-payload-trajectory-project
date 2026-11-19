from pyulog import ULog
import numpy as np

path = "/home/shale/projects/PX4-Autopilot/build/px4_sitl_default/rootfs/log/2026-11-19/09_33_12.ulg"

log = ULog(path)
d = next(x.data for x in log.data_list if x.name == "vehicle_local_position")

t = d["timestamp"] / 1e6
mask = (t >= 32.620) & (t <= 52.612)

# convert ned position to enu
position = np.column_stack((d["y"], d["x"], -d["z"]))[mask]

mean = np.mean(position, axis=0)
std = np.std(position, axis=0)
deviation = np.linalg.norm(position - mean, axis=1)

print("mean position (enu):", mean)
print("std per axis (m):", std)
print("3d rms jitter (m):", np.sqrt(np.mean(deviation**2)))
print("95th percentile jitter (m):", np.percentile(deviation, 95))
