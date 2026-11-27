# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The validation of a build region, per hydrogeological domain (MASTER_PLAN §4.3,
decision 0030), run inside the region's compute job.

- The labels are the region's IGME wells: productive with a recorded yield, dry where a
  configured kind says so. Each is scored by the cell it falls in.
- The index validated leaves out the criteria whose input is the labels themselves (the
  distance to water points), renormalising over the others, as the model does anywhere
  an input is missing.
- A domain is the groundwater body drawn at a cell, or the land outside every body. Each
  body of the region, and the outside, gets a validation: measured, or why not.
- The skill grid holds each measured domain's skill component; NaN elsewhere.
- A criterion admitted by validation (the late-summer vegetation anomaly) is tried in each
  domain with the same wells and background cells, and enters only the domains where it
  improves the AUC (``model/validation.py``).
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from subphora.config.model import ModelSettings
from subphora.config.national import WaterPointsDataset
from subphora.config.validation import LabelSettings, ValidationSettings
from subphora.domain.potential import Variable
from subphora.domain.validation import NO_BODY, CriterionTrial, DomainValidation
from subphora.geo.grid import GridWindow
from subphora.geo.raster import FloatGrid
from subphora.model.evaluate import ABSENT, Category, InputGrids, Quality, evaluate
from subphora.model.validation import (
    Labelled,
    auc_gain,
    not_validated,
    skill_of,
    trial,
    validate_domain,
)

# The label of the domain outside every groundwater body.
NO_BODY_LABEL = "Outside every groundwater body"
# Why a domain has no validation when no national map holds it.
NO_NATIONAL_MAP = "No national map holds this domain: run `subphora national build` for it."


@dataclass(frozen=True, slots=True)
class Wells:
    """The labelled wells of a window, in its CRS."""

    productive: list[tuple[float, float]]
    dry: list[tuple[float, float]]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def labelled_wells(
    features: Sequence[dict[str, Any]], dataset: WaterPointsDataset, labels: LabelSettings
) -> Wells:
    """The productive and dry wells among the water points."""
    productive: list[tuple[float, float]] = []
    dry: list[tuple[float, float]] = []
    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not (isinstance(coordinates, list) and len(coordinates) >= 2):
            continue
        kind = _text(properties.get(dataset.kind_field))
        position = (float(coordinates[0]), float(coordinates[1]))
        if labels.is_dry(kind):
            dry.append(position)
            continue
        flow = properties.get(labels.yield_field)
        if (
            labels.is_well(kind)
            and isinstance(flow, int | float)
            and flow > labels.productive_min_l_s
        ):
            productive.append(position)
    return Wells(productive=productive, dry=dry)


def domain_keys(categories: Sequence[Category]) -> list[tuple[str, str]]:
    """Every domain's key and label, once: the bodies' codes, then the outside."""
    seen: dict[str, str] = {}
    for category in categories:
        seen.setdefault(category.cls, category.label)
    return [*seen.items(), (NO_BODY, NO_BODY_LABEL)]


def domain_codes(body: FloatGrid, categories: Sequence[Category]) -> NDArray[np.int64]:
    """Each cell's domain as an index into ``domain_keys(categories)``."""
    keys = [key for key, _ in domain_keys(categories)]
    lookup = np.array([keys.index(c.cls) for c in categories] + [len(keys) - 1], dtype=np.int64)
    codes = np.nan_to_num(np.asarray(body, dtype=np.float64), nan=float(ABSENT)).astype(np.int64)
    valid = (codes >= 0) & (codes < len(categories))
    result: NDArray[np.int64] = lookup[np.where(valid, codes, len(categories))]
    return result


def _rng(settings: ValidationSettings, region_id: str) -> np.random.Generator:
    salt = int(hashlib.sha256(region_id.encode()).hexdigest()[:12], 16)
    return np.random.default_rng([settings.seed, salt])


def _scored(
    window: GridWindow, points: Sequence[tuple[float, float]], index: NDArray[np.float64]
) -> list[tuple[int, int, float, float]]:
    cells = []
    for x, y in points:
        cell = window.cell_of(x, y)
        if cell is not None and not np.isnan(index[cell]):
            cells.append((cell[0], cell[1], x, y))
    return cells


def _labelled(
    cells: Sequence[tuple[int, int, float, float]], scores: NDArray[np.float64], block_m: float
) -> Labelled:
    return Labelled.of(
        [float(scores[r, k]) for r, k, _, _ in cells], [(x, y) for _, _, x, y in cells], block_m
    )


@dataclass(frozen=True, slots=True)
class _DomainSample:
    """The labelled cells and background cells of one domain, scored by any index."""

    productive: list[tuple[int, int, float, float]]
    dry: list[tuple[int, int, float, float]]
    background: list[tuple[int, int, float, float]]

    def scored(
        self, index: NDArray[np.float64], block_m: float
    ) -> tuple[Labelled, Labelled, Labelled]:
        """The productive, dry and background points scored by ``index``."""
        return (
            _labelled(self.productive, index, block_m),
            _labelled(self.dry, index, block_m),
            _labelled(self.background, index, block_m),
        )


