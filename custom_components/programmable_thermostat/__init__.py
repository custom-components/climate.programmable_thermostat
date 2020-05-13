"""
This is an upgraded version of Generic Thermostat.
This, compared to the old one allow to have a variable target temperature according to a sensor.
Best use is with 'file_restore' that allow to program a temperature profile and the heating system will make your home confortable.
"""
import os
import logging
import asyncio

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
from integrationhelper.const import CC_STARTUP_VERSION
from .climate import ProgrammableThermostat
from .const import (
    VERSION,
    DOMAIN,
    PLATFORM,
    ISSUE_URL
)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    _LOGGER.info(
        CC_STARTUP_VERSION.format(name=DOMAIN, version=VERSION, issue_link=ISSUE_URL)
    )
    return True

async def async_setup_entry(hass, config_entry):
    """Set up this integration using UI."""
    if config_entry.source == config_entries.SOURCE_IMPORT:
        # We get here if the integration is set up using YAML
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return True
    undo_listener = config_entry.add_update_listener(update_listener)
    _LOGGER.info("Added new ProgrammableThermostat entity, entry_id: %s", config_entry.entry_id)
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM))

    return True

async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await asyncio.gather(hass.config_entries.async_forward_entry_unload(config_entry, PLATFORM))

    hass.data[DOMAIN][config_entry.entry_id]["undo_update_listener"]()
    if unload_ok:
        _LOGGER.info("Removed ProgrammableThermostat entity, entry_id: %s", config_entry.entry_id)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok

async def update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
