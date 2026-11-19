#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
if ! command -v gz >/dev/null; then
  echo "gazebo command not found; install gazebo harmonic" >&2
  exit 1
fi
exec gz sim sim/gazebo/worlds/rigid_body_lab.sdf
