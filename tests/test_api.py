"""The REST client: signing, https/http fallback, Standard/Basic fallback, parsing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import aiohttp
import pytest

from custom_components.algo_speaker.api import (
    AlgoAuthError,
    AlgoClient,
    AlgoConnectionError,
    AlgoError,
    AlgoReadOnlyError,
    hmac_digest,
    model_from_product,
    parse_db,
    sign_request,
    signing_message,
    snap_db,
)

from .fake_session import Call, FakeSession

PUBLISHED_MD5 = "6e43c05d82f71e77c586e29edb93b129"


# --- signing --------------------------------------------------------------------------------


def test_published_hmac_examples() -> None:
    """Both worked examples from Algo's REST API guide (password "algo").

    The guide gives only the body's MD5, not the body, so the message is built from it.
    """
    msg = signing_message(
        "POST", "/api/controls/tone/start", 1601312252, "49936", PUBLISHED_MD5, "application/json"
    )
    assert msg == f"POST:/api/controls/tone/start:{PUBLISHED_MD5}:application/json:1601312252:49936"
    assert (
        hmac_digest("algo", msg)
        == "2e109d7aeed54a1cb04c6b72b1d854f442cf1ca15eb0af32f2512dd77ab6b330"
    )
    msg = signing_message(
        "POST",
        "/api/controls/tone/start",
        1601312838,
        "1028014788",
        PUBLISHED_MD5,
        "application/json",
    )
    assert (
        hmac_digest("algo", msg)
        == "c450024af4493f9cdf582499456bf58d7e134b161566e764e61bd52d24f759dc"
    )


def test_sign_request_with_body() -> None:
    body = json.dumps({"path": "chime.wav", "loop": False}).encode()
    headers = sign_request(
        "POST",
        "/api/controls/tone/start",
        "algo",
        body=body,
        content_type="application/json",
        timestamp=1601312838,
        nonce="1028014788",
    )
    md5 = hashlib.md5(body).hexdigest()
    expected = hmac.new(
        b"algo",
        f"POST:/api/controls/tone/start:{md5}:application/json:1601312838:1028014788".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert headers["Authorization"] == f"hmac admin:1028014788:{expected}"
    assert headers["Content-MD5"] == md5
    assert headers["Date"] == "Mon, 28 Sep 2020 17:07:18 GMT"


def test_sign_request_without_body() -> None:
    headers = sign_request(
        "GET", "/api/settings/audio.page.vol", "algo", timestamp=1601312252, nonce="49936"
    )
    expected = hmac.new(
        b"algo", b"GET:/api/settings/audio.page.vol:1601312252:49936", hashlib.sha256
    ).hexdigest()
    assert headers["Authorization"] == f"hmac admin:49936:{expected}"
    assert "Content-MD5" not in headers
    assert headers["Date"].endswith("GMT")


# --- pure helpers ---------------------------------------------------------------------------


def test_model_from_product() -> None:
    assert model_from_product("Algo 8301 IP Paging Adapter & Scheduler") == "8301"
    assert model_from_product("Algo 8190S IP Clock") == "8190S"
    assert model_from_product("Something else") is None
    assert model_from_product(None) is None


def test_parse_and_snap_db() -> None:
    assert parse_db("-18dB") == -18
    assert parse_db("0dB") == 0
    assert parse_db("Default") is None
    assert snap_db(-17) == -18
    assert snap_db(-16) == -15
    assert snap_db(6) == 0
    assert snap_db(-60) == -45
    assert snap_db(-1) == 0


# --- transport ------------------------------------------------------------------------------


def _ok(body: object) -> tuple[int, str]:
    return 200, json.dumps(body)


async def test_https_first_then_remembered() -> None:
    session = FakeSession(lambda c: _ok({"audio.page.vol": "-9dB"}))
    client = AlgoClient(session, "10.0.0.5", "pw")  # type: ignore[arg-type]
    assert await client.get_setting("audio.page.vol") == "-9dB"
    assert session.calls[0].url == "https://10.0.0.5/api/settings/audio.page.vol"
    assert session.calls[0].ssl is False
    assert client.scheme == "https"


async def test_http_fallback_when_https_cannot_connect() -> None:
    def handler(call: Call) -> tuple[int, str]:
        if call.scheme == "https":
            raise aiohttp.ClientConnectionError("refused")
        return _ok({"mcast.mode": "2"})

    session = FakeSession(handler)
    client = AlgoClient(session, "10.0.0.5", None)  # type: ignore[arg-type]
    assert await client.get_setting("mcast.mode") == "2"
    assert [c.scheme for c in session.calls] == ["https", "http"]
    assert client.scheme == "http"
    await client.get_setting("mcast.mode")
    assert [c.scheme for c in session.calls] == ["https", "http", "http"], "http remembered"


async def test_http_status_does_not_fall_back() -> None:
    """Only a failure to connect moves on to http; an HTTP answer is the device's answer."""
    session = FakeSession(lambda c: (500, ""))
    client = AlgoClient(session, "10.0.0.5", None)  # type: ignore[arg-type]
    with pytest.raises(AlgoError):
        await client.get_setting("mcast.mode")
    assert [c.scheme for c in session.calls] == ["https"]


