"""Simulated Algo devices behind FakeSession, shaped like the real ones' answers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
import hashlib
import hmac
import json
from typing import Any
from unittest.mock import patch

import aiohttp

from custom_components.algo_speaker.api import hmac_digest, signing_message

from .fake_session import Call, FakeSession

HOST_8301 = "192.0.2.20"
HOST_8410 = "192.0.2.31"
HOST_OLD = "192.0.2.55"
PASSWORD = "secret"


def make_8301() -> dict[str, Any]:
    return {
        "about": {
            "Product Name": "Algo 8301 IP Paging Adapter & Scheduler",
            "Firmware Version": "5.7",
            "MAC Address": "00:22:ee:00:83:01",
            "Hardware Info": "8301 v4",
        },
        "status": {
            "SIP Registration": "Page, Successful;",
            "Multicast Mode": "Transmitter, RTP: 0, PPA: 0, Spk: 0",
            "Internet Radio Streaming": "Stopped",
        },
        "settings": {
            "audio.page.vol": "-18dB",
            "audio.ring.vol": "-9dB",
            "mcast.mode": "1",
            "radio.use": "1",
            "radio.url": "",
            "radio.fn": "",
            "radio.zone": "7",
        },
    }


def make_8410() -> dict[str, Any]:
    return {
        "about": {
            "Product Name": "Algo 8410 IP Display Speaker",
            "Firmware Version": "5.7",
            "MAC Address": "00:22:ee:18:1a:ce",
        },
        "status": {
            "SIP Registration": "Page, Successful;",
            "Multicast Mode": "Receiver, RTP: 0, PPA: 0, Spk: 0",
        },
        "settings": {"audio.page.vol": "-36dB", "audio.ring.vol": "-36dB", "mcast.mode": "2"},
    }


def make_old() -> dict[str, Any]:
    """Firmware 3.x: no about/status, settings readable, writes refused."""
    return {
        "about": None,
        "status": None,
        "settings": {"audio.page.vol": "-12dB", "audio.ring.vol": "-6dB", "mcast.mode": "2"},
    }


class Fleet:
    """Per-host device state; answers like the hardware (403 without the password)."""

    def __init__(self, devices: dict[str, dict[str, Any]], password: str = PASSWORD) -> None:
        self.devices = devices
        self.password = password
        self.offline: set[str] = set()
        self.session = FakeSession(self.handle)

    @property
    def calls(self) -> list[Call]:
        return self.session.calls

    def writes(self, host: str) -> list[tuple[str, str, Any]]:
        """(method, path, json body) of every non-GET request to ``host``."""
        return [
            (c.method, c.path, json.loads(c.data) if c.data else None)
            for c in self.calls
            if c.method != "GET" and f"//{host}/" in c.url
        ]

    def _signed_ok(self, call: Call) -> bool:
        """Check the HMAC the way the device does (password, path, body MD5, Date, nonce)."""
        if not call.auth.startswith("hmac admin:"):
            return False
        nonce, digest = call.auth.removeprefix("hmac admin:").split(":")
        ts = int(parsedate_to_datetime(call.headers["Date"]).timestamp())
        md5 = hashlib.md5(call.data).hexdigest() if call.data is not None else None
        message = signing_message(call.method, call.path, ts, nonce, md5, "application/json")
        return hmac.compare_digest(digest, hmac_digest(self.password, message))

    def handle(self, call: Call) -> tuple[int, str]:
        host = call.url.split("://", 1)[1].split("/", 1)[0]
        if host in self.offline or host not in self.devices:
            raise aiohttp.ClientConnectionError("offline")
        if self.password and not self._signed_ok(call):
            return 403, ""
        dev = self.devices[host]
        path = call.path
        if call.method == "GET" and path == "/api/info/about":
            return (404, "") if dev["about"] is None else (200, json.dumps(dev["about"]))
        if call.method == "GET" and path == "/api/info/status":
            return (404, "") if dev["status"] is None else (200, json.dumps(dev["status"]))
        if call.method == "GET" and path.startswith("/api/settings/"):
            key = path.removeprefix("/api/settings/")
            value = dev["settings"].get(key, "")
            if key == "radio.url":
                value = value.replace("/", "&#x2F;")  # the 8301 escapes it
            return 200, json.dumps({key: value})
        if call.method == "PUT" and path == "/api/settings":
            if dev["about"] is None:
                return 404, ""
            dev["settings"].update(json.loads(call.data))
            return 200, ""
        if call.method == "POST" and path.startswith("/api/controls/"):
            return 200, ""
        return 404, ""

    @contextmanager
    def patched(self) -> Iterator[Fleet]:
        """Route the integration's HTTP through this fleet."""
        with (
            patch(
                "custom_components.algo_speaker.async_get_clientsession",
                return_value=self.session,
            ),
            patch(
                "custom_components.algo_speaker.config_flow.async_get_clientsession",
                return_value=self.session,
            ),
        ):
            yield self
