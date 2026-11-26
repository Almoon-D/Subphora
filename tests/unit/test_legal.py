# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal filter's engine on the rules of config/legal/es/: every rule kind's branches, a
place in every river-basin district, districts whose plan was not read, the distance limits
at their boundaries, and the disclaimer on every output (MASTER_PLAN §4.5, hard rule 2)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from subphora.config import load_settings
from subphora.config.legal import LegalSettings, LoadState, Translated, Where
from subphora.domain.legal import (
    BodyStatus,
    Finding,
    LegalState,
    LegalStatus,
    NotLoaded,
    NotLoadedScope,
    Outcome,
    RuleSource,
    verdict,
)
from subphora.legal import Distance, LayerAnswer, PlaceFacts, assess, district_of, layers_read

WHEN = datetime(2026, 11, 26, tzinfo=UTC)
SETTINGS: LegalSettings = load_settings().legal
GOOD = "Bueno"
POOR = "Malo"


def body(
    district: str = "ES050",
    status: str | None = GOOD,
    at_risk: bool | None = False,
    code: str | None = None,
) -> BodyStatus:
    return BodyStatus(
        code=code or f"{district}MSBT000000001",
        name="Test body",
        quantitative_status=status,
        declared_at_risk=at_risk,
    )


def facts(**changes: Any) -> PlaceFacts:
    """A place in the Guadalquivir, in Andalusia, far from wells and channels."""
    base: dict[str, Any] = {
        "region": "ES-AN",
        "bodies_read": True,
        "body": body(),
        "layers": {"public-water-domain": LayerAnswer(features=())},
        "water_point": Distance(metres=900, reach_m=10000, method="inventory"),
        "channel": Distance(metres=800, reach_m=2000, method="terrain"),
        "volume_m3_year": 7000,
        "max_flow_l_s": None,
    }
    base.update(changes)
    return PlaceFacts(**base)


def run(place: PlaceFacts, settings: LegalSettings = SETTINGS) -> LegalStatus:
    return assess(settings, place, WHEN)


def finding(status: LegalStatus, rule_id: str) -> Finding:
    return next(f for f in status.findings if f.rule_id == rule_id)


# ── The verdict and the status model ─────────────────────────────────────────────────


def _finding(outcome: Outcome) -> Finding:
    return Finding(
        rule_id="r",
        area="ES",
        title={"en": "t"},
        source=RuleSource(
            name="n", url="https://x", article="a", published=WHEN.date(), checked=WHEN.date()
        ),
        outcome=outcome,
        message="m",
    )


MISSING = NotLoaded(scope=NotLoadedScope.BASIN_PLAN, area="ES010", reason={"en": "not read"})


@pytest.mark.parametrize(
    ("outcomes", "missing", "expected"),
    [
        ([Outcome.BLOCKS, Outcome.CLEAR], [MISSING], LegalState.PROBABLY_NOT_ALLOWED),
        ([Outcome.AUTHORISATION], [MISSING], LegalState.RULES_NOT_LOADED),
        ([Outcome.AUTHORISATION, Outcome.NOTICE], [], LegalState.CONDITIONS_APPLY),
        ([Outcome.CHECK], [], LegalState.CONDITIONS_APPLY),
        ([Outcome.NOTICE, Outcome.CLEAR, Outcome.NOT_APPLICABLE], [], LegalState.NO_BLOCKING_RULE),
        ([], [], LegalState.NO_BLOCKING_RULE),
    ],
)
def test_the_verdict_follows_the_findings(
    outcomes: list[Outcome], missing: list[NotLoaded], expected: LegalState
) -> None:
    state, reason = verdict([_finding(o) for o in outcomes], missing)
    assert state is expected
    assert (reason is not None) == (expected is LegalState.RULES_NOT_LOADED)


def test_a_status_cannot_claim_more_than_its_findings() -> None:
    blocked = _finding(Outcome.BLOCKS)
    common: dict[str, Any] = {
        "source": "s",
        "assessed_at": WHEN,
        "disclaimer": "d",
        "not_loaded": (
            NotLoaded(scope=NotLoadedScope.DISTRICT, area=None, reason={"en": "no body"}),
        ),
    }
    with pytest.raises(ValidationError, match="findings support"):
        LegalStatus(state=LegalState.CONDITIONS_APPLY, findings=(blocked,), reason=None, **common)
    with pytest.raises(ValidationError, match="reason"):
        LegalStatus(state=LegalState.RULES_NOT_LOADED, **common)
    with pytest.raises(ValidationError, match="not evaluated"):
        LegalStatus(state=LegalState.NOT_EVALUATED, findings=(blocked,), **common)
    # An evaluated place names its authority, or says why its district is unknown.
    with pytest.raises(ValidationError, match="authority"):
        LegalStatus(
            state=LegalState.PROBABLY_NOT_ALLOWED,
            source="s",
            assessed_at=WHEN,
            disclaimer="d",
            findings=(blocked,),
        )
    with pytest.raises(ValidationError, match="English"):
        NotLoaded(scope=NotLoadedScope.DISTRICT, area=None, reason={"es": "sin cuerpo"})
    with pytest.raises(ValidationError):
        LegalStatus(state=LegalState.NOT_EVALUATED, source="s", assessed_at=WHEN, disclaimer="")


