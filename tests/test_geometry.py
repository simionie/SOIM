import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from SOIM.lib.geometry_correction import (
    area_tri,
    area_triangle_and_point,
    footprint_polygon,
)


@pytest.mark.parametrize(
    "lon,lat,kind",
    [
        ([10, 11, 11, 10], [0, 0, 1, 1], "Polygon"),
        ([179, -179, -179, 179], [10, 10, 11, 11], "MultiPolygon"),
        ([178, 179, -179, 178], [0, 2, 1, -1], "MultiPolygon"),
        ([179, -179, 179, 178], [0, 2, 3, 1], "MultiPolygon"),
        ([-135, -45, 45, 135], [-89, -89, -89, -89], "Polygon"),
        ([-135, -45, 45, 135], [89, 89, 89, 89], "Polygon"),
    ],
)
def test_footprint_correction_preserves_corners(lon, lat, kind):
    for offset in range(len(lon)):
        xs, ys = np.roll(lon, offset), np.roll(lat, offset)
        for x, y in ((xs, ys), (xs[::-1], ys[::-1])):
            result = footprint_polygon(x, y)
            assert result.is_valid and not result.is_empty
            assert result.geom_type == kind
            assert all(result.distance(Point(a, b)) < 1e-8 for a, b in zip(x, y))
            if kind == "MultiPolygon":
                assert len(result.geoms) == 2
                assert all(part.bounds[2] - part.bounds[0] < 5 for part in result.geoms)
            elif min(map(abs, lat)) == 89:
                assert result.covers(Point(0, np.sign(lat[0]) * 90))


def test_polar_projection_can_create_a_crossing_without_crossing_meridian():
    lon = [-64.2061, -118.6456, 54.8105, 33.8387]
    lat = [89.8194, 89.9085, 89.6184, 89.5878]
    assert not Polygon(zip(lon, lat)).is_valid
    corrected = footprint_polygon(lon, lat)
    assert corrected.is_valid
    assert corrected.area > 0 and len(corrected.exterior.coords) > 5
    assert all(corrected.covers(Point(x, y)) for x, y in zip(lon, lat))


def test_empty_and_degenerate_footprints():
    assert footprint_polygon([], []).is_empty
    assert not footprint_polygon([0] * 4, [0] * 4).is_valid


def test_triangle_containment_area():
    x, y = [0, 2, 0], [0, 0, 2]
    assert area_tri(x, y) == pytest.approx(2)
    assert area_triangle_and_point(x, y, 0.2, 0.2) == pytest.approx(2)
    assert area_triangle_and_point(x, y, 3, 3) > 2
