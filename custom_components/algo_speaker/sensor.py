"""Status sensors; read-only (old firmware) devices get their volumes here instead."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlgoConfigEntry
from .api import parse_db
from .const import (
    KEY_MCAST_MODE,
    KEY_PAGE_VOL,
    KEY_RADIO_URL,
    KEY_RING_VOL,
    MCAST_MODES,
    STATUS_RADIO,
)
from .coordinator import AlgoCoordinator
from .entity import AlgoEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlgoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Pick sensors by what each device can do."""
    stations = entry.runtime_data.stations
    entities: list[SensorEntity] = []
    for c in entry.runtime_data.coordinators.values():
        entities.append(AlgoMulticastModeSensor(c, "multicast_mode"))
        if c.read_only:
            entities += [
                AlgoVolumeSensor(c, "page_volume", KEY_PAGE_VOL),
                AlgoVolumeSensor(c, "ring_volume", KEY_RING_VOL),
            ]
            continue
        entities += [
            AlgoStatusSensor(c, "sip_registration", "SIP Registration"),
            AlgoFirmwareSensor(c, "firmware"),
        ]
        if c.is_radio:
            entities += [
                AlgoNowPlayingSensor(c, "now_playing", stations),
                AlgoStatusSensor(c, "radio_status", STATUS_RADIO),
            ]
    async_add_entities(entities)


class AlgoStatusSensor(AlgoEntity, SensorEntity):
    """One field of /api/info/status, as the device words it."""

    def __init__(self, coordinator: AlgoCoordinator, key: str, field: str) -> None:
        """Bind to one status field."""
        super().__init__(coordinator, key)
        self._field = field

    @property
    def native_value(self) -> str | None:
        """The field's text."""
        value = self.status.get(self._field)
        return str(value) if value is not None else None


class AlgoMulticastModeSensor(AlgoEntity, SensorEntity):
    """Status "Multicast Mode" (e.g. "Receiver, RTP: 7, ..."), else mcast.mode as a word."""

    @property
    def native_value(self) -> str | None:
        """Mode text."""
        status = self.status.get("Multicast Mode")
        if status:
            return str(status)
        mode = self.settings.get(KEY_MCAST_MODE)
        return MCAST_MODES.get(mode or "", mode)


class AlgoFirmwareSensor(AlgoEntity, SensorEntity):
    """Firmware version read at setup."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Firmware version string."""
        return self.coordinator.identity.firmware


class AlgoVolumeSensor(AlgoEntity, SensorEntity):
    """A volume on a device that cannot be written."""

    _attr_native_unit_of_measurement = "dB"

    def __init__(self, coordinator: AlgoCoordinator, key: str, setting: str) -> None:
        """Bind to one settings key."""
        super().__init__(coordinator, key)
        self._setting = setting

    @property
    def native_value(self) -> int | None:
        """Level in dB."""
        return parse_db(self.settings.get(self._setting))


class AlgoNowPlayingSensor(AlgoEntity, SensorEntity):
    """Station name, the raw URL when it is not a configured station, or "Stopped"."""

    def __init__(
        self, coordinator: AlgoCoordinator, key: str, stations: list[tuple[str, str]]
    ) -> None:
        """Remember the configured stations."""
        super().__init__(coordinator, key)
        self._names = {url: name for name, url in stations}

    @property
    def native_value(self) -> str | None:
        """What the 8301 is streaming."""
        if self.coordinator.data is None:
            return None
        if not self.coordinator.music_on(self.coordinator.data):
            return "Stopped"
        url = self.settings.get(KEY_RADIO_URL) or ""
        return self._names.get(url, url)
