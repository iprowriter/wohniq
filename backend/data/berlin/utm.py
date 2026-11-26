"""ETRS89 / UTM → WGS84 latitude/longitude (inverse transverse Mercator, GRS80).

The Kita list gives ETRS89/UTM zone 33N coordinates (EPSG:25833). GRS80 and WGS84 differ by
well under a millimetre at this scale, so the result is used as WGS84 directly. Formulas:
Snyder, "Map Projections — A Working Manual" (USGS PP 1395), pp. 63–64.
"""

from __future__ import annotations

import math

_A = 6378137.0
_F = 1 / 298.257222101  # GRS80
_K0 = 0.9996
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)


def utm_to_latlng(easting: float, northing: float, zone: int = 33) -> tuple[float, float]:
    x = easting - 500000.0
    y = northing
    lon0 = math.radians(zone * 6 - 183)
    m = y / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2**2 / 64 - 5 * _E2**3 / 256))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = _A / math.sqrt(1 - _E2 * sin1**2)
    t1 = tan1**2
    c1 = _EP2 * cos1**2
    r1 = _A * (1 - _E2) / (1 - _E2 * sin1**2) ** 1.5
    d = x / (n1 * _K0)
    lat = phi1 - (n1 * tan1 / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _EP2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * _EP2 - 3 * c1**2) * d**6 / 720
    )
    lon = (
        lon0
        + (
            d
            - (1 + 2 * t1 + c1) * d**3 / 6
            + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _EP2 + 24 * t1**2) * d**5 / 120
        )
        / cos1
    )
    return math.degrees(lat), math.degrees(lon)
