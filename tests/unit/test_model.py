# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The water-potential model on synthetic grids: suitability, the renormalised index,
confidence, the explanation of a cell, and the domain rules of hard rule 1."""

import math
from datetime import UTC, datetime

import numpy as np
import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.model import ModelSettings
from subphora.domain.layers import LayerDetail
from subphora.domain.potential import (
    DISTANCES,
    ComponentId,
    Confidence,
    ConfidenceComponent,
    ConfidenceLabel,
    InputSource,
    InputValue,
    MissingReason,
    PotentialEstimate,
    Variable,
)
from subphora.model import (
    Category,
    InputGrids,
    Quality,
    dataset_quality,
    evaluate,
    explain_cell,
    not_validated,
)
from subphora.model.evaluate import ABSENT, label, suitability
from subphora.model.quality import age_fit, ground_resolution_m

MODEL: ModelSettings = load_settings().model
PERFECT = Quality(resolution=1.0, age=1.0)
QUALITY = {c.id: PERFECT for c in MODEL.criteria if c.variable is not None}
PERMEABILITY = [Category("ALTA", "CARBONATADAS-ALTA"), Category("BAJA", "DETRÍTICAS-BAJA")]
STATUS = [Category("Bueno", "Body A (ES000)"), Category("Malo", "Body B (ES001)")]
CATEGORIES = {Variable.PERMEABILITY_CLASS: PERMEABILITY, Variable.GROUNDWATER_STATUS: STATUS}
SOURCE = InputSource(
    service_id="test",
    publisher="Test",
    attribution="Test",
    retrieved_at=datetime(2026, 11, 25, tzinfo=UTC),
    detail=LayerDetail(cell_m=25),
    resolution_m=25,
)
SOURCES = {c.id: SOURCE for c in MODEL.criteria if c.variable is not None}
UNVALIDATED = not_validated("none", "Outside every groundwater body", "No national map.")
# Every input at a value whose suitability is 1 in the default lookups.
BEST: dict[Variable, float] = {
    Variable.PERMEABILITY_CLASS: 0.0,  # ALTA is 0.8, see below
    Variable.SLOPE_DEG: 1.0,
    Variable.TWI: 12.0,
    Variable.DRAINAGE_DISTANCE_M: 100.0,
    Variable.CLAY_PCT: 5.0,
    Variable.GROUNDWATER_STATUS: 0.0,
    Variable.WATER_POINT_DISTANCE_M: 100.0,
}


def grids(values: dict[Variable, float], shape: tuple[int, int] = (2, 2)) -> InputGrids:
    return InputGrids(
        values={v: np.full(shape, value, dtype=np.float32) for v, value in values.items()},
        categories=CATEGORIES,
    )


def weight(criterion_id: str) -> float:
    return MODEL.criterion(criterion_id).weight


def test_breaks_lookup_counts_the_breaks_at_or_below_and_keeps_missing_missing() -> None:
    slope = MODEL.criterion("slope")
    values = np.array([0.0, 2.0, 4.9, 5.0, 25.0, np.nan])
    result = suitability(slope, values)
    assert result[:5].tolist() == [1.0, 0.8, 0.8, 0.6, 0.15]
    assert math.isnan(result[5])


def test_classes_lookup_reads_the_category_and_the_absent_value() -> None:
    bodies = MODEL.criterion("groundwater_body")
    codes = np.array([0.0, 1.0, ABSENT, np.nan, 7.0])
    result = suitability(bodies, codes, STATUS)
    assert result[:3].tolist() == [1.0, 0.6, 0.3]
    # No data, and a code outside the category list, are missing: never guessed.
    assert math.isnan(result[3])
    assert math.isnan(result[4])


def test_an_absent_feature_is_missing_where_the_lookup_says_so() -> None:
    permeability = MODEL.criterion("permeability")
    assert math.isnan(suitability(permeability, np.array([ABSENT]), PERMEABILITY)[0])


def test_a_category_the_lookup_does_not_list_is_missing() -> None:
    bodies = MODEL.criterion("groundwater_body")
    unknown = [Category("Sin evaluar", "Body C")]
    assert math.isnan(suitability(bodies, np.array([0.0]), unknown)[0])


def test_all_inputs_present_give_the_weighted_mean_and_the_present_share() -> None:
    result = evaluate(MODEL, grids(BEST), QUALITY, np.full((2, 2), 100.0))
    # The national inputs: the faults and dips of the parcel scale are missing here.
    present = sum(c.weight for c in MODEL.criteria if c.variable in BEST)
    expected = (present - weight("permeability") * (1 - 0.8)) / present
    assert np.allclose(result.index, expected)
    assert np.allclose(result.components[ComponentId.COVERAGE], present)
    assert np.allclose(result.components[ComponentId.SKILL], MODEL.confidence.skill_not_measured)


def test_weights_are_renormalised_over_the_inputs_present() -> None:
    values = dict(BEST)
    values[Variable.SLOPE_DEG] = float("nan")
    values[Variable.CLAY_PCT] = float("nan")
    values[Variable.PERMEABILITY_CLASS] = 1.0  # BAJA: 0.3
    result = evaluate(MODEL, grids(values), QUALITY, np.full((2, 2), 100.0))
    present = [c for c in MODEL.criteria if c.variable in BEST and c.id not in {"slope", "soil"}]
    total = sum(c.weight for c in present)
    expected = (total - weight("permeability") * (1 - 0.3)) / total
    assert np.allclose(result.index, expected)
    assert np.allclose(result.components[ComponentId.COVERAGE], total)


def test_missing_inputs_lower_confidence_and_none_gives_no_index() -> None:
    full = evaluate(MODEL, grids(BEST), QUALITY, np.full((2, 2), 100.0))
    partial_values = dict(BEST)
    partial_values[Variable.PERMEABILITY_CLASS] = float("nan")
    partial = evaluate(MODEL, grids(partial_values), QUALITY, np.full((2, 2), 100.0))
    none = evaluate(
        MODEL, grids(dict.fromkeys(BEST, float("nan"))), QUALITY, np.full((2, 2), np.nan)
    )
    assert np.all(partial.confidence < full.confidence)
    assert np.all(np.isnan(none.index))
    assert np.all(np.isnan(none.confidence))
    assert np.allclose(none.components[ComponentId.COVERAGE], 0.0)


def test_evidence_falls_linearly_between_its_distances() -> None:
    settings = MODEL.confidence
    distances = np.array(
        [0.0, settings.evidence_full_within_m, 5500.0, settings.evidence_none_beyond_m, np.nan]
    )
    result = evaluate(MODEL, grids(BEST, shape=(5,)), QUALITY, distances).components[
        ComponentId.EVIDENCE
    ]
    assert result.tolist() == pytest.approx([1.0, 1.0, 0.5, 0.0, 0.0])


def test_confidence_labels_follow_the_thresholds() -> None:
    settings = MODEL.confidence
    assert label(settings.thresholds.high, settings) is ConfidenceLabel.HIGH
    assert label(settings.thresholds.medium, settings) is ConfidenceLabel.MEDIUM
    assert label(settings.thresholds.medium - 0.01, settings) is ConfidenceLabel.LOW


def test_quality_from_the_stated_detail_and_unknown_is_never_good() -> None:
    ageing = MODEL.confidence.ageing["geology"]
    unknown = MODEL.confidence.unknown_value
    assert ground_resolution_m(LayerDetail(scale_denominator=200_000), 0.0005) == 100
    assert ground_resolution_m(LayerDetail(cell_m=250), 0.0005) == 250
    assert ground_resolution_m(LayerDetail(), 0.0005) is None
    assert dataset_quality(LayerDetail(cell_m=250), 100, 0.0005, 2026, ageing, unknown) == Quality(
        resolution=0.4, age=unknown
    )
    assert dataset_quality(LayerDetail(), 100, 0.0005, 2026, ageing, unknown).resolution == unknown
    assert age_fit(2020, 2026, ageing, unknown) == 1.0
    halfway = round((ageing.full_years + ageing.zero_years) / 2)
    assert age_fit(2026 - halfway, 2026, ageing, unknown) == pytest.approx(0.5, abs=0.02)
    assert age_fit(1900, 2026, ageing, unknown) == 0.0


def explain(values: dict[Variable, float], evidence: float = 100.0) -> PotentialEstimate:
    caps = dict.fromkeys(DISTANCES, 10_000.0)
    return explain_cell(MODEL, values, CATEGORIES, QUALITY, SOURCES, evidence, caps, UNVALIDATED)


def test_the_explanation_of_a_cell_matches_the_grid() -> None:
    values = dict(BEST)
    values[Variable.CLAY_PCT] = float("nan")
    estimate = explain(values)
    grid = evaluate(MODEL, grids(values, shape=(1,)), QUALITY, np.array([100.0]))
    assert estimate.kind == "index"
    assert estimate.score == pytest.approx(float(grid.index[0]))
    assert estimate.confidence.value == pytest.approx(float(grid.confidence[0]))
    assert {m.criterion: m.reason for m in estimate.missing} == {
        "lineaments": MissingReason.NO_DATASET,
        "bedding_dip": MissingReason.NO_DATASET,
        "piezometric_depth": MissingReason.NO_DATASET,
        "soil": MissingReason.NO_DATA,
    }
    permeability = next(c for c in estimate.contributions if c.criterion == "permeability")
    assert permeability.value == InputValue(category="ALTA", label="CARBONATADAS-ALTA")
    assert permeability.source == SOURCE
    skill = next(c for c in estimate.confidence.components if c.id is ComponentId.SKILL)
    assert not skill.measured


def test_the_explanation_says_absent_and_at_least() -> None:
    values = dict(BEST)
    values[Variable.GROUNDWATER_STATUS] = float(ABSENT)
    values[Variable.WATER_POINT_DISTANCE_M] = 10_000.0
    estimate = explain(values, evidence=10_000.0)
    by_id = {c.criterion: c for c in estimate.contributions}
    assert by_id["groundwater_body"].value == InputValue(absent=True)
    assert by_id["water_points"].value == InputValue(number=10_000.0, unit="m", at_least=True)


def test_no_input_gives_an_estimate_without_score_but_with_confidence() -> None:
    estimate = explain(dict.fromkeys(BEST, float("nan")), evidence=float("nan"))
    assert estimate.score is None
    assert estimate.contributions == ()
    assert len(estimate.missing) == len(MODEL.criteria)
    assert estimate.confidence.label is ConfidenceLabel.LOW


# ── Hard rule 1: the domain refuses an incomplete or mislabelled estimate ───────────────


def complete() -> PotentialEstimate:
    return explain(dict(BEST))


def test_an_estimate_is_a_probability_only_with_one() -> None:
    body = complete().model_dump()
    body["kind"] = "probability"
    with pytest.raises(ValidationError):
        PotentialEstimate.model_validate(body)


def test_an_estimate_needs_its_confidence() -> None:
    body = complete().model_dump()
    del body["confidence"]
    with pytest.raises(ValidationError):
        PotentialEstimate.model_validate(body)


def test_an_estimate_needs_each_input_source() -> None:
    body = complete().model_dump()
    del body["contributions"][0]["source"]
    with pytest.raises(ValidationError):
        PotentialEstimate.model_validate(body)


def test_a_score_must_be_the_sum_of_its_contributions() -> None:
    body = complete().model_dump()
    body["score"] = 0.01
    with pytest.raises(ValidationError, match="sum of the contributions"):
        PotentialEstimate.model_validate(body)


def test_a_criterion_is_not_both_present_and_missing() -> None:
    body = complete().model_dump()
    body["missing"] = [*body["missing"], {"criterion": "slope", "weight": 0.1, "reason": "no_data"}]
    with pytest.raises(ValidationError, match="present or missing"):
        PotentialEstimate.model_validate(body)


def test_shares_must_add_up_to_one() -> None:
    body = complete().model_dump()
    body["contributions"] = body["contributions"][:2]
    with pytest.raises(ValidationError):
        PotentialEstimate.model_validate(body)


def test_a_score_needs_an_input_and_an_input_a_score() -> None:
    body = complete().model_dump()
    body["score"] = None
    with pytest.raises(ValidationError, match="exactly when"):
        PotentialEstimate.model_validate(body)


def test_an_estimate_names_its_criteria() -> None:
    body = complete().model_dump()
    body.update(score=None, contributions=[], missing=[])
    with pytest.raises(ValidationError, match="names its criteria"):
        PotentialEstimate.model_validate(body)


def test_confidence_must_hold_every_component_and_add_up() -> None:
    components = complete().confidence.components
    with pytest.raises(ValidationError, match="each of its components"):
        Confidence(value=0.5, label=ConfidenceLabel.MEDIUM, components=components[:-1])
    with pytest.raises(ValidationError, match="weighted sum"):
        Confidence(value=0.99, label=ConfidenceLabel.HIGH, components=components)
    heavy = (
        ConfidenceComponent(id=components[0].id, weight=0.9, value=0.0, measured=True),
        *components[1:],
    )
    with pytest.raises(ValidationError, match="add up to 1"):
        Confidence(value=0.0, label=ConfidenceLabel.LOW, components=heavy)


def test_a_contribution_is_share_times_suitability() -> None:
    body = complete().model_dump()
    body["contributions"][0]["contribution"] = 0.99
    with pytest.raises(ValidationError, match="share x suitability"):
        PotentialEstimate.model_validate(body)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"number": 1.0, "category": "x"},
        {"category": "x", "unit": "m"},
        {"number": float("inf"), "unit": "m"},
    ],
)
def test_an_input_value_is_one_thing(value: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        InputValue.model_validate(value)
