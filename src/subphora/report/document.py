# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The per-area PDF report (MASTER_PLAN §4.6): what a hydrogeologist or the water authority
needs to judge the detailed map.

Its sections, in order: the area and how it was computed; the area's mean index with its
confidence and what forms it; the index and confidence maps; every candidate spot with its
score, confidence, explanation, depth, cost and legal status; the model's measured skill;
the field records; every source with its date and attribution; the limitations; and the
legal disclaimer. Every score is shown with its confidence and named an index (hard rule
1); what is missing is written as missing, with the reason, never left blank.

The HTML is built here and printed by WeasyPrint, which may load nothing but the images
embedded in it: the report calls no service (hard rule 4).
"""

import base64
from collections.abc import Iterable, Sequence
from html import escape
from importlib import resources

from weasyprint import CSS, HTML, URLFetcher

from subphora.config import ReportSettings
from subphora.domain.depth import DepthEstimate, DrillingCost, LevelsSource
from subphora.domain.legal import Finding, LegalState, LegalStatus, RuleSource
from subphora.domain.parcel_map import AreaAnalysis, Candidate
from subphora.domain.potential import Confidence, InputValue, PotentialEstimate
from subphora.domain.validation import MEASURED, DomainValidation
from subphora.report.catalogue import Catalogue
from subphora.services.export import FieldRecord, MapFigure, ReportData

# Scale-bar lengths tried, in metres: the longest under a quarter of the map's width.
_SCALE_STEPS = (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000)
_OUTCOME_ORDER = ("blocks", "authorisation", "check", "notice", "clear", "not_applicable")


def fetcher() -> URLFetcher:
    """The only fetcher the report has: embedded ``data:`` images, and a failure stops
    the rendering rather than leaving a gap."""
    return URLFetcher(allowed_protocols={"data"}, fail_on_errors=True)


def render_pdf(html: str) -> bytes:
    """The report printed to PDF. Blocks."""
    stylesheet = resources.files("subphora.report").joinpath("report.css").read_text()
    pdf: bytes = HTML(string=html, url_fetcher=fetcher()).write_pdf(
        stylesheets=[CSS(string=stylesheet, url_fetcher=fetcher())]
    )
    return pdf


def _e(text: object) -> str:
    return escape(str(text))


def _p(text: str, cls: str | None = None, **data: str) -> str:
    attributes = "".join(f' data-{k}="{_e(v)}"' for k, v in data.items())
    css = f' class="{cls}"' if cls else ""
    return f"<p{css}{attributes}>{_e(text)}</p>"


def _ul(items: Iterable[str], cls: str | None = None) -> str:
    css = f' class="{cls}"' if cls else ""
    return f"<ul{css}>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _table(head: Sequence[str], rows: Iterable[Sequence[str]], cls: str = "") -> str:
    header = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="{cls}"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>'


def _section(key: str, title: str, body: str) -> str:
    return f'<section id="{key}" data-section="{key}"><h2>{_e(title)}</h2>{body}</section>'


class _Writer:
    """The report's HTML, one method per section."""

    def __init__(self, data: ReportData, c: Catalogue, settings: ReportSettings) -> None:
        self.data = data
        self.c = c
        self.settings = settings
        self.analysis: AreaAnalysis = data.analysis

    # ── Shared texts ─────────────────────────────────────────────────────────────────

    def criterion(self, criterion: str) -> str:
        return self.c.lookup(f"criterion.{criterion}", criterion)

    def score_text(self, estimate: PotentialEstimate) -> str:
        """The index with its confidence: never one without the other (hard rule 1)."""
        c = self.c
        index = (
            c.t("explain.noIndex")
            if estimate.score is None
            else c.t("explain.index", value=c.score(estimate.score))
        )
        return f"{index} · {self.confidence_text(estimate.confidence)}"

    def confidence_text(self, confidence: Confidence) -> str:
        c = self.c
        return c.t(
            "explain.confidence",
            label=c.t(f"explain.confidence.{confidence.label.value}"),
            value=c.score(confidence.value),
        )

    def value_text(self, value: InputValue) -> str:
        c = self.c
        if value.absent:
            return c.t("explain.absent")
        if value.category is not None:
            if value.label and value.label != value.category:
                return f"{value.category} ({value.label})"
            return value.category
        if value.number is not None:
            quantity = c.quantity(value.number, value.unit or "")
            return c.t("explain.atLeast", value=quantity) if value.at_least else quantity
        return c.t("report.missing")

    def detail_text(self, scale: int | None, cell: float | None, edition: int | None) -> str:
        c = self.c
        if scale is not None:
            measure = c.t("detail.scale", value=c.number(scale))
        elif cell is not None:
            measure = c.t("detail.cell", value=c.number(cell))
        else:
            measure = c.t("detail.noScale")
        year = (
            c.t("detail.noEdition") if edition is None else c.t("detail.edition", year=str(edition))
        )
        return f"{measure} · {year}"

    def validation_text(self, validation: DomainValidation) -> list[str]:
        c = self.c
        auc = validation.auc
        params: dict[str, str | int | float] = {
            "label": validation.label,
            "productive": validation.productive,
            "value": "" if auc is None else c.score(auc.value),
            "low": "" if auc is None else c.score(auc.low),
            "high": "" if auc is None else c.score(auc.high),
            "reason": validation.labels_source,
        }
        lines = [c.lookup(f"validation.{validation.state.value}", validation.state.value, **params)]
        if validation.state in MEASURED:
            lines.append(
                c.t("validation.counts", productive=validation.productive, blocks=validation.blocks)
            )
            if validation.design is not None:
                lines.append(
                    c.lookup(
                        f"validation.design.{validation.design.value}",
                        validation.design.value,
                        productive=validation.productive,
                        dry=validation.dry,
                        background=validation.background,
                    )
                )
        if validation.calibration is not None:
            lines.append(c.t("validation.calibrated"))
        return lines

    # ── Sections ─────────────────────────────────────────────────────────────────────

    def heading(self) -> str:
        c, a = self.c, self.analysis
        crs = c.lookup(f"crs.{a.crs}", a.crs)
        label = a.label or c.t("report.unnamed")
        lines = [
            c.t(
                "report.built",
                built=c.moment(a.built_at),
                generated=c.moment(self.data.generated_at),
            ),
            c.t(
                "report.grid",
                cell=c.number(a.cell_m),
                crs=crs,
                code=a.crs,
                area=self._area(a.area_m2),
            ),
            c.lookup(
                f"detailed.terrain.{a.terrain_model}", c.t("report.terrain", model=a.terrain_model)
            ),
            c.t("report.id", id=a.id),
        ]
        return (
            f"<header><h1>{_e(c.t('report.title'))}</h1>"
            f'<p class="subtitle">{_e(label)}</p>'
            + "".join(_p(line) for line in lines)
            + _p(c.t("national.kindNote"), "note")
            + _p(c.t("report.audience"), "note")
            + "</header>"
        )

    def _area(self, square_metres: float) -> str:
        c = self.c
        metres = f"{c.number(square_metres)} m²"
        hectare = 10_000
        return (
            metres
            if square_metres < hectare
            else f"{metres} ({c.number(square_metres / hectare, 2)} ha)"
        )

    def summary(self) -> str:
        c = self.c
        s = self.analysis.summary
        parts = [
            _p(
                c.t(
                    "detailed.cells",
                    cells=c.number(s.cells),
                    cell=c.number(self.analysis.cell_m),
                    area=self._area(self.analysis.area_m2),
                )
            )
        ]
        if s.mean_index is None or s.mean_confidence is None:
            parts.append(_p(c.t("detailed.noScore"), "missing", missing="score"))
        else:
            parts.append(
                '<p class="score"><strong>'
                f"{_e(c.t('explain.index', value=c.score(s.mean_index)))}</strong>"
                f" · {_e(self.confidence_text(s.mean_confidence))}</p>"
            )
            parts.append(
                _table(
                    [
                        c.t("report.column.criterion"),
                        c.t("report.column.weight"),
                        c.t("explain.column.share"),
                        c.t("explain.column.contribution"),
                        c.t("report.column.present"),
                        c.t("report.column.source"),
                    ],
                    [
                        (
                            self.criterion(x.criterion),
                            c.percent(x.weight),
                            c.percent(x.mean_share),
                            c.score(x.mean_contribution),
                            c.percent(x.present_share),
                            x.source.attribution,
                        )
                        for x in s.contributions
                    ],
                    "contributions",
                )
            )
        if s.missing:
            parts.append(f"<h3>{_e(c.t('explain.missing'))}</h3>")
            parts.append(
                _ul(
                    (
                        c.t(
                            f"explain.missing.{m.reason.value}",
                            title=self.criterion(m.criterion),
                            weight=c.percent(m.weight),
                        )
                        for m in s.missing
                    ),
                    "missing",
                )
            )
        return _section("summary", c.t("report.section.summary"), "".join(parts))

    def maps(self) -> str:
        c = self.c
        body = "".join(self._figure(figure) for figure in self.data.maps)
        body += _p(c.t("report.mapNote"), "note")
        return _section("maps", c.t("report.section.maps"), body)

    def _figure(self, figure: MapFigure) -> str:
        c = self.c
        layer = figure.layer
        title = c.lookup(f"layer.{layer.id}", layer.id)
        unit = c.lookup(f"national.unit.{layer.unit}", layer.unit)
        legend = self._legend(figure)
        crs = c.lookup(f"crs.{self.analysis.crs}", self.analysis.crs)
        empty = (
            ""
            if figure.png is not None
            else _p(c.t("report.mapEmpty"), "missing", missing=layer.id)
        )
        return (
            f'<figure data-map="{_e(layer.id)}">{self._svg(figure)}'
            f"<figcaption><strong>{_e(title)}</strong>. {_e(unit)}. "
            f"{_e(c.t('report.mapCaption', crs=crs))}</figcaption>{empty}{legend}</figure>"
        )

    def _legend(self, figure: MapFigure) -> str:
        c, layer = self.c, figure.layer
        edges: list[float | None] = [None, *layer.breaks, None]
        items = []
        for colour, low, high in zip(layer.colours, edges[:-1], edges[1:], strict=True):
            if low is None and high is not None:
                text = f"< {c.quantity(high, layer.unit)}"
            elif high is None and low is not None:
                text = f"≥ {c.quantity(low, layer.unit)}"
            elif low is not None and high is not None:
                text = f"{c.quantity(low, layer.unit)} \u2013 {c.quantity(high, layer.unit)}"
            else:
                text = ""
            items.append(
                f'<li><span class="swatch" style="background:{colour}"></span>{_e(text)}</li>'
            )
        return '<ul class="legend">' + "".join(items) + "</ul>"

    def _svg(self, figure: MapFigure) -> str:
        west, south, east, north = figure.bounds
        width, height = figure.width_px, figure.height_px
        sx = width / (east - west)
        sy = height / (north - south)

        def px(x: float, y: float) -> str:
            return f"{(x - west) * sx:.1f},{(north - y) * sy:.1f}"

        outline = self.settings.outline_colour
        spot = self.settings.candidate_colour
        stroke = max(width, height) / 300
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{self._width_mm(width, height):.1f}mm" class="map">',
            f'<rect width="{width}" height="{height}" fill="#f4f4f4"/>',
        ]
        if figure.png is not None:
            encoded = base64.b64encode(figure.png).decode()
            parts.append(
                f'<image href="data:image/png;base64,{encoded}" width="{width}" '
                f'height="{height}" preserveAspectRatio="none" style="image-rendering:pixelated"/>'
            )
        for polygon in self.data.outline:
            for ring in polygon["coordinates"]:
                points = " ".join(px(p[0], p[1]) for p in ring)
                parts.append(
                    f'<polygon points="{points}" fill="none" stroke="{outline}" '
                    f'stroke-width="{stroke:.1f}"/>'
                )
        radius = stroke * 6
        for candidate in self.analysis.candidates:
            x, y = px(candidate.local.x, candidate.local.y).split(",")
            parts.append(
                f'<circle cx="{x}" cy="{y}" r="{radius:.1f}" fill="#ffffff" stroke="{spot}" '
                f'stroke-width="{stroke:.1f}"/>'
                f'<text x="{x}" y="{y}" dy="0.35em" text-anchor="middle" fill="{spot}" '
                f'font-size="{radius * 1.3:.1f}" font-weight="bold">{candidate.rank}</text>'
            )
        parts.append(self._scale_bar(width, height, sx, stroke))
        parts.append(
            f'<text x="{width - stroke * 6:.1f}" y="{stroke * 10:.1f}" text-anchor="middle" '
            f'font-size="{stroke * 8:.1f}" font-weight="bold">N ↑</text>'
        )
        parts.append("</svg>")
        return "".join(parts)

    def _width_mm(self, width: float, height: float) -> float:
        """The printed width: the configured one, narrower for a tall map so that it keeps
        to the configured width as its height too (it never runs off the page)."""
        size = self.settings.map_width_mm
        return min(size, size * width / height)

    def _scale_bar(self, width: float, height: float, sx: float, stroke: float) -> str:
        span_m = width / sx
        length = next((m for m in reversed(_SCALE_STEPS) if m <= span_m / 4), _SCALE_STEPS[0])
        bar = length * sx
        x0, y0 = stroke * 5, height - stroke * 6
        return (
            f'<rect x="{x0:.1f}" y="{y0 - stroke * 8:.1f}" width="{bar + stroke * 4:.1f}" '
            f'height="{stroke * 11:.1f}" fill="#ffffff" fill-opacity="0.8"/>'
            f'<line x1="{x0 + stroke * 2:.1f}" y1="{y0:.1f}" x2="{x0 + stroke * 2 + bar:.1f}" '
            f'y2="{y0:.1f}" stroke="#000" stroke-width="{stroke:.1f}"/>'
            f'<text x="{x0 + stroke * 2:.1f}" y="{y0 - stroke * 2:.1f}" '
            f'font-size="{stroke * 6:.1f}">{_e(self.c.metres(length))}</text>'
        )

    def candidates(self) -> str:
        c, a = self.c, self.analysis
        if not a.candidates:
            reason = "" if a.no_candidates is None else a.no_candidates.value
            body = _p(
                c.lookup(f"detailed.noCandidates.{reason}", reason), "missing", missing="candidates"
            )
            return _section("candidates", c.t("report.section.candidates"), body)
        overview = _table(
            [
                c.t("report.column.rank"),
                c.t("report.column.index"),
                c.t("report.column.confidence"),
                c.t("report.column.depth"),
                c.t("report.column.cost"),
                c.t("report.column.legal"),
            ],
            [self._overview(candidate) for candidate in a.candidates],
            "overview",
        )
        body = _p(c.t("detailed.candidatesHint"), "note") + overview
        body += "".join(self._candidate(candidate) for candidate in a.candidates)
        return _section("candidates", c.t("report.section.candidates"), body)

    def _overview(self, candidate: Candidate) -> tuple[str, ...]:
        c = self.c
        estimate, depth = candidate.estimate, candidate.depth
        score = c.t("report.missing") if estimate.score is None else c.score(estimate.score)
        confidence = (
            f"{c.t(f'explain.confidence.{estimate.confidence.label.value}')} "
            f"({c.score(estimate.confidence.value)})"
        )
        if depth.state == "estimated" and depth.depth_m is not None:
            depth_text = c.t(
                "report.depthShort",
                depth=c.number(depth.depth_m),
                low=c.number(depth.low_m or 0),
                high=c.number(depth.high_m or 0),
            )
        else:
            depth_text = c.t("report.unknown")
        cost = candidate.cost
        cost_text = (
            c.t("report.unknown")
            if cost is None
            else c.t("report.costShort", low=c.number(int(cost.low)), high=c.number(int(cost.high)))
        )
        return (
            str(candidate.rank),
            score,
            confidence,
            depth_text,
            cost_text,
            c.lookup(
                f"report.legalShort.{candidate.legal.state.value}", candidate.legal.state.value
            ),
        )

    def _candidate(self, candidate: Candidate) -> str:
        c, a = self.c, self.analysis
        estimate = candidate.estimate
        crs = c.lookup(f"crs.{a.crs}", a.crs)
        position = c.t(
            "detailed.candidatePosition",
            crs=crs,
            x=c.number(candidate.local.x),
            y=c.number(candidate.local.y),
            lat=c.number(candidate.latitude, 6),
            lon=c.number(candidate.longitude, 6),
        )
        parts = [
            f'<article class="candidate" data-rank="{candidate.rank}">',
            f"<h3>{_e(c.t('detailed.candidate', rank=candidate.rank))}</h3>",
            _p(position),
            f'<p class="score"><strong>{_e(self.score_text(estimate))}</strong></p>',
        ]
        if estimate.probability is not None:
            p = estimate.probability
            parts.append(
                _p(
                    c.t(
                        "explain.probability",
                        value=c.percent(p.value),
                        low=c.percent(p.low),
                        high=c.percent(p.high),
                    )
                )
            )
        parts.append(self._explanation(estimate))
        parts.append(self._site(candidate))
        parts.append(self._depth(candidate.depth))
        parts.append(self._cost(candidate.cost))
        parts.append(self._legal(candidate.legal))
        parts.append("</article>")
        return "".join(parts)

    def _explanation(self, estimate: PotentialEstimate) -> str:
        c = self.c
        parts = [f"<h4>{_e(c.t('explain.inputs'))}</h4>"]
        parts.append(
            _table(
                [
                    c.t("explain.column.criterion"),
                    c.t("report.column.value"),
                    c.t("explain.column.suitability"),
                    c.t("explain.column.share"),
                    c.t("explain.column.contribution"),
                    c.t("report.column.source"),
                ],
                [
                    (
                        self.criterion(x.criterion),
                        self.value_text(x.value),
                        c.score(x.suitability),
                        c.percent(x.share),
                        c.score(x.contribution),
                        f"{x.source.attribution} ({c.day(x.source.retrieved_at)})",
                    )
                    for x in estimate.contributions
                ],
                "explanation",
            )
        )
        if estimate.missing:
            parts.append(f"<h4>{_e(c.t('explain.missing'))}</h4>")
            parts.append(
                _ul(
                    (
                        c.t(
                            f"explain.missing.{m.reason.value}",
                            title=self.criterion(m.criterion),
                            weight=c.percent(m.weight),
                        )
                        for m in estimate.missing
                    ),
                    "missing",
                )
            )
        components = []
        for component in estimate.confidence.components:
            title = c.lookup(f"component.{component.id.value}", component.id.value)
            weight = c.percent(component.weight)
            components.append(
                c.t("explain.component", title=title, value=c.score(component.value), weight=weight)
                if component.measured
                else c.t("explain.notMeasured", title=title, weight=weight)
            )
        parts.append(f"<h4>{_e(c.t('explain.confidenceHeading'))}</h4>")
        parts.append(_ul(components))
        parts.append(_ul(self.validation_text(estimate.validation), "validation"))
        return "".join(parts)

    def _site(self, candidate: Candidate) -> str:
        c = self.c
        site = candidate.site
        point = site.water_point
        lines = [
            c.t("report.waterPoint", distance=c.metres(point.metres))
            if point.metres is not None
            else c.t("report.noWaterPoint", reach=c.metres(point.reach_m))
        ]
        if site.channel is None:
            lines.append(c.t("report.channelUnknown"))
        elif site.channel.metres is None:
            lines.append(c.t("report.noChannel", reach=c.metres(site.channel.reach_m)))
        else:
            lines.append(c.t("report.channel", distance=c.metres(site.channel.metres)))
        return _ul(lines, "site")

    def _depth(self, depth: DepthEstimate) -> str:
        c = self.c
        if depth.state != "estimated" or depth.water_table is None:
            reason = "" if depth.reason is None else depth.reason.value
            text = c.lookup(f"detailed.depthUnknown.{reason}", c.t("report.unknown"))
            lines = [_p(text, "missing", missing="depth")]
        else:
            table = depth.water_table
            lines = [
                _p(
                    c.t(
                        "detailed.depth",
                        depth=c.number(depth.depth_m or 0),
                        low=c.number(depth.low_m or 0),
                        high=c.number(depth.high_m or 0),
                    )
                ),
                _p(
                    c.t(
                        "detailed.depthDetail",
                        ground=c.number(depth.ground_m or 0),
                        table=c.number(table.elevation_m),
                        count=table.piezometers,
                        body=f"{table.body_label} ({table.body})",
                        nearest=c.metres(table.nearest_m),
                    )
                ),
            ]
            lines.extend(_p(self._levels(s), "note") for s in depth.sources)
        if depth.karst:
            lines.append(_p(c.t("detailed.karst"), "warning"))
        return '<div class="depth">' + "".join(lines) + "</div>"

    def _levels(self, source: LevelsSource) -> str:
        c = self.c
        return c.t(
            "detailed.depthSource",
            **{
                "from": c.day(source.levels_from),
                "to": c.day(source.levels_to),
                "attribution": source.attribution,
            },
        )

    def _cost(self, cost: DrillingCost | None) -> str:
        c = self.c
        if cost is None:
            return _p(c.t("report.noCost"), "missing", missing="cost")
        return _p(
            c.t("detailed.cost", low=c.number(int(cost.low)), high=c.number(int(cost.high)))
        ) + _p(
            c.t(
                "detailed.costDetail",
                drilledLow=c.number(float(cost.drilled_low_m), 1),
                drilledHigh=c.number(float(cost.drilled_high_m), 1),
                perLow=c.number(int(cost.per_metre_low)),
                perHigh=c.number(int(cost.per_metre_high)),
                fixedLow=c.number(int(cost.fixed_low)),
                fixedHigh=c.number(int(cost.fixed_high)),
                date=c.day(cost.priced_on),
                source=cost.source,
            ),
            "note",
        )

    def _legal(self, status: LegalStatus) -> str:
        c = self.c
        parts = [
            f"<h4>{_e(c.t('legal.heading'))}</h4>",
            _p(
                c.lookup(f"legal.state.{status.state.value}", status.state.value),
                "verdict",
                legal=status.state.value,
            ),
        ]
        if status.state is LegalState.NOT_EVALUATED:
            parts.append(_p(status.source, "missing", missing="legal"))
        authority = status.authority
        if authority is not None:
            parts.append(
                _p(
                    c.t(
                        "legal.authority",
                        name=authority.name,
                        district=authority.district_name,
                        code=authority.district,
                    )
                )
            )
            if authority.note:
                parts.append(_p(c.translated(authority.note), "note"))
        body = status.body
        if body is not None:
            if body.declared_at_risk is None:
                risk = c.t("legal.riskUnknown")
            elif body.declared_at_risk:
                risk = c.t("legal.declared", declaration=body.declaration or "")
            else:
                risk = c.t("legal.notDeclared")
            status_text = body.quantitative_status or c.t("legal.unknown")
            parts.append(
                _p(
                    c.t("legal.body", name=body.name, code=body.code, status=status_text)
                    + f" {risk}"
                )
            )
        for missing in status.not_loaded:
            parts.append(
                _p(
                    f"{c.t(f'legal.notLoaded.{missing.scope.value}', area=missing.area or '')} "
                    f"{c.translated(missing.reason)}",
                    "missing",
                    missing="rules",
                )
            )
        findings = sorted(status.findings, key=lambda f: _OUTCOME_ORDER.index(f.outcome.value))
        if findings:
            parts.append(_p(c.t("legal.rules", count=len(findings))))
            parts.append(
                '<ul class="findings">' + "".join(self._finding(f) for f in findings) + "</ul>"
            )
        if status.permits:
            parts.append(_ul(c.translated(p) for p in status.permits))
        parts.append(
            _p(
                c.t("legal.assessed", date=c.day(status.assessed_at))
                + f" {c.t('detailed.disclaimer')}",
                "note",
            )
        )
        return '<div class="legal">' + "".join(parts) + "</div>"

    def _finding(self, finding: Finding) -> str:
        c = self.c
        values: dict[str, str | float] = dict(finding.values)
        because = values.get("because")
        if isinstance(because, str):
            values["because"] = c.lookup(f"legal.because.{because.split(':')[0]}", because)
        message = c.lookup(f"legal.message.{finding.message}", finding.message, **values)
        notes = []
        method, assumed, official = (values.get(k) for k in ("method", "assumed", "official"))
        if isinstance(method, str):
            notes.append(c.lookup(f"legal.method.{method}", method))
        if assumed == "strictest":
            notes.append(c.t("legal.assumed.strictest"))
        if official == "unread":
            notes.append(c.t("legal.official.unread"))
        if finding.uncertain:
            notes.append(c.translated(finding.uncertain))
        outcome = c.lookup(f"legal.outcome.{finding.outcome.value}", finding.outcome.value)
        return (
            f'<li data-outcome="{finding.outcome.value}"><strong>{_e(outcome)}</strong> '
            f"{_e(c.translated(finding.title))}. {_e(message)}"
            + "".join(f' <span class="note">{_e(n)}</span>' for n in notes)
            + f'<br/><span class="note">{_e(self._rule_source(finding.source))}</span></li>'
        )

    def _rule_source(self, source: RuleSource) -> str:
        c = self.c
        text = c.t(
            "legal.source",
            name=source.name,
            article=source.article,
            published=c.day(source.published),
            checked=c.day(source.checked),
        )
        return f"{text} {source.url}"

    def validation(self) -> str:
        c = self.c
        body = _p(c.t("report.validationIntro"), "note")
        for validation in self.analysis.summary.validation:
            body += f'<div class="validation" data-validation="{validation.state.value}">'
            body += _ul(self.validation_text(validation))
            if validation.validated_at is not None:
                body += _p(
                    c.t(
                        "report.validatedAt",
                        date=c.day(validation.validated_at),
                        source=validation.labels_source,
                    ),
                    "note",
                )
            body += "</div>"
        return _section("validation", c.t("report.section.validation"), body)

    def observations(self) -> str:
        c = self.c
        records = self.data.records
        if not records:
            return _section(
                "observations",
                c.t("report.section.observations"),
                _p(c.t("report.noObservations"), "missing", missing="observations"),
            )
        rows = [self._record(r) for r in records if r.observation.kind.value != "track_point"]
        tracks = len({r.observation.track_id for r in records if r.observation.track_id})
        points = sum(1 for r in records if r.observation.kind.value == "track_point")
        body = _p(c.t("report.observationsIntro", count=len(records)), "note")
        if rows:
            body += _table(
                [
                    c.t("report.column.when"),
                    c.t("report.column.kind"),
                    c.t("report.column.where"),
                    c.t("report.column.text"),
                ],
                rows,
                "observations",
            )
        if tracks:
            body += _p(c.t("report.tracks", tracks=tracks, points=points))
        return _section("observations", c.t("report.section.observations"), body)

    def _record(self, record: FieldRecord) -> tuple[str, ...]:
        c = self.c
        o = record.observation
        if o.position is None or record.local is None:
            where = c.t("report.noPosition")
        else:
            where = c.t(
                "report.position",
                x=c.number(record.local[0]),
                y=c.number(record.local[1]),
                accuracy=c.metres(o.position.accuracy_m),
            )
        return (
            c.moment(o.recorded_at),
            c.lookup(f"report.kind.{o.kind.value}", o.kind.value),
            where,
            o.text or "",
        )

    def sources(self) -> str:
        c, a = self.c, self.analysis
        lines = []
        for dataset, source in a.sources.items():
            service = self.data.services.get(source.service_id)
            detail = self.detail_text(
                source.detail.scale_denominator, source.detail.cell_m, source.detail.edition
            )
            licence = (
                c.t("report.licenceUnknown")
                if service is None
                else c.t("report.licence", licence=service.licence, terms=service.terms_url)
            )
            lines.append(
                c.t(
                    "report.source",
                    title=c.lookup(f"report.dataset.{dataset}", dataset),
                    publisher=source.publisher,
                    attribution=source.attribution,
                    detail=detail,
                    date=c.day(source.retrieved_at),
                    licence=licence,
                )
            )
        levels: dict[str, LevelsSource] = {}
        prices: dict[str, DrillingCost] = {}
        rules: dict[str, RuleSource] = {}
        for candidate in a.candidates:
            levels.update({s.sha256: s for s in candidate.depth.sources})
            if candidate.cost is not None:
                prices[candidate.cost.source] = candidate.cost
            rules.update(
                {f.source.url + f.source.article: f.source for f in candidate.legal.findings}
            )
        for level in levels.values():
            lines.append(
                c.t(
                    "report.levelsSource",
                    attribution=level.attribution,
                    file=level.file_name,
                    imported=c.day(level.imported_at),
                    levels=self._levels(level),
                )
            )
        for cost in prices.values():
            lines.append(c.t("report.pricesSource", source=cost.source, date=c.day(cost.priced_on)))
        body = _ul(lines, "sources")
        if rules:
            body += f"<h3>{_e(c.t('report.rulesHeading'))}</h3>"
            body += _ul((self._rule_source(r) for r in rules.values()), "sources")
        body += _p(c.t("report.attributionNote"), "note")
        return _section("sources", c.t("report.section.sources"), body)

    def limitations(self) -> str:
        c, a = self.c, self.analysis
        lines = [c.t(f"report.limit.{n}") for n in range(1, 7)]
        lines.append(
            c.lookup(
                f"detailed.terrain.{a.terrain_model}", c.t("report.terrain", model=a.terrain_model)
            )
        )
        lines.extend(
            c.t(
                f"explain.missing.{m.reason.value}",
                title=self.criterion(m.criterion),
                weight=c.percent(m.weight),
            )
            for m in a.summary.missing
        )
        if any(v.state not in MEASURED for v in a.summary.validation):
            lines.append(c.t("report.limitNotValidated"))
        karst = [str(x.rank) for x in a.candidates if x.depth.karst]
        if karst:
            lines.append(c.t("report.limitKarst", ranks=", ".join(karst)))
        if any(x.legal.state is LegalState.RULES_NOT_LOADED for x in a.candidates):
            lines.append(c.t("report.limitRules"))
        return _section("limitations", c.t("report.section.limitations"), _ul(lines, "limitations"))

    def disclaimer(self) -> str:
        c = self.c
        body = _p(c.t("detailed.disclaimer"), "disclaimer") + _p(
            c.t("report.disclaimer"), "disclaimer"
        )
        return _section("disclaimer", c.t("report.section.disclaimer"), body)


def report_html(data: ReportData, catalogue: Catalogue, settings: ReportSettings) -> str:
    """The whole report as one HTML document."""
    w = _Writer(data, catalogue, settings)
    sections = [
        w.heading(),
        w.summary(),
        w.maps(),
        w.candidates(),
        w.validation(),
        w.observations(),
        w.sources(),
        w.limitations(),
        w.disclaimer(),
    ]
    title = _e(catalogue.t("report.title"))
    footer = _e(catalogue.t("report.footer", id=data.analysis.id))
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f'<title>{title}</title><meta name="description" content="{footer}"></head>'
        f'<body><div class="footer">{footer}</div>' + "".join(sections) + "</body></html>"
    )


__all__ = ["fetcher", "render_pdf", "report_html"]
