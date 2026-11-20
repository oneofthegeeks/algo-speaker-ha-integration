"""Client for the Algo IP speaker REST API.

Everything here was checked against real devices (8301, 8410, 8186, 8188) unless noted:

* Base URL: https first (self-signed certificates, so no verification), http if https cannot
  connect at all. The scheme that worked is remembered per device.
* Auth "Standard": an HMAC-SHA256 keyed with the REST API password over
  ``METHOD:PATH[:MD5:CONTENT-TYPE]:TS:NONCE``. A device on auth "None" accepts signed
  requests too. A wrong password answers 403 with an empty body; a device set to "Basic" auth
  answers a signed request the same way, so a 403 is retried once with Basic, and the mode
  that worked is remembered per device.
* Devices answer one request at a time (~300 ms each), so each client serialises its
  requests behind a lock.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import html
import json
import logging
import re
import secrets
import time
from typing import Any

import aiohttp

from .const import (
    KEY_PAGE_VOL,
    KEY_RADIO_FN,
    KEY_RADIO_URL,
    KEY_RADIO_USE,
    KEY_RADIO_ZONE,
    MUSIC_ZONE,
    VOLUME_MAX_DB,
    VOLUME_MIN_DB,
    VOLUME_STEP_DB,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
CONTENT_TYPE_JSON = "application/json"
AUTH_STANDARD = "standard"
AUTH_BASIC = "basic"

_MODEL_RE = re.compile(r"\b(8\d{3}S?)\b")
_DB_RE = re.compile(r"^\s*(-?\d+)\s*dB\s*$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


class AlgoError(Exception):
    """Base error for an Algo device."""


class AlgoConnectionError(AlgoError):
    """The device could not be reached over https or http."""


class AlgoAuthError(AlgoError):
    """The device refused the password (403 after the Basic retry)."""


class AlgoResponseError(AlgoError):
    """The device answered with an unexpected HTTP status."""

    def __init__(self, host: str, method: str, path: str, status: int) -> None:
        """Keep the status so callers can tell a missing endpoint from a failure."""
        super().__init__(f"{host}: {method} {path} returned HTTP {status}")
        self.status = status


class AlgoReadOnlyError(AlgoError):
    """The device refused a settings write (old firmware answers PUT with 400/404)."""


# --- pure helpers ---------------------------------------------------------------------------


def signing_message(
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body_md5: str | None = None,
    content_type: str | None = None,
) -> str:
    """The string Algo's Standard auth signs: METHOD:PATH[:MD5:CONTENT-TYPE]:TS:NONCE."""
    if body_md5 is not None:
        return f"{method}:{path}:{body_md5}:{content_type}:{timestamp}:{nonce}"
    return f"{method}:{path}:{timestamp}:{nonce}"


def hmac_digest(password: str, message: str) -> str:
    """Hex HMAC-SHA256 of ``message`` keyed with the REST API password."""
    return hmac.new(password.encode(), message.encode(), hashlib.sha256).hexdigest()


