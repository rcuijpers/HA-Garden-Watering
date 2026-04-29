"""Config flow for Garden Irrigation integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
    BooleanSelector,
)

from .const import (
    DOMAIN,
    DEFAULT_MAX_ZONES,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_IDLE_THRESHOLD,
    DEFAULT_LEAK_CHECK_INTERVAL,
    DEFAULT_ZONE_DURATION,
    DEFAULT_EVENING_ADVICE_TIME,
    DEFAULT_MORNING_START_TIME,
    ZONE_TYPES,
    CONF_MAIN_VALVE,
    CONF_ZONES,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONE_FLOW_ENTITY,
    CONF_ZONE_DEFAULT_DURATION,
    CONF_ZONE_ENABLED,
    CONF_WEATHER_ENTITY,
    CONF_PRECIPITATION_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_RAIN_THRESHOLD,
    CONF_TEMP_THRESHOLD,
    CONF_FLOW_SENSOR,
    CONF_IDLE_THRESHOLD,
    CONF_LEAK_DETECTION,
    CONF_LEAK_CHECK_INTERVAL,
    CONF_NOTIFY_SERVICE,
    CONF_EVENING_ADVICE_TIME,
    CONF_MORNING_START_TIME,
    CONF_AUTO_START,
    CONF_REQUIRE_CONFIRMATION,
)

def _normalize_time(value: str) -> str:
    """Normalize TimeSelector output (HH:MM:SS or H:MM:SS) to HH:MM."""
    parts = value.split(":")
    return f"{int(parts[0]):02d}:{parts[1]}"


def _entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    return hass.states.get(entity_id) is not None or entity_id == ""


class GardenIrrigationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Garden Irrigation config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}
        self._zones: list[dict] = []
        self._zone_count: int = 1
        self._current_zone: int = 0

    async def async_step_user(self, user_input=None):
        """Step 1: Main valve selection."""
        if user_input is not None:
            self._data[CONF_MAIN_VALVE] = user_input[CONF_MAIN_VALVE]
            return await self.async_step_zones()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MAIN_VALVE): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "valve"])
                ),
            }),
        )

    async def async_step_zones(self, user_input=None):
        """Step 2a: Ask how many zones."""
        errors = {}
        if user_input is not None:
            count = user_input["zone_count"]
            if not (1 <= count <= DEFAULT_MAX_ZONES):
                errors["zone_count"] = "invalid_threshold"
            else:
                self._zone_count = count
                self._current_zone = 0
                self._zones = []
                return await self.async_step_zone_detail()

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema({
                vol.Required("zone_count", default=1): NumberSelector(
                    NumberSelectorConfig(min=1, max=DEFAULT_MAX_ZONES, step=1, mode=NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )

    async def async_step_zone_detail(self, user_input=None):
        """Step 2b: Configure each zone (repeated per zone)."""
        errors = {}
        zone_num = self._current_zone + 1

        if user_input is not None:
            name = user_input.get(CONF_ZONE_NAME, "").strip()
            if not name:
                errors[CONF_ZONE_NAME] = "zone_name_empty"
            else:
                zone = {
                    CONF_ZONE_ID: f"zone_{zone_num}",
                    CONF_ZONE_NAME: name,
                    CONF_ZONE_TYPE: user_input[CONF_ZONE_TYPE],
                    CONF_ZONE_FLOW_ENTITY: user_input.get(CONF_ZONE_FLOW_ENTITY) or None,
                    CONF_ZONE_DEFAULT_DURATION: int(user_input[CONF_ZONE_DEFAULT_DURATION]),
                    CONF_ZONE_ENABLED: user_input.get(CONF_ZONE_ENABLED, True),
                }
                self._zones.append(zone)
                self._current_zone += 1

                if self._current_zone < self._zone_count:
                    return await self.async_step_zone_detail()

                self._data[CONF_ZONES] = self._zones
                return await self.async_step_weather()

        return self.async_show_form(
            step_id="zone_detail",
            data_schema=vol.Schema({
                vol.Required(CONF_ZONE_NAME, default=f"Zone {zone_num}"): TextSelector(),
                vol.Required(CONF_ZONE_TYPE, default="drip"): SelectSelector(
                    SelectSelectorConfig(options=ZONE_TYPES, mode=SelectSelectorMode.LIST, translation_key="zone_type")
                ),
                vol.Optional(CONF_ZONE_FLOW_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "valve"])
                ),
                vol.Required(CONF_ZONE_DEFAULT_DURATION, default=DEFAULT_ZONE_DURATION): NumberSelector(
                    NumberSelectorConfig(min=1, max=240, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ZONE_ENABLED, default=True): BooleanSelector(),
            }),
            description_placeholders={"zone_num": str(zone_num)},
            errors=errors,
        )

    async def async_step_weather(self, user_input=None):
        """Step 3: Weather data configuration."""
        errors = {}
        if user_input is not None:
            for key in (CONF_RAIN_THRESHOLD, CONF_TEMP_THRESHOLD):
                try:
                    val = float(user_input[key])
                    if val < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    errors[key] = "invalid_threshold"

            if not errors:
                self._data.update({
                    CONF_WEATHER_ENTITY: user_input[CONF_WEATHER_ENTITY],
                    CONF_PRECIPITATION_SENSOR: user_input.get(CONF_PRECIPITATION_SENSOR) or None,
                    CONF_TEMPERATURE_SENSOR: user_input.get(CONF_TEMPERATURE_SENSOR) or None,
                    CONF_RAIN_THRESHOLD: float(user_input[CONF_RAIN_THRESHOLD]),
                    CONF_TEMP_THRESHOLD: float(user_input[CONF_TEMP_THRESHOLD]),
                })
                return await self.async_step_flow_meter()

        return self.async_show_form(
            step_id="weather",
            data_schema=vol.Schema({
                vol.Required(CONF_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=["weather"])
                ),
                vol.Optional(CONF_PRECIPITATION_SENSOR): EntitySelector(
                    EntitySelectorConfig(device_class=["precipitation"])
                ),
                vol.Optional(CONF_TEMPERATURE_SENSOR): EntitySelector(
                    EntitySelectorConfig(device_class=["temperature"])
                ),
                vol.Required(CONF_RAIN_THRESHOLD, default=DEFAULT_RAIN_THRESHOLD): NumberSelector(
                    NumberSelectorConfig(min=0, max=100, step=0.5, unit_of_measurement="mm", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_TEMP_THRESHOLD, default=DEFAULT_TEMP_THRESHOLD): NumberSelector(
                    NumberSelectorConfig(min=-10, max=50, step=0.5, unit_of_measurement="°C", mode=NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )

    async def async_step_flow_meter(self, user_input=None):
        """Step 4: Optional flow meter configuration."""
        errors = {}
        if user_input is not None:
            self._data.update({
                CONF_FLOW_SENSOR: user_input.get(CONF_FLOW_SENSOR) or None,
                CONF_IDLE_THRESHOLD: float(user_input.get(CONF_IDLE_THRESHOLD, DEFAULT_IDLE_THRESHOLD)),
                CONF_LEAK_DETECTION: bool(user_input.get(CONF_LEAK_DETECTION, False)),
                CONF_LEAK_CHECK_INTERVAL: int(user_input.get(CONF_LEAK_CHECK_INTERVAL, DEFAULT_LEAK_CHECK_INTERVAL)),
            })
            return await self.async_step_notifications()

        return self.async_show_form(
            step_id="flow_meter",
            data_schema=vol.Schema({
                vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
                    EntitySelectorConfig(device_class=["volume_flow_rate", "water"])
                ),
                vol.Required(CONF_IDLE_THRESHOLD, default=DEFAULT_IDLE_THRESHOLD): NumberSelector(
                    NumberSelectorConfig(min=0, max=50, step=0.1, unit_of_measurement="L/min", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_LEAK_DETECTION, default=False): BooleanSelector(),
                vol.Required(CONF_LEAK_CHECK_INTERVAL, default=DEFAULT_LEAK_CHECK_INTERVAL): NumberSelector(
                    NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )

    async def async_step_notifications(self, user_input=None):
        """Step 5: Notifications and schedule."""
        errors = {}

        # Discover available notify services at runtime so the user can pick their phone
        notify_services = sorted(
            f"notify.{svc}"
            for svc in self.hass.services.async_services().get("notify", {}).keys()
            if svc != "notify"  # skip the generic 'notify.notify' alias if present
        )
        if not notify_services:
            notify_services = ["notify.notify"]

        if user_input is not None:
            if not errors:
                self._data.update({
                    CONF_NOTIFY_SERVICE: user_input[CONF_NOTIFY_SERVICE],  # list
                    CONF_EVENING_ADVICE_TIME: _normalize_time(user_input[CONF_EVENING_ADVICE_TIME]),
                    CONF_MORNING_START_TIME: _normalize_time(user_input[CONF_MORNING_START_TIME]),
                    CONF_AUTO_START: bool(user_input.get(CONF_AUTO_START, False)),
                    CONF_REQUIRE_CONFIRMATION: bool(user_input.get(CONF_REQUIRE_CONFIRMATION, True)),
                })
                return self.async_create_entry(title="Garden Irrigation", data=self._data)

        default_services = notify_services[:1] if notify_services else ["notify.notify"]

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema({
                vol.Required(CONF_NOTIFY_SERVICE, default=default_services): SelectSelector(
                    SelectSelectorConfig(
                        options=notify_services,
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
                vol.Required(CONF_EVENING_ADVICE_TIME, default=DEFAULT_EVENING_ADVICE_TIME): TimeSelector(),
                vol.Required(CONF_MORNING_START_TIME, default=DEFAULT_MORNING_START_TIME): TimeSelector(),
                vol.Required(CONF_AUTO_START, default=False): BooleanSelector(),
                vol.Required(CONF_REQUIRE_CONFIRMATION, default=True): BooleanSelector(),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GardenIrrigationOptionsFlow(config_entry)


class GardenIrrigationOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for post-setup reconfiguration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        data = self._entry.data
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_RAIN_THRESHOLD, default=data.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD)): NumberSelector(
                    NumberSelectorConfig(min=0, max=100, step=0.5, unit_of_measurement="mm", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_TEMP_THRESHOLD, default=data.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD)): NumberSelector(
                    NumberSelectorConfig(min=-10, max=50, step=0.5, unit_of_measurement="°C", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_AUTO_START, default=data.get(CONF_AUTO_START, False)): BooleanSelector(),
                vol.Required(CONF_REQUIRE_CONFIRMATION, default=data.get(CONF_REQUIRE_CONFIRMATION, True)): BooleanSelector(),
                vol.Required(CONF_LEAK_DETECTION, default=data.get(CONF_LEAK_DETECTION, False)): BooleanSelector(),
                vol.Required(CONF_LEAK_CHECK_INTERVAL, default=data.get(CONF_LEAK_CHECK_INTERVAL, DEFAULT_LEAK_CHECK_INTERVAL)): NumberSelector(
                    NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )
