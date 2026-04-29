"""Button platform for Garden Irrigation."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        StopAllButton(coordinator, entry),
        TestEveningNotificationButton(coordinator, entry),
    ])


class StopAllButton(CoordinatorEntity[GardenIrrigationCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "stop_all"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_stop_all"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Garden Irrigation",
            "manufacturer": "Garden Irrigation",
            "model": "v0.1.0",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_stop_all()


class TestEveningNotificationButton(CoordinatorEntity[GardenIrrigationCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "test_evening_notification"
    _attr_icon = "mdi:bell-ring-outline"
    _attr_entity_registry_enabled_default = False  # hidden by default, enable to use

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_test_evening_notification"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Garden Irrigation",
            "manufacturer": "Garden Irrigation",
            "model": "v0.1.0",
        }

    async def async_press(self) -> None:
        await self.coordinator._send_notification(
            message="Dit is een testmelding van Garden Irrigation.\nLong press om de actieknoppen te zien.",
            title="🌱 Test avondmelding",
            actions=[
                {
                    "action": "IRRIGATE_CONFIRM_test",
                    "title": "✓ In orde gemaakt",
                },
                {
                    "action": "IRRIGATE_SKIP_test",
                    "title": "Overslaan",
                    "destructive": True,
                },
            ],
        )
