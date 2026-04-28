"""DataUpdateCoordinator for Garden Irrigation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    COORDINATOR_UPDATE_INTERVAL,
    STORAGE_KEY_DROUGHT,
    STORAGE_VERSION,
    FLOW_VERIFY_DELAY,
    DRY_DAY_MULTIPLIER,
    HOT_DAY_MULTIPLIER,
    MAX_DRY_MULTIPLIER,
    MAX_HEAT_MULTIPLIER,
    MAX_COMBINED_MULTIPLIER,
    SPRINKLER_COMBINED_CAP,
    ADVICE_SKIP,
    ADVICE_OPTIONAL,
    ADVICE_RECOMMENDED,
    ADVICE_URGENT,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_LEAK_DETECTED,
    ZONE_TYPE_DRIP,
    ZONE_TYPE_SPRINKLER,
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
)

_LOGGER = logging.getLogger(__name__)


class GardenIrrigationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches weather data and manages irrigation sessions."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self._entry = entry
        self._config = entry.data

        self._status: str = STATUS_IDLE
        self._active_zone: str | None = None
        self._session_lock = asyncio.Lock()

        self._consumption_today: float = 0.0
        self._consumption_week: float = 0.0
        self._last_session: dict | None = None

        self._auto_mode: bool = False
        self._leak_detection_enabled: bool = self._config.get(CONF_LEAK_DETECTION, False)

        self._dry_days: int = 0
        self._hot_days: int = 0

        storage_key = STORAGE_KEY_DROUGHT.format(entry_id=entry.entry_id)
        self._store: Store = Store(hass, STORAGE_VERSION, storage_key)
        self._leak_task: asyncio.Task | None = None

    async def async_setup(self) -> None:
        """Load persisted drought state and start background tasks."""
        stored = await self._store.async_load()
        if stored:
            self._dry_days = stored.get("dry_days", 0)
            self._hot_days = stored.get("hot_days", 0)
            last_watered = stored.get("last_watered")
            if last_watered:
                self._last_session = self._last_session or {}
                self._last_session.setdefault("started", last_watered)

        if self._leak_detection_enabled and self._config.get(CONF_FLOW_SENSOR):
            self._start_leak_detection_task()

        self._setup_scheduled_tasks()

    def _setup_scheduled_tasks(self) -> None:
        """Register time-based and state-based listeners for automation logic."""
        evening_time = self._config.get(CONF_EVENING_ADVICE_TIME, "20:00")
        morning_time = self._config.get(CONF_MORNING_START_TIME, "06:00")

        e_hour, e_min = (int(x) for x in evening_time.split(":"))
        m_hour, m_min = (int(x) for x in morning_time.split(":"))

        self._unsub_evening = async_track_time_change(
            self.hass, self._async_send_evening_advice, hour=e_hour, minute=e_min, second=0
        )
        self._unsub_morning = async_track_time_change(
            self.hass, self._async_morning_auto_start, hour=m_hour, minute=m_min, second=0
        )

        # Watch all advice sensors for rain-cancel
        self._unsub_rain_cancel = async_track_state_change_event(
            self.hass,
            [f"sensor.{DOMAIN}_advice_{z[CONF_ZONE_ID]}"
             for z in self._config.get(CONF_ZONES, [])],
            self._async_rain_cancel_listener,
        )

    @callback
    def _async_send_evening_advice(self, now) -> None:
        self.hass.async_create_task(self._send_evening_advice())

    async def _send_evening_advice(self) -> None:
        """Send an evening notification with tomorrow's watering advice."""
        if not self.data:
            return
        lines = []
        icon_map = {ADVICE_SKIP: "🚫", ADVICE_OPTIONAL: "💧",
                    ADVICE_RECOMMENDED: "💦", ADVICE_URGENT: "🚨"}
        for zone in self._config.get(CONF_ZONES, []):
            if not zone.get(CONF_ZONE_ENABLED, True):
                continue
            zone_id = zone[CONF_ZONE_ID]
            advice = self.data.get("advice", {}).get(zone_id, {})
            level = advice.get("level", ADVICE_OPTIONAL)
            duration = advice.get("recommended_duration", zone.get(CONF_ZONE_DEFAULT_DURATION))
            reason = advice.get("reason", "")
            split = advice.get("split_session_suggested", False)
            icon = icon_map.get(level, "💧")
            line = f"{icon} {zone[CONF_ZONE_NAME]}: {level} ({duration} min)"
            if reason:
                line += f" — {reason}"
            if split:
                line += " ⚠️ gesplitste sessie aanbevolen"
            lines.append(line)

        message = (
            f"Droge dagen: {self._dry_days}, Hete dagen: {self._hot_days}\n\n"
            + "\n".join(lines)
        )
        await self._send_notification(message, title="🌱 Bewateringsadvies voor morgen")

    @callback
    def _async_morning_auto_start(self, now) -> None:
        if self._config.get(CONF_AUTO_START) and self._auto_mode:
            self.hass.async_create_task(self._morning_auto_start())

    async def _morning_auto_start(self) -> None:
        """Start all zones whose advice is recommended or urgent."""
        if not self.data or self._status == STATUS_RUNNING:
            return
        for zone in self._config.get(CONF_ZONES, []):
            if not zone.get(CONF_ZONE_ENABLED, True):
                continue
            zone_id = zone[CONF_ZONE_ID]
            level = self.data.get("advice", {}).get(zone_id, {}).get("level")
            if level in (ADVICE_RECOMMENDED, ADVICE_URGENT):
                await self.async_start_zone(zone_id)

    @callback
    def _async_rain_cancel_listener(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state and new_state.state == ADVICE_SKIP and self._status == STATUS_RUNNING:
            self.hass.async_create_task(self._rain_cancel())

    async def _rain_cancel(self) -> None:
        await self.async_stop_all()
        await self._send_notification(
            "De bewatering is gestopt wegens verwachte neerslag.",
            title="🌧️ Bewatering geannuleerd",
        )

    async def async_shutdown(self) -> None:
        """Cancel background tasks and listeners on unload."""
        if self._leak_task and not self._leak_task.done():
            self._leak_task.cancel()
        for unsub in ("_unsub_evening", "_unsub_morning", "_unsub_rain_cancel"):
            fn = getattr(self, unsub, None)
            if fn:
                fn()

    # ------------------------------------------------------------------
    # DataUpdateCoordinator interface
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch weather data and recalculate advice."""
        try:
            forecast_rain, current_temp = await self._fetch_weather()
        except Exception as exc:
            raise UpdateFailed(f"Weather fetch failed: {exc}") from exc

        await self._update_drought_counters(forecast_rain, current_temp)

        advice: dict[str, dict] = {}
        for zone in self._config.get(CONF_ZONES, []):
            if not zone.get(CONF_ZONE_ENABLED, True):
                continue
            advice[zone[CONF_ZONE_ID]] = self._calculate_zone_advice(
                zone, forecast_rain, current_temp
            )

        return {
            "advice": advice,
            "consumption_today": self._consumption_today,
            "consumption_week": self._consumption_week,
            "last_session": self._last_session,
            "status": self._status,
            "active_zone": self._active_zone,
            "dry_days": self._dry_days,
            "hot_days": self._hot_days,
            "forecast_rain_24h": forecast_rain,
            "current_temp": current_temp,
        }

    # ------------------------------------------------------------------
    # Weather helpers
    # ------------------------------------------------------------------

    async def _fetch_weather(self) -> tuple[float, float]:
        """Return (forecast_rain_mm, current_temp_celsius)."""
        rain = await self._get_precipitation()
        temp = self._get_temperature()
        return rain, temp

    async def _get_precipitation(self) -> float:
        """Get precipitation forecast for the next 24 hours."""
        precip_sensor = self._config.get(CONF_PRECIPITATION_SENSOR)
        if precip_sensor:
            state = self.hass.states.get(precip_sensor)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    return float(state.state)
                except ValueError:
                    pass

        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return 0.0

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            forecasts = (response or {}).get(weather_entity, {}).get("forecast", [])
            total_rain = 0.0
            cutoff = dt_util.utcnow() + timedelta(hours=24)
            for fc in forecasts:
                fc_time_str = fc.get("datetime")
                if not fc_time_str:
                    continue
                try:
                    fc_time = datetime.fromisoformat(fc_time_str)
                    if fc_time.tzinfo is None:
                        fc_time = fc_time.replace(tzinfo=timezone.utc)
                    if fc_time > cutoff:
                        break
                except ValueError:
                    continue
                total_rain += float(fc.get("precipitation", 0) or 0)
            return total_rain
        except Exception:
            _LOGGER.debug("Could not fetch hourly forecast, trying daily")

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            forecasts = (response or {}).get(weather_entity, {}).get("forecast", [])
            if forecasts:
                return float(forecasts[0].get("precipitation", 0) or 0)
        except Exception:
            _LOGGER.debug("Could not fetch daily forecast for %s", weather_entity)

        return 0.0

    def _get_temperature(self) -> float:
        """Get current temperature."""
        temp_sensor = self._config.get(CONF_TEMPERATURE_SENSOR)
        if temp_sensor:
            state = self.hass.states.get(temp_sensor)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    return float(state.state)
                except ValueError:
                    pass

        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if weather_entity:
            state = self.hass.states.get(weather_entity)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    return float(state.attributes.get("temperature", 0))
                except (ValueError, TypeError):
                    pass

        return 0.0

    # ------------------------------------------------------------------
    # Drought tracking
    # ------------------------------------------------------------------

    async def _update_drought_counters(self, rain: float, temp: float) -> None:
        """Update consecutive dry/hot day counters once per calendar day."""
        today_key = dt_util.now().date().isoformat()
        stored = await self._store.async_load() or {}

        if stored.get("last_update_date") == today_key:
            return

        rain_threshold = self._config.get(CONF_RAIN_THRESHOLD, 5.0)
        temp_threshold = self._config.get(CONF_TEMP_THRESHOLD, 20.0)

        if rain >= rain_threshold:
            self._dry_days = 0
        else:
            self._dry_days += 1

        if temp >= temp_threshold:
            self._hot_days += 1
        else:
            self._hot_days = 0

        await self._store.async_save({
            **stored,
            "dry_days": self._dry_days,
            "hot_days": self._hot_days,
            "last_update_date": today_key,
        })

    # ------------------------------------------------------------------
    # Advice calculation
    # ------------------------------------------------------------------

    def _calculate_zone_advice(
        self,
        zone: dict,
        forecast_rain: float,
        current_temp: float,
    ) -> dict:
        """Determine advice level and recommended duration for a zone."""
        rain_threshold = self._config.get(CONF_RAIN_THRESHOLD, 5.0)
        temp_threshold = self._config.get(CONF_TEMP_THRESHOLD, 20.0)
        base_duration = zone.get(CONF_ZONE_DEFAULT_DURATION, 20)
        zone_type = zone.get(CONF_ZONE_TYPE, ZONE_TYPE_DRIP)

        # Advice level
        if forecast_rain >= rain_threshold:
            level = ADVICE_SKIP
            reason = f"Regen verwacht: {forecast_rain:.1f} mm (drempel {rain_threshold} mm)"
        elif self._dry_days == 0 and current_temp < temp_threshold:
            level = ADVICE_OPTIONAL
            reason = "Geen droge periode, gematigde temperatuur"
        elif self._dry_days >= 3 or (self._dry_days >= 2 and self._hot_days >= 2):
            level = ADVICE_URGENT
            reason = f"{self._dry_days} droge dagen, {self._hot_days} hete dagen — dringende bewatering"
        else:
            level = ADVICE_RECOMMENDED
            reason = f"{self._dry_days} droge dagen, {current_temp:.0f}°C"

        # Duration multipliers
        dry_mult = min(1.0 + self._dry_days * DRY_DAY_MULTIPLIER, MAX_DRY_MULTIPLIER)
        heat_mult = min(1.0 + self._hot_days * HOT_DAY_MULTIPLIER, MAX_HEAT_MULTIPLIER)
        combined = min(dry_mult * heat_mult, MAX_COMBINED_MULTIPLIER)

        split_suggested = False
        if zone_type == ZONE_TYPE_SPRINKLER and combined > SPRINKLER_COMBINED_CAP:
            combined = SPRINKLER_COMBINED_CAP
            split_suggested = True
            reason += " — overweeg gesplitste sessie"

        recommended_duration = round(base_duration * combined)

        return {
            "level": level,
            "reason": reason,
            "recommended_duration": recommended_duration,
            "split_session_suggested": split_suggested,
        }

    # ------------------------------------------------------------------
    # Session management (public API for entities)
    # ------------------------------------------------------------------

    async def async_start_zone(self, zone_id: str, duration_override: int | None = None) -> None:
        """Open main valve and zone valve, run timer, then close."""
        async with self._session_lock:
            if self._status == STATUS_RUNNING:
                _LOGGER.warning("Session already running, ignoring start request for %s", zone_id)
                return

            zone = self._zone_by_id(zone_id)
            if zone is None:
                _LOGGER.error("Zone %s not found", zone_id)
                return

            duration_min = duration_override
            if duration_min is None and self.data:
                duration_min = self.data.get("advice", {}).get(zone_id, {}).get("recommended_duration")
            if duration_min is None:
                duration_min = zone.get(CONF_ZONE_DEFAULT_DURATION, 20)

            self._status = STATUS_RUNNING
            self._active_zone = zone_id
            self.async_set_updated_data({**(self.data or {}), "status": STATUS_RUNNING, "active_zone": zone_id})

        session_start = dt_util.utcnow()
        liters_start = self._read_flow_total()

        try:
            await self._valve_turn_on(self._config[CONF_MAIN_VALVE])
            flow_entity = zone.get(CONF_ZONE_FLOW_ENTITY)
            if flow_entity:
                await self._valve_turn_on(flow_entity)

            if self._config.get(CONF_FLOW_SENSOR):
                await asyncio.sleep(FLOW_VERIFY_DELAY)
                if not self._verify_flow():
                    _LOGGER.warning("Flow verification failed for zone %s — continuing anyway", zone_id)

            await asyncio.sleep(duration_min * 60)

        finally:
            flow_entity = zone.get(CONF_ZONE_FLOW_ENTITY)
            if flow_entity:
                await self._valve_turn_off(flow_entity)
            await self._valve_turn_off(self._config[CONF_MAIN_VALVE])

            duration_sec = (dt_util.utcnow() - session_start).total_seconds()
            liters = max(0.0, self._read_flow_total() - liters_start)

            self._last_session = {
                "started": session_start.isoformat(),
                "duration": int(duration_sec),
                "liters": liters,
            }
            self._consumption_today += liters
            self._consumption_week += liters

            await self._save_last_watered(session_start)

            self._status = STATUS_IDLE
            self._active_zone = None
            await self.async_request_refresh()

    async def async_stop_all(self) -> None:
        """Immediately close all valves."""
        for zone in self._config.get(CONF_ZONES, []):
            flow_entity = zone.get(CONF_ZONE_FLOW_ENTITY)
            if flow_entity:
                await self._valve_turn_off(flow_entity)
        await self._valve_turn_off(self._config[CONF_MAIN_VALVE])
        self._status = STATUS_IDLE
        self._active_zone = None
        self.async_set_updated_data({**(self.data or {}), "status": STATUS_IDLE, "active_zone": None})

    async def async_set_auto_mode(self, enabled: bool) -> None:
        self._auto_mode = enabled
        self.async_set_updated_data({**(self.data or {}), "auto_mode": enabled})

    async def async_set_leak_detection(self, enabled: bool) -> None:
        self._leak_detection_enabled = enabled
        if enabled and self._config.get(CONF_FLOW_SENSOR):
            self._start_leak_detection_task()
        elif not enabled and self._leak_task and not self._leak_task.done():
            self._leak_task.cancel()

    async def async_update_zone_duration(self, zone_id: str, minutes: int) -> None:
        """Persist a duration override for a zone into options."""
        options = dict(self._entry.options)
        overrides = dict(options.get("duration_overrides", {}))
        overrides[zone_id] = minutes
        options["duration_overrides"] = overrides
        self.hass.config_entries.async_update_entry(self._entry, options=options)

    def get_zone_duration(self, zone_id: str) -> int:
        """Return the current (possibly overridden) duration for a zone."""
        override = self._entry.options.get("duration_overrides", {}).get(zone_id)
        if override is not None:
            return int(override)
        zone = self._zone_by_id(zone_id)
        return zone.get(CONF_ZONE_DEFAULT_DURATION, 20) if zone else 20

    # ------------------------------------------------------------------
    # Leak detection background task
    # ------------------------------------------------------------------

    def _start_leak_detection_task(self) -> None:
        if self._leak_task and not self._leak_task.done():
            return
        self._leak_task = self.hass.async_create_task(self._leak_detection_loop())

    async def _leak_detection_loop(self) -> None:
        interval_sec = self._config.get(CONF_LEAK_CHECK_INTERVAL, 5) * 60
        while True:
            await asyncio.sleep(interval_sec)
            if self._status == STATUS_RUNNING:
                continue
            flow_sensor = self._config.get(CONF_FLOW_SENSOR)
            if not flow_sensor:
                break
            state = self.hass.states.get(flow_sensor)
            if state is None or state.state in ("unavailable", "unknown"):
                continue
            try:
                flow = float(state.state)
            except ValueError:
                continue
            idle_threshold = self._config.get(CONF_IDLE_THRESHOLD, 0.5)
            if flow > idle_threshold:
                _LOGGER.warning("Leak detected! Flow: %.2f L/min (threshold: %.2f)", flow, idle_threshold)
                self._status = STATUS_LEAK_DETECTED
                self.async_set_updated_data({**(self.data or {}), "status": STATUS_LEAK_DETECTED})
                await self._send_notification(
                    f"Lek gedetecteerd! Waterflow: {flow:.1f} L/min buiten bewateringstijden."
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _zone_by_id(self, zone_id: str) -> dict | None:
        for zone in self._config.get(CONF_ZONES, []):
            if zone[CONF_ZONE_ID] == zone_id:
                return zone
        return None

    async def _valve_turn_on(self, entity_id: str) -> None:
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(domain, "turn_on", {"entity_id": entity_id}, blocking=True)

    async def _valve_turn_off(self, entity_id: str) -> None:
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(domain, "turn_off", {"entity_id": entity_id}, blocking=True)

    def _verify_flow(self) -> bool:
        """Return True if flow sensor shows water flowing."""
        flow_sensor = self._config.get(CONF_FLOW_SENSOR)
        if not flow_sensor:
            return True
        state = self.hass.states.get(flow_sensor)
        if state is None or state.state in ("unavailable", "unknown"):
            return True
        try:
            return float(state.state) > self._config.get(CONF_IDLE_THRESHOLD, 0.5)
        except ValueError:
            return True

    def _read_flow_total(self) -> float:
        """Read cumulative flow total from sensor (if available)."""
        flow_sensor = self._config.get(CONF_FLOW_SENSOR)
        if not flow_sensor:
            return 0.0
        state = self.hass.states.get(flow_sensor)
        if state is None or state.state in ("unavailable", "unknown"):
            return 0.0
        try:
            return float(state.attributes.get("total_increasing", state.state))
        except (ValueError, TypeError):
            return 0.0

    async def _save_last_watered(self, timestamp: datetime) -> None:
        stored = await self._store.async_load() or {}
        await self._store.async_save({
            **stored,
            "last_watered": timestamp.isoformat(),
            "dry_days": self._dry_days,
            "hot_days": self._hot_days,
        })

    async def _send_notification(self, message: str, title: str = "Tuinbewatering") -> None:
        services = self._config.get(CONF_NOTIFY_SERVICE, [])
        # Support both old string format and new list format
        if isinstance(services, str):
            services = [services]
        for svc in services:
            parts = svc.split(".")
            service_name = parts[-1] if len(parts) > 1 else svc
            try:
                await self.hass.services.async_call(
                    "notify",
                    service_name,
                    {"message": message, "title": title},
                    blocking=False,
                )
            except Exception as exc:
                _LOGGER.warning("Could not send notification to %s: %s", svc, exc)