# ── A place where every rule is loaded ───────────────────────────────────────────────


def test_a_good_body_far_from_everything_meets_only_the_andalusian_open_question() -> None:
    status = run(facts())
    assert status.authority is not None
    assert status.authority.name == "Confederación Hidrográfica del Guadalquivir"
    assert status.authority.level == "state"
    assert status.not_loaded == ()
    # The Andalusian well authorisation in a State basin is an open question: a condition.
    open_question = finding(status, "laa-51-2-well-state-basins")
    assert open_question.outcome is Outcome.AUTHORISATION
    assert open_question.uncertain is not None
    assert status.state is LegalState.CONDITIONS_APPLY
    assert finding(status, "rdph-85-notice").outcome is Outcome.NOTICE
    # The plan's exclusion circle replaces the national distance.
    national = finding(status, "rdph-87-2-distance")
    assert national.outcome is Outcome.NOT_APPLICABLE
    assert national.values == {"by": "phg-50-3-distance"}
    assert finding(status, "phg-50-3-distance").outcome is Outcome.CLEAR
    assert status.permits
    assert all("en" in p and "es" in p for p in status.permits)


def unread_region(region: str) -> LegalSettings:
    """The rules with one region's water law not read (every region's is loaded)."""
    areas = SETTINGS.areas
    law = LoadState(state="not_read", reason=Translated(en="The law was not read.", es="No leída."))
    regions = areas.regions | {region: areas.regions[region].model_copy(update={"water_law": law})}
    return SETTINGS.model_copy(update={"areas": areas.model_copy(update={"regions": regions})})


def test_outside_andalusia_the_guadalquivir_applies_no_andalusian_rule() -> None:
    status = run(facts(region="ES-CM"))
    assert status.state is LegalState.CONDITIONS_APPLY
    assert status.not_loaded == ()
    assert not any(f.area == "ES-AN" for f in status.findings)


def test_a_regional_law_not_read_says_so_and_why() -> None:
    status = run(facts(region="ES-CM"), unread_region("ES-CM"))
    assert status.state is LegalState.RULES_NOT_LOADED
    (missing,) = status.not_loaded
    assert missing.scope is NotLoadedScope.REGIONAL_LAW
    assert missing.area == "ES-CM"
    assert missing.reason == {"en": "The law was not read.", "es": "No leída."}
    assert status.reason == missing.reason["en"]


def test_in_an_andalusian_district_the_junta_decides() -> None:
    status = run(facts(body=body("ES060")))
    assert status.authority is not None
    assert status.authority.level == "regional"
    assert finding(status, "laa-51-2-well").outcome is Outcome.AUTHORISATION
    assert finding(status, "laa-51-2-well").uncertain is None
    assert status.state is LegalState.CONDITIONS_APPLY


# ── Rule kinds, branch by branch ─────────────────────────────────────────────────────


def test_above_the_small_use_volume_a_concession_and_the_no_new_concessions_rule_apply() -> None:
    small = run(facts(body=body(status=POOR)))
    assert finding(small, "rdph-87-1-concession").outcome is Outcome.NOT_APPLICABLE
    assert finding(small, "phg-38-4-no-concessions").outcome is Outcome.NOT_APPLICABLE
    big = run(facts(body=body(status=POOR), volume_m3_year=7001))
    assert finding(big, "rdph-87-1-concession").outcome is Outcome.AUTHORISATION
    assert finding(big, "rdph-85-notice").outcome is Outcome.NOT_APPLICABLE
    assert finding(big, "rdph-84-2-at-risk").outcome is Outcome.NOT_APPLICABLE
    assert finding(big, "phg-38-4-no-concessions").outcome is Outcome.BLOCKS
    assert big.state is LegalState.PROBABLY_NOT_ALLOWED
    good = run(facts(volume_m3_year=9000))
    assert finding(good, "phg-38-4-no-concessions").outcome is Outcome.CLEAR
    unknown = run(facts(body=body(status=None), volume_m3_year=9000))
    assert finding(unknown, "phg-38-4-no-concessions").outcome is Outcome.CHECK