def validate_region(
    region_id: str,
    window: GridWindow,
    grids: Mapping[Variable, FloatGrid],
    categories: Mapping[Variable, Sequence[Category]],
    model: ModelSettings,
    quality: Mapping[str, Quality],
    wells: Wells,
    settings: ValidationSettings,
    validated_at: datetime,
) -> tuple[tuple[DomainValidation, ...], FloatGrid]:
    """Every domain's validation in the region, and its skill grid.

    Each criterion admitted by validation is tried in every domain against the model
    without it; the validation reported is that of the model with the criteria each domain
    admitted."""
    excluded = {c.variable for c in model.criteria if c.id in settings.labels.excluded_criteria}
    inputs = InputGrids(
        values={v: g for v, g in grids.items() if v not in excluded}, categories=categories
    )
    evidence = grids[Variable.WATER_POINT_DISTANCE_M]
    base = evaluate(model, inputs, quality, evidence).index
    tried = [c for c in model.gated if c.variable in inputs.values]
    everywhere = np.ones(base.shape, dtype=bool)
    with_index = {
        c.id: evaluate(model, inputs, quality, evidence, admitted={c.id: everywhere}).index
        for c in tried
    }
    body_categories = categories[Variable.GROUNDWATER_BODY]
    domains = domain_codes(grids[Variable.GROUNDWATER_BODY], body_categories)
    keys = domain_keys(body_categories)
    rng = _rng(settings, region_id)
    productive = _scored(window, wells.productive, base)
    dry = _scored(window, wells.dry, base)
    rows, columns = np.nonzero(~np.isnan(base))
    cell_domains = domains[rows, columns]
    with_dry = bool(settings.labels.dry_kinds)
    samples: list[_DomainSample] = []
    first: list[DomainValidation] = []
    trials: list[tuple[CriterionTrial, ...]] = []
    for code, (key, label) in enumerate(keys):
        inside = np.flatnonzero(cell_domains == code)
        if inside.size > settings.background_per_domain:
            inside = rng.choice(inside, size=settings.background_per_domain, replace=False)
        sample = _DomainSample(
            productive=[c for c in productive if domains[c[0], c[1]] == code],
            dry=[c for c in dry if domains[c[0], c[1]] == code],
            background=[
                (
                    r,
                    k,
                    window.west + (k + 0.5) * window.cell_m,
                    window.north - (r + 0.5) * window.cell_m,
                )
                for r, k in zip(rows[inside].tolist(), columns[inside].tolist(), strict=True)
            ],
        )
        samples.append(sample)
        scored = sample.scored(base, settings.block_m)
        without = validate_domain(key, label, *scored, settings, validated_at, rng)
        first.append(without)
        domain_trials = []
        for criterion in tried:
            scored_with = sample.scored(with_index[criterion.id], settings.block_m)
            with_ = validate_domain(key, label, *scored_with, settings, validated_at, rng)
            negative = 1 if with_dry else 2
            gain = (
                auc_gain(
                    (scored[0], scored[negative]),
                    (scored_with[0], scored_with[negative]),
                    settings,
                    rng,
                )
                if without.auc is not None and with_.auc is not None
                else None
            )
            domain_trials.append(
                trial(criterion.id, without, with_, gain, settings.trials.min_gain_low)
            )
        trials.append(tuple(domain_trials))
    admitted = {
        c.id: np.isin(
            domains,
            [
                code
                for code, t in enumerate(trials)
                if any(x.criterion == c.id and x.admitted for x in t)
            ],
        )
        for c in tried
    }
    final = evaluate(model, inputs, quality, evidence, admitted=admitted).index
    results = []
    skill = np.full(base.shape, np.nan, dtype=np.float32)
    for code, (key, label) in enumerate(keys):
        if any(t.admitted for t in trials[code]):
            result = validate_domain(
                key,
                label,
                *samples[code].scored(final, settings.block_m),
                settings,
                validated_at,
                rng,
            )
        else:
            result = first[code]
        result = result.model_copy(update={"trials": trials[code]})
        results.append(result)
        value = skill_of(result, model.confidence)
        if value is not None:
            skill[domains == code] = value
    return tuple(results), skill


def admitted_grids(
    body: FloatGrid,
    categories: Sequence[Category],
    validations: Mapping[str, DomainValidation],
    model: ModelSettings,
) -> dict[str, NDArray[np.bool_]]:
    """Per criterion admitted by validation, the cells of the domains that admitted it."""
    domains = domain_codes(body, categories)
    keys = domain_keys(categories)
    result = {}
    for criterion in model.gated:
        codes = [
            code
            for code, (key, _) in enumerate(keys)
            if key in validations and criterion.id in validations[key].admitted
        ]
        result[criterion.id] = np.isin(domains, codes)
    return result


def skill_grid(
    body: FloatGrid,
    categories: Sequence[Category],
    validations: Mapping[str, DomainValidation],
    model: ModelSettings,
) -> FloatGrid:
    """The skill grid from validations measured elsewhere (the national map's)."""
    domains = domain_codes(body, categories)
    skill = np.full(np.shape(body), np.nan, dtype=np.float32)
    for code, (key, _) in enumerate(domain_keys(categories)):
        validation = validations.get(key)
        value = None if validation is None else skill_of(validation, model.confidence)
        if value is not None:
            skill[domains == code] = value
    return skill


def domain_validations(
    categories: Sequence[Category], validations: Mapping[str, DomainValidation]
) -> tuple[DomainValidation, ...]:
    """One validation per domain of ``categories``: the one given, or "not validated"."""
    return tuple(
        validations.get(key) or not_validated(key, label, NO_NATIONAL_MAP)
        for key, label in domain_keys(categories)
    )
