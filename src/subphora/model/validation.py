# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Validation of the index against labelled wells, per hydrogeological domain, and its
calibration where allowed (MASTER_PLAN §4.3, decision 0030).

- The AUC is the chance that a productive well's cell scores above a dry well's (or,
  without dry wells, above a random cell of the domain), ties counting half.
- Its interval is a percentile bootstrap over spatial blocks: whole blocks are resampled,
  so wells that share their geology are never split between "seen" and "unseen".
- The index has no fitted parameter, so cross-validation over blocks applies to the
  calibration: a logistic curve fitted on the other folds predicts each fold, and its
  out-of-fold Brier score is reported; the interval of a probability comes from the
  curves of the block bootstrap.
- A domain without enough labels is "not enough labels"; one whose interval reaches 0.5
  is "no better than chance here". Nothing is ever filled in.
- A criterion that enters only where it helps is tried per domain: the same wells and
  background cells are scored with and without it, and the gain in AUC gets a paired
  interval from the same block resamples. It enters only where that interval's lower
  bound is above the configured minimum.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import ConfidenceSettings
from subphora.config.validation import ValidationSettings
from subphora.domain.validation import (
    MEASURED,
    AucInterval,
    Calibration,
    CriterionTrial,
    DomainValidation,
    LabelDesign,
    NoCalibration,
    Probability,
    TrialOutcome,
    ValidationState,
)

type Floats = NDArray[np.float64]
type Ints = NDArray[np.int64]

# Logistic fitting: Newton steps, and a small ridge that keeps a separable set finite.
_NEWTON_STEPS = 50
_RIDGE = 1e-6
_CONVERGED = 1e-10


@dataclass(frozen=True, slots=True)
class Labelled:
    """Scored points of one class: their index and their spatial block."""

    scores: Floats
    blocks: Ints

    @classmethod
    def of(
        cls, scores: Sequence[float], xy: Sequence[tuple[float, float]], block_m: float
    ) -> Labelled:
        return cls(
            scores=np.asarray(scores, dtype=np.float64),
            blocks=block_ids(np.asarray(xy, dtype=np.float64).reshape(-1, 2), block_m),
        )

    @property
    def count(self) -> int:
        return int(self.scores.size)


def block_ids(xy: Floats, block_m: float) -> Ints:
    """One integer per square block of side ``block_m`` holding each point."""
    cells = np.floor(xy / block_m).astype(np.int64)
    # Cantor-free pairing: the grid of Spain is far smaller than 2**31 blocks a side.
    return cells[:, 0] * (1 << 31) + cells[:, 1]


def weighted_auc(
    positive: Floats,
    negative: Floats,
    w_positive: Floats | None = None,
    w_negative: Floats | None = None,
) -> float:
    """P(positive > negative) + P(tie) / 2, with optional weights; NaN without either."""
    wp = np.ones_like(positive) if w_positive is None else w_positive
    wn = np.ones_like(negative) if w_negative is None else w_negative
    total_p, total_n = float(wp.sum()), float(wn.sum())
    if total_p <= 0 or total_n <= 0:
        return math.nan
    order = np.argsort(negative, kind="stable")
    sorted_n = negative[order]
    cumulative = np.concatenate(([0.0], np.cumsum(wn[order])))
    below = cumulative[np.searchsorted(sorted_n, positive, side="left")]
    at_or_below = cumulative[np.searchsorted(sorted_n, positive, side="right")]
    wins = below + (at_or_below - below) / 2
    return float((wp * wins).sum() / (total_p * total_n))


def _block_weights(rng: np.random.Generator, blocks: Ints, *classes: Labelled) -> list[Floats]:
    """Resample the blocks with replacement: each point weighs its block's draws."""
    drawn = rng.choice(blocks, size=blocks.size, replace=True)
    unique, counts = np.unique(drawn, return_counts=True)
    weights = []
    for labelled in classes:
        index = np.searchsorted(unique, labelled.blocks)
        index = np.clip(index, 0, max(unique.size - 1, 0))
        hit = unique[index] == labelled.blocks
        weights.append(np.where(hit, counts[index], 0).astype(np.float64))
    return weights


def auc_interval(
    positive: Labelled, negative: Labelled, settings: ValidationSettings, rng: np.random.Generator
) -> AucInterval:
    blocks = np.unique(np.concatenate((positive.blocks, negative.blocks)))
    value = weighted_auc(positive.scores, negative.scores)
    estimates = []
    for _ in range(settings.bootstrap.samples):
        wp, wn = _block_weights(rng, blocks, positive, negative)
        estimate = weighted_auc(positive.scores, negative.scores, wp, wn)
        if not math.isnan(estimate):
            estimates.append(estimate)
    tail = (1 - settings.bootstrap.level) / 2
    low, high = (
        (float(q) for q in np.quantile(estimates, [tail, 1 - tail]))
        if estimates
        else (value, value)
    )
    return AucInterval(
        value=value, low=min(low, value), high=max(high, value), level=settings.bootstrap.level
    )