@pytest.mark.parametrize(
    ("place", "outcome", "message"),
    [
        (facts(body=body(at_risk=True)), Outcome.AUTHORISATION, "authorisation_body"),
        (facts(body=body(at_risk=None)), Outcome.CHECK, "status_unknown"),
        (facts(body=body(at_risk=False)), Outcome.CLEAR, "body_not_marked"),
        (facts(body=None), Outcome.CLEAR, "outside_bodies"),
        (facts(body=None, bodies_read=False), Outcome.CHECK, "body_unknown"),
    ],
)
def test_a_body_declared_at_risk_needs_an_authorisation(
    place: PlaceFacts, outcome: Outcome, message: str
) -> None:
    status = run(place)
    result = finding(status, "rdph-84-2-at-risk")
    assert (result.outcome, result.message) == (outcome, message)


def test_preventive_control_is_read_from_the_junta_layer() -> None:
    marked = LayerAnswer(features=({"control_preventivo": "Sometida a control preventivo"},))
    other = LayerAnswer(features=({"control_preventivo": "No"},))
    place = facts(body=body("ES060"))
    layers = dict(place.layers)

    def at(answer: LayerAnswer) -> Finding:
        status = run(
            facts(body=body("ES060"), layers={**layers, "andalusia-preventive-control": answer})
        )
        return finding(status, "phcma-39-preventive")

    hit = at(marked)
    assert hit.outcome is Outcome.AUTHORISATION
    assert hit.values["because"] == "marked:andalusia-preventive-control"
    assert at(other).outcome is Outcome.CLEAR
    assert at(LayerAnswer(features=(), covers=False)).outcome is Outcome.CLEAR
    assert at(LayerAnswer(features=None)).outcome is Outcome.CHECK
    # Not asked at all: unknown, a condition.
    assert finding(run(place), "phcma-39-preventive").outcome is Outcome.CHECK


def test_the_layers_read_are_those_of_the_rules_that_apply() -> None:
    assert layers_read(SETTINGS, "ES040", "ES-CM") == [
        "public-water-domain",
        "guadiana-abstraction-limits",
    ]
    assert "andalusia-preventive-control" in layers_read(SETTINGS, "ES060", "ES-AN")
    assert layers_read(SETTINGS, None, None) == ["public-water-domain"]


# ── Distances, at their limits ───────────────────────────────────────────────────────


def _distance(place: PlaceFacts, rule: str = "phg-50-3-distance") -> Finding:
    return finding(run(place), rule)


@pytest.mark.parametrize(
    ("metres", "outcome"), [(499.9, Outcome.BLOCKS), (500.0, Outcome.CLEAR), (500.1, Outcome.CLEAR)]
)
def test_the_exclusion_circle_is_a_minimum_distance(metres: float, outcome: Outcome) -> None:
    result = _distance(
        facts(water_point=Distance(metres=metres, reach_m=10000, method="inventory"))
    )
    assert result.outcome is outcome
    assert result.values["minimum"] == 500.0


@pytest.mark.parametrize(
    ("volume", "status", "minimum"),
    [
        (500, GOOD, 50.0),
        (1000, GOOD, 50.0),
        (4000, GOOD, 275.0),
        (7000, GOOD, 500.0),
        (2000, POOR, 275.0),
        (3000, POOR, 500.0),
        (6000, POOR, 500.0),
    ],
)
def test_the_guadalquivir_circle_grows_with_the_volume(
    volume: float, status: str, minimum: float
) -> None:
    result = _distance(facts(volume_m3_year=volume, body=body(status=status)))
    assert result.values["minimum"] == pytest.approx(minimum, abs=0.1)


def test_with_the_status_unknown_the_strictest_distance_is_used() -> None:
    result = _distance(facts(volume_m3_year=2000, body=body(status=None)))
    assert result.values["minimum"] == 275.0
    assert result.values["assumed"] == "strictest"


@pytest.mark.parametrize(
    ("volume", "status", "minimum"),
    [(1500, GOOD, 50.0), (1501, GOOD, 100.0), (1000, None, 100.0)],
)
def test_the_andalusian_mediterranean_distances(
    volume: float, status: str | None, minimum: float
) -> None:
    place = facts(body=body("ES060", status=status), volume_m3_year=volume)
    assert _distance(place, "phcma-53-5-distance").values["minimum"] == minimum


