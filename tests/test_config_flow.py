"""Config, reauth, reconfigure and options flows."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.algo_speaker.const import (
    CONF_AUTH_MODE,
    CONF_DEVICES,
    CONF_HOSTS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DEFAULT_STATIONS,
    DOMAIN,
)
from custom_components.algo_speaker.util import (
    StationLineError,
    parse_hosts,
    parse_stations,
)

from .devices import HOST_8301, HOST_8410, HOST_OLD, PASSWORD, Fleet, make_8301, make_8410


@pytest.fixture(autouse=True)
def no_setup():
    """Flows only; entry setup is tested elsewhere."""
    with patch("custom_components.algo_speaker.async_setup_entry", return_value=True):
        yield


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_user_success(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410()})
    with fleet.patched():
        result = await _start(hass)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: PASSWORD,
                CONF_AUTH_MODE: "standard",
                CONF_HOSTS: f"{HOST_8301}, {HOST_8410}\n{HOST_8301}",
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Algo speakers"
    data = result["data"]
    assert data[CONF_HOSTS] == [HOST_8301, HOST_8410]
    assert data[CONF_AUTH_MODE] == "standard"
    assert data[CONF_DEVICES][HOST_8301]["model"] == "8301"
    assert data[CONF_DEVICES][HOST_8410]["mac"] == "00:22:ee:18:1a:ce"


async def test_user_cannot_connect_lists_hosts(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()})
    with fleet.patched():
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: PASSWORD, CONF_HOSTS: f"{HOST_8301},10.9.9.9,10.9.9.8"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"]["hosts"] == "10.9.9.9, 10.9.9.8"


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()})
    with fleet.patched():
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "", CONF_HOSTS: HOST_8301}
        )
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["description_placeholders"]["hosts"] == HOST_8301


async def test_user_basic_needs_password(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()})
    with fleet.patched():
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_AUTH_MODE: "basic", CONF_HOSTS: HOST_8301}
        )
    assert result["errors"] == {CONF_PASSWORD: "password_required"}
    assert fleet.calls == []


async def test_user_basic_http_only_device_explains(hass: HomeAssistant) -> None:
    fleet = Fleet({HOST_8301: make_8301()})
    real = fleet.handle

    def http_only(call):
        if call.scheme == "https":
            import aiohttp

            raise aiohttp.ClientConnectionError("no https")
        return real(call)

    fleet.session.handler = http_only
    with fleet.patched():
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: PASSWORD, CONF_AUTH_MODE: "basic", CONF_HOSTS: HOST_8301},
        )
    assert result["errors"] == {"base": "cannot_connect_basic"}
    assert all(c.scheme == "https" for c in fleet.calls), "Basic never went over http"


async def test_user_no_hosts(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD, CONF_HOSTS: " , "}
    )
    assert result["errors"] == {CONF_HOSTS: "no_hosts"}


def _entry(hass: HomeAssistant, **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Algo speakers",
        data={
            CONF_PASSWORD: PASSWORD,
            CONF_AUTH_MODE: "standard",
            CONF_HOSTS: [HOST_8301],
            CONF_DEVICES: {HOST_8301: {"model": "8301", "mac": "00:22:ee:00:83:01"}},
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_reauth(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301()}, password="new-pw")
    with fleet.patched():
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-pw"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-pw"


async def test_reauth_with_one_host_offline(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_HOSTS: [HOST_8301, HOST_8410]}
    )
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410()}, password="new-pw")
    fleet.offline.add(HOST_8410)
    with fleet.patched():
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-pw"}
        )
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-pw"


async def test_reauth_all_offline_is_cannot_connect(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301()})
    fleet.offline.add(HOST_8301)
    with fleet.patched():
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "x"}
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410()})
    with fleet.patched():
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: PASSWORD,
                CONF_AUTH_MODE: "standard",
                CONF_HOSTS: f"{HOST_8301}\n{HOST_8410}",
            },
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOSTS] == [HOST_8301, HOST_8410]


# --- options ---------------------------------------------------------------------------------


async def test_options_defaults_and_save(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301(), HOST_8410: make_8410()})
    with fleet.patched():
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        schema_defaults = {
            str(k): k.description.get("suggested_value") for k in result["data_schema"].schema
        }
        assert schema_defaults[CONF_STATIONS] == DEFAULT_STATIONS
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOSTS: f"{HOST_8301}\n{HOST_8410}",
                CONF_AUTH_MODE: "standard",
                CONF_STATIONS: "Lush | https://ice5.somafm.com/lush-128-aac\n\n",
                CONF_SCAN_INTERVAL: 45,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 45
    assert entry.data[CONF_HOSTS] == [HOST_8301, HOST_8410]
    assert entry.data[CONF_DEVICES][HOST_8410]["model"] == "8410"
    # Only the new host was checked; the known one kept its cached identity.
    assert all(HOST_8301 not in c.url for c in fleet.calls)


@pytest.mark.parametrize(
    "line",
    [
        "No pipe https://x.example/s",
        "Name | ftp://x.example/s",
        " | https://x.example/s",
        "Name |",
    ],
)
async def test_options_rejects_bad_station_line(hass: HomeAssistant, line: str) -> None:
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOSTS: HOST_8301,
            CONF_AUTH_MODE: "standard",
            CONF_STATIONS: f"Lush | https://ice5.somafm.com/lush-128-aac\n{line}",
            CONF_SCAN_INTERVAL: 30,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STATIONS: "invalid_station"}
    assert result["description_placeholders"]["line"] == line.strip()


async def test_options_new_host_unreachable(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301()})
    with fleet.patched():
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOSTS: f"{HOST_8301}\n{HOST_OLD}",
                CONF_AUTH_MODE: "standard",
                CONF_STATIONS: DEFAULT_STATIONS,
                CONF_SCAN_INTERVAL: 30,
            },
        )
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"]["hosts"] == HOST_OLD
    assert entry.data[CONF_HOSTS] == [HOST_8301]


async def test_options_auth_mode_change_rechecks_every_host(hass: HomeAssistant) -> None:
    entry = _entry(hass)
    fleet = Fleet({HOST_8301: make_8301()})  # wants HMAC, so "none" is refused
    with fleet.patched():
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOSTS: HOST_8301,
                CONF_AUTH_MODE: "none",
                CONF_STATIONS: DEFAULT_STATIONS,
                CONF_SCAN_INTERVAL: 30,
            },
        )
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_AUTH_MODE] == "standard"


# --- parsing ---------------------------------------------------------------------------------


def test_parse_hosts() -> None:
    assert parse_hosts("a, b\nc  a\n") == ["a", "b", "c"]
    assert parse_hosts("") == []


def test_parse_default_stations() -> None:
    stations = parse_stations(DEFAULT_STATIONS)
    assert len(stations) == 7
    assert stations[0] == ("Groove Salad", "https://ice5.somafm.com/groovesalad-128-aac")
    assert stations[-1] == ("Doomed", "https://ice5.somafm.com/doomed-128-aac")


def test_parse_stations_rejects_duplicate_names() -> None:
    with pytest.raises(StationLineError):
        parse_stations("A | https://x.example/1\nA | https://x.example/2")