def auc_gain(
    without: tuple[Labelled, Labelled],
    with_: tuple[Labelled, Labelled],
    settings: ValidationSettings,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    """The AUC with a criterion minus the AUC without it, over the same positive and
    negative points (each pair's points in the same order and blocks), and the interval of
    a paired percentile bootstrap: each resample of blocks weighs both scorings alike."""
    positive_a, negative_a = without
    positive_b, negative_b = with_
    if positive_a.count != positive_b.count or negative_a.count != negative_b.count:
        raise ValueError("a paired gain scores the same points twice")
    gain = weighted_auc(positive_b.scores, negative_b.scores) - weighted_auc(
        positive_a.scores, negative_a.scores
    )
    blocks = np.unique(np.concatenate((positive_a.blocks, negative_a.blocks)))
    estimates = []
    for _ in range(settings.bootstrap.samples):
        wp, wn = _block_weights(rng, blocks, positive_a, negative_a)
        a = weighted_auc(positive_a.scores, negative_a.scores, wp, wn)
        b = weighted_auc(positive_b.scores, negative_b.scores, wp, wn)
        if not (math.isnan(a) or math.isnan(b)):
            estimates.append(b - a)
    tail = (1 - settings.bootstrap.level) / 2
    low, high = (
        (float(q) for q in np.quantile(estimates, [tail, 1 - tail])) if estimates else (gain, gain)
    )
    return gain, min(low, gain), max(high, gain)


def trial(
    criterion: str,
    without: DomainValidation,
    with_: DomainValidation,
    gain: tuple[float, float, float] | None,
    min_gain_low: float,
) -> CriterionTrial:
    """How a criterion fared in a domain: it enters only where both validations were
    measured and the gain's interval lies above ``min_gain_low``."""
    if without.auc is None or with_.auc is None or gain is None:
        return CriterionTrial(
            criterion=criterion, outcome=TrialOutcome.NOT_MEASURED, auc_without=None, auc_with=None
        )
    value, low, high = gain
    return CriterionTrial(
        criterion=criterion,
        outcome=TrialOutcome.IMPROVES if low > min_gain_low else TrialOutcome.NO_GAIN,
        auc_without=without.auc,
        auc_with=with_.auc,
        gain=value,
        gain_low=low,
        gain_high=high,
    )


def _sigmoid(z: Floats) -> Floats:
    result: Floats = 1 / (1 + np.exp(-np.clip(z, -500, 500)))
    return result


def fit_logistic(x: Floats, y: Floats, weights: Floats | None = None) -> tuple[float, float]:
    """Intercept and slope of P(y=1) = 1 / (1 + exp(-(a + b x))), by Newton's method."""
    w = np.ones_like(x) if weights is None else weights
    design = np.column_stack((np.ones_like(x), x))
    beta = np.zeros(2)
    for _ in range(_NEWTON_STEPS):
        p = _sigmoid(design @ beta)
        gradient = design.T @ (w * (y - p)) - _RIDGE * beta
        hessian = (design * (w * p * (1 - p))[:, None]).T @ design + _RIDGE * np.eye(2)
        step = np.linalg.solve(hessian, gradient)
        beta = beta + step
        if float(np.abs(step).max()) < _CONVERGED:
            break
    return float(beta[0]), float(beta[1])


def calibrate(
    productive: Labelled,
    dry: Labelled,
    settings: ValidationSettings,
    rng: np.random.Generator,
) -> Calibration:
    """The logistic calibration, its out-of-fold Brier score over block folds, and the
    curves of its block bootstrap."""
    x = np.concatenate((productive.scores, dry.scores))
    y = np.concatenate((np.ones(productive.count), np.zeros(dry.count)))
    blocks = np.concatenate((productive.blocks, dry.blocks))
    unique = np.unique(blocks)
    fold_of_block = np.empty(unique.size, dtype=np.int64)
    fold_of_block[rng.permutation(unique.size)] = (
        np.arange(unique.size) % settings.calibration.folds
    )
    folds = fold_of_block[np.searchsorted(unique, blocks)]
    predicted = np.empty_like(x)
    for fold in range(settings.calibration.folds):
        held = folds == fold
        a, b = fit_logistic(x[~held], y[~held])
        predicted[held] = _sigmoid(a + b * x[held])
    brier = float(np.mean((predicted - y) ** 2))
    intercept, slope = fit_logistic(x, y)
    both = Labelled(scores=x, blocks=blocks)
    curves = []
    for _ in range(settings.bootstrap.samples):
        (weights,) = _block_weights(rng, unique, both)
        positive = float((weights * y).sum())
        if positive <= 0 or positive >= float(weights.sum()):
            continue
        curves.append(fit_logistic(x, y, weights))
    return Calibration(
        intercept=intercept,
        slope=slope,
        bootstrap=tuple(curves),
        level=settings.bootstrap.level,
        brier_out_of_fold=min(1.0, brier),
    )


def not_validated(domain: str, label: str, reason: str) -> DomainValidation:
    """The explicit state of a domain nothing measured; ``reason`` says why."""
    return DomainValidation(
        domain=domain,
        label=label,
        state=ValidationState.NOT_VALIDATED,
        design=None,
        productive=0,
        dry=0,
        background=0,
        blocks=0,
        auc=None,
        calibration=None,
        no_calibration=NoCalibration.NOT_VALIDATED,
        excluded_criteria=(),
        labels_source=reason,
        validated_at=None,
    )


def validate_domain(
    domain: str,
    label: str,
    productive: Labelled,
    dry: Labelled,
    background: Labelled,
    settings: ValidationSettings,
    validated_at: datetime,
    rng: np.random.Generator,
    *,
    dry_labels: bool | None = None,
    labels_source: str | None = None,
    excluded_criteria: tuple[str, ...] | None = None,
) -> DomainValidation:
    """One domain's validation from its scored labels (``dry`` is used only when the
    settings name dry kinds, or ``dry_labels`` says the labels hold dry wells;
    ``background`` otherwise). Labels other than the public wells name their own source
    and the criteria left out of the index they grade."""
    with_dry = bool(settings.labels.dry_kinds) if dry_labels is None else dry_labels
    design = LabelDesign.PRESENCE_ABSENCE if with_dry else LabelDesign.PRESENCE_BACKGROUND
    negative = dry if with_dry else background
    minimum = settings.minimum
    blocks = int(np.unique(productive.blocks).size)
    enough = (
        productive.count >= minimum.productive
        and blocks >= minimum.blocks
        and negative.count >= (minimum.dry if with_dry else 1)
    )
    auc = auc_interval(productive, negative, settings, rng) if enough else None
    if auc is None:
        state = ValidationState.NOT_ENOUGH_LABELS
    elif auc.low > 0.5:
        state = ValidationState.VALIDATED
    else:
        state = ValidationState.NO_BETTER_THAN_CHANCE
    calibration = None
    if state is not ValidationState.VALIDATED:
        reason: NoCalibration | None = NoCalibration.NOT_VALIDATED
    elif not with_dry:
        reason = NoCalibration.NO_DRY_LABELS
    elif min(productive.count, dry.count) < settings.calibration.min_per_class:
        reason = NoCalibration.TOO_FEW_LABELS
    else:
        calibration = calibrate(productive, dry, settings, rng)
        reason = None
    return DomainValidation(
        domain=domain,
        label=label,
        state=state,
        design=design,
        productive=productive.count,
        dry=dry.count if with_dry else 0,
        background=0 if with_dry else background.count,
        blocks=blocks,
        auc=auc,
        calibration=calibration,
        no_calibration=reason,
        excluded_criteria=(
            tuple(settings.labels.excluded_criteria)
            if excluded_criteria is None
            else excluded_criteria
        ),
        labels_source=settings.labels.source if labels_source is None else labels_source,
        validated_at=validated_at,
    )


def skill_of(validation: DomainValidation, settings: ConfidenceSettings) -> float | None:
    """The confidence's skill component in a domain: 0 at or below chance, rising to 1
    where the AUC interval's lower bound reaches ``skill_full_at_auc``; None where the
    domain was not measured."""
    if validation.state not in MEASURED or validation.auc is None:
        return None
    span = settings.skill_full_at_auc - 0.5
    return float(min(1.0, max(0.0, (validation.auc.low - 0.5) / span)))


def probabilities(calibration: Calibration, scores: Floats) -> Floats:
    """The calibrated probability at each score (NaN stays NaN)."""
    return _sigmoid(calibration.intercept + calibration.slope * np.asarray(scores, np.float64))


def probability_of(validation: DomainValidation, score: float) -> Probability | None:
    """The calibrated probability at a score, with its bootstrap interval; None where the
    domain is not calibrated."""
    calibration = validation.calibration
    if calibration is None:
        return None
    value = float(_sigmoid(np.array([calibration.intercept + calibration.slope * score]))[0])
    curves = np.asarray(calibration.bootstrap, dtype=np.float64)
    spread = _sigmoid(curves[:, 0] + curves[:, 1] * score)
    tail = (1 - calibration.level) / 2
    low, high = (float(q) for q in np.quantile(spread, [tail, 1 - tail]))
    return Probability(
        value=value,
        low=min(low, value),
        high=max(high, value),
        level=calibration.level,
        domain=validation.domain,
    )
