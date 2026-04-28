"""Switch, Button and Number platforms for Garden Irrigation."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEFAULT_ZONE_DURATION,
    DEFAULT_RAIN_THRESHOLD,
    CONF_ZONES,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_ENABLED,
    CONF_RAIN_THRESHOLD,
    STATUS_RUNNING,
)
from .coordinator import GardenIrrigationCoordinator


def _device_info(entry: ConfigEntry) -> dict:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "Garden Irrigation",
        "manufacturer": "Garden Irrigation",
        "model": "v0.1.0",
    }


# ---------------------------------------------------------------------------
# Switch platform
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = [z for z in entry.data.get(CONF_ZONES, []) if z.get(CONF_ZONE_ENABLED, True)]

    entities: list = [
        AutoModeSwitch(coordinator, entry),
        LeakDetectionSwitch(coordinator, entry),
    ]
    for zone in zones:
        entities.append(ZoneStartSwitch(coordinator, entry, zone))

    async_add_entities(entities)


class _GardenSwitchBase(CoordinatorEntity[GardenIrrigationCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)


class ZoneStartSwitch(_GardenSwitchBase):
    _attr_translation_key = "start_zone"
    _attr_icon = "mdi:water"

    def __init__(self, coordinator, entry, zone: dict) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone
        self._zone_id = zone[CONF_ZONE_ID]
        self._attr_unique_id = f"{entry.entry_id}_start_{self._zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone[CONF_ZONE_NAME]}

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return data.get("status") == STATUS_RUNNING and data.get("active_zone") == self._zone_id

    async def async_turn_on(self, **kwargs) -> None:
        duration = self.coordinator.get_zone_duration(self._zone_id)
        self.hass.async_create_task(self.coordinator.async_start_zone(self._zone_id, duration))

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_stop_all()


class AutoModeSwitch(_GardenSwitchBase):
    _attr_translation_key = "auto_mode"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_auto_mode"

    @property
    def is_on(self) -> bool:
        return self.coordinator._auto_mode

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_mode(False)


class LeakDetectionSwitch(_GardenSwitchBase):
    _attr_translation_key = "leak_detection_switch"
    _attr_icon = "mdi:pipe-leak"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_leak_detection_switch"

    @property
    def is_on(self) -> bool:
        return self.coordinator._leak_detection_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_leak_detection(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_leak_detection(False)


# ---------------------------------------------------------------------------
# Button platform — loaded via __init__ registering the platform separately
# ---------------------------------------------------------------------------

class StopAllButton(CoordinatorEntity[GardenIrrigationCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "stop_all"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stop_all"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_stop_all()


# ---------------------------------------------------------------------------
# Number platform
# ---------------------------------------------------------------------------

class ZoneDurationNumber(CoordinatorEntity[GardenIrrigationCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "duration"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 1
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._zone = zone
        self._zone_id = zone[CONF_ZONE_ID]
        self._attr_unique_id = f"{entry.entry_id}_duration_{self._zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone[CONF_ZONE_NAME]}
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float:
        return float(self.coordinator.get_zone_duration(self._zone_id))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_update_zone_duration(self._zone_id, int(value))
        self.async_write_ha_state()


class RainThresholdNumber(CoordinatorEntity[GardenIrrigationCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "rain_threshold"
    _attr_native_unit_of_measurement = "mm"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rain_threshold"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float:
        return float(
            self._entry.options.get(CONF_RAIN_THRESHOLD)
            or self._entry.data.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD)
        )

    async def async_set_native_value(self, value: float) -> None:
        options = {**self._entry.options, CONF_RAIN_THRESHOLD: value}
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self.coordinator.async_request_refresh()
