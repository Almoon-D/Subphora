# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The detailed potential map of one area of interest (MASTER_PLAN §4.3, parcel scale).

A job computes it on demand; its result is an ``AreaAnalysis``: where the grid is, the
area's summary (mean index and confidence, with what forms them, and the validation of
each hydrogeological domain it touches), and the ranked candidate spots, each a full
estimate with its legal status (hard rules 1 and 2), its depth to water and drilling cost
or an explicit "unknown".
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from subphora.domain import DomainModel
from subphora.domain.depth import DepthEstimate, DrillingCost
from subphora.domain.legal import LegalStatus
from subphora.domain.parcels import LocalPoint
from subphora.domain.potential import (
    Confidence,
    InputSource,
    MissingInput,
    PotentialEstimate,
    Variable,
)
from subphora.domain.validation import DomainValidation

_TOLERANCE = 1e-4
_UNIT = Field(ge=0, le=1)


class Candidate(DomainModel):
    """A spot of the area worth a closer look: a cell with a high index and enough
    confidence, with everything that explains it."""

    rank: int = Field(ge=1)
    longitude: float
    latitude: float
    local: LocalPoint
    estimate: PotentialEstimate
    legal: LegalStatus
    depth: DepthEstimate
    # The cost of drilling to that depth; exactly when the depth is estimated.
    cost: DrillingCost | None

    @model_validator(mode="after")
    def _scored(self) -> Self:
        if self.estimate.score is None:
            raise ValueError("a candidate has a score")
        if (self.cost is not None) != (self.depth.state == "estimated"):
            raise ValueError("a candidate has a cost exactly when its depth is estimated")
        return self


class NoCandidates(StrEnum):
    """Why an area has no candidate spot."""

    # No cell of the area has a score.
    NO_SCORE = "no_score"
    # Cells have a score, but none reaches the minimum confidence.
    LOW_CONFIDENCE = "low_confidence"


class CriterionSummary(DomainModel):
    """A criterion over the scored cells of an area: its mean share of the weight (zero
    where its input is missing), its mean contribution, and the share of the cells where
    its input is present."""

    criterion: str
    weight: float = Field(gt=0, le=1)
    mean_share: float = _UNIT
    mean_contribution: float = _UNIT
    present_share: float = Field(gt=0, le=1)
    source: InputSource


class AreaSummary(DomainModel):
    """The area's mean index and confidence and what forms them (hard rule 1)."""

    kind: Literal["index"] = "index"
    # The cells inside the area, and those with a score.
    cells: int = Field(ge=0)
    scored_cells: int = Field(ge=0)
    mean_index: float | None = _UNIT
    mean_confidence: Confidence | None
    contributions: tuple[CriterionSummary, ...]
    # Criteria whose input is present at no cell of the area.
    missing: tuple[MissingInput, ...]
    # The validation of each hydrogeological domain with a cell in the area.
    validation: tuple[DomainValidation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.scored_cells > self.cells:
            raise ValueError("more cells scored than the area holds")
        scored = self.scored_cells > 0
        if (self.mean_index is not None) != scored or (self.mean_confidence is not None) != scored:
            raise ValueError("a mean index and confidence exist exactly when a cell is scored")
        if bool(self.contributions) != scored:
            raise ValueError("contributions exist exactly when a cell is scored")
        names = [c.criterion for c in self.contributions] + [m.criterion for m in self.missing]
        if not names or len(set(names)) != len(names):
            raise ValueError("each criterion is present or missing, once")
        domains = [v.domain for v in self.validation]
        if len(set(domains)) != len(domains):
            raise ValueError("each domain is validated once")
        if self.mean_index is not None:
            if abs(sum(c.mean_share for c in self.contributions) - 1) > _TOLERANCE:
                raise ValueError("the mean shares must add up to 1")
            total = sum(c.mean_contribution for c in self.contributions)
            if abs(self.mean_index - total) > _TOLERANCE:
                raise ValueError("the mean index must be the sum of the mean contributions")
        return self


class AreaAnalysis(DomainModel):
    """The detailed map of one area: its grid, summary and candidates."""

    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    # The area's own name, as the search found it (None for a drawn polygon).
    label: str | None
    # The CRS and cell of the grid (the area's local UTM zone, or REGCAN95 in the Canaries).
    crs: str
    cell_m: float = Field(gt=0)
    # The grid's corners in degrees (west, south, east, north), area and buffer.
    bbox: tuple[float, float, float, float]
    # In square metres: the area's outline, or the disc analysed around a point.
    area_m2: float = Field(gt=0)
    built_at: AwareDatetime
    # The variables published as map layers at the grid's resolution.
    layers: tuple[Variable, ...]
    summary: AreaSummary
    candidates: tuple[Candidate, ...]
    no_candidates: NoCandidates | None
    # Every input read, per dataset: where and when.
    sources: dict[str, InputSource]
    # The terrain model read (MDT05 until MDT02's download is verified).
    terrain_model: str = Field(min_length=1)

    @model_validator(mode="after")
    def _candidates(self) -> Self:
        if bool(self.candidates) == (self.no_candidates is not None):
            raise ValueError("an area has candidates or says why it has none")
        ranks = [c.rank for c in self.candidates]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("candidates are ranked 1, 2, 3…")
        return self


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ParcelFailure(StrEnum):
    """Why a detailed map is refused, failed, or cannot answer. Each has its own status."""

    INVALID_AREA = "invalid_area"
    TOO_LARGE = "too_large"
    OUTSIDE_COVERAGE = "outside_coverage"
    UNKNOWN_JOB = "unknown_job"
    NOT_READY = "not_ready"
    OUTSIDE_GRID = "outside_grid"
    UNKNOWN_LAYER = "unknown_layer"
    UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    COMPUTING_FAILED = "computing_failed"
    UNREADABLE = "unreadable"


# The failures a job ends in; the others refuse a request.
JOB_FAILURES = frozenset(
    {ParcelFailure.UPSTREAM_ERROR, ParcelFailure.UPSTREAM_TIMEOUT, ParcelFailure.COMPUTING_FAILED}
)


class ParcelJob(DomainModel):
    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    state: JobState
    failure: ParcelFailure | None = None
    detail: str | None = None
    # When to ask again while the job is queued or running.
    poll_after_s: float = Field(gt=0)
    analysis: AreaAnalysis | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.analysis is not None) != (self.state is JobState.DONE):
            raise ValueError("a job has its analysis exactly when it is done")
        if (self.failure is not None) != (self.state is JobState.FAILED):
            raise ValueError("a job has a failure exactly when it failed")
        if self.failure is not None and self.failure not in JOB_FAILURES:
            raise ValueError(f"{self.failure} is not how a job ends")
        return self


class ParcelExplanation(DomainModel):
    """``GET /api/parcel/{id}/explain``: the detailed map's estimate at a tapped point."""

    longitude: float
    latitude: float
    area_id: str
    cell_m: float = Field(gt=0)
    built_at: AwareDatetime
    estimate: PotentialEstimate


class ParcelError(Exception):
    def __init__(self, failure: ParcelFailure, detail: str) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
