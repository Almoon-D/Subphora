# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Field records (MASTER_PLAN §4.7, hard rule 5): the record's rules, the idempotent
upsert of ``POST /api/field/observations``, the files of ``PUT …/media``, every way they
are refused, a store that fails, and ``subphora field summary``. Every place is synthetic."""

import asyncio
import hashlib
import json
import sqlite3
import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

import subphora.config
from subphora.__main__ import main
from subphora.api import create_app
from subphora.api.map import map_config
from subphora.config import Settings
from subphora.domain.field import FieldSummary, Observation, ObservationKind
from subphora.services.field import FieldService
from tests.support import fast_settings, signed_in

PHOTO = b"\xff\xd8\xff\xe0 synthetic jpeg bytes"
VOICE = b"\x1aE\xdf\xa3 synthetic webm bytes"


@pytest.fixture
def settings() -> Settings:
    return fast_settings()


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"field mode asked the network: {request.url.host}")


@asynccontextmanager
async def serve(settings: Settings, root: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        settings,
        root=root,
        transport=httpx.MockTransport(_no_network),
        executor=ThreadPoolExecutor(max_workers=1),
    )
    async with app.router.lifespan_context(app), signed_in(app, settings, root) as client:
        yield client


def new_id() -> str:
    return str(uuid.uuid7())


FIX = {
    "longitude": -3.61,
    "latitude": 39.07,
    "accuracy_m": 6.5,
    "altitude_m": 620.0,
    "altitude_accuracy_m": 10.0,
    "heading_deg": 90.0,
    "speed_m_s": 1.2,
    "fixed_at": "2026-11-26T10:00:00Z",
}
TARGET = {"area_id": "0123456789abcdef", "rank": 1, "longitude": -3.6105, "latitude": 39.0702}


def note(text: str = "Afloramiento de calizas junto al camino", **extra: Any) -> dict[str, Any]:
    return {
        "id": new_id(),
        "kind": "note",
        "recorded_at": "2026-11-26T10:00:05Z",
        "position": FIX,
        "target": TARGET,
        "text": text,
        **extra,
    }


def media_record(kind: str, content: bytes, content_type: str) -> dict[str, Any]:
    return {
        "id": new_id(),
        "kind": kind,
        "recorded_at": "2026-11-26T10:01:00Z",
        "position": None,
        "target": None,
        "text": None,
        "media": {
            "content_type": content_type,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }


def track_point(track: str) -> dict[str, Any]:
    return {
        "id": new_id(),
        "kind": "track_point",
        "recorded_at": "2026-11-26T10:02:00Z",
        "position": FIX,
        "target": None,
        "track_id": track,
    }


def batch(*records: dict[str, Any]) -> dict[str, Any]:
    return {"observations": list(records)}


def outcomes(answer: httpx.Response) -> list[str]:
    return [result["outcome"] for result in answer.json()["results"]]


# The record's own rules.


def test_a_record_needs_a_uuidv7_in_canonical_form() -> None:
    for wrong in (str(uuid.uuid4()), new_id().upper(), "not-a-uuid", new_id().replace("-", "")):
        with pytest.raises(ValidationError):
            Observation.model_validate(note(id=wrong))
    assert Observation.model_validate(note()).kind is ObservationKind.NOTE


def test_times_are_kept_in_utc() -> None:
    madrid = timezone(timedelta(hours=1))
    record = note(recorded_at=datetime(2026, 11, 26, 11, 0, tzinfo=madrid).isoformat())
    observation = Observation.model_validate(record)
    assert observation.recorded_at == datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
    assert observation.recorded_at.tzinfo is UTC
    assert observation.position is not None
    assert observation.position.fixed_at.tzinfo is UTC
    with pytest.raises(ValidationError):
        Observation.model_validate(note(recorded_at="2026-11-26T10:00:05"))


@pytest.mark.parametrize(
    "record",
    [
        note(text="   "),
        note(text=None),
        note(media=media_record("photo", PHOTO, "image/jpeg")["media"]),
        note(track_id=new_id()),
        {**media_record("photo", PHOTO, "image/jpeg"), "media": None},
        media_record("photo", VOICE, "audio/webm"),
        media_record("voice", PHOTO, "image/jpeg"),
        {**track_point(new_id()), "position": None},
        {**track_point(new_id()), "track_id": None},
        {**track_point(new_id()), "text": "a point says nothing"},
        {**track_point(new_id()), "track_id": str(uuid.uuid4())},
        note(position={**FIX, "accuracy_m": 0}),
        note(position={**FIX, "heading_deg": 360}),
        note(kind="resistivity"),
        note(target={**TARGET, "area_id": "parcel-1"}),
    ],
    ids=[
        "blank note",
        "note without text",
        "note with a file",
        "note on a track",
        "photo without its file",
        "photo that is audio",
        "voice memo that is an image",
        "track point without position",
        "track point without track",
        "track point with text",
        "track that is not a UUIDv7",
        "accuracy of zero",
        "heading of 360",
        "an instrument kind",
        "target without a map id",
    ],
)
def test_a_record_that_breaks_its_kind_is_refused(record: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Observation.model_validate(record)


# The upsert.


async def test_a_retried_batch_stores_each_record_once(settings: Settings, tmp_path: Path) -> None:
    track = new_id()
    records = [
        note(),
        media_record("photo", PHOTO, "image/jpeg"),
        track_point(track),
        track_point(track),
    ]
    async with serve(settings, tmp_path) as client:
        first = await client.post("/api/field/observations", json=batch(*records))
        again = await client.post("/api/field/observations", json=batch(*records))
        # A batch cut short and sent again with the next records: the old ones are duplicates.
        later = note("Pozo abandonado, brocal de piedra")
        mixed = await client.post("/api/field/observations", json=batch(records[0], later))
    assert first.status_code == again.status_code == mixed.status_code == 200
    assert outcomes(first) == ["created"] * 4
    assert outcomes(again) == ["duplicate"] * 4
    assert outcomes(mixed) == ["duplicate", "created"]
    assert [r["id"] for r in first.json()["results"]] == [r["id"] for r in records]
    summary = await _summary(settings, tmp_path)
    assert summary == {"note": 2, "photo": 1, "voice": 0, "track_point": 2, "tracks": 1}


async def test_a_different_record_under_a_stored_id_is_a_conflict_and_changes_nothing(
    settings: Settings, tmp_path: Path
) -> None:
    original = note("Primera versión")
    changed = {**original, "text": "Otra cosa"}
    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(original))
        answer = await client.post("/api/field/observations", json=batch(changed))
        retried = await client.post("/api/field/observations", json=batch(original))
    assert outcomes(answer) == ["conflict"]
    assert outcomes(retried) == ["duplicate"]
    database = tmp_path / settings.field.store.database
    stored = _stored_bodies(database)
    assert [json.loads(body)["text"] for body in stored] == ["Primera versión"]


async def test_the_same_id_twice_in_one_batch_is_stored_once(
    settings: Settings, tmp_path: Path
) -> None:
    record = note()
    async with serve(settings, tmp_path) as client:
        answer = await client.post("/api/field/observations", json=batch(record, record))
    assert outcomes(answer) == ["created", "duplicate"]


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        (b"not json", 400, "invalid_observation"),
        (json.dumps({"observations": []}).encode(), 400, "invalid_observation"),
        (json.dumps(batch(note(text=" "))).encode(), 400, "invalid_observation"),
        (json.dumps(batch(note("x" * 5001))).encode(), 422, "note_too_long"),
        (
            json.dumps(batch(media_record("photo", PHOTO, "image/gif"))).encode(),
            415,
            "media_type",
        ),
        (
            json.dumps(
                batch(
                    {
                        **media_record("photo", PHOTO, "image/jpeg"),
                        "media": {
                            "content_type": "image/jpeg",
                            "size_bytes": 31457281,
                            "sha256": "0" * 64,
                        },
                    }
                )
            ).encode(),
            413,
            "media_too_large",
        ),
        (json.dumps(batch(*[note() for _ in range(51)])).encode(), 413, "too_many"),
    ],
    ids=["not json", "empty", "blank note", "long note", "gif", "huge file", "51 records"],
)
async def test_a_refused_batch_stores_nothing(
    settings: Settings, tmp_path: Path, body: bytes, status: int, code: str
) -> None:
    async with serve(settings, tmp_path) as client:
        answer = await client.post(
            "/api/field/observations", content=body, headers={"content-type": "application/json"}
        )
    assert answer.status_code == status
    assert answer.json()["code"] == code
    # The detail says where, never what a record holds.
    assert "Afloramiento" not in answer.text
    assert sum((await _summary(settings, tmp_path)).values()) == 0


async def test_a_store_that_cannot_open_answers_503_so_the_browser_retries(
    settings: Settings, tmp_path: Path
) -> None:
    (tmp_path / settings.field.store.database).mkdir(parents=True)
    async with serve(settings, tmp_path) as client:
        answer = await client.post("/api/field/observations", json=batch(note()))
    assert answer.status_code == 503
    assert answer.json()["code"] == "store_unavailable"


async def test_a_failure_mid_batch_stores_none_of_it(settings: Settings, tmp_path: Path) -> None:
    """The batch is one transaction: a database that fails half-way keeps nothing."""
    database = tmp_path / settings.field.store.database
    first = note()
    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(first))
        # A trigger that fails on the second insert of the next batch.
        _execute(
            database,
            "CREATE TRIGGER fail_second BEFORE INSERT ON observations"
            " WHEN (SELECT COUNT(*) FROM observations) >= 2"
            " BEGIN SELECT RAISE(ABORT, 'disk full'); END",
        )
        answer = await client.post("/api/field/observations", json=batch(note(), note()))
        _execute(database, "DROP TRIGGER fail_second")
        retried = await client.post("/api/field/observations", json=batch(first))
    assert answer.status_code == 503
    assert len(_stored_bodies(database)) == 1
    assert outcomes(retried) == ["duplicate"]


# The files.


async def test_a_file_is_stored_once_after_its_record(settings: Settings, tmp_path: Path) -> None:
    photo = media_record("photo", PHOTO, "image/jpeg")
    voice = media_record("voice", VOICE, "audio/webm")
    path = f"/api/field/observations/{photo['id']}/media"
    async with serve(settings, tmp_path) as client:
        early = await client.put(path, content=PHOTO, headers={"content-type": "image/jpeg"})
        await client.post("/api/field/observations", json=batch(photo, voice))
        stored = await client.put(path, content=PHOTO, headers={"content-type": "image/jpeg"})
        again = await client.put(path, content=PHOTO, headers={"content-type": "image/jpeg"})
        # MediaRecorder names its codec: the type's parameters are dropped.
        memo = await client.put(
            f"/api/field/observations/{voice['id']}/media",
            content=VOICE,
            headers={"content-type": "audio/webm;codecs=opus"},
        )
    assert early.status_code == 404
    assert early.json()["code"] == "unknown_observation"
    assert stored.status_code == 201
    assert stored.json() == {"id": photo["id"], "outcome": "created"}
    assert again.status_code == 200
    assert again.json()["outcome"] == "duplicate"
    assert memo.status_code == 201
    media = tmp_path / settings.field.store.media_dir
    assert (media / f"{photo['id']}.jpg").read_bytes() == PHOTO
    assert (media / f"{voice['id']}.webm").read_bytes() == VOICE
    assert sorted(p.name for p in media.iterdir()) == sorted(
        [f"{photo['id']}.jpg", f"{voice['id']}.webm"]
    )
    counts = (await _read_summary(settings, tmp_path)).kinds
    assert {c.kind.value: c.with_media for c in counts} == {
        "note": 0,
        "photo": 1,
        "voice": 1,
        "track_point": 0,
    }


@pytest.mark.parametrize(
    ("content", "content_type", "status", "code"),
    [
        (PHOTO, "image/png", 415, "media_type"),
        (PHOTO[:-1], "image/jpeg", 400, "media_mismatch"),
        (PHOTO[:-1] + b"!", "image/jpeg", 400, "media_mismatch"),
        (b"x" * 31457281, "image/jpeg", 413, "media_too_large"),
    ],
    ids=["other type", "truncated", "corrupted", "too large"],
)
async def test_a_file_that_is_not_the_declared_one_is_refused(
    settings: Settings, tmp_path: Path, content: bytes, content_type: str, status: int, code: str
) -> None:
    photo = media_record("photo", PHOTO, "image/jpeg")
    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(photo))
        answer = await client.put(
            f"/api/field/observations/{photo['id']}/media",
            content=content,
            headers={"content-type": content_type},
        )
    assert answer.status_code == status
    assert answer.json()["code"] == code
    assert not (tmp_path / settings.field.store.media_dir).exists()


async def test_a_file_streamed_past_the_limit_is_refused(
    settings: Settings, tmp_path: Path
) -> None:
    """No Content-Length (a chunked upload): the server stops reading at the limit."""
    photo = media_record("photo", PHOTO, "image/jpeg")
    limit = settings.field.media.max_bytes

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(limit // 1_000_000 + 2):
            yield b"x" * 1_000_000

    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(photo))
        answer = await client.put(
            f"/api/field/observations/{photo['id']}/media",
            content=chunks(),
            headers={"content-type": "image/jpeg"},
        )
    assert answer.status_code == 413


async def test_a_record_without_a_file_takes_none(settings: Settings, tmp_path: Path) -> None:
    record = note()
    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(record))
        answer = await client.put(
            f"/api/field/observations/{record['id']}/media",
            content=PHOTO,
            headers={"content-type": "image/jpeg"},
        )
        not_v7 = await client.put(
            f"/api/field/observations/{uuid.uuid4()}/media",
            content=PHOTO,
            headers={"content-type": "image/jpeg"},
        )
    assert answer.status_code == 422
    assert answer.json()["code"] == "no_media"
    assert not_v7.status_code == 422


async def test_a_file_that_cannot_be_written_leaves_no_trace_and_can_be_retried(
    settings: Settings, tmp_path: Path
) -> None:
    photo = media_record("photo", PHOTO, "image/jpeg")
    path = f"/api/field/observations/{photo['id']}/media"
    media = tmp_path / settings.field.store.media_dir
    async with serve(settings, tmp_path) as client:
        await client.post("/api/field/observations", json=batch(photo))
        media.parent.mkdir(parents=True, exist_ok=True)
        media.write_text("a file where the folder should be")
        failed = await client.put(path, content=PHOTO, headers={"content-type": "image/jpeg"})
        media.unlink()
        retried = await client.put(path, content=PHOTO, headers={"content-type": "image/jpeg"})
    assert failed.status_code == 503
    assert retried.status_code == 201
    assert [p.name for p in media.iterdir()] == [f"{photo['id']}.jpg"]


# The configuration the browser reads, and the summary.


def test_the_map_config_carries_field_mode(settings: Settings) -> None:
    field = map_config(settings).field
    assert field.at_spot_m == settings.field.at_spot_m
    assert field.sync_batch_size == settings.field.sync.batch_size
    assert "audio/webm" in field.media_types
    assert "image/jpeg" in field.media_types


def test_media_types_need_both_families(config_dir: Path) -> None:
    path = config_dir / "defaults" / "field.yaml"
    text = path.read_text()
    path.write_text(text.replace("    audio/webm: webm\n", "    audio/webm: WEBM!\n"))
    with pytest.raises(ValidationError, match="extension"):
        fast_settings(config_dir)
    lines = [line for line in text.splitlines() if "    audio/" not in line]
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValidationError, match="voice memos"):
        fast_settings(config_dir)
    path.write_text(text.replace("    image/png: png\n", "    image png: png\n"))
    with pytest.raises(ValidationError, match="not a media type"):
        fast_settings(config_dir)


def test_the_summary_command_counts_what_was_synced(
    settings: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: Any
) -> None:
    async def fill() -> None:
        track = new_id()
        async with serve(settings, tmp_path) as client:
            await client.post("/api/field/observations", json=batch(note(), track_point(track)))

    asyncio.run(fill())
    monkeypatch.setattr(subphora.config, "REPO_ROOT", tmp_path)
    assert main(["field", "summary"]) == 0
    printed = capsys.readouterr().out
    assert "note: 1 records" in printed
    assert "track_point: 1 records" in printed
    assert "tracks: 1" in printed
    assert "recorded from 2026-11-26T10:00:05+00:00 to 2026-11-26T10:02:00+00:00" in printed


# Helpers that read the store directly.


async def _read_summary(settings: Settings, root: Path) -> FieldSummary:
    return await FieldService(settings, root).summary()


async def _summary(settings: Settings, root: Path) -> dict[str, int]:
    summary = await _read_summary(settings, root)
    counts = {count.kind.value: count.records for count in summary.kinds}
    return {**counts, "tracks": summary.tracks}


def _execute(database: Path, statement: str) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def _stored_bodies(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    try:
        return [row[0] for row in connection.execute("SELECT body FROM observations")]
    finally:
        connection.close()
