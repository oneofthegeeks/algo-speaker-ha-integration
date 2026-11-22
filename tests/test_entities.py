"""Entities and services against simulated devices, through a real entry setup."""

from __future__ import annotations

from collections.abc import AsyncIterator

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.algo_speaker.const import (
    CONF_AUTH_MODE,
    CONF_DEVICES,
    CONF_HOSTS,
    CONF_STATIONS,
    DOMAIN,
)

from .devices import HOST_8301, HOST_8410, HOST_OLD, PASSWORD, Fleet, make_8301, make_8410, make_old

LUSH = "https://ice5.somafm.com/lush-128-aac"
DOOMED = "https://ice5.somafm.com/doomed-128-aac"
STATIONS = f"Lush | {LUSH}\nDoomed | {DOOMED}"

# entity_ids follow the device names "Algo 8301 192.0.2.20" etc.
E_8301 = "algo_8301_192_0_2_20"
E_8410 = "algo_8410_192_0_2_31"
E_OLD = "algo_192_0_2_55"


@pytest.fixture
async def fleet(hass: HomeAssistant) -> AsyncIterator[Fleet]:
    """Three devices (8301, 8410, firmware 3.x) set up as one entry."""
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410(), HOST_OLD: make_old()})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Algo speakers",
        data={
            CONF_PASSWORD: PASSWORD,
            CONF_AUTH_MODE: "standard",
            CONF_HOSTS: [HOST_8301, HOST_8410, HOST_OLD],
            CONF_DEVICES: {},
        },
        options={CONF_STATIONS: STATIONS},
    )
    entry.add_to_hass(hass)
    with fleet.patched():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        fleet.entry = entry  # type: ignore[attr-defined]
        yield fleet


def _entities_of(hass: HomeAssistant, prefix: str) -> set[str]:
    return {e for e in er.async_get(hass).entities if prefix in e}


async def test_entities_per_model(hass: HomeAssistant, fleet: Fleet) -> None:
    assert _entities_of(hass, E_8301) == {
        f"number.{E_8301}_music_page_volume",
        f"number.{E_8301}_ring_volume",
        f"button.{E_8301}_test_tone",
        f"button.{E_8301}_stop_tone",
        f"sensor.{E_8301}_sip_registration",
        f"sensor.{E_8301}_multicast_mode",
        f"sensor.{E_8301}_firmware",
        f"sensor.{E_8301}_now_playing",
        f"sensor.{E_8301}_radio_status",
        f"switch.{E_8301}_music",
        f"select.{E_8301}_station",
    }
    assert _entities_of(hass, E_8410) == {
        f"number.{E_8410}_music_page_volume",
        f"number.{E_8410}_ring_volume",
        f"button.{E_8410}_test_tone",
        f"button.{E_8410}_stop_tone",
        f"sensor.{E_8410}_sip_registration",
        f"sensor.{E_8410}_multicast_mode",
        f"sensor.{E_8410}_firmware",
        f"switch.{E_8410}_strobe",
    }


async def test_read_only_device_gets_no_writable_entities(
    hass: HomeAssistant, fleet: Fleet
) -> None:
    assert _entities_of(hass, E_OLD) == {
        f"sensor.{E_OLD}_music_page_volume",
        f"sensor.{E_OLD}_ring_volume",
        f"sensor.{E_OLD}_multicast_mode",
    }
    assert hass.states.get(f"sensor.{E_OLD}_music_page_volume").state == "-12"
    assert hass.states.get(f"sensor.{E_OLD}_multicast_mode").state == "Receiver"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"firmware_read_only_{HOST_OLD}")
    assert fleet.writes(HOST_OLD) == []


async def test_states_and_device_info(hass: HomeAssistant, fleet: Fleet) -> None:
    assert hass.states.get(f"number.{E_8301}_music_page_volume").state == "-18"
    assert hass.states.get(f"sensor.{E_8301}_now_playing").state == "Stopped"
    assert hass.states.get(f"switch.{E_8301}_music").state == "off"
    assert hass.states.get(f"select.{E_8301}_station").state == "unknown"
    assert hass.states.get(f"sensor.{E_8410}_multicast_mode").state.startswith("Receiver")
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "00:22:ee:18:1a:ce")})
    assert device is not None
    assert (device.manufacturer, device.model, device.sw_version) == ("Algo", "8410", "5.7")


