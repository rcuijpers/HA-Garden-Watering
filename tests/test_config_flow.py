"""Tests for the Garden Irrigation config flow."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.garden_irrigation.config_flow import (
    GardenIrrigationConfigFlow,
    _validate_time,
)
import voluptuous as vol


# ---------------------------------------------------------------------------
# _validate_time
# ---------------------------------------------------------------------------

class TestValidateTime:
    def test_valid_times(self):
        assert _validate_time("06:00") == "06:00"
        assert _validate_time("20:30") == "20:30"
        assert _validate_time("00:00") == "00:00"
        assert _validate_time("23:59") == "23:59"

    def test_invalid_times(self):
        for bad in ("24:00", "6:00", "06:60", "abc", ""):
            with pytest.raises(vol.Invalid):
                _validate_time(bad)


# ---------------------------------------------------------------------------
# Config flow step tests (mocked HA)
# ---------------------------------------------------------------------------

def _make_mock_hass():
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services.async_call = AsyncMock(return_value={})
    return hass


class TestConfigFlowSteps:
    """Test each step of the config flow in isolation."""

    def _make_flow(self):
        flow = GardenIrrigationConfigFlow()
        flow.hass = _make_mock_hass()
        flow.context = {}
        flow.async_show_form = MagicMock(side_effect=lambda **kw: {"type": "form", **kw})
        flow.async_create_entry = MagicMock(side_effect=lambda **kw: {"type": "create_entry", **kw})
        return flow

    @pytest.mark.asyncio
    async def test_step_user_shows_form_without_input(self):
        flow = self._make_flow()
        result = await flow.async_step_user(user_input=None)
        assert result["type"] == "form"
        assert result["step_id"] == "main_valve"

    @pytest.mark.asyncio
    async def test_step_user_stores_main_valve(self):
        flow = self._make_flow()
        flow.async_step_zones = AsyncMock(return_value={"type": "form", "step_id": "zones"})
        result = await flow.async_step_user(user_input={"main_valve": "switch.garden"})
        assert flow._data["main_valve"] == "switch.garden"

    @pytest.mark.asyncio
    async def test_zones_step_validates_count(self):
        flow = self._make_flow()
        result = await flow.async_step_zones(user_input={"zone_count": 9})
        assert result["errors"]["zone_count"] == "invalid_threshold"

    @pytest.mark.asyncio
    async def test_zone_detail_requires_name(self):
        flow = self._make_flow()
        flow._zone_count = 1
        flow._current_zone = 0
        flow._zones = []
        result = await flow.async_step_zone_detail(user_input={
            "name": "",
            "type": "drip",
            "default_duration": 20,
            "enabled": True,
        })
        assert result["errors"]["name"] == "zone_name_empty"

    @pytest.mark.asyncio
    async def test_zone_detail_stores_zone(self):
        flow = self._make_flow()
        flow._zone_count = 1
        flow._current_zone = 0
        flow._zones = []
        flow.async_step_weather = AsyncMock(return_value={"type": "form", "step_id": "weather"})
        await flow.async_step_zone_detail(user_input={
            "name": "Moestuin",
            "type": "drip",
            "default_duration": 20,
            "enabled": True,
        })
        assert len(flow._zones) == 1
        assert flow._zones[0]["name"] == "Moestuin"
        assert flow._zones[0]["id"] == "zone_1"

    @pytest.mark.asyncio
    async def test_weather_step_rejects_negative_threshold(self):
        flow = self._make_flow()
        result = await flow.async_step_weather(user_input={
            "weather_entity": "weather.home",
            "rain_threshold": -1,
            "temp_threshold": 20,
        })
        assert "rain_threshold" in result["errors"]

    @pytest.mark.asyncio
    async def test_notifications_rejects_bad_time(self):
        flow = self._make_flow()
        result = await flow.async_step_notifications(user_input={
            "notify_service": "notify.test",
            "evening_advice_time": "25:00",
            "morning_start_time": "06:00",
            "auto_start": False,
            "require_confirmation": True,
        })
        assert "evening_advice_time" in result["errors"]

    @pytest.mark.asyncio
    async def test_full_happy_path_creates_entry(self):
        flow = self._make_flow()
        flow._data = {
            "main_valve": "switch.garden",
            "zones": [{"id": "zone_1", "name": "Tuin", "type": "drip",
                        "flow_entity": None, "default_duration": 20, "enabled": True}],
            "weather_entity": "weather.home",
            "precipitation_sensor": None,
            "temperature_sensor": None,
            "rain_threshold": 5.0,
            "temp_threshold": 20.0,
            "flow_sensor": None,
            "idle_threshold": 0.5,
            "leak_detection": False,
            "leak_check_interval": 5,
        }
        await flow.async_step_notifications(user_input={
            "notify_service": "notify.mobile",
            "evening_advice_time": "20:00",
            "morning_start_time": "06:00",
            "auto_start": False,
            "require_confirmation": True,
        })
        flow.async_create_entry.assert_called_once()
        call_kwargs = flow.async_create_entry.call_args.kwargs
        assert call_kwargs["title"] == "Garden Irrigation"
        assert call_kwargs["data"]["notify_service"] == "notify.mobile"
