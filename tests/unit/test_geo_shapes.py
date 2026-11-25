# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Drawn and published outlines: geodesic area, a point inside, simple rings."""

import pytest

from subphora.geo import ShapeError, check_simple_ring, geodesic_area_m2, point_inside

# A square of 0.01° near Daimiel: about 864 m east-west by 1,112 m north-south.
SQUARE = ((-3.62, 39.06), (-3.61, 39.06), (-3.61, 39.07), (-3.62, 39.07), (-3.62, 39.06))
HOLE = ((-3.616, 39.064), (-3.614, 39.064), (-3.614, 39.066), (-3.616, 39.066), (-3.616, 39.064))
# A U shape whose centroid lies outside it.
U_SHAPE = (
    (0.0, 40.0),
    (3.0, 40.0),
    (3.0, 43.0),
    (2.0, 43.0),
    (2.0, 41.0),
    (1.0, 41.0),
    (1.0, 43.0),
    (0.0, 43.0),
    (0.0, 40.0),
)


def test_the_geodesic_area_of_a_square_and_its_hole() -> None:
    area = geodesic_area_m2([(SQUARE,)])
    assert area == pytest.approx(864_000 * 1.112, rel=0.01)
    holed = geodesic_area_m2([(SQUARE, HOLE)])
    assert area - holed == pytest.approx(geodesic_area_m2([(HOLE,)]))
    # The orientation of the ring does not matter.
    assert geodesic_area_m2([(tuple(reversed(SQUARE)),)]) == pytest.approx(area)


def test_a_point_inside_is_the_centroid_when_it_lies_inside() -> None:
    assert point_inside([(SQUARE,)]) == pytest.approx((-3.615, 39.065))


def test_a_point_inside_a_concave_outline_is_a_vertex() -> None:
    assert point_inside([(U_SHAPE,)]) == U_SHAPE[0]


def test_the_largest_polygon_gives_the_point() -> None:
    small = tuple((lon + 1, lat) for lon, lat in HOLE)
    assert point_inside([(small,), (SQUARE,)]) == pytest.approx((-3.615, 39.065))


def test_simple_rings_pass() -> None:
    check_simple_ring(SQUARE)
    check_simple_ring(U_SHAPE)


@pytest.mark.parametrize(
    ("ring", "message"),
    [
        (SQUARE[:-1], "closed ring"),
        (SQUARE[:2] + SQUARE[:1], "closed ring"),
        (((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)), "twice"),
        (((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (0.0, 0.0)), "no area"),
        # A bow tie: two sides cross.
        (((0.0, 0.0), (2.0, 2.0), (2.0, 0.0), (0.0, 1.0), (0.0, 0.0)), "cross"),
        # A side that runs back along another.
        (((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)), "cross"),
    ],
)
def test_rings_that_are_not_simple(ring: tuple[tuple[float, float], ...], message: str) -> None:
    with pytest.raises(ShapeError, match=message):
        check_simple_ring(ring)
