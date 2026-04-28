"""Sensor platform for Garden Irrigation."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ADVICE_LEVELS,
    CONF_ZONES,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_ENABLED,
    ATTR_REASON,
    ATTR_RECOMMENDED_DURATION,
    ATTR_DRY_DAYS,
    ATTR_HOT_DAYS,
    ATTR_ZONE_TYPE,
    ATTR_LAST_SESSION_DURATION,
    ATTR_LAST_SESSION_LITERS,
    ATTR_SPLIT_SESSION_SUGGESTED,
)
from .coordinator import GardenIrrigationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = [z for z in entry.data.get(CONF_ZONES, []) if z.get(CONF_ZONE_ENABLED, True)]

    entities: list[SensorEntity] = [
        IrrigationStatusSensor(coordinator, entry),
        ConsumptionTodaySensor(coordinator, entry),
        ConsumptionWeekSensor(coordinator, entry),
        LastSessionSensor(coordinator, entry),
        DryDaysSensor(coordinator, entry),
        HotDaysSensor(coordinator, entry),
    ]

    for zone in zones:
        entities.append(AdviceSensor(coordinator, entry, zone))
        entities.append(RecommendedDurationSensor(coordinator, entry, zone))

    async_add_entities(entities)


class _GardenSensorBase(CoordinatorEntity[GardenIrrigationCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Garden Irrigation",
            "manufacturer": "Garden Irrigation",
            "model": "v0.1.0",
        }


class IrrigationStatusSensor(_GardenSensorBase):
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["idle", "running", "leak_detected"]

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data or {}).get("status")


class ConsumptionTodaySensor(_GardenSensorBase):
    _attr_translation_key = "consumption_today"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_consumption_today"

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("consumption_today")


class ConsumptionWeekSensor(_GardenSensorBase):
    _attr_translation_key = "consumption_week"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_consumption_week"

    @property
    def native_value(self) -> float | None:
        return (self.coordinator.data or {}).get("consumption_week")


class LastSessionSensor(_GardenSensorBase):
    _attr_translation_key = "last_session"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_session"

    @property
    def native_value(self):
        last = (self.coordinator.data or {}).get("last_session")
        if not last:
            return None
        from homeassistant.util.dt import parse_datetime
        return parse_datetime(last["started"])

    @property
    def extra_state_attributes(self) -> dict:
        last = (self.coordinator.data or {}).get("last_session") or {}
        return {
            ATTR_LAST_SESSION_DURATION: last.get("duration"),
            ATTR_LAST_SESSION_LITERS: last.get("liters"),
        }


class DryDaysSensor(_GardenSensorBase):
    _attr_translation_key = "dry_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"
    _attr_icon = "mdi:weather-sunny-off"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_dry_days"

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("dry_days")


class HotDaysSensor(_GardenSensorBase):
    _attr_translation_key = "hot_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"
    _attr_icon = "mdi:thermometer-high"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_hot_days"

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("hot_days")


class AdviceSensor(_GardenSensorBase):
    _attr_translation_key = "advice"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ADVICE_LEVELS
    _attr_icon = "mdi:water-check"

    def __init__(self, coordinator, entry, zone: dict) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone
        self._zone_id = zone[CONF_ZONE_ID]
        self._attr_unique_id = f"{entry.entry_id}_advice_{self._zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone[CONF_ZONE_NAME]}

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data or {}).get("advice", {}).get(self._zone_id, {}).get("level")

    @property
    def extra_state_attributes(self) -> dict:
        zone_advice = (self.coordinator.data or {}).get("advice", {}).get(self._zone_id, {})
        return {
            ATTR_REASON: zone_advice.get("reason"),
            ATTR_RECOMMENDED_DURATION: zone_advice.get("recommended_duration"),
            ATTR_SPLIT_SESSION_SUGGESTED: zone_advice.get("split_session_suggested", False),
            ATTR_DRY_DAYS: (self.coordinator.data or {}).get("dry_days"),
            ATTR_HOT_DAYS: (self.coordinator.data or {}).get("hot_days"),
            ATTR_ZONE_TYPE: self._zone.get("type"),
        }


class RecommendedDurationSensor(_GardenSensorBase):
    _attr_translation_key = "recommended_duration"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry, zone: dict) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone
        self._zone_id = zone[CONF_ZONE_ID]
        self._attr_unique_id = f"{entry.entry_id}_recommended_duration_{self._zone_id}"
        self._attr_translation_placeholders = {"zone_name": zone[CONF_ZONE_NAME]}

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get("advice", {}).get(self._zone_id, {}).get("recommended_duration")
