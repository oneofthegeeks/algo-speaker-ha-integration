"""One DataUpdateCoordinator per Algo device."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AlgoAuthError, AlgoClient, AlgoError, DeviceIdentity
from .const import (
    DOMAIN,
    KEY_MCAST_MODE,
    KEY_PAGE_VOL,
    KEY_RADIO_URL,
    KEY_RADIO_USE,
    KEY_RING_VOL,
    MANUFACTURER,
    RADIO_MODEL,
    STROBE_BRIGHTNESS,
    STROBE_BRIGHTNESS_8190S,
    STROBE_MODELS,
)

if TYPE_CHECKING:
    from . import AlgoConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AlgoData:
    """One poll of a device."""

    settings: dict[str, str | None] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)


class AlgoCoordinator(DataUpdateCoordinator[AlgoData]):
    """Polls one device: status, then a few settings, one request at a time."""

    config_entry: AlgoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AlgoConfigEntry,
        client: AlgoClient,
        identity: DeviceIdentity,
        scan_interval: int,
    ) -> None:
        """Set up polling for one host."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Algo {identity.host}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.identity = identity
        # The station the Music switch plays: the last one seen playing or chosen. STOP clears
        # radio.url on the device, so this is the only memory of it (lost on restart).
        self.last_station_url: str | None = None
        # The strobe's state can't be read back from the device; it is what was last sent.
        self.strobe_on = False

    # -- what the device is --

    @property
    def host(self) -> str:
        """The address the device was configured with."""
        return self.identity.host

    @property
    def device_uid(self) -> str:
        """Stable id for the device: its MAC when known, else its host."""
        return format_mac(self.identity.mac) if self.identity.mac else self.identity.host

    @property
    def read_only(self) -> bool:
        """Firmware too old for control."""
        return self.identity.read_only

    @property
    def is_radio(self) -> bool:
        """The 8301 has internet radio."""
        return self.identity.model == RADIO_MODEL and not self.read_only

    @property
    def has_strobe(self) -> bool:
        """Only some models have a strobe."""
        return self.identity.model in STROBE_MODELS and not self.read_only

    @property
    def strobe_levels(self) -> dict[str, int]:
        """ledlvl per brightness name for this model."""
        return STROBE_BRIGHTNESS_8190S if self.identity.model == "8190S" else STROBE_BRIGHTNESS

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry entry."""
        ident = self.identity
        info = DeviceInfo(
            identifiers={(DOMAIN, self.device_uid)},
            manufacturer=MANUFACTURER,
            model=ident.model or ident.product,
            name=f"Algo {ident.model} {ident.host}" if ident.model else f"Algo {ident.host}",
            sw_version=ident.firmware,
            configuration_url=f"{self.client.scheme or 'http'}://{ident.host}",
        )
        if ident.mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(ident.mac))}
        return info

    # -- polling --

    @property
    def setting_keys(self) -> list[str]:
        """The settings read on every poll."""
        keys = [KEY_PAGE_VOL, KEY_RING_VOL, KEY_MCAST_MODE]
        if self.is_radio:
            keys += [KEY_RADIO_USE, KEY_RADIO_URL]
        return keys

    async def _async_update_data(self) -> AlgoData:
        try:
            status = {} if self.read_only else await self.client.get_status()
            settings = await self.client.get_settings(self.setting_keys)
        except AlgoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AlgoError as err:
            raise UpdateFailed(str(err)) from err
        data = AlgoData(settings=settings, status=status)
        if self.music_on(data):
            self.last_station_url = settings.get(KEY_RADIO_URL)
        return data

    @staticmethod
    def music_on(data: AlgoData | None) -> bool:
        """The house convention: on when radio.use is "1" and radio.url is set."""
        if data is None:
            return False
        return data.settings.get(KEY_RADIO_USE) == "1" and bool(data.settings.get(KEY_RADIO_URL))

    def patch_settings(self, values: dict[str, str | None]) -> None:
        """Apply a write we know succeeded, so entities update before the next poll."""
        if self.data is None:
            return
        self.data.settings.update(values)
        self.async_update_listeners()
