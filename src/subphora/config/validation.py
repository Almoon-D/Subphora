# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/validation.yaml``: the labelled wells, spatial blocks,
bootstrap and thresholds of the model's validation and calibration (MASTER_PLAN §4.3)."""

from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section


class LabelSettings(Section):
    yield_field: str = Field(min_length=1)
    productive_min_l_s: float = Field(ge=0)
    well_kinds: list[str] = Field(min_length=1)
    dry_kinds: list[str]
    source: str = Field(min_length=1)
    excluded_criteria: list[str]

    @staticmethod
    def _starts(kind: str, kinds: list[str]) -> bool:
        lowered = kind.strip().lower()
        return any(lowered.startswith(k.lower()) for k in kinds)

    def is_well(self, kind: str) -> bool:
        return self._starts(kind, self.well_kinds)

    def is_dry(self, kind: str) -> bool:
        return bool(self.dry_kinds) and self._starts(kind, self.dry_kinds)


class BootstrapSettings(Section):
    samples: int = Field(ge=20)
    level: float = Field(gt=0, lt=1)


class MinimumLabels(Section):
    productive: PositiveInt
    dry: PositiveInt
    blocks: int = Field(ge=2)


class CalibrationSettings(Section):
    min_per_class: PositiveInt
    folds: int = Field(ge=2)


class TrialSettings(Section):
    """How a criterion admitted by validation is tried (model.yaml ``admission``)."""

    # It enters a domain only where the lower bound of the gain's interval (AUC with it
    # minus AUC without it) is above this.
    min_gain_low: float = Field(ge=0, lt=1)


class ValidationSettings(Section):
    labels: LabelSettings
    block_m: PositiveFloat
    background_per_domain: PositiveInt
    seed: int = Field(ge=0)
    bootstrap: BootstrapSettings
    minimum: MinimumLabels
    calibration: CalibrationSettings
    trials: TrialSettings

    @model_validator(mode="after")
    def _calibration_above_minimum(self) -> Self:
        if self.calibration.min_per_class < max(self.minimum.productive, self.minimum.dry):
            raise ValueError("calibration.min_per_class is below the validation's minimum")
        if self.calibration.folds > self.minimum.blocks:
            raise ValueError("calibration.folds exceeds minimum.blocks: a fold would be empty")
        return self
