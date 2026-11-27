# Copyright (c) 2026 Almoon-D. All rights reserved.
"""How well the model discriminates known wells in a hydrogeological domain, and its
calibration where one is allowed (MASTER_PLAN §4.3, validation and calibration).

A domain is a groundwater body, or the land outside every body. Its validation always has
an explicit state: validated, "no better than chance here", not enough labelled wells, or
not validated at all. A calibration, which turns the index into a probability, exists only
for a validated domain whose labels include recorded dry wells, in enough number; otherwise
the validation says why there is none and the score stays an index.
"""

import math
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel

_UNIT = Field(ge=0, le=1)
# The domain of the cells outside every groundwater body.
NO_BODY = "none"


class ValidationState(StrEnum):
    # The AUC interval's lower bound is above 0.5.
    VALIDATED = "validated"
    # Enough labels, but the interval reaches 0.5: "no better than chance here".
    NO_BETTER_THAN_CHANCE = "no_better_than_chance"
    # Too few labelled wells or spatial blocks to measure anything.
    NOT_ENOUGH_LABELS = "not_enough_labels"
    # Nothing measured it: no national map holds the domain.
    NOT_VALIDATED = "not_validated"


MEASURED = frozenset({ValidationState.VALIDATED, ValidationState.NO_BETTER_THAN_CHANCE})


class LabelDesign(StrEnum):
    # Productive wells against recorded dry ones.
    PRESENCE_ABSENCE = "presence_absence"
    # Productive wells against a sample of the domain's cells (no dry well recorded).
    PRESENCE_BACKGROUND = "presence_background"


class NoCalibration(StrEnum):
    """Why a domain's index is not turned into a probability."""

    NOT_VALIDATED = "not_validated"
    NO_DRY_LABELS = "no_dry_labels"
    TOO_FEW_LABELS = "too_few_labels"


class AucInterval(DomainModel):
    value: float = _UNIT
    low: float = _UNIT
    high: float = _UNIT
    # The interval's coverage, such as 0.95.
    level: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.low <= self.value <= self.high:
            raise ValueError("an AUC lies inside its interval")
        return self


class Calibration(DomainModel):
    """A logistic curve from index to probability, with the curves of its spatial block
    bootstrap for the interval, and its out-of-fold Brier score."""

    intercept: float
    slope: float
    bootstrap: tuple[tuple[float, float], ...] = Field(min_length=2)
    level: float = Field(gt=0, lt=1)
    brier_out_of_fold: float = _UNIT

    @model_validator(mode="after")
    def _finite(self) -> Self:
        numbers = [self.intercept, self.slope, *(v for pair in self.bootstrap for v in pair)]
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError("a calibration's coefficients are finite")
        return self


class TrialOutcome(StrEnum):
    """What the validation said about a criterion that enters only where it helps."""

    # The gain's interval lies above the configured minimum: the criterion enters here.
    IMPROVES = "improves"
    # Measured both ways, and the gain's interval reaches the minimum: it stays out.
    NO_GAIN = "no_gain"
    # Too few labelled wells to measure either way: it stays out.
    NOT_MEASURED = "not_measured"


class CriterionTrial(DomainModel):
    """A domain's validation with and without one criterion (the same wells, the same
    background cells), and the paired bootstrap interval of the AUC's gain."""

    criterion: str = Field(min_length=1)
    outcome: TrialOutcome
    auc_without: AucInterval | None
    auc_with: AucInterval | None
    # The gain (AUC with minus without) and its interval; None when not measured.
    gain: float | None = Field(default=None, ge=-1, le=1)
    gain_low: float | None = Field(default=None, ge=-1, le=1)
    gain_high: float | None = Field(default=None, ge=-1, le=1)

    @property
    def admitted(self) -> bool:
        return self.outcome is TrialOutcome.IMPROVES

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        measured = self.outcome is not TrialOutcome.NOT_MEASURED
        numbers = (self.auc_without, self.auc_with, self.gain, self.gain_low, self.gain_high)
        if any(n is None for n in numbers) == measured:
            raise ValueError("a trial has both AUCs and its gain exactly when measured")
        if (
            self.gain is not None
            and self.gain_low is not None
            and self.gain_high is not None
            and not self.gain_low <= self.gain <= self.gain_high
        ):
            raise ValueError("a gain lies inside its interval")
        return self


class DomainValidation(DomainModel):
    domain: str = Field(min_length=1)
    label: str = Field(min_length=1)
    state: ValidationState
    design: LabelDesign | None
    productive: int = Field(ge=0)
    dry: int = Field(ge=0)
    background: int = Field(ge=0)
    blocks: int = Field(ge=0)
    auc: AucInterval | None
    calibration: Calibration | None
    no_calibration: NoCalibration | None
    # The criteria left out of the index validated (its labels are their input).
    excluded_criteria: tuple[str, ...]
    # Where the labels come from, and when they were read; None when nothing was measured.
    labels_source: str = Field(min_length=1)
    validated_at: AwareDatetime | None
    # The criteria that enter only where validation shows they help: how each was tried
    # here. The AUC above is that of the model with the criteria admitted.
    trials: tuple[CriterionTrial, ...] = ()

    @property
    def admitted(self) -> frozenset[str]:
        """The criteria tried here that entered the model."""
        return frozenset(t.criterion for t in self.trials if t.admitted)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        state = self.state
        if (self.auc is not None) != (state in MEASURED):
            raise ValueError("an AUC exists exactly when the domain was measured")
        if self.auc is not None:
            if state is ValidationState.VALIDATED and self.auc.low <= 0.5:
                raise ValueError("a validated domain's interval lies above 0.5")
            if state is ValidationState.NO_BETTER_THAN_CHANCE and self.auc.low > 0.5:
                raise ValueError("'no better than chance' means the interval reaches 0.5")
        if (self.validated_at is None) != (state is ValidationState.NOT_VALIDATED):
            raise ValueError("a domain has a validation date exactly when it was validated")
        if (self.design is None) != (state is ValidationState.NOT_VALIDATED):
            raise ValueError("a design is stated exactly when the domain was validated")
        if (self.calibration is None) == (self.no_calibration is None):
            raise ValueError("a domain is calibrated or says why not")
        names = [t.criterion for t in self.trials]
        if len(set(names)) != len(names):
            raise ValueError("a criterion is tried once per domain")
        if self.calibration is not None and (
            state is not ValidationState.VALIDATED
            or self.design is not LabelDesign.PRESENCE_ABSENCE
        ):
            raise ValueError("only a validated domain with dry wells is calibrated")
        return self


class Probability(DomainModel):
    """The calibrated probability of a productive well at a cell, with its interval."""

    value: float = _UNIT
    low: float = _UNIT
    high: float = _UNIT
    level: float = Field(gt=0, lt=1)
    domain: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.low <= self.value <= self.high:
            raise ValueError("a probability lies inside its interval")
        return self