async def test_station_select_plays(hass: HomeAssistant, fleet: Fleet) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: f"select.{E_8301}_station", "option": "Doomed"},
        blocking=True,
    )
    assert fleet.writes(HOST_8301)[0] == (
        "PUT",
        "/api/settings",
        {"radio.use": "1", "radio.url": DOOMED, "radio.fn": "", "radio.zone": "7"},
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"select.{E_8301}_station").state == "Doomed"
    assert hass.states.get(f"switch.{E_8301}_music").state == "on"
    assert hass.states.get(f"sensor.{E_8301}_now_playing").state == "Doomed"


async def test_music_switch_payloads(hass: HomeAssistant, fleet: Fleet) -> None:
    switch = f"switch.{E_8301}_music"
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: switch}, blocking=True)
    # Nothing played yet, so the first configured station.
    assert fleet.writes(HOST_8301) == [
        (
            "PUT",
            "/api/settings",
            {"radio.use": "1", "radio.url": LUSH, "radio.fn": "", "radio.zone": "7"},
        )
    ]
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert fleet.writes(HOST_8301)[-1] == ("PUT", "/api/settings", {"radio.url": ""})
    await hass.async_block_till_done()
    assert hass.states.get(switch).state == "off"
    assert hass.states.get(f"sensor.{E_8301}_now_playing").state == "Stopped"
    # radio.use stays "1" (the house convention).
    assert fleet.devices[HOST_8301]["settings"]["radio.use"] == "1"


async def test_music_switch_resumes_last_station(hass: HomeAssistant, fleet: Fleet) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: f"select.{E_8301}_station", "option": "Doomed"},
        blocking=True,
    )
    switch = f"switch.{E_8301}_music"
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert fleet.writes(HOST_8301)[-1][2]["radio.url"] == DOOMED


async def test_unknown_url_shows_raw(hass: HomeAssistant, fleet: Fleet) -> None:
    fleet.devices[HOST_8301]["settings"]["radio.url"] = "https://other.example/s"
    coordinator = fleet.entry.runtime_data.coordinators[HOST_8301]  # type: ignore[attr-defined]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{E_8301}_now_playing").state == "https://other.example/s"
    assert hass.states.get(f"select.{E_8301}_station").state == "unknown"


@pytest.mark.parametrize(("value", "expected"), [(-17, "-18dB"), (-16, "-15dB"), (-45, "-45dB")])
async def test_volume_snaps_to_grid(
    hass: HomeAssistant, fleet: Fleet, value: float, expected: str
) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: f"number.{E_8410}_ring_volume", "value": value},
        blocking=True,
    )
    assert fleet.writes(HOST_8410) == [("PUT", "/api/settings", {"audio.ring.vol": expected})]
    assert hass.states.get(f"number.{E_8410}_ring_volume").state == expected[:-2]


async def test_strobe_switch(hass: HomeAssistant, fleet: Fleet) -> None:
    switch = f"switch.{E_8410}_strobe"
    assert hass.states.get(switch).attributes.get("assumed_state") is True
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert fleet.writes(HOST_8410) == [
        (
            "POST",
            "/api/controls/strobe/start",
            {"pattern": 2, "color1": "red", "color2": "red", "ledlvl": "255"},
        )
    ]
    assert hass.states.get(switch).state == "on"
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True)
    assert fleet.writes(HOST_8410)[-1] == ("POST", "/api/controls/strobe/stop", None)
    assert hass.states.get(switch).state == "off"


async def test_buttons(hass: HomeAssistant, fleet: Fleet) -> None:
    for name in ("test_tone", "stop_tone"):
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: f"button.{E_8410}_{name}"}, blocking=True
        )
    assert [w[1] for w in fleet.writes(HOST_8410)] == [
        "/api/controls/test/start",
        "/api/controls/tone/stop",
    ]


# --- services --------------------------------------------------------------------------------


def _device_id(hass: HomeAssistant, uid: str) -> str:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, uid)})
    assert device is not None
    return device.id


async def test_service_play_tone_sets_ring_volume_first(hass: HomeAssistant, fleet: Fleet) -> None:
    await hass.services.async_call(
        DOMAIN,
        "play_tone",
        {
            "device_id": [_device_id(hass, "00:22:ee:18:1a:ce")],
            "file": "chime.wav",
            "volume_db": -10,
        },
        blocking=True,
    )
    assert fleet.writes(HOST_8410) == [
        ("PUT", "/api/settings", {"audio.ring.vol": "-9dB"}),
        ("POST", "/api/controls/tone/start", {"path": "chime.wav", "loop": False}),
    ]