def test_outside_bodies_and_in_poor_ones_the_mediterranean_plan() -> None:
    outside = _distance(facts(body=None, region="ES-AN"), "rdph-87-2-distance")
    # Outside every body the district is unknown: the national distance applies.
    assert outside.values["minimum"] == 100.0
    poor = _distance(facts(body=body("ES060", status=POOR)), "phcma-53-5-distance")
    assert (poor.outcome, poor.message) == (Outcome.CHECK, "distance_by_authorisation")


@pytest.mark.parametrize(
    ("flow", "minimum"), [(None, 100.0), (0.1, 20.0), (0.15, 100.0), (1.0, 100.0)]
)
def test_the_national_distance_depends_on_the_flow(flow: float | None, minimum: float) -> None:
    # The Júcar plan sets no distance of its own: the national one applies.
    place = facts(body=body("ES080"), region="ES-VC", max_flow_l_s=flow)
    assert _distance(place, "rdph-87-2-distance").values["minimum"] == minimum


@pytest.mark.parametrize(
    ("point", "outcome", "message"),
    [
        (None, Outcome.CHECK, "distance_not_measured"),
        (Distance(None, 10000, "inventory"), Outcome.CLEAR, "no_point_within"),
        (Distance(None, 50, "inventory"), Outcome.CHECK, "distance_not_measured"),
        (Distance(99.9, 10000, "inventory"), Outcome.BLOCKS, "too_close_to_point"),
        (Distance(100.0, 10000, "inventory"), Outcome.CLEAR, "point_far_enough"),
    ],
)
def test_a_distance_never_passes_unmeasured(
    point: Distance | None, outcome: Outcome, message: str
) -> None:
    result = _distance(
        facts(body=body("ES080"), region="ES-VC", water_point=point), "rdph-87-2-distance"
    )
    assert (result.outcome, result.message) == (outcome, message)


@pytest.mark.parametrize(
    ("official", "channel", "outcome", "message"),
    [
        (({"Tipo Zona": "Zona de Policía"},), None, Outcome.AUTHORISATION, "inside_water_domain"),
        ((), None, Outcome.CHECK, "channel_not_measured"),
        ((), Distance(99.9, 2000, "terrain"), Outcome.AUTHORISATION, "near_channel"),
        ((), Distance(100.0, 2000, "terrain"), Outcome.CLEAR, "far_from_channel"),
        ((), Distance(None, 2000, "terrain"), Outcome.CLEAR, "no_channel_within"),
        ((), Distance(None, 60, "terrain"), Outcome.CHECK, "channel_not_measured"),
        (None, Distance(300, 2000, "terrain"), Outcome.CLEAR, "far_from_channel"),
        (
            ({"Tipo Zona": "Otra"},),
            Distance(300, 2000, "terrain"),
            Outcome.CLEAR,
            "far_from_channel",
        ),
    ],
)
def test_the_zona_de_policia_official_first_then_the_terrain(
    official: tuple[dict[str, str], ...] | None,
    channel: Distance | None,
    outcome: Outcome,
    message: str,
) -> None:
    place = facts(layers={"public-water-domain": LayerAnswer(features=official)}, channel=channel)
    result = finding(run(place), "rdph-87-4-policia")
    assert (result.outcome, result.message) == (outcome, message)
    if official is None:
        assert result.values["official"] == "unread"


@pytest.mark.parametrize(
    ("answer", "outcome", "message"),
    [
        (
            LayerAnswer(features=({"zona": "11.1.2", "nom_objeto": "Laguna"},)),
            Outcome.BLOCKS,
            "inside_zone",
        ),
        (LayerAnswer(features=()), Outcome.CLEAR, "outside_zone"),
        (LayerAnswer(features=(), covers=False), Outcome.NOT_APPLICABLE, "zone_not_here"),
        (LayerAnswer(features=None), Outcome.CHECK, "zone_unknown"),
    ],
)
def test_a_closed_perimeter_of_the_guadiana_blocks(
    answer: LayerAnswer, outcome: Outcome, message: str
) -> None:
    place = facts(
        body=body("ES040"), region="ES-CM", layers={"guadiana-abstraction-limits": answer}
    )
    status = run(place)
    result = finding(status, "phgn-11-1-perimeters")
    assert (result.outcome, result.message) == (outcome, message)
    if outcome is Outcome.BLOCKS:
        assert result.values["zone"] == "Laguna"
        # A blocking rule decides, whatever is not loaded.
        assert status.state is LegalState.PROBABLY_NOT_ALLOWED
    else:
        assert status.state is LegalState.CONDITIONS_APPLY


