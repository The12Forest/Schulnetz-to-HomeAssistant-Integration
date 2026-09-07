"""The Schulnetz integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import COORDINATOR, DOMAIN, STRUCTURE_HASH
from .coordinator import SchulnetzCoordinator, structural_hash

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SchulnetzCoordinator(hass, entry)

    try:
        await coordinator.async_push_credentials()
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Could not push credentials to Schulnetz server: {err}"
        ) from err

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not fetch Schulnetz data: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        STRUCTURE_HASH: structural_hash(coordinator.data),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _on_coordinator_update() -> None:
        """Reload the entry when the set of subjects/exams changes."""
        store = hass.data[DOMAIN][entry.entry_id]
        new_hash = structural_hash(coordinator.data)
        if new_hash != store[STRUCTURE_HASH]:
            _LOGGER.info("Schulnetz structure changed; reloading entities")
            store[STRUCTURE_HASH] = new_hash
            await hass.config_entries.async_reload(entry.entry_id)

    coordinator.async_add_listener(_on_coordinator_update)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