async def test_service_strobe_and_stream_validation(hass: HomeAssistant, fleet: Fleet) -> None:
    dev_8301 = _device_id(hass, "00:22:ee:00:83:01")
    dev_8410 = _device_id(hass, "00:22:ee:18:1a:ce")
    dev_old = _device_id(hass, HOST_OLD)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "strobe_start", {"device_id": dev_8301}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "play_stream", {"device_id": dev_8410, "url": LUSH}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "stop_tone", {"device_id": dev_old}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "play_stream", {"device_id": dev_8301, "url": "ftp://x"}, blocking=True
        )
    assert fleet.writes(HOST_8301) == fleet.writes(HOST_8410) == fleet.writes(HOST_OLD) == []

    await hass.services.async_call(
        DOMAIN,
        "strobe_start",
        {"device_id": dev_8410, "pattern": 7, "color1": "amber", "brightness": "medium"},
        blocking=True,
    )
    assert fleet.writes(HOST_8410)[-1] == (
        "POST",
        "/api/controls/strobe/start",
        {"pattern": 7, "color1": "amber", "color2": "amber", "ledlvl": "56"},
    )
    assert hass.states.get(f"switch.{E_8410}_strobe").state == "on"
    await hass.services.async_call(
        DOMAIN, "play_stream", {"device_id": dev_8301, "url": LUSH}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "stop_stream", {"device_id": dev_8301}, blocking=True)
    assert fleet.writes(HOST_8301)[-1] == ("PUT", "/api/settings", {"radio.url": ""})


async def test_offline_device_does_not_block_others(hass: HomeAssistant) -> None:
    """A cached device that is offline at startup is unavailable; the rest load."""
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410()})
    fleet.offline.add(HOST_8410)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PASSWORD: PASSWORD,
            CONF_HOSTS: [HOST_8301, HOST_8410],
            CONF_DEVICES: {
                HOST_8410: {"model": "8410", "mac": "00:22:ee:18:1a:ce", "firmware": "5.7"}
            },
        },
    )
    entry.add_to_hass(hass)
    with fleet.patched():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"switch.{E_8410}_strobe").state == "unavailable"
    assert hass.states.get(f"switch.{E_8301}_music").state == "off"


async def test_unknown_offline_device_retries_setup(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: PASSWORD, CONF_HOSTS: [HOST_8301, "10.9.9.9"], CONF_DEVICES: {}},
    )
    entry.add_to_hass(hass)
    with fleet.patched():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_password_starts_reauth(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()}, password="changed")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: "old", CONF_HOSTS: [HOST_8301], CONF_DEVICES: {}},
    )
    entry.add_to_hass(hass)
    with fleet.patched():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress()
    )


async def test_refused_polls_start_reauth_only_after_three(
    hass: HomeAssistant, fleet: Fleet
) -> None:
    """One refused poll is a failed poll; reauth (which stops polling) waits for three in a row."""
    coordinator = fleet.entry.runtime_data.coordinators[HOST_8301]  # type: ignore[attr-defined]

    def reauth_started() -> bool:
        return any(
            f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress()
        )

    fleet.password = "changed"
    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert not reauth_started()

    # The device accepts the password again: the count starts over.
    fleet.password = PASSWORD
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success

    fleet.password = "changed"
    for _ in range(3):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert reauth_started()


async def test_diagnostics_redact_password(hass: HomeAssistant, fleet: Fleet) -> None:
    from custom_components.algo_speaker.diagnostics import async_get_config_entry_diagnostics

    diag = await async_get_config_entry_diagnostics(hass, fleet.entry)  # type: ignore[attr-defined]
    assert diag["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert PASSWORD not in str(diag)
    text = str(diag)
    for secret in ("Page, Successful", "00:22:ee:18:1a:ce", "00:22:ee:00:83:01"):
        assert secret not in text
    assert diag["devices"][HOST_8410]["data"]["status"]["SIP Registration"] == "**REDACTED**"
    assert diag["devices"][HOST_8301]["identity"]["model"] == "8301"