def test_the_duero_zoning_blocks_only_its_closed_zones() -> None:
    def at(value: str, volume: float = 7001) -> Finding:
        answer = LayerAnswer(features=({"f_valoracion_final": value, "nombre": "Sector"},))
        place = facts(
            body=body("ES020"),
            region="ES-CL",
            layers={"duero-groundwater-zoning": answer},
            volume_m3_year=volume,
        )
        return finding(run(place), "phd-33-zoning")

    assert at("Zona No Autorizada").outcome is Outcome.BLOCKS
    # The zoning binds new concessions: a small-use well of 7,000 m³/year is outside it.
    small = at("Zona No Autorizada", 7000)
    assert (small.outcome, small.message) == (Outcome.NOT_APPLICABLE, "only_concessions")
    assert small.values == {"limit": 7000.0}
    other = at("Zona con limitaciones específicas")
    assert (other.outcome, other.message) == (Outcome.CHECK, "zone_other")
    assert other.values == {"zone": "Sector", "value": "Zona con limitaciones específicas"}


# ── Each basin plan's own rules ──────────────────────────────────────────────────────


def at(district: str, region: str, rule: str, **changes: Any) -> Finding:
    """The finding of one rule at a place of a district, with the planned well changed."""
    place: dict[str, Any] = {"body": body(district, code=changes.pop("code", None))}
    if "status" in changes:
        place["body"] = body(district, status=changes.pop("status"), code=place["body"].code)
    return finding(run(facts(region=region, **place, **changes)), rule)


def outcome_at(district: str, region: str, rule: str, **changes: Any) -> Outcome | None:
    """The rule's outcome at the place; None where the rule does not apply at all."""
    code = changes.pop("code", None)
    status = run(facts(body=body(district, code=code), region=region, **changes))
    return next((f.outcome for f in status.findings if f.rule_id == rule), None)


def applies(status: LegalStatus, rule_id: str) -> bool:
    return any(f.rule_id == rule_id for f in status.findings)


def minimum(result: Finding) -> float:
    return float(result.values["minimum"])


@pytest.mark.parametrize(
    ("volume", "flow", "expected"),
    [
        (3649, 0.14, 20.0),
        (3650, 0.14, 100.0),
        (3649, 0.15, 50.0),
        (3649, 0.99, 50.0),
        (3649, 1.0, 100.0),
        (3649, None, 100.0),
    ],
)
def test_the_mino_sil_distance(volume: float, flow: float | None, expected: float) -> None:
    result = at("ES010", "ES-GA", "phms-32-distance", volume_m3_year=volume, max_flow_l_s=flow)
    assert minimum(result) == expected


@pytest.mark.parametrize(
    ("volume", "expected"),
    [(999, 100.0), (1000, 250.0), (7000, 250.0), (25750, 325.0), (44500, 400.0), (90000, 400.0)],
)
def test_the_tajo_distance_grows_with_the_volume(volume: float, expected: float) -> None:
    assert minimum(at("ES030", "ES-MD", "pht-22-distance", volume_m3_year=volume)) == expected


@pytest.mark.parametrize(
    ("code", "rule", "volume", "expected"),
    [
        ("ES030MSBT030-004", "pht-22-distance-torrelaguna", 82000, 325.0),
        ("ES030MSBT030-010", "pht-22-distance-madrid", 32000, 325.0),
        ("ES030MSBT030-010", "pht-22-distance-madrid", 57000, 400.0),
        ("ES030MSBT030-018", "pht-22-distance-south", 22000, 325.0),
    ],
)
def test_the_tajo_bodies_with_their_own_scale(
    code: str, rule: str, volume: float, expected: float
) -> None:
    status = run(facts(body=body(code=code), region="ES-MD", volume_m3_year=volume))
    assert minimum(finding(status, rule)) == expected
    assert finding(status, "pht-22-distance").values == {"by": rule}
    # Elsewhere in the basin the body's own scale does not apply.
    assert not applies(run(facts(body=body("ES030"), region="ES-MD")), rule)


@pytest.mark.parametrize(
    ("code", "volume", "outcome"),
    [
        ("ES030MSBT030-011", 7001, Outcome.AUTHORISATION),
        ("ES030MSBT030-011", 7000, Outcome.NOT_APPLICABLE),
        ("ES030MSBT030-001", 7001, None),
    ],
)
def test_the_tajo_bodies_at_risk_need_an_authorisation_for_a_concession(
    code: str, volume: float, outcome: Outcome | None
) -> None:
    rule = "pht-35-at-risk-zones"
    assert outcome_at("ES030", "ES-MD", rule, code=code, volume_m3_year=volume) is outcome


