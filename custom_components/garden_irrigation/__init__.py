"""Garden Irrigation integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ZONES, CONF_ZONE_ID, CONF_ZONE_NAME, CONF_ZONE_ENABLED
from .coordinator import GardenIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = ["sensor", "switch", "button", "number"]

_LOVELACE_URL_PATH = "garden-irrigation"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garden Irrigation from a config entry."""
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    zones = [z for z in entry.data.get(CONF_ZONES, []) if z.get(CONF_ZONE_ENABLED, True)]
    hass.async_create_task(_async_setup_dashboard(hass, entry, zones))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_setup_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, zones: list[dict]
) -> None:
    """Auto-create a Lovelace dashboard for this integration on first setup."""
    try:
        from homeassistant.components import lovelace as lovelace_component
        from homeassistant.components.lovelace import dashboard as lovelace_dashboard
        from homeassistant.helpers.storage import Store

        lovelace_data = hass.data.get(lovelace_component.DOMAIN)
        if lovelace_data is None:
            _LOGGER.debug("Lovelace not available yet, skipping dashboard creation")
            return

        if _LOVELACE_URL_PATH in lovelace_data.get("dashboards", {}):
            return

        dashboard_config = _build_dashboard_config(entry, zones)

        store = Store(hass, 1, f"lovelace.{_LOVELACE_URL_PATH}")
        await store.async_save({"config": dashboard_config})

        ll_config = {
            "mode": "storage",
            "url_path": _LOVELACE_URL_PATH,
            "title": "Tuinbewatering",
            "icon": "mdi:sprinkler-variant",
            "show_in_sidebar": True,
            "require_admin": False,
        }
        ll = lovelace_dashboard.LovelaceStorage(hass, ll_config)
        lovelace_data["dashboards"][_LOVELACE_URL_PATH] = ll
        hass.bus.async_fire("lovelace_updated", {"url_path": _LOVELACE_URL_PATH})
        _LOGGER.info("Garden Irrigation dashboard created at /%s", _LOVELACE_URL_PATH)

    except Exception as exc:
        _LOGGER.warning(
            "Could not auto-create dashboard (not critical): %s. "
            "Import dashboard/lovelace_dashboard.yaml manually.",
            exc,
        )


def _build_dashboard_config(entry: ConfigEntry, zones: list[dict]) -> dict:
    zone_cards = []
    for zone in zones:
        zid = zone[CONF_ZONE_ID]
        zname = zone[CONF_ZONE_NAME]
        zone_cards.append({
            "type": "entities",
            "title": zname,
            "entities": [
                {"entity": f"sensor.{DOMAIN}_advice_{zid}", "name": "Advies"},
                {"entity": f"sensor.{DOMAIN}_recommended_duration_{zid}", "name": "Aanbevolen duur"},
                {"entity": f"number.{DOMAIN}_duration_{zid}", "name": "Ingestelde duur"},
                {"entity": f"switch.{DOMAIN}_start_{zid}", "name": "Starten"},
            ],
        })

    return {
        "views": [{
            "title": "Overzicht",
            "path": "garden-irrigation-overview",
            "icon": "mdi:sprinkler-variant",
            "cards": [
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {"type": "entity", "entity": f"sensor.{DOMAIN}_status", "name": "Status"},
                        {"type": "entity", "entity": f"sensor.{DOMAIN}_dry_days", "name": "Droge dagen"},
                        {"type": "entity", "entity": f"sensor.{DOMAIN}_hot_days", "name": "Hete dagen"},
                    ],
                },
                {
                    "type": "entities",
                    "title": "Besturing",
                    "entities": [
                        {"entity": f"switch.{DOMAIN}_auto_mode", "name": "Automodus"},
                        {"entity": f"switch.{DOMAIN}_leak_detection_switch", "name": "Lekdetectie"},
                        {"entity": f"number.{DOMAIN}_rain_threshold", "name": "Regendrempel"},
                        {
                            "type": "button",
                            "name": "Stop alle zones",
                            "tap_action": {
                                "action": "call-service",
                                "service": "button.press",
                                "target": {"entity_id": f"button.{DOMAIN}_stop_all"},
                            },
                            "icon": "mdi:stop-circle-outline",
                        },
                    ],
                },
                *zone_cards,
                {
                    "type": "history-graph",
                    "title": "Waterverbruik",
                    "hours_to_show": 168,
                    "entities": [
                        {"entity": f"sensor.{DOMAIN}_consumption_today", "name": "Vandaag"},
                        {"entity": f"sensor.{DOMAIN}_consumption_week", "name": "Deze week"},
                    ],
                },
                {
                    "type": "entities",
                    "title": "Laatste sessie",
                    "entities": [
                        {"entity": f"sensor.{DOMAIN}_last_session", "name": "Starttijd"},
                    ],
                },
            ],
        }],
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)
    return True
