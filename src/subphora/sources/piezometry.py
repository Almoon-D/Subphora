# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Reading the national piezometry database: an Access file the owner downloads by hand
(its form is human-only and is never automated, docs/knowledge/water-authorities.md).

The file is read with mdbtools' ``mdb-export`` (``brew install mdbtools`` or
``apt install mdbtools``), which prints a table as CSV; dates are asked as ISO dates, since
its default prints two-digit years. A ``.zip`` is unpacked to a temporary folder first.
Nothing here touches the network.
"""

import csv
import hashlib
import io
import subprocess
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_ACCESS_SUFFIXES = (".accdb", ".mdb")
_DATE_FORMAT = "%Y-%m-%d"
_CHUNK = 1 << 20


class PiezometryReadError(Exception):
    """The file cannot be read: missing, not an Access database, or no mdb-export."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def access_file(path: Path) -> Iterator[Path]:
    """The Access database itself: ``path``, or the one database inside a zip."""
    if not path.is_file():
        raise PiezometryReadError(f"{path} does not exist: download it by hand first")
    if path.suffix.lower() in _ACCESS_SUFFIXES:
        yield path
        return
    if not zipfile.is_zipfile(path):
        raise PiezometryReadError(f"{path.name} is neither an Access database nor a zip")
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(_ACCESS_SUFFIXES)]
        if len(names) != 1:
            raise PiezometryReadError(f"{path.name} must hold one Access database, not {names}")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / Path(names[0]).name
            with archive.open(names[0]) as source, target.open("wb") as sink:
                while chunk := source.read(_CHUNK):
                    sink.write(chunk)
            yield target


def export_table(database: Path, table: str, mdb_export: str) -> Iterator[dict[str, str]]:
    """The rows of one table as dicts of column to text (empty where null)."""
    command = [mdb_export, "-D", _DATE_FORMAT, "-T", _DATE_FORMAT, str(database), table]
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError:
        raise PiezometryReadError(
            f"{mdb_export} is not installed: install mdbtools (brew install mdbtools, "
            "or apt install mdbtools)"
        ) from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()[:300]
        raise PiezometryReadError(f"{mdb_export} could not read {table}: {detail}")
    text = result.stdout.decode("utf-8", "replace")
    yield from csv.DictReader(io.StringIO(text))
