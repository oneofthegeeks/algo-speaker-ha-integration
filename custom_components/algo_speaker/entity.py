"""Base entity for Algo devices."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AlgoError
from .const import DOMAIN
from .coordinator import AlgoCoordinator


class AlgoEntity(CoordinatorEntity[AlgoCoordinator]):
    """An entity on one Algo device, named from its translation key."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AlgoCoordinator, key: str) -> None:
        """Tie the entity to its device."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_uid}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def settings(self) -> dict[str, str | None]:
        """The settings from the last poll ({} before the first good one)."""
        data = self.coordinator.data
        return data.settings if data else {}

    @property
    def status(self) -> dict[str, Any]:
        """/api/info/status from the last poll."""
        data = self.coordinator.data
        return data.status if data else {}

    async def _device_call[T](self, call: Awaitable[T]) -> T:
        """Run a device request, turning a device error into a Home Assistant one."""
        return await device_call(self.coordinator.host, call)


async def device_call[T](host: str, call: Awaitable[T]) -> T:
    """Await ``call``; raise HomeAssistantError naming the device if it fails."""
    try:
        return await call
    except AlgoError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_error",
            translation_placeholders={"device": host, "error": str(err)},
        ) from err
