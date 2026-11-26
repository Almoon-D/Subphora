# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The report's text: the web interface's Spanish catalogue (decision 0038), read from
its JSON file, with numbers, dates and units written as the interface writes them."""

import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Spanish groups thousands only from five digits on (13.352, but 1234).
_GROUPING_FROM = 10_000
_KILOMETRE = 1000.0
# Digits of a quantity by its unit, as the interface's legends write them.
_DIGITS = {"index": 2, "confidence": 2, "twi": 0, "deg": 0, "m": 0, "pct": 0}

type Param = str | int | float


class CatalogueError(ValueError):
    """The catalogue cannot be read, or lacks a message the report needs."""


class Catalogue:
    def __init__(self, messages: Mapping[str, str], zone: ZoneInfo) -> None:
        self._messages = dict(messages)
        self._zone = zone

    @classmethod
    def load(cls, path: Path, zone: ZoneInfo) -> Catalogue:
        try:
            messages = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CatalogueError(f"the catalogue {path.name} cannot be read: {exc}") from exc
        if not isinstance(messages, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in messages.items()
        ):
            raise CatalogueError(f"the catalogue {path.name} is not a map of texts")
        return cls(messages, zone)

    def _fill(self, template: str, params: Mapping[str, Param], strict: bool) -> str:
        def value(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in params:
                if strict:
                    raise CatalogueError(f"missing parameter {name}")
                return match.group(0)
            given = params[name]
            return given if isinstance(given, str) else self.number(given)

        return _PLACEHOLDER.sub(value, template)

    def t(self, key: str, **params: Param) -> str:
        """The message for ``key`` with every ``{name}`` filled; raises CatalogueError."""
        template = self._messages.get(key)
        if template is None:
            raise CatalogueError(f"the catalogue has no message {key!r}")
        try:
            return self._fill(template, params, strict=True)
        except CatalogueError as exc:
            raise CatalogueError(f"{key}: {exc}") from exc

    def lookup(self, key: str, fallback: str, **params: Param) -> str:
        """The message for a key built at run time, or ``fallback`` when it has none."""
        template = self._messages.get(key)
        return fallback if template is None else self._fill(template, params, strict=False)

    @staticmethod
    def translated(text: Mapping[str, str]) -> str:
        """A server text given per language: Spanish, else English."""
        return text.get("es") or text.get("en") or next(iter(text.values()), "")

    @staticmethod
    def number(value: float, digits: int = 0) -> str:
        """A number the Spanish way: 13.352 · 2,50."""
        text = f"{abs(value):.{digits}f}"
        whole, _, fraction = text.partition(".")
        if int(whole) >= _GROUPING_FROM:
            whole = f"{int(whole):,}".replace(",", ".")
        sign = "-" if value < 0 and float(text) != 0 else ""
        return f"{sign}{whole}{',' + fraction if fraction else ''}"

    def percent(self, share: float) -> str:
        return f"{self.number(share * 100)}\u00a0%"

    def score(self, value: float) -> str:
        return self.number(value, 2)

    def quantity(self, value: float, unit: str) -> str:
        """A value in a unit, as the legend and the explanation write it."""
        number = self.number(value, _DIGITS.get(unit, 2))
        match unit:
            case "deg":
                return f"{number}°"
            case "m":
                if value >= _KILOMETRE:
                    return f"{self.number(value / _KILOMETRE, 1)} km"
                return f"{number} m"
            case "pct":
                return f"{number} %"
            case "km_km2":
                return f"{number} km/km²"
            case _:
                return number

    def metres(self, value: float) -> str:
        return self.quantity(value, "m")

    def day(self, value: datetime | date) -> str:
        """A day in the area's local time: 26/11/2026."""
        if isinstance(value, datetime):
            value = value.astimezone(self._zone).date()
        return f"{value.day:02d}/{value.month:02d}/{value.year}"

    def moment(self, value: datetime) -> str:
        local = value.astimezone(self._zone)
        return f"{self.day(local)} {local.hour:02d}:{local.minute:02d} ({local.tzname()})"


__all__ = ["Catalogue", "CatalogueError"]
