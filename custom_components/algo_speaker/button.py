"""Test tone and stop tone buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlgoConfigEntry
from .entity import AlgoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlgoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Both buttons on every writable device."""
    entities: list[ButtonEntity] = []
    for c in entry.runtime_data.coordinators.values():
        if not c.read_only:
            entities += [AlgoTestToneButton(c, "test_tone"), AlgoStopToneButton(c, "stop_tone")]
    async_add_entities(entities)


class AlgoTestToneButton(AlgoEntity, ButtonEntity):
    """The device's built-in test tone (the 8410 also flashes its strobe)."""

    async def async_press(self) -> None:
        """POST /api/controls/test/start."""
        await self._device_call(self.coordinator.client.test_tone())


class AlgoStopToneButton(AlgoEntity, ButtonEntity):
    """Stop whatever tone is playing."""

    async def async_press(self) -> None:
        """POST /api/controls/tone/stop."""
        await self._device_call(self.coordinator.client.tone_stop())
