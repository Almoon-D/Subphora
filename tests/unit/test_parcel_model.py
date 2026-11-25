# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The parcel scale's pieces on synthetic grids: candidates, the area's means, the
structural inputs (lineament density, nearest dip, distances to points), the map image,
the domain rules of hard rules 1 and 2, and what parcel.yaml refuses."""

import io
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.domain.layers import LayerDetail
from subphora.domain.legal import LegalState, LegalStatus
from subphora.domain.parcel_map import (
    AreaAnalysis,
    AreaSummary,
    Candidate,
    CriterionSummary,
    JobState,
    NoCandidates,
    ParcelFailure,
    ParcelJob,
)
from subphora.domain.parcels import LocalPoint
from subphora.domain.potential import InputSource, MissingInput, MissingReason, Variable
from subphora.geo.grid import GridWindow
from subphora.geo.raster import distance_to_points, line_density, nearest_value
from subphora.geo.render import overlay_image
from subphora.model import (
    InputGrids,
    Quality,
    area_means,
    confidence_of,
    evaluate,
    explain_cell,
    select_candidates,
)
from tests.unit.test_national_settings import edit, refused

SETTINGS = load_settings()
MODEL = SETTINGS.model
WHEN = datetime(2026, 11, 25, tzinfo=UTC)
SOURCE = InputSource(
    service_id="test",
    publisher="Test",
    attribution="Test",
    retrieved_at=WHEN,
    detail=LayerDetail(cell_m=5),
    resolution_m=5,
)
LEGAL = LegalStatus(
    state=LegalState.NOT_EVALUATED, source="not built", assessed_at=WHEN, disclaimer="Guidance"
)
WINDOW = GridWindow(crs="EPSG:25830", cell_m=10, west=0, north=1000, width=100, height=100)


# ── Candidates and means ───────────────────────────────────────────────────────────────


def test_candidates_are_the_best_confident_cells_apart() -> None:
    index = np.array([[0.9, 0.95, 0.1], [0.5, 0.8, 0.2], [0.7, np.nan, 0.6]])
    confidence = np.array([[0.5, 0.3, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]])
    inside = np.ones(index.shape, dtype=bool)
    inside[2, 0] = False
    chosen = select_candidates(index, confidence, inside, 10, 3, 0.4, 15)
    # 0.95 lacks confidence; 0.8 is 14 m from 0.9 and 0.5 is 10 m (closer than 15); 0.7 is
    # outside; 0.2 is 10 m from 0.6; 0.1 is 20 m from both chosen.
    assert chosen == [(0, 0), (2, 2), (0, 2)]
    # At least one cell apart: 0.8 qualifies once the separation allows it.
    assert select_candidates(index, confidence, inside, 10, 2, 0.4, 10) == [(0, 0), (1, 1)]
    assert select_candidates(index, confidence, inside, 10, 3, 0.99, 0) == []


def test_equal_indices_are_ordered_by_confidence_then_position() -> None:
    index = np.full((2, 2), 0.5)
    confidence = np.array([[0.5, 0.6], [0.6, 0.5]])
    inside = np.ones((2, 2), dtype=bool)
    assert select_candidates(index, confidence, inside, 5, 4, 0.0, 0) == [
        (0, 1),
        (1, 0),
        (0, 0),
        (1, 1),
    ]


def _grids(values: dict[Variable, Any], shape: tuple[int, int]) -> InputGrids:
    return InputGrids(
        values={
            v: np.broadcast_to(np.asarray(g, dtype=np.float64), shape) for v, g in values.items()
        },
        categories={},
    )


def test_the_area_means_add_up_like_a_cell() -> None:
    shape = (1, 3)
    values = {
        Variable.SLOPE_DEG: [1.0, 30.0, 1.0],
        Variable.TWI: [12.0, np.nan, 5.0],
        Variable.LINEAMENT_DENSITY: [5.0, 0.0, np.nan],
    }
    quality = dict.fromkeys(("slope", "wetness", "lineaments"), Quality(1.0, 1.0))
    evaluation = evaluate(MODEL, _grids(values, shape), quality, np.full(shape, 100.0))
    inside = np.array([[True, True, False]])
    means = area_means(MODEL, evaluation, inside)
    assert (means.cells, means.scored_cells) == (2, 2)
    assert means.mean_index == pytest.approx(float(np.mean(evaluation.index[0, :2])))
    assert sum(c.mean_contribution for c in means.criteria.values()) == pytest.approx(
        means.mean_index
    )
    assert sum(c.mean_share for c in means.criteria.values()) == pytest.approx(1)
    assert means.criteria["wetness"].present_share == 0.5
    assert means.criteria["slope"].present_share == 1.0
    assert set(means.criteria) == {"slope", "wetness", "lineaments"}
    confidence = confidence_of(means.components, MODEL.confidence)
    assert means.mean_confidence is not None
    assert confidence.value == pytest.approx(means.mean_confidence)
    nothing = area_means(MODEL, evaluation, np.zeros(shape, dtype=bool))
    assert (nothing.mean_index, nothing.mean_confidence, nothing.criteria) == (None, None, {})


def test_a_parcel_only_criterion_is_missing_where_its_grid_is_not_made() -> None:
    estimate = explain_cell(
        MODEL,
        {Variable.SLOPE_DEG: 1.0},
        {},
        {"slope": Quality(1.0, 1.0)},
        {"slope": SOURCE},
        100.0,
        {},
    )
    reasons = {m.criterion: m.reason for m in estimate.missing}
    assert reasons["lineaments"] is MissingReason.NO_DATASET
    assert reasons["bedding_dip"] is MissingReason.NO_DATASET
    with_dip = explain_cell(
        MODEL,
        {Variable.SLOPE_DEG: 1.0, Variable.BEDDING_DIP_DEG: float("nan")},
        {},
        {"slope": Quality(1.0, 1.0), "bedding_dip": Quality(1.0, 1.0)},
        {"slope": SOURCE, "bedding_dip": SOURCE},
        100.0,
        {},
    )
    assert {m.criterion: m.reason for m in with_dip.missing}["bedding_dip"] is MissingReason.NO_DATA


# ── Structural inputs and distances ────────────────────────────────────────────────────


def test_lineament_density_is_the_length_within_the_radius_per_km2() -> None:
    # A straight line 1 km long through the window's centre, north to south.
    line = [(500.0, 0.0), (500.0, 1000.0)]
    density = line_density(WINDOW, [line, [(1.0, 1.0)]], radius_m=200)
    centre = density[50, 50]
    # Within 200 m of the centre: 400 m of line over a disc of ~0.126 km².
    assert centre == pytest.approx(0.4 / (math.pi * 0.2**2), rel=0.05)
    assert density[50, 5] == pytest.approx(0, abs=1e-6)
    assert np.all(density >= 0)
    assert np.all(line_density(WINDOW, [], radius_m=200) == 0)


def test_the_nearest_dip_reaches_only_so_far() -> None:
    dips = nearest_value(WINDOW, [(105.0, 895.0), (900.0, 100.0)], [20.0, 60.0], 150)
    assert dips[10, 10] == 20
    assert dips[89, 89] == 60
    assert math.isnan(dips[50, 50])
    assert np.all(np.isnan(nearest_value(WINDOW, [], [], 150)))


def test_distances_to_points_reach_beyond_the_window_and_stop_at_the_cap() -> None:
    distance = distance_to_points(WINDOW, [(-1000.0, 995.0)], cap_m=5000)
    assert distance[0, 0] == pytest.approx(1005, abs=1)
    capped = distance_to_points(WINDOW, [(-1000.0, 995.0)], cap_m=500)
    assert np.all(capped == 500)
    assert np.all(distance_to_points(WINDOW, [], cap_m=700) == 700)


def test_the_map_image_lies_where_its_grid_does() -> None:
    data = np.full(WINDOW.shape, 0.5, dtype=np.float32)
    data[:10] = np.nan
    png, (west, south, east, north) = overlay_image(
        data, WINDOW.transform, "EPSG:25830", [0.2, 0.6], ["#000000", "#111111", "#222222"], 40
    )
    assert png is not None
    image = Image.open(io.BytesIO(png))
    assert max(image.size) == 40
    assert west < east
    assert south < north
    empty, _ = overlay_image(
        np.full(WINDOW.shape, np.nan, dtype=np.float32),
        WINDOW.transform,
        "EPSG:25830",
        [0.5],
        ["#000000", "#ffffff"],
        40,
    )
    assert empty is None


# ── Domain rules ───────────────────────────────────────────────────────────────────────


def _estimate() -> Any:
    return explain_cell(
        MODEL, {Variable.SLOPE_DEG: 1.0}, {}, {"slope": Quality(1, 1)}, {"slope": SOURCE}, 100, {}
    )


def _candidate(rank: int = 1, estimate: Any = None) -> Candidate:
    return Candidate(
        rank=rank,
        longitude=-3.7,
        latitude=40.4,
        local=LocalPoint(crs="EPSG:25830", x=0, y=0),
        estimate=estimate or _estimate(),
        legal=LEGAL,
    )


def test_a_legal_status_is_never_blank() -> None:
    assert LEGAL.reason is None
    with pytest.raises(ValidationError):
        LegalStatus(state=LegalState.NOT_EVALUATED, source="", assessed_at=WHEN, disclaimer="x")
    with pytest.raises(ValidationError, match="reason"):
        LegalStatus(state=LegalState.RULES_NOT_LOADED, source="x", assessed_at=WHEN, disclaimer="x")
    with pytest.raises(ValidationError, match="reason"):
        LegalStatus(
            state=LegalState.NOT_EVALUATED,
            source="x",
            assessed_at=WHEN,
            disclaimer="x",
            reason="none",
        )
    with pytest.raises(ValidationError):
        Candidate.model_validate({**_candidate().model_dump(), "legal": None})


def test_a_candidate_has_a_score() -> None:
    unscored = explain_cell(
        MODEL, {Variable.SLOPE_DEG: float("nan")}, {}, {"slope": Quality(1, 1)}, {}, 100, {}
    )
    with pytest.raises(ValidationError, match="score"):
        _candidate(estimate=unscored)


def _summary(**overrides: Any) -> AreaSummary:
    confidence = confidence_of(dict.fromkeys(MODEL.confidence.weights, 0.5), MODEL.confidence)
    fields: dict[str, Any] = {
        "cells": 2,
        "scored_cells": 2,
        "mean_index": 0.6,
        "mean_confidence": confidence,
        "contributions": (
            CriterionSummary(
                criterion="slope",
                weight=0.1,
                mean_share=1.0,
                mean_contribution=0.6,
                present_share=1.0,
                source=SOURCE,
            ),
        ),
        "missing": (MissingInput(criterion="soil", weight=0.07, reason=MissingReason.NO_DATA),),
    }
    return AreaSummary(**{**fields, **overrides})


def test_an_area_summary_adds_up() -> None:
    assert _summary().mean_index == 0.6
    with pytest.raises(ValidationError, match="sum of the mean contributions"):
        _summary(mean_index=0.7)
    with pytest.raises(ValidationError, match="exactly when a cell is scored"):
        _summary(scored_cells=0)
    with pytest.raises(ValidationError, match="more cells"):
        _summary(cells=1)
    with pytest.raises(ValidationError, match="once"):
        _summary(missing=(MissingInput(criterion="slope", weight=0.1, reason="no_data"),))
    empty = _summary(scored_cells=0, mean_index=None, mean_confidence=None, contributions=())
    assert empty.mean_index is None


def _analysis(**overrides: Any) -> AreaAnalysis:
    fields: dict[str, Any] = {
        "id": "0123456789abcdef",
        "label": None,
        "crs": "EPSG:25830",
        "cell_m": 5,
        "bbox": (-3.71, 40.41, -3.69, 40.43),
        "area_m2": 1000,
        "built_at": WHEN,
        "layers": (Variable.INDEX,),
        "summary": _summary(),
        "candidates": (_candidate(),),
        "no_candidates": None,
        "sources": {},
        "terrain_model": "MDT05",
    }
    return AreaAnalysis(**{**fields, **overrides})


def test_an_analysis_has_ranked_candidates_or_says_why_not() -> None:
    assert _analysis().candidates[0].rank == 1
    assert _analysis(candidates=(), no_candidates=NoCandidates.NO_SCORE).candidates == ()
    with pytest.raises(ValidationError, match="says why"):
        _analysis(candidates=())
    with pytest.raises(ValidationError, match="says why"):
        _analysis(no_candidates=NoCandidates.LOW_CONFIDENCE)
    with pytest.raises(ValidationError, match="ranked"):
        _analysis(candidates=(_candidate(rank=2),))


def test_a_job_is_consistent_with_its_state() -> None:
    done = ParcelJob(
        id="0123456789abcdef", state=JobState.DONE, poll_after_s=1, analysis=_analysis()
    )
    assert done.analysis is not None
    with pytest.raises(ValidationError, match="analysis"):
        ParcelJob(id="0123456789abcdef", state=JobState.DONE, poll_after_s=1)
    with pytest.raises(ValidationError, match="failure"):
        ParcelJob(id="0123456789abcdef", state=JobState.FAILED, poll_after_s=1)
    with pytest.raises(ValidationError, match="how a job ends"):
        ParcelJob(
            id="0123456789abcdef",
            state=JobState.FAILED,
            failure=ParcelFailure.TOO_LARGE,
            poll_after_s=1,
        )


# ── parcel.yaml ────────────────────────────────────────────────────────────────────────


def test_the_parcel_settings_load() -> None:
    parcel = SETTINGS.parcel
    assert parcel.faults.is_fault("Falla conocida")
    assert parcel.faults.is_fault("Cabalgamiento supuesto")
    assert not parcel.faults.is_fault("Contacto concordante")
    assert not parcel.faults.is_fault("Contacto mecánico por solifluxión")
    assert parcel.jobs.output_path(Path("/root")) == Path("/root/data/parcels")


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda d: d.update(buffer_m=1000), "last break of drainage"),
        (lambda d: d.update(water_points_radius_m=4000), "last break of water_points"),
        (lambda d: d.update(water_points_radius_m=9000), "evidence_none_beyond_m"),
        (lambda d: d["faults"].update(radius_m=5000), "must not exceed buffer_m"),
        (lambda d: d.update(layers=["nothing"]), "not national tile layers"),
        (lambda d: d.update(layers=["potential-index", "potential-index"]), "unique"),
        (lambda d: d["terrain"]["coverages"].pop("canaries"), "no coverage for the canaries"),
        (
            lambda d: d["terrain"]["coverages"].update(moon=d["terrain"]["coverages"]["canaries"]),
            "not national grids",
        ),
        (
            lambda d: d["terrain"]["coverages"]["canaries"].update(coverage="Elevacion4083_2"),
            "does not list",
        ),
        (lambda d: d["faults"].update(service="ign-mdt-wcs"), "not a rest"),
        (lambda d: d["bedding"].update(ageing="forever"), "ageing profile"),
    ],
)
def test_parcel_settings_refuse(config_dir: Path, change: Any, match: str) -> None:
    edit(config_dir, "parcel.yaml", change)
    refused(config_dir, match)