def sign_request(
    method: str,
    path: str,
    password: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Return the headers for an Algo "Standard" (HMAC) signed request.

    ``path`` is the URL path only. With a body, the MD5 is of the exact bytes sent.
    The device checks the timestamp against its own (NTP) clock, within about 30 s.
    """
    ts = int(time.time()) if timestamp is None else timestamp
    nonce = nonce if nonce is not None else str(secrets.randbelow(10**9))
    headers = {"Date": formatdate(ts, usegmt=True)}
    md5 = None
    if body is not None:
        md5 = hashlib.md5(body).hexdigest()  # noqa: S324 - Algo's protocol, not a security hash
        headers["Content-MD5"] = md5
    message = signing_message(method, path, ts, nonce, md5, content_type)
    headers["Authorization"] = f"hmac admin:{nonce}:{hmac_digest(password, message)}"
    return headers


def basic_auth_header(password: str) -> dict[str, str]:
    """Return the header for Algo "Basic" auth (user is always admin)."""
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def model_from_product(product: str | None) -> str | None:
    """'Algo 8301 IP Paging Adapter & Scheduler' -> '8301'."""
    match = _MODEL_RE.search(product or "")
    return match.group(1) if match else None


def parse_db(value: str | None) -> int | None:
    """'-18dB' -> -18. Anything else (e.g. 'Default', '') -> None."""
    match = _DB_RE.match(value or "")
    return int(match.group(1)) if match else None


def snap_db(value: float) -> int:
    """Clamp a volume to 0..-45 dB and snap it to the nearest 3 dB step."""
    value = max(VOLUME_MIN_DB, min(VOLUME_MAX_DB, value))
    snapped = int(round(value / VOLUME_STEP_DB) * VOLUME_STEP_DB)
    return snapped or 0  # never -0


def is_stream_url(url: str) -> bool:
    """Whether a radio URL looks like something the 8301 can pull."""
    return bool(_URL_RE.match(url or ""))


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    """What a device says it is, read once at setup."""

    host: str
    model: str | None
    product: str | None
    firmware: str | None
    mac: str | None
    # Firmware 3.x has no /api/info/about and refuses settings writes.
    read_only: bool

    def as_dict(self) -> dict[str, Any]:
        """Serialise for the config entry cache."""
        return {
            "model": self.model,
            "product": self.product,
            "firmware": self.firmware,
            "mac": self.mac,
            "read_only": self.read_only,
        }

    @classmethod
    def from_dict(cls, host: str, data: dict[str, Any]) -> DeviceIdentity:
        """Rebuild from the config entry cache."""
        return cls(
            host=host,
            model=data.get("model"),
            product=data.get("product"),
            firmware=data.get("firmware"),
            mac=data.get("mac"),
            read_only=bool(data.get("read_only")),
        )


# --- client -----------------------------------------------------------------------------------


class AlgoClient:
    """One Algo device. Requests are serialised; the device handles one at a time."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        password: str | None,
        timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
    ) -> None:
        """Set up the client; nothing is sent until the first request."""
        self.host = host
        self._session = session
        self._password = password or ""
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self.scheme: str | None = None  # "https" or "http" once one has worked
        self.auth_mode: str = AUTH_STANDARD

    # -- transport --

    async def _send(
        self, scheme: str, method: str, path: str, body: bytes | None, auth: str | None
    ) -> tuple[int, str]:
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = CONTENT_TYPE_JSON
        if auth == AUTH_STANDARD:
            headers |= sign_request(
                method, path, self._password, body=body, content_type=CONTENT_TYPE_JSON
            )
        elif auth == AUTH_BASIC:
            headers |= basic_auth_header(self._password)
        async with self._session.request(
            method,
            f"{scheme}://{self.host}{path}",
            data=body,
            headers=headers,
            timeout=self._timeout,
            ssl=False,  # LAN devices with self-signed certificates
            allow_redirects=False,
        ) as resp:
            return resp.status, await resp.text()

    async def _send_any_scheme(
        self, method: str, path: str, body: bytes | None, auth: str | None
    ) -> tuple[int, str]:
        """Send over the remembered scheme, or https then http when none is known yet.

        Only a failure to connect moves on to http; any HTTP answer is the device's answer.
        """
        schemes = [self.scheme] if self.scheme else ["https", "http"]
        last_err: Exception | None = None
        for scheme in schemes:
            try:
                result = await self._send(scheme, method, path, body, auth)
            except (aiohttp.ClientError, TimeoutError) as err:
                last_err = err
                continue
            self.scheme = scheme
            return result
        # Forget the scheme so the next attempt tries both again (the device may have changed).
        self.scheme = None
        raise AlgoConnectionError(f"{self.host}: cannot connect ({last_err!r})") from last_err

    async def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Send one request and return the parsed JSON body (None when empty)."""
        body = json.dumps(payload).encode() if payload is not None else None
        async with self._lock:
            return await self._authed(method, path, body)

    async def _authed(self, method: str, path: str, body: bytes | None) -> Any:
        if not self._password:
            status, text = await self._send_any_scheme(method, path, body, None)
            if status in (401, 403):
                raise AlgoAuthError(f"{self.host} wants a REST API password")
            return self._result(method, path, status, text)

        first = self.auth_mode
        status, text = await self._send_any_scheme(method, path, body, first)
        if status == 403 and first == AUTH_STANDARD:
            # A device on Basic auth answers a signed request with the same bare 403.
            status, text = await self._send_any_scheme(method, path, body, AUTH_BASIC)
            if status not in (401, 403):
                _LOGGER.debug("%s uses Basic auth", self.host)
                self.auth_mode = AUTH_BASIC
        if status in (401, 403):
            # Neither mode got in: re-detect from Standard next time (the password may change).
            self.auth_mode = AUTH_STANDARD
            raise AlgoAuthError(
                f"{self.host} refused the REST API password (check it, and the device's NTP clock)"
            )
        return self._result(method, path, status, text)

    def _result(self, method: str, path: str, status: int, text: str) -> Any:
        if not 200 <= status < 300:
            raise AlgoResponseError(self.host, method, path, status)
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    # -- reads --

    async def get_about(self) -> dict[str, Any] | None:
        """/api/info/about, or None on firmware too old to have it (404)."""
        try:
            data = await self.request("GET", "/api/info/about")
        except AlgoResponseError as err:
            if err.status == 404:
                return None
            raise
        return data if isinstance(data, dict) else {}

    async def get_status(self) -> dict[str, Any]:
        """/api/info/status (firmware 5.4+); {} where the device has none."""
        try:
            data = await self.request("GET", "/api/info/status")
        except AlgoResponseError as err:
            if err.status in (400, 404):
                return {}
            raise
        return data if isinstance(data, dict) else {}

    async def get_setting(self, key: str) -> str | None:
        """One setting's value as the device stores it (a string)."""
        data = await self.request("GET", f"/api/settings/{key}")
        if not isinstance(data, dict) or key not in data:
            return None
        value = data[key]
        if value is None:
            return None
        value = str(value)
        # The 8301 hands radio.url back HTML-escaped ("https:&#x2F;&#x2F;...").
        return html.unescape(value) if key == KEY_RADIO_URL else value

    async def get_settings(self, keys: list[str]) -> dict[str, str | None]:
        """Several settings, read one after another (the device is single-threaded)."""
        return {key: await self.get_setting(key) for key in keys}

    async def list_tones(self) -> list[str]:
        """Tone files the device can play."""
        data = await self.request("GET", "/api/files/tones")
        files = data.get("filelist") if isinstance(data, dict) else None
        return [str(f) for f in files] if isinstance(files, list) else []

    async def identify(self) -> DeviceIdentity:
        """Read what the device is. Raises AlgoConnectionError / AlgoAuthError."""
        about = await self.get_about()
        if about is None:
            # Firmware 3.x: no about, but settings reads work. This read also proves the
            # password, so a bad one fails here rather than on the first poll.
            await self.get_setting(KEY_PAGE_VOL)
            return DeviceIdentity(self.host, None, None, None, None, read_only=True)
        product = about.get("Product Name")
        return DeviceIdentity(
            host=self.host,
            model=model_from_product(product),
            product=product,
            firmware=about.get("Firmware Version"),
            mac=about.get("MAC Address"),
            read_only=False,
        )

    # -- writes --

    async def put_settings(self, settings: dict[str, str]) -> None:
        """PUT /api/settings. The device validates nothing, so callers read back what matters."""
        try:
            await self.request("PUT", "/api/settings", settings)
        except AlgoResponseError as err:
            if err.status in (400, 404):
                raise AlgoReadOnlyError(
                    f"{self.host} refused a settings write (firmware too old for control)"
                ) from err
            raise

    async def set_volume(self, key: str, db: float) -> int:
        """Write a volume snapped to the 3 dB grid, read it back, and return it."""
        value = snap_db(db)
        await self.put_settings({key: f"{value}dB"})
        stored = parse_db(await self.get_setting(key))
        if stored != value:
            raise AlgoError(f"{self.host} did not take {key}={value}dB (reads {stored})")
        return value

    async def play_stream(self, url: str) -> None:
        """8301 internet radio: multicast ``url`` to the music zone. Reads back radio.url."""
        if not is_stream_url(url):
            raise ValueError("The stream address must start with http:// or https://")
        await self.put_settings(
            {
                KEY_RADIO_USE: "1",
                KEY_RADIO_URL: url,
                # A file here would win whenever the URL is unreachable.
                KEY_RADIO_FN: "",
                KEY_RADIO_ZONE: MUSIC_ZONE,
            }
        )
        stored = await self.get_setting(KEY_RADIO_URL)
        if stored != url:
            raise AlgoError(f"{self.host} did not take the stream (radio.url reads {stored!r})")

    async def stop_stream(self) -> None:
        """8301 internet radio: stop by clearing radio.url (radio.use stays "1")."""
        await self.put_settings({KEY_RADIO_URL: ""})

    async def tone_start(self, path: str, loop: bool = False) -> None:
        """Play a tone file stored on the device."""
        await self.request("POST", "/api/controls/tone/start", {"path": path, "loop": loop})

    async def tone_stop(self) -> None:
        """Stop whatever tone is playing."""
        await self.request("POST", "/api/controls/tone/stop")

    async def strobe_start(self, pattern: int, color1: str, color2: str, ledlvl: int) -> None:
        """Start the strobe (strobe models only)."""
        await self.request(
            "POST",
            "/api/controls/strobe/start",
            {"pattern": pattern, "color1": color1, "color2": color2, "ledlvl": str(ledlvl)},
        )

    async def strobe_stop(self) -> None:
        """Stop the strobe."""
        await self.request("POST", "/api/controls/strobe/stop")

    async def test_tone(self) -> None:
        """Play the built-in test tone."""
        await self.request("POST", "/api/controls/test/start")
