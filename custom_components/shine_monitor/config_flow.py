"""Config flow for Shine Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_COMPANY_KEY,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_TOKEN,
    CONF_SECRET,
    CONF_UPDATE_INTERVAL,
    CONF_CURRENCY,
    CONF_ENABLE_DEVICES,
    DEFAULT_CURRENCY,
    DEFAULT_ENABLE_DEVICES,
    CURRENCY_OPTIONS,
)
from .coordinator import ShineMonitorAPIClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_COMPANY_KEY): str,
    }
)


class ShineMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shine Monitor."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self.plants: list[dict[str, Any]] = []
        self.auth_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                client = ShineMonitorAPIClient(
                    session=session,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    company_key=user_input[CONF_COMPANY_KEY],
                )

                # Authenticate and get token
                await client.authenticate()

                # Fetch plants
                plants = await client.get_plants()

                if not plants:
                    errors["base"] = "no_plants"
                else:
                    self.auth_info = {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_COMPANY_KEY: user_input[CONF_COMPANY_KEY],
                        CONF_TOKEN: client.token,
                        CONF_SECRET: client.secret,
                    }
                    self.plants = plants
                    return await self.async_step_plant()

            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error during authentication: %s", err)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle plant selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_plant = next(
                (
                    plant
                    for plant in self.plants
                    if str(plant["pid"]) == user_input["plant"]
                ),
                None,
            )

            if selected_plant:
                # Check if this plant is already configured
                await self.async_set_unique_id(str(selected_plant["pid"]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Shine Monitor - {selected_plant['name']}",
                    data={
                        **self.auth_info,
                        CONF_PLANT_ID: str(selected_plant["pid"]),
                        CONF_PLANT_NAME: selected_plant["name"],
                    },
                )

        plant_options = {str(plant["pid"]): plant["name"] for plant in self.plants}

        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema(
                {vol.Required("plant"): vol.In(plant_options)}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ShineMonitorOptionsFlowHandler()


class ShineMonitorOptionsFlowHandler(OptionsFlow):
    """Handle Shine Monitor options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_interval = self.config_entry.options.get(CONF_UPDATE_INTERVAL, 5)
        current_currency = self.config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        current_enable_devices = self.config_entry.options.get(
            CONF_ENABLE_DEVICES, DEFAULT_ENABLE_DEVICES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Optional(
                        CONF_CURRENCY,
                        default=current_currency,
                    ): vol.In(CURRENCY_OPTIONS),
                    vol.Optional(
                        CONF_ENABLE_DEVICES,
                        default=current_enable_devices,
                    ): bool,
                }
            ),
            description_placeholders={
                "update_interval_description": "Update interval in minutes (1-60)",
                "currency_description": "Currency symbol for profit display",
                "enable_devices_description": "Enable per-device sensors (inverters, dataloggers)",
            },
        )

