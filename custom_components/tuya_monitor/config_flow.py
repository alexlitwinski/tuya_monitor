"""Config flow for Tuya Monitor integration."""
import logging
import voluptuous as vol
import aiohttp
import time
import hashlib
import hmac
import base64

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_NAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_REGION,
    CONF_ACCESS_TOKEN,
)

from .const import (
    DOMAIN,
    CONF_USER_ID,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_PROPERTIES,
    CONF_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

def generate_sign(client_secret, token, t, method='HMAC-SHA256'):
    """Generate Tuya API signature using the exact method from the working example."""
    message = f"{token}{t}"
    sign = hmac.new(
        client_secret.encode('utf-8'), 
        message.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest().upper()
    return sign

class TuyaMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Monitor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate Tuya credentials
                await self._validate_tuya_credentials(
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    user_input[CONF_REGION]
                )

                # Get a fresh token using provided credentials
                session = aiohttp.ClientSession()
                new_token_info = await get_new_token(
                    session, 
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    user_input[CONF_REGION]
                )
                await session.close()
                
                # Only proceed if we successfully got a token
                if not new_token_info:
                    errors["base"] = "token_failed"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({
                            vol.Required(CONF_NAME, default="Tuya Monitor"): str,
                            vol.Required(CONF_CLIENT_ID): str,
                            vol.Required(CONF_CLIENT_SECRET): str,
                            vol.Required(CONF_REGION, default="us"): vol.In(["us", "eu", "cn", "in"]),
                            vol.Optional(CONF_USER_ID): str,
                        }),
                        errors=errors,
                    )
                
                # Create the config entry with the fresh token
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Tuya Monitor"),
                    data={
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                        CONF_REGION: user_input[CONF_REGION],
                        CONF_ACCESS_TOKEN: new_token_info["access_token"],
                        CONF_REFRESH_TOKEN: new_token_info["refresh_token"],
                        CONF_TOKEN_EXPIRATION: new_token_info["expiration_time"],
                        CONF_USER_ID: user_input.get(CONF_USER_ID, ""),
                    },
                    options={CONF_DEVICES: {}},
                )
            except Exception as err:
                _LOGGER.error(f"Error validating Tuya credentials: {err}")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="Tuya Monitor"): str,
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
                vol.Required(CONF_REGION, default="us"): vol.In(["us", "eu", "cn", "in"]),
                vol.Optional(CONF_USER_ID): str,
            }),
            errors=errors,
        )

    async def _validate_tuya_credentials(self, client_id, client_secret, region):
        """Validate Tuya API credentials by attempting to get a token."""
        
        # Validate by attempting to get a token
        try:
            async with aiohttp.ClientSession() as session:
                # Get a new token to validate credentials
                token_result = await get_new_token(
                    session, 
                    client_id, 
                    client_secret, 
                    region
                )
                
                if not token_result or not token_result.get("access_token"):
                    _LOGGER.error("Failed to obtain token with provided credentials")
                    raise Exception("Invalid credentials - could not obtain access token")
                
                _LOGGER.info("Successfully validated Tuya credentials")
                return
                
        except Exception as err:
            _LOGGER.error(f"Error validating credentials: {err}")
            raise
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(validation_url, headers=headers) as response:
                    if response.status != 200:
                        data = await response.json()
                        error_msg = data.get("msg", f"API returned status code {response.status}")
                        _LOGGER.error(f"Tuya API validation error: {error_msg}")
                        raise Exception(error_msg)
                    
                    data = await response.json()
                    if not data.get("success", False):
                        error_msg = data.get("msg", "Unknown validation error")
                        _LOGGER.error(f"Tuya API validation error: {error_msg}")
                        raise Exception(error_msg)
                    
            except Exception as err:
                _LOGGER.error(f"Tuya API validation error: {err}")
                raise

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TuyaMonitorOptionsFlowHandler(config_entry)


class TuyaMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Tuya Monitor options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.current_device_id = None
        self.options = dict(config_entry.options)
        self.devices = self.options.get(CONF_DEVICES, {})

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        """Show the menu for options flow."""
        if user_input is not None:
            if user_input["menu_option"] == "add_device":
                return await self.async_step_add_device()
            if user_input["menu_option"] == "remove_device":
                return await self.async_step_remove_device()

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema({
                vol.Required("menu_option", default="add_device"): vol.In({
                    "add_device": "Add Device",
                    "remove_device": "Remove Device",
                }),
            }),
        )

    async def async_step_add_device(self, user_input=None):
        """Handle adding a device."""
        errors = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            
            # Process properties as a list
            if isinstance(user_input[CONF_PROPERTIES], str):
                properties = [p.strip() for p in user_input[CONF_PROPERTIES].split(",") if p.strip()]
            else:
                properties = user_input[CONF_PROPERTIES]
            
            # Create or update device configuration
            if CONF_DEVICES not in self.options:
                self.options[CONF_DEVICES] = {}
                
            self.options[CONF_DEVICES][device_id] = {
                CONF_PROPERTIES: properties,
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            }
            
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_PROPERTIES, description="Comma-separated list of properties (leave empty to fetch all)"): str,
                vol.Required(CONF_SCAN_INTERVAL, default=60): int,
            }),
            errors=errors,
        )

    async def async_step_remove_device(self, user_input=None):
        """Handle removing a device."""
        errors = {}

        if not self.devices:
            return await self.async_step_menu()

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            if device_id in self.options[CONF_DEVICES]:
                del self.options[CONF_DEVICES][device_id]
            
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(list(self.devices.keys()) or ["NO_DEVICES"]),
            }),
            errors=errors,
        )
