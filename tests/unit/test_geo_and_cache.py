# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Reprojection (axis order, failures) and the file cache (lifetimes, corruption)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from subphora.geo import ReprojectionError, bbox_of, to_lon_lat, transform_point
from subphora.store import FileCache

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)


def test_epsg_4326_positions_are_latitude_first() -> None:
    assert to_lon_lat([(42.880433, -8.545248)], "EPSG:4326") == ((-8.545248, 42.880433),)


def test_utm_positions_become_longitude_latitude() -> None:
    # Praza do Obradoiro's reference point, as Catastro gave it in EPSG:25830.
    ((lon, lat),) = to_lon_lat([(47127.41, 4762495.08)], "EPSG:25830")
    assert lon == pytest.approx(-8.5448, abs=1e-4)
    assert lat == pytest.approx(42.8806, abs=1e-4)


def test_a_point_into_its_utm_zone_is_easting_northing() -> None:
    x, y = transform_point((-8.544782, 42.880633), "EPSG:25829")
    assert x == pytest.approx(537175.8, abs=0.5)
    assert y == pytest.approx(4747659.9, abs=0.5)


def test_no_positions_give_no_positions() -> None:
    assert to_lon_lat([], "EPSG:25830") == ()


def test_an_unknown_crs_is_refused() -> None:
    with pytest.raises(ReprojectionError, match="unknown CRS"):
        to_lon_lat([(0.0, 0.0)], "EPSG:999999")


def test_an_impossible_position_is_refused() -> None:
    with pytest.raises(ReprojectionError, match="cannot reproject"):
        transform_point((0.0, 95.0), "EPSG:25830")


def test_bbox() -> None:
    polygons = ((((-1.0, 2.0), (3.0, -4.0), (0.0, 0.0), (-1.0, 2.0)),),)
    assert bbox_of(polygons) == (-1.0, -4.0, 3.0, 2.0)


def test_bbox_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="no positions"):
        bbox_of(())


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_a_stored_entry_is_read_back_until_it_expires(tmp_path: Path) -> None:
    clock = Clock(NOW)
    cache = FileCache(tmp_path, clock)
    cache.put("catastro-ovc", "k", b"body", NOW, lifetime_s=60)
    clock.now = NOW + timedelta(seconds=59)
    hit = cache.get("catastro-ovc", "k", lifetime_s=60)
    assert hit is not None
    assert (hit.content, hit.fetched_at) == (b"body", NOW)
    clock.now = NOW + timedelta(seconds=60)
    assert cache.get("catastro-ovc", "k", lifetime_s=60) is None


def test_lifetime_zero_never_reads_or_writes(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, Clock(NOW))
    cache.put("google-map-tiles", "k", b"tile", NOW, lifetime_s=0)
    assert list(tmp_path.iterdir()) == []
    assert cache.get("google-map-tiles", "k", lifetime_s=0) is None


def test_keys_do_not_collide(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, Clock(NOW))
    cache.put("catastro-ovc", "a", b"A", NOW, lifetime_s=60)
    cache.put("catastro-ovc", "b", b"B", NOW, lifetime_s=60)
    a, b = (cache.get("catastro-ovc", k, 60) for k in "ab")
    assert a is not None
    assert b is not None
    assert (a.content, b.content) == (b"A", b"B")


def _meta_file(root: Path) -> Path:
    (meta,) = (root / "catastro-ovc").glob("*.json")
    return meta


@pytest.mark.parametrize(
    "meta",
    [
        "not json",
        json.dumps({"other": 1}),
        json.dumps({"fetched_at": "yesterday"}),
        json.dumps({"fetched_at": "2026-11-24T12:00:00"}),  # naive
        json.dumps({"fetched_at": "2026-11-25T12:00:00+00:00"}),  # in the future
        json.dumps(["fetched_at"]),
    ],
)
def test_a_corrupt_or_odd_entry_is_a_miss(tmp_path: Path, meta: str) -> None:
    cache = FileCache(tmp_path, Clock(NOW))
    cache.put("catastro-ovc", "k", b"body", NOW, lifetime_s=60)
    _meta_file(tmp_path).write_text(meta, encoding="utf-8")
    assert cache.get("catastro-ovc", "k", lifetime_s=60) is None


def test_a_missing_body_is_a_miss(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, Clock(NOW))
    cache.put("catastro-ovc", "k", b"body", NOW, lifetime_s=60)
    for body in (tmp_path / "catastro-ovc").glob("*.bin"):
        body.unlink()
    assert cache.get("catastro-ovc", "k", lifetime_s=60) is None


def test_a_naive_time_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FileCache(tmp_path).put("catastro-ovc", "k", b"", datetime(2026, 1, 1), lifetime_s=60)


@pytest.mark.parametrize("namespace", ["../etc", "Catastro", "", "a/b"])
def test_the_namespace_is_a_service_id(tmp_path: Path, namespace: str) -> None:
    with pytest.raises(ValueError, match="namespace"):
        FileCache(tmp_path).get(namespace, "k", lifetime_s=60)


def test_a_failed_write_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        FileCache(tmp_path).put("catastro-ovc", "k", b"body", NOW, lifetime_s=60)
    assert list((tmp_path / "catastro-ovc").iterdir()) == []
