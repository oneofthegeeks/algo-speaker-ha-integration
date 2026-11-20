"""Parsing of the text fields in the config and options flows."""

from __future__ import annotations

import re

from .api import is_stream_url


class StationLineError(ValueError):
    """A stations line that is not "Name | URL"."""

    def __init__(self, line: str) -> None:
        """Keep the offending line for the form error."""
        super().__init__(line)
        self.line = line


def parse_hosts(text: str) -> list[str]:
    """Comma, whitespace or newline separated hosts, de-duplicated in order."""
    hosts: list[str] = []
    for part in re.split(r"[,\s]+", text or ""):
        host = part.strip()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def parse_stations(text: str) -> list[tuple[str, str]]:
    """One "Name | URL" per line; blank lines are skipped. Raises StationLineError."""
    stations: list[tuple[str, str]] = []
    names: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        name, sep, url = line.partition("|")
        name, url = name.strip(), url.strip()
        if not sep or not name or not is_stream_url(url) or name in names:
            raise StationLineError(line)
        names.add(name)
        stations.append((name, url))
    return stations
