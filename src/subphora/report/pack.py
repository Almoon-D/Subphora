# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The professional export pack (MASTER_PLAN §4.6): one ZIP with the PDF report, the GIS
layers (a GeoPackage and COGs, each with its CRS declared) and the tables as CSV.

``manifest.json`` lists every file, the CRS, and each part that is missing with its reason;
``LEEME.txt`` says the same in Spanish for whoever opens the folder. Photos and voice memos
go in only when the owner asks (``media``).
"""

import csv
import io
import json
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from subphora import __version__
from subphora.domain.parcel_map import AreaAnalysis
from subphora.report.catalogue import Catalogue
from subphora.services.export import FieldRecord, PackFiles, ReportData

type Row = Sequence[str | int | float | None]


def _csv(header: Sequence[str], rows: Iterable[Row]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(["" if v is None else v for v in row] for row in rows)
    # With a byte-order mark, spreadsheets read the accents right.
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _candidates(analysis: AreaAnalysis) -> bytes:
    header = (
        "rank",
        "x",
        "y",
        "longitude",
        "latitude",
        "kind",
        "index",
        "confidence",
        "confidence_label",
        "probability",
        "depth_state",
        "depth_unknown_reason",
        "depth_m",
        "depth_low_m",
        "depth_high_m",
        "karst",
        "cost_low_eur",
        "cost_high_eur",
        "legal_state",
        "authority",
        "district",
        "groundwater_body",
        "water_point_m",
    )
    rows = []
    for c in analysis.candidates:
        e, d, cost, legal = c.estimate, c.depth, c.cost, c.legal
        rows.append(
            (
                c.rank,
                c.local.x,
                c.local.y,
                c.longitude,
                c.latitude,
                e.kind,
                e.score,
                e.confidence.value,
                e.confidence.label.value,
                None if e.probability is None else e.probability.value,
                d.state,
                None if d.reason is None else d.reason.value,
                d.depth_m,
                d.low_m,
                d.high_m,
                str(d.karst).lower(),
                None if cost is None else str(cost.low),
                None if cost is None else str(cost.high),
                legal.state.value,
                None if legal.authority is None else legal.authority.name,
                None if legal.authority is None else legal.authority.district,
                None if legal.body is None else legal.body.code,
                c.site.water_point.metres,
            )
        )
    return _csv(header, rows)


def _contributions(analysis: AreaAnalysis) -> bytes:
    header = (
        "rank",
        "criterion",
        "status",
        "value",
        "unit",
        "suitability",
        "weight",
        "share",
        "contribution",
        "service",
        "retrieved_at",
    )
    rows: list[Row] = []
    for c in analysis.candidates:
        for x in c.estimate.contributions:
            v = x.value
            value = v.number if v.number is not None else (v.category if v.category else "absent")
            rows.append(
                (
                    c.rank,
                    x.criterion,
                    "present",
                    value,
                    v.unit,
                    x.suitability,
                    x.weight,
                    x.share,
                    x.contribution,
                    x.source.service_id,
                    x.source.retrieved_at.isoformat(),
                )
            )
        for m in c.estimate.missing:
            rows.append(
                (c.rank, m.criterion, m.reason.value, None, None, None, m.weight, 0, 0, None, None)
            )
    return _csv(header, rows)


def _sources(data: ReportData) -> bytes:
    header = (
        "dataset",
        "service",
        "publisher",
        "attribution",
        "retrieved_at",
        "scale_denominator",
        "cell_m",
        "edition",
        "licence",
        "terms_url",
    )
    rows = []
    for dataset, s in data.analysis.sources.items():
        service = data.services.get(s.service_id)
        rows.append(
            (
                dataset,
                s.service_id,
                s.publisher,
                s.attribution,
                s.retrieved_at.isoformat(),
                s.detail.scale_denominator,
                s.detail.cell_m,
                s.detail.edition,
                None if service is None else service.licence,
                None if service is None else service.terms_url,
            )
        )
    return _csv(header, rows)


def _observations(records: Sequence[FieldRecord]) -> bytes:
    header = (
        "id",
        "kind",
        "recorded_at",
        "longitude",
        "latitude",
        "x",
        "y",
        "accuracy_m",
        "text",
        "target_area",
        "target_rank",
        "track_id",
        "media_type",
    )
    rows = []
    for r in records:
        o, fix = r.observation, r.observation.position
        rows.append(
            (
                o.id,
                o.kind.value,
                o.recorded_at.isoformat(),
                None if fix is None else fix.longitude,
                None if fix is None else fix.latitude,
                None if r.local is None else r.local[0],
                None if r.local is None else r.local[1],
                None if fix is None else fix.accuracy_m,
                o.text,
                None if o.target is None else o.target.area_id,
                None if o.target is None else o.target.rank,
                o.track_id,
                None if o.media is None else o.media.content_type,
            )
        )
    return _csv(header, rows)


def _readme(data: ReportData, files: Sequence[str], layers: PackFiles, c: Catalogue) -> bytes:
    a = data.analysis
    crs = c.lookup(f"crs.{a.crs}", a.crs)
    lines = [
        c.t("pack.readme.title", id=a.id),
        c.t("pack.readme.generated", date=c.moment(data.generated_at)),
        c.t("pack.readme.crs", crs=crs, code=a.crs),
        "",
        c.t("pack.readme.files"),
        *(f"- {name}: {c.lookup(f'pack.file.{_kind(name)}', name)}" for name in files),
    ]
    if layers.missing:
        lines += ["", c.t("pack.readme.missing")]
        lines += [f"- {c.t(f'pack.missing.{m.value}')}" for m in layers.missing]
    lines += ["", c.t("national.kindNote"), c.t("detailed.disclaimer"), ""]
    return "\r\n".join(lines).encode("utf-8")


def _kind(name: str) -> str:
    if name.startswith("media/"):
        return "media"
    return Path(name).stem


def build_pack(
    data: ReportData, pdf: bytes, layers: PackFiles, catalogue: Catalogue, target: Path
) -> None:
    """Write the pack's ZIP to ``target``. Blocks."""
    a = data.analysis
    tables = {
        "candidates.csv": _candidates(a),
        "contributions.csv": _contributions(a),
        "sources.csv": _sources(data),
        "observations.csv": _observations(data.records),
    }
    names = ["report.pdf", *(n for n, _ in layers.files), *tables]
    manifest = {
        "area_id": a.id,
        "label": a.label,
        "crs": a.crs,
        "cell_m": a.cell_m,
        "built_at": a.built_at.isoformat(),
        "generated_at": data.generated_at.isoformat(),
        "subphora": __version__,
        "kind": "index",
        "files": [*names, "LEEME.txt"],
        "missing": [m.value for m in layers.missing],
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as pack:
        pack.writestr("report.pdf", pdf)
        for name, path in layers.files:
            pack.write(path, name)
        for name, content in tables.items():
            pack.writestr(name, content)
        pack.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        pack.writestr("LEEME.txt", _readme(data, [*names, "manifest.json"], layers, catalogue))


__all__ = ["build_pack"]
