"""Config flow for the Schulnetz integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CUSTOM_URL,
    CONF_DEVICE_NAME_TEMPLATE,
    CONF_EXAM_NAME_TEMPLATE,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_SCHOOL,
    CONF_SUBJECT_ALIASES,
    CONF_TOTP_SECRET,
    DEFAULT_DEVICE_NAME_TEMPLATE,
    DEFAULT_EXAM_NAME_TEMPLATE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCHOOL,
    DOMAIN,
)
from .schools import CUSTOM, SCHOOLS

_LOGGER = logging.getLogger(__name__)


def _school_step_schema() -> vol.Schema:
    options = [
        {"value": code, "label": f"{name} ({code})"} for code, name in SCHOOLS
    ]
    options.append({"value": CUSTOM, "label": "Custom…"})
    return vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_SCHOOL, default=DEFAULT_SCHOOL): selector(
                {"select": {"options": options, "mode": "dropdown"}}
            ),
        }
    )


STEP_CUSTOM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CUSTOM_URL): str,
    }
)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_TOTP_SECRET): str,
    }
)


async def _test_connection(
    hass: HomeAssistant,
    host: str,
    port: int,
    email: str,
    password: str,
    totp_secret: str,
    school: str,
    custom_url: str | None,
) -> None:
    """Push credentials to the node server and verify it is reachable."""
    base = f"http://{host}:{port}"
    session = async_get_clientsession(hass)
    payload: dict[str, Any] = {
        CONF_EMAIL: email,
        CONF_PASSWORD: password,
        CONF_TOTP_SECRET: totp_secret,
    }
    if school == CUSTOM:
        payload[CONF_CUSTOM_URL] = custom_url
    else:
        payload[CONF_SCHOOL] = school

    async with session.post(
        f"{base}/api/config",
        json=payload,
        timeout=30,
    ) as resp:
        resp.raise_for_status()


class SchulnetzConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schulnetz."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = int(user_input[CONF_PORT])
            self._school = user_input[CONF_SCHOOL]
            self._custom_url = None
            if self._school == CUSTOM:
                return await self.async_step_custom_url()
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user", data_schema=_school_step_schema(), errors=errors
        )

    async def async_step_custom_url(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            custom_url = (user_input.get(CONF_CUSTOM_URL) or "").strip()
            if not custom_url:
                errors[CONF_CUSTOM_URL] = "invalid_url"
            else:
                self._custom_url = custom_url
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="custom_url",
            data_schema=STEP_CUSTOM_URL_SCHEMA,
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            totp_secret = user_input[CONF_TOTP_SECRET]

            try:
                await _test_connection(
                    self.hass,
                    self._host,
                    self._port,
                    email,
                    password,
                    totp_secret,
                    self._school,
                    self._custom_url,
                )
            except Exception:
                _LOGGER.exception("Failed to connect to Schulnetz server")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{self._host}:{self._port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Schulnetz ({self._host})",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_SCHOOL: self._school,
                        CONF_CUSTOM_URL: self._custom_url,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_TOTP_SECRET: totp_secret,
                    },
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        return SchulnetzOptionsFlow(config_entry)


class SchulnetzOptionsFlow(OptionsFlow):
    """Handle options for Schulnetz."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._entry.options
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=options.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
                vol.Optional(
                    CONF_DEVICE_NAME_TEMPLATE,
                    default=options.get(
                        CONF_DEVICE_NAME_TEMPLATE, DEFAULT_DEVICE_NAME_TEMPLATE
                    ),
                ): str,
                vol.Optional(
                    CONF_EXAM_NAME_TEMPLATE,
                    default=options.get(
                        CONF_EXAM_NAME_TEMPLATE, DEFAULT_EXAM_NAME_TEMPLATE
                    ),
                ): str,
                vol.Optional(
                    CONF_SUBJECT_ALIASES,
                    default=options.get(CONF_SUBJECT_ALIASES, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)