@pytest.mark.parametrize(
    ("code", "volume", "outcome", "message"),
    [
        ("ES040MSBT000030606", 7001, Outcome.BLOCKS, "no_new_concessions_here"),
        ("ES040MSBT000030606", 7000, Outcome.NOT_APPLICABLE, "only_concessions"),
    ],
)
def test_the_guadiana_bodies_closed_to_new_concessions(
    code: str, volume: float, outcome: Outcome, message: str
) -> None:
    status = run(facts(body=body(code=code), region="ES-CM", volume_m3_year=volume))
    result = finding(status, "phgn-31-1-no-concessions")
    assert (result.outcome, result.message) == (outcome, message)
    if outcome is Outcome.BLOCKS:
        assert status.state is LegalState.PROBABLY_NOT_ALLOWED
    other = "ES040MSBT000030601"
    assert outcome_at("ES040", "ES-CM", "phgn-31-1-no-concessions", code=other) is None


def test_the_segura_admits_no_new_volumes_above_the_small_use() -> None:
    blocked = at("ES070", "ES-MC", "phs-45-3-no-new-volumes", volume_m3_year=7001)
    assert (blocked.outcome, blocked.message) == (Outcome.BLOCKS, "no_new_concessions_here")
    small = at("ES070", "ES-MC", "phs-45-3-no-new-volumes")
    assert small.outcome is Outcome.NOT_APPLICABLE
    risk = finding(run(facts(body=body("ES070", at_risk=True), region="ES-MC")), "phs-49-1-at-risk")
    assert risk.outcome is Outcome.AUTHORISATION
    assert minimum(at("ES070", "ES-MC", "phs-46-1-distance")) == 100.0


def test_the_jucar_small_wells_and_poor_bodies() -> None:
    small = at("ES080", "ES-VC", "phj-49-4-small-wells")
    assert small.outcome is Outcome.AUTHORISATION
    big = at("ES080", "ES-VC", "phj-49-4-small-wells", volume_m3_year=7001)
    assert (big.outcome, big.message) == (Outcome.NOT_APPLICABLE, "above_small_use")
    poor = at("ES080", "ES-VC", "phj-45-6-no-concessions", status=POOR, volume_m3_year=7001)
    assert poor.outcome is Outcome.BLOCKS
    good = at("ES080", "ES-VC", "phj-45-6-no-concessions", volume_m3_year=7001)
    assert good.outcome is Outcome.CLEAR


@pytest.mark.parametrize(
    ("code", "volume", "rule", "expected"),
    [
        ("ES091MSBT067", 7000, "phe-45-4-distance", 200.0),
        ("ES091MSBT067", 7001, "phe-45-4-distance", 400.0),
        ("ES091MSBT001", 7000, "phe-25-2-distance", 100.0),
    ],
)
def test_the_ebro_distances(code: str, volume: float, rule: str, expected: float) -> None:
    status = run(facts(body=body(code=code), region="ES-AR", volume_m3_year=volume))
    assert minimum(finding(status, rule)) == expected


def test_the_ebro_closes_one_body_to_new_concessions() -> None:
    closed = at(
        "ES091", "ES-AR", "phe-45-2-no-concessions", code="ES091MSBT079", volume_m3_year=8000
    )
    assert closed.outcome is Outcome.BLOCKS
    other = outcome_at("ES091", "ES-AR", "phe-45-2-no-concessions", volume_m3_year=8000)
    assert other is None


@pytest.mark.parametrize(
    ("code", "outcome"),
    [
        # MITECO's layer splits some bodies: ES100MSBT18 covers ES100MSBT18_01.
        ("ES100MSBT18_01", Outcome.AUTHORISATION),
        ("ES100MSBT18", Outcome.AUTHORISATION),
        ("ES100MSBT180", None),
        ("ES100MSBT36", None),
    ],
)
def test_the_catalan_bodies_that_need_an_authorisation(code: str, outcome: Outcome | None) -> None:
    assert outcome_at("ES100", "ES-CT", "phcat-42-5-authorisation", code=code) is outcome


@pytest.mark.parametrize(
    ("district", "rule"),
    [
        ("ES017", "phco-34-3-poor-body"),
        ("ES018", "phcoc-34-3-poor-body"),
        ("ES100", "phcat-41-poor-body"),
    ],
)
def test_a_poor_body_needs_an_authorisation(district: str, rule: str) -> None:
    region = DISTRICT_REGION[district]
    assert at(district, region, rule, status=POOR).outcome is Outcome.AUTHORISATION
    assert at(district, region, rule).outcome is Outcome.CLEAR


