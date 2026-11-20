"""The Algo Speakers integration: Algo IP speakers, paging adapters and strobes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AUTH_STANDARD, AlgoAuthError, AlgoClient, AlgoError, DeviceIdentity
from .const import (
    CONF_AUTH_MODE,
    CONF_DEVICES,
    CONF_HOSTS,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATIONS,
    DOMAIN,
)
from .coordinator import AlgoCoordinator
from .services import async_setup_services
from .util import StationLineError, parse_stations

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class AlgoRuntimeData:
    """What a loaded entry holds."""

    coordinators: dict[str, AlgoCoordinator]
    stations: list[tuple[str, str]]


type AlgoConfigEntry = ConfigEntry[AlgoRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services once, for every entry."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlgoConfigEntry) -> bool:
    """Identify each device, then start polling it."""
    session = async_get_clientsession(hass)
    password = entry.data.get(CONF_PASSWORD, "")
    auth_mode = entry.data.get(CONF_AUTH_MODE, AUTH_STANDARD)
    hosts: list[str] = entry.data[CONF_HOSTS]
    cache: dict[str, dict[str, Any]] = dict(entry.data.get(CONF_DEVICES, {}))
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    try:
        stations = parse_stations(entry.options.get(CONF_STATIONS, DEFAULT_STATIONS))
    except StationLineError:
        _LOGGER.warning("Ignoring the stations list: a line is not 'Name | URL'")
        stations = []

    clients = {host: AlgoClient(session, host, password, auth_mode) for host in hosts}

    async def identify(host: str) -> DeviceIdentity:
        try:
            identity = await clients[host].identify()
        except AlgoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AlgoError as err:
            if host in cache:
                # Offline now but known: keep its entities (unavailable) and the rest running.
                _LOGGER.info("%s is offline; using its cached identity", host)
                return DeviceIdentity.from_dict(host, cache[host])
            raise ConfigEntryNotReady(f"Cannot reach {host}: {err}") from err
        cache[host] = identity.as_dict()
        return identity

    # Different devices can be asked at once; each client still sends one request at a time.
    identities = await asyncio.gather(*(identify(h) for h in hosts))
    if cache != entry.data.get(CONF_DEVICES):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DEVICES: {h: cache[h] for h in hosts if h in cache}}
        )

    coordinators = {
        identity.host: AlgoCoordinator(hass, entry, clients[identity.host], identity, scan_interval)
        for identity in identities
    }
    # async_refresh, not first_refresh: one dead device must not hold back the others. Run
    # together so each offline device's timeout isn't added one after another.
    await asyncio.gather(*(c.async_refresh() for c in coordinators.values()))
    for identity in identities:
        _sync_read_only_issue(hass, identity)

    entry.runtime_data = AlgoRuntimeData(coordinators=coordinators, stations=stations)
    _remove_stale_devices(hass, entry, coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlgoConfigEntry) -> bool:
    """Unload the platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AlgoConfigEntry) -> None:
    """Drop the read-only repair issues this entry raised."""
    for host in entry.data.get(CONF_HOSTS, []):
        ir.async_delete_issue(hass, DOMAIN, _issue_id(host))


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: AlgoConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow deleting a device only once its host is no longer configured."""
    return not any(
        (DOMAIN, c.device_uid) in device.identifiers
        for c in entry.runtime_data.coordinators.values()
    )


def _issue_id(host: str) -> str:
    return f"firmware_read_only_{host}"


def _sync_read_only_issue(hass: HomeAssistant, identity: DeviceIdentity) -> None:
    if identity.read_only:
        ir.async_create_issue(
            hass,
            DOMAIN,
            _issue_id(identity.host),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="firmware_read_only",
            translation_placeholders={"host": identity.host},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(identity.host))


def _remove_stale_devices(
    hass: HomeAssistant, entry: AlgoConfigEntry, coordinators: dict[str, AlgoCoordinator]
) -> None:
    """Hosts removed in the options flow leave devices behind; detach them from this entry."""
    current = {(DOMAIN, c.device_uid) for c in coordinators.values()}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers & current:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
