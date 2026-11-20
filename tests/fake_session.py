"""A stand-in for aiohttp.ClientSession that routes requests to a Python handler."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Call:
    """One request the client sent."""

    method: str
    url: str
    headers: dict[str, str]
    data: bytes | None
    ssl: Any = None

    @property
    def scheme(self) -> str:
        return self.url.split("://", 1)[0]

    @property
    def path(self) -> str:
        return "/" + self.url.split("://", 1)[1].split("/", 1)[1]

    @property
    def auth(self) -> str:
        return self.headers.get("Authorization", "")


class _Response:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


@dataclass
class FakeSession:
    """``handler(call)`` returns (status, text) or raises (e.g. aiohttp.ClientConnectorError)."""

    handler: Callable[[Call], tuple[int, str]]
    calls: list[Call] = field(default_factory=list)

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        call = Call(method, url, dict(kwargs.get("headers") or {}), kwargs.get("data"))
        call.ssl = kwargs.get("ssl")
        self.calls.append(call)
        status, text = self.handler(call)
        return _Response(status, text)
