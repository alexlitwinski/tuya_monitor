"""Config flow for Tuya Monitor integration."""
import logging
import voluptuous as vol
import aiohttp
import time
import hashlib
import hmac
import base64
import uuid  # Adicionando importação do uuid
import async_timeout  # Adicionando importação do async_timeout

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
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRATION,
)

TUYA_REGION_ENDPOINTS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com"
}

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


def generate_nonce():
    """Generate a random nonce string."""
    return str(uuid.uuid4())


async def get_new_token(session, client_id, client_secret, region="us"):
    """Get a new token from Tuya API."""
    try:
        region_map = {
            "us": "https://openapi.tuyaus.com",
            "eu": "https://openapi.tuyaeu.com",
            "cn": "https://openapi.tuyacn.com",
            "in": "https://openapi.tuyain.com"
        }
        base_url = region_map.get(region, TUYA_REGION_ENDPOINTS["us"])
        token_url = f"{base_url}/v1.0/token?grant_type=1"
        
        # Generate timestamp and signature
        timestamp = str(int(time.time() * 1000))
        nonce = generate_nonce()
        
        # Create string to sign and sign it
        string_to_sign = client_id + timestamp + nonce
        signature = hmac.new(
            client_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        sign_hex = base64.b64encode(signature).decode('utf-8')
        
        # Prepare headers and body
        headers = {
            "client_id": client_id,
            "sign": sign_hex,
            "t": timestamp,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }
        
        _LOGGER.debug(f"Attempting to get new token with URL: {token_url}")
        _LOGGER.debug(f"Headers: {headers}")
        
        async with async_timeout.timeout(10):
            async with session.get(token_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(f"Get token failed with status {response.status}: {error_text}")
                    return None
                    
                data = await response.json()
                _LOGGER.debug(f"Token response: {data}")
                
                if not data.get("success", False):
                    error_msg = data.get("msg", "Unknown error")
                    _LOGGER.error(f"Get token failed: {error_msg}")
                    return None
                
                result = data.get("result", {})
                if not result:
                    _LOGGER.error("Empty result from get token")
                    return None
                
                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token")
                expire_time = result.get("expire_time")
                
                _LOGGER.info(f"Successfully obtained new token. Token expires in {expire_time} seconds")
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expire_time": expire_time,
                    "expiration_time": int(time.time()) + int(expire_time)
                }
    
    except Exception as e:
        _LOGGER.error(f"Error getting new Tuya token: {e}")
        return None

class TuyaMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Monitor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Create a simple session for this request only
                async with aiohttp.ClientSession() as session:
                    # Get a fresh token using provided credentials
                    new_token_info = await get_new_token(
                        session, 
                        user_input[CONF_CLIENT_ID],
                        user_input[CONF_CLIENT_SECRET],
                        user_input[CONF_REGION]
                    )
                
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
