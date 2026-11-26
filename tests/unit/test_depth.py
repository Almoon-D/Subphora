# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The depth to water and the drilling cost (MASTER_PLAN §4.3): the water table from one
groundwater body only, its uncertainty growing with distance, "unknown" and why, the karst
flag, and the cost in Decimal euros."""

import math
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.depth import CostRange, DrillingSettings
from subphora.domain.depth import DepthEstimate, DepthUnknown, DrillingCost, LevelsSource
from subphora.model import PiezometerPoint, depth_at, drilling_cost, water_table

SETTINGS = load_settings()
TABLE = SETTINGS.piezometry.water_table
SOURCE = LevelsSource(
    service_id="miteco-piezometry-db",
    publisher="MITECO",
    attribution="MITECO",
    file_name="basedatospiezometria.zip",
    sha256="0" * 64,
    imported_at=datetime(2026, 11, 26, tzinfo=UTC),
    levels_from=date(2020, 1, 1),
    levels_to=date(2024, 12, 31),
)
BODY = ("ES040MSBT000030607", "Sierra de Altomira")


def piezometer(x: float, level: float, body: str = BODY[0], spread: float = 1.0) -> PiezometerPoint:
    return PiezometerPoint(
        x=x,
        y=0.0,
        body=body,
        level_m=level,
        low_m=level - spread,
        high_m=level + spread,
        sources=(SOURCE.service_id,),
    )


def depth(
    points: list[PiezometerPoint],
    x: float = 0.0,
    ground: float = 700.0,
    body: tuple[str, str] | None = BODY,
    karst: bool = False,
    sources: dict[str, LevelsSource] | None = None,
    imported: bool = True,
) -> DepthEstimate:
    named = sources if sources is not None else ({SOURCE.service_id: SOURCE} if imported else None)
    return depth_at(x, 0.0, ground, body, points, TABLE, karst, named)


def test_the_water_table_weighs_the_nearer_piezometer_more() -> None:
    table = water_table(0, 0, *BODY, [piezometer(-1000, 600), piezometer(3000, 680)], TABLE)
    assert table is not None
    # Inverse squared distance: weights 1/1e6 and 1/9e6.
    assert table.elevation_m == pytest.approx((600 * 9 + 680) / 10)
    assert table.piezometers == 2
    assert table.nearest_m == 1000
    # Seasonal half-range 1 m, plus 2 m per km to the nearest piezometer.
    assert table.high_m - table.elevation_m == pytest.approx(1 + TABLE.growth_m_per_km * 1)


def test_uncertainty_grows_with_distance_and_ends_in_unknown() -> None:
    near = water_table(0, 0, *BODY, [piezometer(500, 600)], TABLE)
    far = water_table(0, 0, *BODY, [piezometer(4500, 600)], TABLE)
    assert near is not None
    assert far is not None
    assert far.high_m - far.low_m > near.high_m - near.low_m
    beyond = depth([piezometer(TABLE.max_distance_m + 1, 600)])
    assert beyond.state == "unknown"
    assert beyond.reason is DepthUnknown.NO_PIEZOMETER_NEARBY


def test_a_piezometer_of_another_body_is_never_used_however_near() -> None:
    other = piezometer(10, 690, body="ES040MSBT000030611")
    across = depth([other])
    assert across.state == "unknown"
    assert across.reason is DepthUnknown.NO_PIEZOMETER_NEARBY
    own = depth([other, piezometer(2000, 600)])
    assert own.water_table is not None
    assert own.water_table.elevation_m == 600
    assert own.water_table.body == BODY[0]


def test_a_piezometer_at_the_spot_gives_its_own_level() -> None:
    table = water_table(0, 0, *BODY, [piezometer(0.5, 640), piezometer(800, 600)], TABLE)
    assert table is not None
    assert (table.elevation_m, table.piezometers) == (640, 1)


def test_depth_is_ground_minus_water_table_with_its_range() -> None:
    result = depth([piezometer(1000, 600)])
    assert result.state == "estimated"
    assert result.depth_m == pytest.approx(100)
    assert result.low_m == pytest.approx(100 - 3)
    assert result.high_m == pytest.approx(100 + 3)
    assert result.ground_m == 700
    assert result.sources == (SOURCE,)
    assert not result.karst


def test_a_water_table_above_ground_reads_as_zero_depth() -> None:
    result = depth([piezometer(100, 710)], ground=700)
    assert (result.depth_m, result.low_m) == (0, 0)
    assert result.high_m is not None
    assert result.high_m < 1


def test_karst_is_flagged_on_an_estimate_and_on_an_unknown() -> None:
    assert depth([piezometer(1000, 600)], karst=True).karst
    assert depth([], karst=True).karst
    assert SETTINGS.piezometry.is_karst("CARBONATADAS-ALTA")
    assert not SETTINGS.piezometry.is_karst("DETRÍTICAS-ALTA")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"imported": False}, DepthUnknown.NOT_IMPORTED),
        ({"body": None}, DepthUnknown.OUTSIDE_BODIES),
        ({"ground": math.nan}, DepthUnknown.NO_GROUND_ELEVATION),
    ],
)
def test_an_unknown_depth_says_why(change: dict[str, object], reason: DepthUnknown) -> None:
    result = depth([piezometer(1000, 600)], **change)  # type: ignore[arg-type]
    assert (result.state, result.reason, result.depth_m) == ("unknown", reason, None)
    assert drilling_cost(result, SETTINGS.drilling) is None


def test_an_estimated_depth_has_every_figure_and_an_unknown_none() -> None:
    body = depth([piezometer(1000, 600)]).model_dump()
    with pytest.raises(ValidationError, match="every figure"):
        DepthEstimate.model_validate({**body, "sources": ()})
    with pytest.raises(ValidationError, match="inside its range"):
        DepthEstimate.model_validate({**body, "depth_m": 500})
    with pytest.raises(ValidationError, match="says why"):
        DepthEstimate.model_validate({"state": "unknown", "depth_m": 10})
    with pytest.raises(ValidationError, match="says why"):
        DepthEstimate.model_validate({"state": "unknown"})


# ── Cost ───────────────────────────────────────────────────────────────────────────────


def test_cost_is_metres_drilled_times_cost_per_metre_plus_fixed_costs_in_decimal() -> None:
    drilling = DrillingSettings(
        currency="EUR",
        per_metre=CostRange(low=Decimal("38.50"), high=Decimal("120")),
        fixed=CostRange(low=Decimal("350"), high=Decimal("3000")),
        below_water_table_m=20,
        source="test quotes",
        priced_on=date(2026, 11, 26),
    )
    result = depth([piezometer(1000, 600, spread=0.5)])
    cost = drilling_cost(result, drilling)
    assert cost is not None
    # Depth 97.5-102.5 m (half-range 0.5 + 2 m/km), plus 20 m below the water table.
    assert (cost.drilled_low_m, cost.drilled_high_m) == (Decimal("117.5"), Decimal("122.5"))
    # 117.5 x 38.50 + 350 = 4,873.75, rounded half up to the euro; 122.5 x 120 + 3,000.
    assert cost.low == Decimal("4874")
    assert cost.high == Decimal("17700")
    assert isinstance(cost.low, Decimal)
    assert cost.currency == "EUR"
    assert cost.source == "test quotes"


def test_the_default_prices_name_their_source_and_date() -> None:
    drilling = SETTINGS.drilling
    assert drilling.per_metre.low <= drilling.per_metre.high
    assert "VERIFY-LIVE(drilling-prices)" in drilling.source
    assert drilling.priced_on.year == 2026
    with pytest.raises(ValidationError, match="low must not exceed high"):
        CostRange(low=Decimal(2), high=Decimal(1))


def test_a_cost_range_is_ordered() -> None:
    cost = drilling_cost(depth([piezometer(1000, 600)]), SETTINGS.drilling)
    assert cost is not None
    with pytest.raises(ValidationError, match="at most"):
        DrillingCost.model_validate({**cost.model_dump(), "low": cost.high + 1})


def test_a_depth_names_only_the_sources_of_the_piezometers_it_used() -> None:
    basin = SOURCE.model_copy(update={"service_id": "chj-piezometry", "file_name": "F71.zip"})
    unused = SOURCE.model_copy(update={"service_id": "chguadiana-piezometry"})
    near = PiezometerPoint(
        x=500,
        y=0,
        body=BODY[0],
        level_m=600,
        low_m=599,
        high_m=601,
        sources=("miteco-piezometry-db", "chj-piezometry"),
    )
    far = PiezometerPoint(
        x=TABLE.max_distance_m + 10,
        y=0,
        body=BODY[0],
        level_m=600,
        low_m=599,
        high_m=601,
        sources=("chguadiana-piezometry",),
    )
    named = {s.service_id: s for s in (SOURCE, basin, unused)}
    result = depth([near, far], sources=named)
    assert result.sources == (SOURCE, basin)
    assert depth([], sources=named).sources == ()


def test_the_depth_grid_is_the_depth_at_every_cell() -> None:
    import numpy as np

    from subphora.model import depth_grid

    other = ("ES040MSBT000030608", "Otra")
    points = [
        piezometer(-1000, 600, spread=2.0),
        piezometer(3000, 680),
        piezometer(250, 640, body=other[0]),
        # Exactly at the maximum distance from the cell at x = -2000 (kept, as depth_at keeps it).
        piezometer(-2000 - TABLE.max_distance_m, 610),
        PiezometerPoint(
            x=500.0, y=0.5, body=BODY[0], level_m=650, low_m=649, high_m=651, sources=("x",)
        ),
    ]
    xs = np.array([[-2000.0, -1000.0, 0.0, 500.0, 20000.0, 0.0, 0.0]])
    ys = np.zeros_like(xs)
    ground = np.array([[700, 700, 690, 660, 700, np.nan, 700]], dtype=np.float32)
    # Codes into [BODY, other]: the last cell is outside every body, the one before has no
    # ground elevation.
    bodies = np.array([[0, 0, 0, 0, 0, 0, -1]], dtype=np.float32)
    grid = depth_grid(xs, ys, ground, bodies, [BODY[0], other[0]], points, TABLE)
    for column in range(xs.shape[1]):
        body = BODY if bodies[0, column] == 0 else None
        one = depth_at(
            float(xs[0, column]),
            0.0,
            float(ground[0, column]),
            body,
            points,
            TABLE,
            False,
            {SOURCE.service_id: SOURCE, "x": SOURCE},
        )
        figures = (grid.depth[0, column], grid.low[0, column], grid.high[0, column])
        if one.state == "estimated":
            assert figures == pytest.approx((one.depth_m, one.low_m, one.high_m), abs=1e-3)
        else:
            assert all(np.isnan(f) for f in figures)
    # The far cell, the cell without ground and the cell outside every body are unknown.
    assert np.isnan(grid.depth[0, 4:]).all()
    assert not np.isnan(grid.depth[0, :4]).any()
