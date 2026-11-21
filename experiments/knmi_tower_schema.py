"""Explicit, validated NetCDF wind-variable schema for Cabauw tower observations."""
from __future__ import annotations

import math
import numpy as np


SPEED_UNITS = {'m/s', 'ms-1', 'm.s-1', 'm.s^-1'}
DIRECTION_UNITS = {'degree', 'degrees', 'degrees_true', 'deg', 'degreesfromnorth'}
HEIGHT_UNITS = {'m', 'meter', 'metre', 'meters', 'metres'}


def normalized_units(value):
    return str(value).lower().strip().replace(' ', '')


def validate_variable_units(speed, direction, level_label):
    su = normalized_units(speed.attrs.get('units', ''))
    du = normalized_units(direction.attrs.get('units', ''))
    if su not in SPEED_UNITS:
        raise ValueError(f'{level_label}: wind speed units not verified as m/s: {su!r}')
    if du not in DIRECTION_UNITS:
        raise ValueError(f'{level_label}: wind direction units not verified as degrees: {du!r}')
    declared = str(direction.attrs.get('standard_name', '')).lower().strip()
    if declared and declared != 'wind_from_direction':
        raise ValueError(f'{level_label}: direction standard_name {declared!r} not meteorological FROM')


def resolve_wind_levels(ds, mapping, time_name):
    """Return height, source names, and 1D time series. Never guess variable mappings."""
    if ('profile' in mapping) == ('levels' in mapping):
        raise ValueError('mapping requires exactly one of profile or levels')
    ntime = ds.sizes[time_name]
    levels = []

    if 'levels' in mapping:
        for height_str, pair in mapping['levels'].items():
            height = float(height_str)
            if not math.isfinite(height) or not 0 < height < 5000:
                raise ValueError('invalid physical measurement height')
            sn, dn = pair['speed'], pair['direction_from']
            if sn not in ds or dn not in ds:
                raise ValueError(f'mapped wind level {height_str} missing {sn} or {dn}; '
                                 'for Cabauw tower data use profile mapping (F,D over z)')
            speed, direction = ds[sn], ds[dn]
            if speed.dims != (time_name,) or direction.dims != (time_name,):
                raise ValueError(f'{height_str} m data must be 1D time-aligned')
            validate_variable_units(speed, direction, f'{height_str} m')
            levels.append((height, sn, dn, speed, direction))
    else:
        p = mapping['profile']
        zn = p['height_coordinate']
        sn, dn = p['speed'], p['direction_from']
        for name in (zn, sn, dn):
            if name not in ds:
                raise ValueError(f'profile mapping requires NetCDF variable {name!r}; '
                                 f'available variables: {list(ds.variables)}')
        z = ds[zn]
        if z.ndim != 1 or z.dims != (zn,):
            raise ValueError('height coordinate must be 1D along its own named dimension')
        zunit = normalized_units(z.attrs.get('units', ''))
        if zunit not in HEIGHT_UNITS:
            raise ValueError(f'height coordinate units must explicitly be metres: got {zunit!r}')
        heights = np.asarray(z.values, dtype=float)
        if not np.all(np.isfinite(heights)) or len(np.unique(heights)) != len(heights):
            raise ValueError('height levels must be finite and distinct')
        if np.any(heights <= 0) or np.any(heights >= 5000):
            raise ValueError('height levels outside supported AGL range')
        speed, direction = ds[sn], ds[dn]
        if set(speed.dims) != {time_name, zn} or set(direction.dims) != {time_name, zn}:
            raise ValueError('F and D must be 2D with time and height dimensions')
        if speed.sizes[time_name] != ntime or direction.sizes[time_name] != ntime or speed.sizes[zn] != len(heights) or direction.sizes[zn] != len(heights):
            raise ValueError('wind arrays incompatible with time and height coordinates')
        validate_variable_units(speed, direction, 'tower profile')
        tolerance = float(p.get('height_tolerance_m', 0.05))
        if not math.isfinite(tolerance) or tolerance < 0 or tolerance > 1:
            raise ValueError('height matching tolerance must be 0..1 m')
        chosen = p.get('selected_heights_m', [])
        if not isinstance(chosen, list) or not chosen:
            raise ValueError('selected_heights_m must explicitly list requested physical heights')
        if len(set(map(float, chosen))) != len(chosen):
            raise ValueError('selected heights contain duplicates')
        for requested in chosen:
            requested = float(requested)
            idx = np.flatnonzero(np.abs(heights - requested) <= tolerance)
            if len(idx) != 1:
                raise ValueError(f'requested {requested:g} m height not uniquely present; actual heights: {heights.tolist()}')
            i = int(idx[0])
            actual_height = float(heights[i])
            s = speed.isel({zn: i}, drop=True).transpose(time_name)
            d = direction.isel({zn: i}, drop=True).transpose(time_name)
            levels.append((actual_height, sn, dn, s, d))
    if not levels:
        raise ValueError('no wind levels mapped')
    if len({r[0] for r in levels}) != len(levels):
        raise ValueError('duplicate physical wind height')
    return sorted(levels, key=lambda r: r[0])
