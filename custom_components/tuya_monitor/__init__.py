"""Tuya Monitor integration for Home Assistant."""
import logging
import time
import hashlib
import hmac
import asyncio
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_REGION,
    CONF_ACCESS_TOKEN,
)

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_USER_ID,
    CONF_DEVICES,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config):
    """Set up the Tuya Monitor component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tuya Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    client_id = entry.data.get(CONF_CLIENT_ID)
    client_secret = entry.data.get(CONF_CLIENT_SECRET)
    region = entry.data.get(CONF_REGION)
    access_token = entry.data.get(CONF_ACCESS_TOKEN)
    
    api = TuyaAPI(
        hass, 
        client_id,
        client_secret,
        region,
        access_token,
    )
    
    # Store API instance
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": {},
    }
    
    # Set up coordinators for each device
    if CONF_DEVICES in entry.options:
        for device_id, device_config in entry.options[CONF_DEVICES].items():
            coordinator = DeviceDataUpdateCoordinator(
                hass,
                api,
                device_id,
                device_config,
            )
            await coordinator.async_config_entry_first_refresh()
            hass.data[DOMAIN][entry.entry_id]["coordinators"][device_id] = coordinator
    
    # Forward the setup to the sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    # Register update listener for changes to options
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

class TuyaAPI:
    """Class to interact with Tuya Cloud API."""
    
    def __init__(self, hass, client_id, client_secret, region, access_token):
        """Initialize the API."""
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.access_token = access_token
        self._session = async_get_clientsession(hass)
        self.base_url = f"https://openapi.tuya{region}.com"
    
    def _calculate_sign(self, method, path, params, body, timestamp):
        """Calculate the signature for API requests."""
        # Prepare the string to be signed
        str_to_sign = self.client_id + self.access_token + timestamp
        
        # Add HTTP method
        str_to_sign += method
        
        # Add Content-SHA256
        if body:
            content_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
        else:
            content_sha256 = hashlib.sha256(b"").hexdigest()
        
        str_to_sign += content_sha256
        
        # Add headers (none in this case)
        str_to_sign += ""
        
        # Add URL
        url_path = f"/{path}"
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url_path += f"?{query_string}"
        
        str_to_sign += url_path
        
        # Calculate HMAC-SHA256
        signature = hmac.new(
            self.client_secret.encode("utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()
        
        return signature
    
    async def get_device_properties(self, device_id, properties):
        """Get device properties."""
        timestamp = str(int(time.time() * 1000))
        method = "GET"
        path = f"v2.0/cloud/thing/{device_id}/shadow/properties"
        params = {"codes": ",".join(properties)}
        
        sign = self._calculate_sign(method, path, params, "", timestamp)
        
        headers = {
            "client_id": self.client_id,
            "sign_method": "HMAC-SHA256",
            "t": timestamp,
            "sign": sign,
            "access_token": self.access_token,
            "Content-Type": "application/json",
        }
        
        url = f"{self.base_url}/{path}"
        
        try:
            async with self._session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    _LOGGER.error(f"API request failed: {resp.status}")
                    return None
                
                data = await resp.json()
                if data.get("success", False):
                    return data.get("result", {})
                else:
                    _LOGGER.error(f"API returned error: {data.get('msg')}")
                    return None
        
        except Exception as e:
            _LOGGER.error(f"Error fetching device properties: {e}")
            return None

class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""
    
    def __init__(self, hass, api, device_id, device_config):
        """Initialize."""
        self.api = api
        self.device_id = device_id
        self.properties = device_config.get("properties", [])
        self.scan_interval = device_config.get("scan_interval", 60)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=self.scan_interval),
        )
    
    async def _async_update_data(self):
        """Update data via API."""
        try:
            data = await self.api.get_device_properties(self.device_id, self.properties)
            if data is None:
                raise UpdateFailed("Failed to fetch device data")
            return data
        except Exception as e:
            raise UpdateFailed(f"Error communicating with API: {e}")
