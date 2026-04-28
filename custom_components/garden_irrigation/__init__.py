"""Garden Irrigation integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator
from .switch import StopAllButton, ZoneDurationNumber, RainThresholdNumber

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = ["sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garden Irrigation from a config entry."""
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Register button and number entities directly
    from homeassistant.helpers import entity_platform as ep
    from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
    from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
    from .const import CONF_ZONES, CONF_ZONE_ID, CONF_ZONE_NAME, CONF_ZONE_ENABLED

    zones = [z for z in entry.data.get(CONF_ZONES, []) if z.get(CONF_ZONE_ENABLED, True)]

    button_entities = [StopAllButton(coordinator, entry)]
    number_entities: list = [RainThresholdNumber(coordinator, entry)]
    for zone in zones:
        number_entities.append(ZoneDurationNumber(coordinator, entry, zone))

    hass.async_create_task(
        _async_add_platform_entities(hass, entry, BUTTON_DOMAIN, button_entities)
    )
    hass.async_create_task(
        _async_add_platform_entities(hass, entry, NUMBER_DOMAIN, number_entities)
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_add_platform_entities(hass, entry, platform_domain, entities):
    """Add entities to a platform domain."""
    from homeassistant.helpers.entity_component import EntityComponent
    component = hass.data.get(platform_domain)
    if component is None:
        return
    await component.async_add_entities(entities)


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
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating config entry from version %s", config_entry.version)
    # Stub for future migrations
    return True