@pytest.mark.parametrize(
    ("flow", "volume", "expected"),
    [
        (0.15, 7000, 20.0),
        (0.16, 7000, 100.0),
        (0.5, 7000, 100.0),
        (1.0, 7000, 200.0),
        (2.0, 7000, 350.0),
        (5.0, 7000, 500.0),
        (None, 7000, 200.0),
    ],
)
def test_the_balearic_distance_grows_with_the_flow(
    flow: float | None, volume: float, expected: float
) -> None:
    result = at("ES110", "ES-IB", "phib-113-7-distance", max_flow_l_s=flow, volume_m3_year=volume)
    assert minimum(result) == expected


def test_above_five_litres_a_second_the_balearic_distance_is_left_to_a_study() -> None:
    result = at("ES110", "ES-IB", "phib-113-7-distance", max_flow_l_s=5.1, volume_m3_year=8000)
    assert (result.outcome, result.message) == (Outcome.CHECK, "distance_by_authorisation")


@pytest.mark.parametrize(
    ("district", "small", "limit"),
    [("ES120", "phgc-73-small-use", 1500), ("ES124", "phtf-small-use", 2000)],
)
def test_the_canary_islands_small_use_and_concessions(
    district: str, small: str, limit: float
) -> None:
    concession = small.split("-")[0] + ("-76-concession" if district == "ES120" else "-concession")
    status = run(facts(body=body(district), region="ES-CN", volume_m3_year=limit))
    assert finding(status, small).outcome is Outcome.AUTHORISATION
    assert finding(status, concession).outcome is Outcome.NOT_APPLICABLE
    assert finding(status, "lac-73-title").outcome is Outcome.AUTHORISATION
    above = run(facts(body=body(district), region="ES-CN", volume_m3_year=limit + 1))
    assert finding(above, small).outcome is Outcome.NOT_APPLICABLE
    assert finding(above, concession).outcome is Outcome.AUTHORISATION


@pytest.mark.parametrize(("district", "prefix"), [("ES150", "phce"), ("ES160", "phml")])
def test_ceuta_and_melilla_bind_only_concessions(district: str, prefix: str) -> None:
    region = DISTRICT_REGION[district]
    small = run(facts(body=body(district), region=region))
    assert finding(small, f"{prefix}-21-1-supply-first").outcome is Outcome.NOT_APPLICABLE
    assert finding(small, f"{prefix}-21-2-distance").outcome is Outcome.NOT_APPLICABLE
    big = run(facts(body=body(district), region=region, volume_m3_year=7001))
    assert finding(big, f"{prefix}-21-1-supply-first").outcome is Outcome.AUTHORISATION
    assert minimum(finding(big, f"{prefix}-21-2-distance")) == 100.0


@pytest.mark.parametrize("district", ["ES063", "ES064"])
def test_the_other_andalusian_districts_follow_the_mediterranean_plan(district: str) -> None:
    prefix = "phgb" if district == "ES063" else "phtop"
    assert minimum(at(district, "ES-AN", f"{prefix}-53-5-distance", volume_m3_year=1500)) == 50.0
    assert minimum(at(district, "ES-AN", f"{prefix}-53-5-distance", volume_m3_year=1501)) == 100.0
    risk = run(facts(body=body(district, at_risk=True)))
    assert finding(risk, f"{prefix}-53-1-authorisation").outcome is Outcome.AUTHORISATION


def test_drilling_needs_the_mining_authority_everywhere() -> None:
    for place in (facts(), facts(body=None), facts(body=body("ES014"), region="ES-GA")):
        assert finding(run(place), "rgnbsm-108-mining").outcome is Outcome.AUTHORISATION


# ── New rule fields: their checks ────────────────────────────────────────────────────


def test_a_where_names_something_and_a_volume_range_is_not_empty() -> None:
    raw = SETTINGS.model_dump()
    with pytest.raises(ValidationError, match="names districts, bodies or both"):
        Where.model_validate({})
    rule = next(r for r in raw["rules"] if r["id"] == "phj-49-4-small-wells")
    rule["applies_above_m3"] = 7000
    with pytest.raises(ValidationError, match="volume range is empty"):
        LegalSettings.model_validate(raw)


# ── Every district ───────────────────────────────────────────────────────────────────

