"""Tests for the Garden Irrigation coordinator logic."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.const import (
    ADVICE_SKIP,
    ADVICE_OPTIONAL,
    ADVICE_RECOMMENDED,
    ADVICE_URGENT,
    ZONE_TYPE_DRIP,
    ZONE_TYPE_SPRINKLER,
    ZONE_TYPE_OTHER,
)


def _make_zone(zone_id="zone_1", name="Tuin", zone_type=ZONE_TYPE_DRIP, duration=20):
    return {
        "id": zone_id,
        "name": name,
        "type": zone_type,
        "flow_entity": None,
        "default_duration": duration,
        "enabled": True,
    }


def _make_coordinator(zones=None, rain_threshold=5.0, temp_threshold=20.0,
                      dry_days=0, hot_days=0):
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services.async_call = AsyncMock(return_value={})
    hass.async_create_task = MagicMock()

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "main_valve": "switch.garden",
        "zones": zones or [_make_zone()],
        "weather_entity": "weather.home",
        "precipitation_sensor": None,
        "temperature_sensor": None,
        "rain_threshold": rain_threshold,
        "temp_threshold": temp_threshold,
        "flow_sensor": None,
        "idle_threshold": 0.5,
        "leak_detection": False,
        "leak_check_interval": 5,
        "notify_service": "notify.test",
    }
    entry.options = {}

    coordinator = GardenIrrigationCoordinator.__new__(GardenIrrigationCoordinator)
    coordinator.hass = hass
    coordinator._entry = entry
    coordinator._config = entry.data
    coordinator._dry_days = dry_days
    coordinator._hot_days = hot_days
    coordinator._status = "idle"
    coordinator._active_zone = None
    coordinator._auto_mode = False
    coordinator._leak_detection_enabled = False
    coordinator._consumption_today = 0.0
    coordinator._consumption_week = 0.0
    coordinator._last_session = None
    return coordinator


class TestAdviceLevel:
    """Test _calculate_zone_advice returns correct levels."""

    def test_skip_when_rain_exceeds_threshold(self):
        c = _make_coordinator(rain_threshold=5.0)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=6.0, current_temp=18.0)
        assert advice["level"] == ADVICE_SKIP

    def test_optional_when_no_dry_days_and_cool(self):
        c = _make_coordinator(temp_threshold=20.0, dry_days=0, hot_days=0)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=0.0, current_temp=15.0)
        assert advice["level"] == ADVICE_OPTIONAL

    def test_recommended_with_one_dry_day(self):
        c = _make_coordinator(dry_days=1, hot_days=0)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=0.0, current_temp=15.0)
        assert advice["level"] == ADVICE_RECOMMENDED

    def test_recommended_when_hot_but_not_dry(self):
        c = _make_coordinator(dry_days=0, hot_days=3)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=0.0, current_temp=25.0)
        assert advice["level"] == ADVICE_RECOMMENDED

    def test_urgent_after_three_dry_days(self):
        c = _make_coordinator(dry_days=3, hot_days=0)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=0.0, current_temp=15.0)
        assert advice["level"] == ADVICE_URGENT

    def test_urgent_with_two_dry_and_two_hot(self):
        c = _make_coordinator(dry_days=2, hot_days=2)
        advice = c._calculate_zone_advice(_make_zone(), forecast_rain=0.0, current_temp=25.0)
        assert advice["level"] == ADVICE_URGENT


class TestDurationMultipliers:
    """Test that duration multipliers are applied correctly."""

    def test_no_modifier_when_fresh(self):
        c = _make_coordinator(dry_days=0, hot_days=0)
        advice = c._calculate_zone_advice(_make_zone(duration=20), 0.0, 15.0)
        assert advice["recommended_duration"] == 20  # 1.0 × 1.0 = 1.0

    def test_dry_days_increase_duration_for_drip(self):
        c = _make_coordinator(dry_days=3, hot_days=0)
        advice = c._calculate_zone_advice(_make_zone(duration=20, zone_type=ZONE_TYPE_DRIP), 0.0, 15.0)
        # dry_mult = min(1 + 3*0.20, 3.0) = 1.6; heat_mult = 1.0; combined = 1.6
        assert advice["recommended_duration"] == 32  # round(20 * 1.6)

    def test_sprinkler_capped_at_2x(self):
        c = _make_coordinator(dry_days=10, hot_days=10)
        zone = _make_zone(duration=20, zone_type=ZONE_TYPE_SPRINKLER)
        advice = c._calculate_zone_advice(zone, 0.0, 30.0)
        # Combined would be > 2.0 → capped at 2.0 for sprinklers
        assert advice["recommended_duration"] == 40  # round(20 * 2.0)
        assert advice["split_session_suggested"] is True

    def test_drip_not_capped_at_sprinkler_cap(self):
        c = _make_coordinator(dry_days=10, hot_days=10)
        zone = _make_zone(duration=20, zone_type=ZONE_TYPE_DRIP)
        advice = c._calculate_zone_advice(zone, 0.0, 30.0)
        # For drip: combined = min(3.0 * 2.0, 3.5) = 3.5
        assert advice["recommended_duration"] == 70  # round(20 * 3.5)
        assert advice["split_session_suggested"] is False

    def test_max_combined_cap(self):
        c = _make_coordinator(dry_days=20, hot_days=20)
        zone = _make_zone(duration=10, zone_type=ZONE_TYPE_DRIP)
        advice = c._calculate_zone_advice(zone, 0.0, 50.0)
        # dry_mult = 3.0 (capped), heat_mult = 2.0 (capped), combined = min(6.0, 3.5) = 3.5
        assert advice["recommended_duration"] == 35

    def test_no_duration_increase_on_skip(self):
        c = _make_coordinator(dry_days=5, hot_days=5)
        zone = _make_zone(duration=20)
        advice = c._calculate_zone_advice(zone, forecast_rain=10.0, current_temp=30.0)
        assert advice["level"] == ADVICE_SKIP
        # Duration still calculated (user may override skip manually)
        assert advice["recommended_duration"] > 0

    def test_reason_included_in_advice(self):
        c = _make_coordinator(dry_days=2, hot_days=1)
        advice = c._calculate_zone_advice(_make_zone(), 0.0, 22.0)
        assert "reason" in advice
        assert len(advice["reason"]) > 0


class TestZoneDurationOverride:
    """Test coordinator.get_zone_duration respects overrides."""

    def test_returns_default_when_no_override(self):
        c = _make_coordinator()
        c._entry.options = {}
        assert c.get_zone_duration("zone_1") == 20

    def test_returns_override_when_set(self):
        c = _make_coordinator()
        c._entry.options = {"duration_overrides": {"zone_1": 35}}
        assert c.get_zone_duration("zone_1") == 35

    def test_returns_default_for_unknown_zone(self):
        c = _make_coordinator()
        c._entry.options = {}
        assert c.get_zone_duration("zone_99") == 20
