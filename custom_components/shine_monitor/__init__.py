"""Initialize the Shine Monitor integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_COMPANY_KEY,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_TOKEN,
    CONF_SECRET,
)
from .coordinator import ShineMonitorAPIClient, ShineMonitorDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Shine Monitor component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shine Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client using Home Assistant's shared session
    session = async_get_clientsession(hass)
    client = ShineMonitorAPIClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        company_key=entry.data[CONF_COMPANY_KEY],
    )

    # Set stored token/secret if available
    if entry.data.get(CONF_TOKEN) and entry.data.get(CONF_SECRET):
        client.set_credentials(
            token=entry.data[CONF_TOKEN],
            secret=entry.data[CONF_SECRET],
        )

    # Create coordinator
    coordinator = ShineMonitorDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        plant_id=entry.data[CONF_PLANT_ID],
        plant_name=entry.data.get(CONF_PLANT_NAME, f"Plant {entry.data[CONF_PLANT_ID]}"),
    )

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up services (only once)
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unload services if no more entries
    if not hass.data[DOMAIN]:
        await async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