# A region each district lies in (a place of it); Ceuta and Melilla are their own.
DISTRICT_REGION = {
    "ES010": "ES-GA", "ES014": "ES-GA", "ES017": "ES-PV", "ES018": "ES-AS", "ES020": "ES-CL",
    "ES030": "ES-MD", "ES040": "ES-EX", "ES050": "ES-AN", "ES060": "ES-AN", "ES063": "ES-AN",
    "ES064": "ES-AN", "ES070": "ES-MC", "ES080": "ES-VC", "ES091": "ES-AR", "ES100": "ES-CT",
    "ES110": "ES-IB", "ES120": "ES-CN", "ES122": "ES-CN", "ES123": "ES-CN", "ES124": "ES-CN",
    "ES125": "ES-CN", "ES126": "ES-CN", "ES127": "ES-CN", "ES150": "ES-CE", "ES160": "ES-ML",
}  # fmt: skip


def test_every_district_of_spain_is_listed() -> None:
    assert set(SETTINGS.areas.districts) == set(DISTRICT_REGION)
    assert set(DISTRICT_REGION.values()) <= set(SETTINGS.areas.regions)
    assert len(SETTINGS.areas.regions) == 19


@pytest.mark.parametrize(("district", "region"), sorted(DISTRICT_REGION.items()))
def test_a_place_in_every_district(district: str, region: str) -> None:
    status = run(facts(body=body(district), region=region))
    assert status.authority is not None
    assert status.authority.district == district
    assert status.authority.name == SETTINGS.areas.districts[district].authority
    assert status.disclaimer.startswith("Guidance, not legal advice")
    assert status.findings, "national rules apply everywhere"
    assert {"rdph-85-notice", "rdph-87-4-policia"} <= {f.rule_id for f in status.findings}
    plan = SETTINGS.areas.districts[district].plan
    law = SETTINGS.areas.regions[region].water_law
    if plan.state == "loaded" and law.state == "loaded":
        assert status.state in {LegalState.CONDITIONS_APPLY, LegalState.NO_BLOCKING_RULE}
        assert status.not_loaded == ()
    else:
        assert status.state is LegalState.RULES_NOT_LOADED
        scopes = {n.scope for n in status.not_loaded}
        assert (NotLoadedScope.BASIN_PLAN in scopes) == (plan.state != "loaded")
        assert (NotLoadedScope.REGIONAL_LAW in scopes) == (law.state != "loaded")
        assert all(n.reason["en"] and n.reason["es"] for n in status.not_loaded)


def test_a_district_whose_plan_was_not_read_says_so_and_why() -> None:
    status = run(facts(body=body("ES014"), region="ES-GA"))
    assert status.state is LegalState.RULES_NOT_LOADED
    (plan,) = status.not_loaded
    assert plan.scope is NotLoadedScope.BASIN_PLAN
    assert plan.area == "ES014"
    assert plan.reason == SETTINGS.areas.districts["ES014"].plan.reason.model_dump()
    assert status.reason == plan.reason["en"]


def test_the_district_comes_from_the_body_code() -> None:
    assert district_of(SETTINGS, body("ES124")) == "ES124"
    assert district_of(SETTINGS, None) is None
    odd = BodyStatus(code="X1", name="n", quantitative_status=None, declared_at_risk=None)
    assert district_of(SETTINGS, odd) is None


@pytest.mark.parametrize(
    ("place", "reason"),
    [
        (facts(body=None), "No groundwater body"),
        (facts(body=None, bodies_read=False), "could not be read"),
        (
            facts(
                body=BodyStatus(
                    code="ES999MSBT1", name="n", quantitative_status=GOOD, declared_at_risk=False
                )
            ),
            "not in the legal filter",
        ),
    ],
)
def test_an_unknown_district_is_rules_not_loaded(place: PlaceFacts, reason: str) -> None:
    status = run(place)
    assert status.state is LegalState.RULES_NOT_LOADED
    assert status.authority is None
    (district, *_) = status.not_loaded
    assert district.scope is NotLoadedScope.DISTRICT
    assert reason in district.reason["en"]


def test_an_unknown_region_is_rules_not_loaded() -> None:
    for region in (None, "ES-XX"):
        status = run(facts(region=region))
        assert status.state is LegalState.RULES_NOT_LOADED
        assert any(n.scope is NotLoadedScope.REGIONAL_LAW for n in status.not_loaded)


def test_every_output_carries_the_disclaimer_and_sources() -> None:
    places = [facts(), facts(body=None), facts(region="ES-GA", body=body("ES014"))]
    for place in places:
        status = run(place)
        assert status.disclaimer == SETTINGS.texts.disclaimer
        for result in status.findings:
            assert result.source.url.startswith("https://")
            assert result.source.checked >= result.source.published
            assert result.title["en"]
            assert result.title["es"]