async def test_unreachable_raises_connection_error() -> None:
    def handler(call: Call) -> tuple[int, str]:
        raise TimeoutError

    client = AlgoClient(FakeSession(handler), "10.0.0.5", "pw")  # type: ignore[arg-type]
    with pytest.raises(AlgoConnectionError):
        await client.get_about()


async def test_no_password_sends_no_authorization() -> None:
    session = FakeSession(lambda c: _ok({"mcast.mode": "2"}))
    await AlgoClient(session, "h", "").get_setting("mcast.mode")  # type: ignore[arg-type]
    assert "Authorization" not in session.calls[0].headers


async def test_no_password_and_403_is_auth_error() -> None:
    client = AlgoClient(FakeSession(lambda c: (403, "")), "h", None)  # type: ignore[arg-type]
    with pytest.raises(AlgoAuthError):
        await client.get_about()


async def test_body_is_signed_exactly_as_sent() -> None:
    session = FakeSession(lambda c: (200, ""))
    await AlgoClient(session, "h", "pw").tone_start("chime.wav")  # type: ignore[arg-type]
    call = session.calls[0]
    assert json.loads(call.data) == {"path": "chime.wav", "loop": False}
    assert call.headers["Content-Type"] == "application/json"
    assert call.headers["Content-MD5"] == hashlib.md5(call.data).hexdigest()
    assert call.auth.startswith("hmac admin:")


async def test_standard_403_retries_basic_and_remembers() -> None:
    def handler(call: Call) -> tuple[int, str]:
        if call.auth.startswith("hmac"):
            return 403, ""
        return _ok({"audio.page.vol": "-9dB"})

    session = FakeSession(handler)
    client = AlgoClient(session, "h", "letmein")  # type: ignore[arg-type]
    assert await client.get_setting("audio.page.vol") == "-9dB"
    basic = "Basic " + base64.b64encode(b"admin:letmein").decode()
    assert [c.auth.split(" ")[0] for c in session.calls] == ["hmac", "Basic"]
    assert session.calls[1].auth == basic
    await client.get_setting("audio.page.vol")
    assert session.calls[2].auth == basic, "Basic is remembered for this device"


async def test_403_after_basic_is_auth_error() -> None:
    session = FakeSession(lambda c: (403, ""))
    client = AlgoClient(session, "h", "wrong")  # type: ignore[arg-type]
    with pytest.raises(AlgoAuthError):
        await client.get_about()
    assert len(session.calls) == 2, "one Standard attempt, one Basic retry"


async def test_basic_answer_that_is_not_auth_is_the_real_answer() -> None:
    def handler(call: Call) -> tuple[int, str]:
        return (403, "") if call.auth.startswith("hmac") else (404, "")

    client = AlgoClient(FakeSession(handler), "h", "pw")  # type: ignore[arg-type]
    assert await client.get_about() is None, "404 on about = old firmware, not a bad password"


# --- device semantics ----------------------------------------------------------------------


async def test_identify_reads_about() -> None:
    about = {
        "Product Name": "Algo 8301 IP Paging Adapter & Scheduler",
        "Firmware Version": "5.7",
        "MAC Address": "00:22:ee:01:02:03",
        "Hardware Info": "8301 v4",
    }
    ident = await AlgoClient(FakeSession(lambda c: _ok(about)), "h", "pw").identify()  # type: ignore[arg-type]
    assert (ident.model, ident.firmware, ident.mac, ident.read_only) == (
        "8301",
        "5.7",
        "00:22:ee:01:02:03",
        False,
    )


