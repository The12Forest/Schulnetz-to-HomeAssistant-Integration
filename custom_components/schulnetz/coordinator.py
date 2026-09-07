"""Data coordinator for the Schulnetz integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CUSTOM_URL,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_SCHOOL,
    CONF_TOTP_SECRET,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCHOOL,
    DOMAIN,
)
from .schools import CUSTOM

_LOGGER = logging.getLogger(__name__)


def base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def structural_hash(data: dict[str, Any] | None) -> str:
    """Return a stable hash of the set of subjects and exams."""
    if not data or "subjects" not in data:
        return ""
    keys = []
    for subject in data["subjects"]:
        raw = subject.get("subject", "")
        keys.append(raw)
        for exam in subject.get("exams", []):
            keys.append(f"{raw}|{exam.get('date', '')}|{exam.get('name', '')}")
    return "|".join(sorted(keys))


class SchulnetzCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches marks/tests from the Schulnetz node server."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = int(entry.data[CONF_PORT])
        self.email = entry.data[CONF_EMAIL]
        self.password = entry.data[CONF_PASSWORD]
        self.totp_secret = entry.data[CONF_TOTP_SECRET]
        self.school = entry.data.get(CONF_SCHOOL, DEFAULT_SCHOOL)
        self.custom_url = entry.data.get(CONF_CUSTOM_URL)
        self.session = async_get_clientsession(hass)

        options = entry.options
        interval_minutes = options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        try:
            interval_minutes = int(interval_minutes)
        except (TypeError, ValueError):
            interval_minutes = DEFAULT_SCAN_INTERVAL_MINUTES

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )

    def _url(self, path: str) -> str:
        return f"{base_url(self.host, self.port)}{path}"

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self.session.post(
                self._url("/api/scrape"), timeout=180
            ) as resp:
                status = resp.status
                try:
                    data = await resp.json()
                except Exception:
                    data = {}
        except Exception as err:
            raise UpdateFailed(f"Cannot reach Schulnetz server: {err}") from err

        if status == 400 and not data.get("subjects"):
            raise ConfigEntryAuthFailed(
                "No credentials configured on the Schulnetz server"
            )

        if "subjects" not in data:
            raise UpdateFailed(f"Unexpected response from Schulnetz server: {status}")

        if status == 429:
            _LOGGER.info("Scrape throttled; serving cached state")
        elif status == 502:
            _LOGGER.warning("Scrape failed; serving stale state: %s", data.get("error"))
        elif status != 200:
            raise UpdateFailed(f"Schulnetz server returned status {status}")

        return data

    async def async_push_credentials(self) -> None:
        """Push credentials to the node server (used during setup)."""
        payload: dict[str, Any] = {
            CONF_EMAIL: self.email,
            CONF_PASSWORD: self.password,
            CONF_TOTP_SECRET: self.totp_secret,
        }
        if self.school == CUSTOM:
            payload[CONF_CUSTOM_URL] = self.custom_url
        else:
            payload[CONF_SCHOOL] = self.school

        async with self.session.post(
            self._url("/api/config"),
            json=payload,
            timeout=30,
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Failed to push credentials: {resp.status}")
