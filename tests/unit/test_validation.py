# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Validation and calibration on synthetic labels of known skill (MASTER_PLAN §4.3): the
AUC and its block-bootstrap interval, "no better than chance", too few labels, the
calibration refused below its threshold or without dry wells, and the domain rules."""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.validation import ValidationSettings
from subphora.domain.potential import ComponentId, PotentialEstimate, Variable
from subphora.domain.validation import (
    NO_BODY,
    CriterionTrial,
    DomainValidation,
    LabelDesign,
    NoCalibration,
    TrialOutcome,
    ValidationState,
)
from subphora.geo.grid import GridWindow
from subphora.model import (
    Category,
    Labelled,
    Quality,
    not_validated,
    probability_of,
    skill_of,
    validate_domain,
)
from subphora.model.validation import auc_gain, fit_logistic, weighted_auc
from subphora.services.validation import (
    NO_NATIONAL_MAP,
    Wells,
    admitted_grids,
    domain_validations,
    labelled_wells,
    skill_grid,
    validate_region,
)

SETTINGS = load_settings()
VALIDATION = SETTINGS.validation
MODEL = SETTINGS.model
WHEN = datetime(2026, 11, 26, tzinfo=UTC)
WITH_DRY = VALIDATION.model_copy(
    update={"labels": VALIDATION.labels.model_copy(update={"dry_kinds": ["Seco"]})}
)


def rng(seed: int = 1) -> np.random.Generator:
    return np.random.default_rng(seed)


def labelled(scores: np.ndarray, spread_m: float = 100_000) -> Labelled:
    """Points spread over many 10 km blocks, one score each."""
    generator = rng(len(scores))
    xy = generator.uniform(0, spread_m, size=(len(scores), 2))
    return Labelled.of(scores.tolist(), [tuple(p) for p in xy], VALIDATION.block_m)


def validate(
    productive: Labelled,
    negative: Labelled,
    settings: ValidationSettings = VALIDATION,
) -> DomainValidation:
    empty = Labelled.of([], [], settings.block_m)
    dry, background = (negative, empty) if settings.labels.dry_kinds else (empty, negative)
    return validate_domain("ES0", "Body (ES0)", productive, dry, background, settings, WHEN, rng())


# ── The AUC ────────────────────────────────────────────────────────────────────────────


def test_the_auc_ranks_and_counts_ties_as_half() -> None:
    high, low = np.array([0.8, 0.9]), np.array([0.1, 0.2])
    assert weighted_auc(high, low) == 1.0
    assert weighted_auc(low, high) == 0.0
    assert weighted_auc(np.array([0.5]), np.array([0.5])) == 0.5
    assert weighted_auc(np.array([0.5, 0.9]), np.array([0.5]), np.array([1.0, 3.0])) == 0.875
    assert np.isnan(weighted_auc(np.array([]), low))


def test_a_skilled_index_is_validated_with_an_interval_around_its_auc() -> None:
    generator = rng(7)
    productive = labelled(generator.normal(0.7, 0.1, 200))
    background = labelled(generator.normal(0.5, 0.1, 2000))
    result = validate(productive, background)
    assert result.state is ValidationState.VALIDATED
    assert result.design is LabelDesign.PRESENCE_BACKGROUND
    assert result.auc is not None
    # Two normals a distance d apart (sd s): AUC = Phi(d / (s sqrt 2)) = Phi(1.414) = 0.921.
    assert result.auc.value == pytest.approx(0.921, abs=0.03)
    assert result.auc.low < result.auc.value < result.auc.high
    assert result.auc.low > 0.5
    assert (result.productive, result.background, result.dry) == (200, 2000, 0)
    assert result.excluded_criteria == ("water_points",)
    # Without dry wells there is no calibration, and it says why.
    assert result.calibration is None
    assert result.no_calibration is NoCalibration.NO_DRY_LABELS


def test_an_index_at_chance_is_flagged_no_better_than_chance() -> None:
    generator = rng(3)
    productive = labelled(generator.uniform(0, 1, 150))
    background = labelled(generator.uniform(0, 1, 2000))
    result = validate(productive, background)
    assert result.state is ValidationState.NO_BETTER_THAN_CHANCE
    assert result.auc is not None
    assert result.auc.low <= 0.5 <= result.auc.high
    assert result.no_calibration is NoCalibration.NOT_VALIDATED
    assert skill_of(result, MODEL.confidence) == 0.0


def test_too_few_wells_or_blocks_measure_nothing() -> None:
    background = labelled(rng().uniform(0, 1, 500))
    few = validate(labelled(np.full(VALIDATION.minimum.productive - 1, 0.9)), background)
    assert few.state is ValidationState.NOT_ENOUGH_LABELS
    assert few.auc is None
    # Enough wells, but all in one block: neighbours are not independent evidence.
    clustered = validate(labelled(np.full(100, 0.9), spread_m=5_000), background)
    assert clustered.state is ValidationState.NOT_ENOUGH_LABELS
    assert clustered.blocks == 1
    assert skill_of(clustered, MODEL.confidence) is None


# ── Calibration ────────────────────────────────────────────────────────────────────────


def logistic_labels(count: int, seed: int) -> tuple[Labelled, Labelled]:
    """Wells whose chance of being productive is 1 / (1 + exp(-(-4 + 8 x)))."""
    generator = rng(seed)
    x = generator.uniform(0, 1, count)
    productive = generator.uniform(0, 1, count) < 1 / (1 + np.exp(-(-4 + 8 * x)))
    xy = generator.uniform(0, 200_000, size=(count, 2))
    block = VALIDATION.block_m
    return (
        Labelled.of(x[productive].tolist(), [tuple(p) for p in xy[productive]], block),
        Labelled.of(x[~productive].tolist(), [tuple(p) for p in xy[~productive]], block),
    )


def test_enough_dry_and_productive_wells_calibrate_the_index_into_a_probability() -> None:
    productive, dry = logistic_labels(1200, seed=11)
    result = validate(productive, dry, WITH_DRY)
    assert result.design is LabelDesign.PRESENCE_ABSENCE
    assert result.state is ValidationState.VALIDATED
    assert result.calibration is not None
    assert result.no_calibration is None
    assert result.calibration.slope == pytest.approx(8, rel=0.25)
    assert result.calibration.brier_out_of_fold < 0.25
    middle = probability_of(result, 0.5)
    assert middle is not None
    assert middle.value == pytest.approx(0.5, abs=0.08)
    assert middle.low < middle.value < middle.high
    assert middle.domain == "ES0"
    high = probability_of(result, 0.9)
    assert high is not None
    assert high.value > middle.value


def test_calibration_is_refused_below_its_threshold() -> None:
    productive, dry = logistic_labels(150, seed=5)
    assert min(productive.count, dry.count) < WITH_DRY.calibration.min_per_class
    result = validate(productive, dry, WITH_DRY)
    assert result.state is ValidationState.VALIDATED
    assert result.calibration is None
    assert result.no_calibration is NoCalibration.TOO_FEW_LABELS
    assert probability_of(result, 0.9) is None


def test_the_logistic_fit_recovers_known_coefficients_and_stays_finite_when_separable() -> None:
    x = np.linspace(0, 1, 2001)
    p = 1 / (1 + np.exp(-(-2 + 4 * x)))
    a, b = fit_logistic(
        np.concatenate((x, x)),
        np.concatenate((np.ones_like(x), np.zeros_like(x))),
        np.concatenate((p, 1 - p)),
    )
    assert (a, b) == (pytest.approx(-2, abs=0.01), pytest.approx(4, abs=0.01))
    separable = fit_logistic(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0.0, 0.0, 1.0, 1.0]))
    assert all(np.isfinite(separable))


# ── Skill in the confidence ────────────────────────────────────────────────────────────


def test_skill_rises_from_chance_to_full_and_is_unmeasured_without_a_validation() -> None:
    generator = rng(7)
    strong = validate(
        labelled(generator.normal(0.9, 0.05, 200)), labelled(generator.normal(0.3, 0.05, 2000))
    )
    assert skill_of(strong, MODEL.confidence) == 1.0
    unmeasured = not_validated(NO_BODY, "Outside", NO_NATIONAL_MAP)
    assert skill_of(unmeasured, MODEL.confidence) is None


# ── The region: labels, domains and the skill grid ─────────────────────────────────────


def _feature(x: float, y: float, **properties: Any) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [x, y]},
        "properties": properties,
    }


def test_only_wells_with_a_recorded_yield_are_productive_and_dry_kinds_are_dry() -> None:
    dataset = SETTINGS.national.datasets.water_points
    features = [
        _feature(1, 1, Naturaleza="Sondeo", Caudal_Referencia_L_s=3.0),
        _feature(2, 2, Naturaleza="POZO excavado", Caudal_Referencia_L_s=0.5),
        _feature(3, 3, Naturaleza="Sondeo", Caudal_Referencia_L_s=0.0),
        _feature(4, 4, Naturaleza="Manantial", Caudal_Referencia_L_s=9.0),
        _feature(5, 5, Naturaleza="Sondeo"),
        _feature(6, 6, Naturaleza="Sondeo seco"),
        {"type": "Feature", "geometry": None, "properties": {"Naturaleza": "Sondeo"}},
    ]
    assert labelled_wells(features, dataset, VALIDATION.labels) == Wells(
        productive=[(1.0, 1.0), (2.0, 2.0)], dry=[]
    )
    dry_too = labelled_wells(
        features, dataset, WITH_DRY.labels.model_copy(update={"dry_kinds": ["Sondeo seco"]})
    )
    assert dry_too.dry == [(6.0, 6.0)]


def test_a_region_validates_each_body_and_the_outside_and_draws_skill_where_measured() -> None:
    window = GridWindow(crs="EPSG:25830", cell_m=1000, west=0, north=100_000, width=100, height=100)
    columns = np.tile(np.arange(100), (100, 1)).astype(np.float32)
    # Body 0 in the west half, body 1 in the east; slope falls eastwards inside each half,
    # so the index rises from west to east within a body.
    body = np.where(columns < 50, 0.0, 1.0).astype(np.float32)
    slope = (30 - (columns % 50) * 0.6).astype(np.float32)
    grids = {
        Variable.SLOPE_DEG: slope,
        Variable.WATER_POINT_DISTANCE_M: np.full((100, 100), 100.0, dtype=np.float32),
        Variable.GROUNDWATER_BODY: body,
    }
    categories = {
        Variable.GROUNDWATER_BODY: [Category("ES0", "West (ES0)"), Category("ES1", "East (ES1)")]
    }
    # West: wells on the gentlest slopes (skilled). East: wells anywhere (chance).
    generator = rng(2)
    west = [
        (float(x), float(y))
        for x, y in zip(
            generator.uniform(45_000, 50_000, 80), generator.uniform(0, 100_000, 80), strict=True
        )
    ]
    east = [
        (float(x), float(y))
        for x, y in zip(
            generator.uniform(50_000, 100_000, 80), generator.uniform(0, 100_000, 80), strict=True
        )
    ]
    quality = {"slope": Quality(1.0, 1.0), "water_points": Quality(1.0, 1.0)}
    results, skill = validate_region(
        "box",
        window,
        grids,
        categories,
        MODEL,
        quality,
        Wells(productive=west + east, dry=[]),
        VALIDATION,
        WHEN,
    )
    by_domain = {r.domain: r for r in results}
    assert set(by_domain) == {"ES0", "ES1", NO_BODY}
    assert by_domain["ES0"].state is ValidationState.VALIDATED
    assert by_domain["ES1"].state is ValidationState.NO_BETTER_THAN_CHANCE
    assert by_domain[NO_BODY].state is ValidationState.NOT_ENOUGH_LABELS
    assert np.all(skill[:, :50] > 0)
    assert np.all(skill[:, 50:] == 0)
    # The same validations give the same skill grid elsewhere (the detailed map's).
    again = skill_grid(body, categories[Variable.GROUNDWATER_BODY], by_domain, MODEL)
    assert np.array_equal(again, skill)
    # The same build draws the same background: the result is reproducible.
    repeat, _ = validate_region(
        "box",
        window,
        grids,
        categories,
        MODEL,
        quality,
        Wells(productive=west + east, dry=[]),
        VALIDATION,
        WHEN,
    )
    assert repeat == results


def test_the_vegetation_enters_only_the_domains_where_it_improves_the_validation() -> None:
    window = GridWindow(crs="EPSG:25830", cell_m=1000, west=0, north=100_000, width=100, height=100)
    columns = np.tile(np.arange(100), (100, 1)).astype(np.float32)
    body = np.where(columns < 50, 0.0, 1.0).astype(np.float32)
    # The slope says nothing anywhere. In the west the wells sit in a strip that stays
    # green in late summer; in the east the vegetation is the same everywhere.
    vegetation = np.where(columns < 50, np.where(columns >= 40, 0.25, -0.1), 0.0)
    grids = {
        Variable.SLOPE_DEG: np.full((100, 100), 10.0, dtype=np.float32),
        Variable.WATER_POINT_DISTANCE_M: np.full((100, 100), 100.0, dtype=np.float32),
        Variable.GROUNDWATER_BODY: body,
        Variable.VEGETATION_ANOMALY: vegetation.astype(np.float32),
    }
    categories = {
        Variable.GROUNDWATER_BODY: [Category("ES0", "West (ES0)"), Category("ES1", "East (ES1)")]
    }
    generator = rng(3)
    west = list(
        zip(
            generator.uniform(40_000, 50_000, 80).tolist(),
            generator.uniform(0, 100_000, 80).tolist(),
            strict=True,
        )
    )
    east = list(
        zip(
            generator.uniform(50_000, 100_000, 80).tolist(),
            generator.uniform(0, 100_000, 80).tolist(),
            strict=True,
        )
    )
    quality = {name: Quality(1.0, 1.0) for name in ("slope", "water_points", "vegetation")}
    results, skill = validate_region(
        "box",
        window,
        grids,
        categories,
        MODEL,
        quality,
        Wells(productive=west + east, dry=[]),
        VALIDATION,
        WHEN,
    )
    by_domain = {r.domain: r for r in results}
    (west_trial,) = by_domain["ES0"].trials
    (east_trial,) = by_domain["ES1"].trials
    (outside_trial,) = by_domain[NO_BODY].trials
    assert west_trial.outcome is TrialOutcome.IMPROVES
    assert west_trial.gain_low is not None
    assert west_trial.gain_low > 0
    assert east_trial.outcome is TrialOutcome.NO_GAIN
    assert east_trial.gain == 0
    assert outside_trial.outcome is TrialOutcome.NOT_MEASURED
    assert by_domain["ES0"].admitted == {"vegetation"}
    assert by_domain["ES1"].admitted == frozenset()
    # The validation reported in the west is that of the model with the vegetation.
    assert by_domain["ES0"].state is ValidationState.VALIDATED
    final, tried = by_domain["ES0"].auc, west_trial.auc_with
    assert final is not None
    assert tried is not None
    assert final.value == pytest.approx(tried.value)
    assert by_domain["ES1"].auc == east_trial.auc_without
    assert np.all(skill[:, :50] > 0)
    admitted = admitted_grids(body, categories[Variable.GROUNDWATER_BODY], by_domain, MODEL)
    assert np.array_equal(admitted["vegetation"], columns < 50)
    # A model without the vegetation input tries nothing.
    del grids[Variable.VEGETATION_ANOMALY]
    plain, _ = validate_region(
        "box",
        window,
        grids,
        categories,
        MODEL,
        quality,
        Wells(productive=west + east, dry=[]),
        VALIDATION,
        WHEN,
    )
    assert all(r.trials == () for r in plain)


def test_the_paired_gain_scores_the_same_points_and_a_trial_states_it_consistently() -> None:
    generator = rng(5)
    productive = labelled(generator.normal(0.6, 0.1, 100))
    negative = labelled(generator.normal(0.5, 0.1, 500))
    gain, low, high = auc_gain((productive, negative), (productive, negative), VALIDATION, rng())
    assert gain == low == high == 0
    with pytest.raises(ValueError, match="same points"):
        auc_gain((productive, negative), (productive, productive), VALIDATION, rng())
    auc = _validated().auc
    assert auc is not None
    with pytest.raises(ValidationError, match="exactly when measured"):
        CriterionTrial(
            criterion="vegetation", outcome=TrialOutcome.NO_GAIN, auc_without=auc, auc_with=None
        )
    with pytest.raises(ValidationError, match="inside its interval"):
        CriterionTrial(
            criterion="vegetation",
            outcome=TrialOutcome.NO_GAIN,
            auc_without=auc,
            auc_with=auc,
            gain=0.2,
            gain_low=-0.1,
            gain_high=0.1,
        )
    unmeasured = CriterionTrial(
        criterion="vegetation", outcome=TrialOutcome.NOT_MEASURED, auc_without=None, auc_with=None
    )
    body = _validated().model_dump()
    twice = [unmeasured.model_dump()] * 2
    with pytest.raises(ValidationError, match="tried once"):
        DomainValidation.model_validate({**body, "trials": twice})


def test_a_domain_no_national_map_holds_is_not_validated_and_says_why() -> None:
    (body, outside) = domain_validations([Category("ES9", "Far (ES9)")], {})
    assert body.state is outside.state is ValidationState.NOT_VALIDATED
    assert body.labels_source == NO_NATIONAL_MAP
    assert (body.validated_at, body.design, body.auc) == (None, None, None)


# ── Domain rules ───────────────────────────────────────────────────────────────────────


def _validated() -> DomainValidation:
    generator = rng(7)
    return validate(
        labelled(generator.normal(0.7, 0.1, 200)), labelled(generator.normal(0.5, 0.1, 2000))
    )


def test_a_validation_states_its_figures_consistently() -> None:
    body = _validated().model_dump()
    with pytest.raises(ValidationError, match=r"above 0\.5"):
        DomainValidation.model_validate({**body, "auc": {**body["auc"], "low": 0.4}})
    with pytest.raises(ValidationError, match="AUC exists"):
        DomainValidation.model_validate({**body, "auc": None})
    with pytest.raises(ValidationError, match="calibrated or says why"):
        DomainValidation.model_validate({**body, "no_calibration": None})
    with pytest.raises(ValidationError, match="validation date"):
        DomainValidation.model_validate({**body, "validated_at": None})
    calibration = {
        "intercept": 0.0,
        "slope": 1.0,
        "bootstrap": [[0.0, 1.0], [0.1, 1.1]],
        "level": 0.95,
        "brier_out_of_fold": 0.2,
    }
    with pytest.raises(ValidationError, match="dry wells is calibrated"):
        DomainValidation.model_validate(
            {**body, "calibration": calibration, "no_calibration": None}
        )
    with pytest.raises(ValidationError, match="inside its interval"):
        DomainValidation.model_validate({**body, "auc": {**body["auc"], "value": 0.999}})


def test_an_estimate_carries_its_domain_and_measures_skill_only_where_validated() -> None:
    from tests.unit.test_model import BEST, explain

    estimate = explain(dict(BEST))
    body = estimate.model_dump()
    assert estimate.validation.state is ValidationState.NOT_VALIDATED
    body["validation"] = _validated().model_dump()
    with pytest.raises(ValidationError, match="skill is measured"):
        PotentialEstimate.model_validate(body)
    for component in body["confidence"]["components"]:
        if component["id"] == ComponentId.SKILL:
            component["measured"] = True
    assert PotentialEstimate.model_validate(body).validation.state is ValidationState.VALIDATED
    with pytest.raises(ValidationError, match="calibrated domain"):
        PotentialEstimate.model_validate(
            {
                **body,
                "kind": "probability",
                "probability": {
                    "value": 0.5,
                    "low": 0.4,
                    "high": 0.6,
                    "level": 0.95,
                    "domain": "ES0",
                },
            }
        )


def test_the_validation_settings_refuse_an_impossible_calibration() -> None:
    raw = VALIDATION.model_dump()
    with pytest.raises(ValidationError, match="below the validation's minimum"):
        ValidationSettings.model_validate({**raw, "calibration": {"min_per_class": 10, "folds": 5}})
    with pytest.raises(ValidationError, match="fold would be empty"):
        ValidationSettings.model_validate(
            {**raw, "calibration": {"min_per_class": 100, "folds": 9}}
        )