async def test_old_firmware_is_read_only() -> None:
    def handler(call: Call) -> tuple[int, str]:
        if call.path == "/api/info/about":
            return 404, ""
        if call.method == "PUT":
            return 400, ""
        return _ok({"audio.page.vol": "-9dB"})

    client = AlgoClient(FakeSession(handler), "h", "pw")  # type: ignore[arg-type]
    ident = await client.identify()
    assert ident.read_only is True
    assert ident.model is None
    with pytest.raises(AlgoReadOnlyError):
        await client.put_settings({"audio.page.vol": "-9dB"})


async def test_put_404_is_read_only() -> None:
    client = AlgoClient(FakeSession(lambda c: (404, "")), "h", "pw")  # type: ignore[arg-type]
    with pytest.raises(AlgoReadOnlyError):
        await client.stop_stream()


async def test_radio_url_is_html_unescaped() -> None:
    raw = {"radio.url": "https:&#x2F;&#x2F;ice5.somafm.com&#x2F;doomed-128-aac"}
    client = AlgoClient(FakeSession(lambda c: _ok(raw)), "h", "pw")  # type: ignore[arg-type]
    assert await client.get_setting("radio.url") == "https://ice5.somafm.com/doomed-128-aac"


async def test_play_stream_payload_and_read_back() -> None:
    url = "https://ice5.somafm.com/lush-128-aac"
    stored: dict[str, str] = {}

    def handler(call: Call) -> tuple[int, str]:
        if call.method == "PUT":
            stored.update(json.loads(call.data))
            return 200, ""
        key = call.path.rsplit("/", 1)[1]
        # The 8301 escapes slashes on the way out.
        return _ok({key: stored.get(key, "").replace("/", "&#x2F;")})

    session = FakeSession(handler)
    await AlgoClient(session, "h", "pw").play_stream(url)  # type: ignore[arg-type]
    assert json.loads(session.calls[0].data) == {
        "radio.use": "1",
        "radio.url": url,
        "radio.fn": "",
        "radio.zone": "7",
    }
    assert session.calls[1].path == "/api/settings/radio.url"


async def test_play_stream_rejects_bad_url() -> None:
    session = FakeSession(lambda c: (200, ""))
    with pytest.raises(ValueError):
        await AlgoClient(session, "h", "pw").play_stream("ftp://nope")  # type: ignore[arg-type]
    assert session.calls == []


async def test_stop_stream_only_clears_url() -> None:
    session = FakeSession(lambda c: (200, ""))
    await AlgoClient(session, "h", "pw").stop_stream()  # type: ignore[arg-type]
    assert session.calls[0].method == "PUT"
    assert json.loads(session.calls[0].data) == {"radio.url": ""}


async def test_set_volume_snaps_and_reads_back() -> None:
    stored: dict[str, str] = {}

    def handler(call: Call) -> tuple[int, str]:
        if call.method == "PUT":
            stored.update(json.loads(call.data))
            return 200, ""
        key = call.path.rsplit("/", 1)[1]
        return _ok({key: stored.get(key, "")})

    session = FakeSession(handler)
    assert await AlgoClient(session, "h", "pw").set_volume("audio.page.vol", -17) == -18  # type: ignore[arg-type]
    assert json.loads(session.calls[0].data) == {"audio.page.vol": "-18dB"}


async def test_controls_payloads() -> None:
    session = FakeSession(lambda c: (200, ""))
    client = AlgoClient(session, "h", None)  # type: ignore[arg-type]
    await client.strobe_start(2, "red", "red", 255)
    await client.strobe_stop()
    await client.tone_stop()
    await client.test_tone()
    assert [(c.method, c.path) for c in session.calls] == [
        ("POST", "/api/controls/strobe/start"),
        ("POST", "/api/controls/strobe/stop"),
        ("POST", "/api/controls/tone/stop"),
        ("POST", "/api/controls/test/start"),
    ]
    assert json.loads(session.calls[0].data) == {
        "pattern": 2,
        "color1": "red",
        "color2": "red",
        "ledlvl": "255",
    }
    assert session.calls[1].data is None
