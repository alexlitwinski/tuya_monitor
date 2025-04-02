"""Tuya Monitor for Home Assistant

A simple integration to monitor property values from Tuya devices using the Tuya Cloud API.
"""
import logging
from datetime import timedelta

import aiohttp
import async_timeout
import hashlib
import hmac
import time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_REGION,
    CONF_ACCESS_TOKEN,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator, 
    UpdateFailed
)
from homeassistant.const import Platform

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_PROPERTIES,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tuya Monitor from a config entry."""
    # Store a reference to the entry to access options later
    hass.data.setdefault(DOMAIN, {})
    
    # Get Tuya API credentials from config entry
    config = entry.data
    
    # Create a dictionary to store coordinators for each device
    coordinators = {}
    
    # Setup coordinators for each configured device
    devices = entry.options.get(CONF_DEVICES, {})
    if not devices:
        _LOGGER.warning("No Tuya devices configured")
    
    for device_id, device_config in devices.items():
        _LOGGER.info(f"Setting up coordinator for device: {device_id}")
        _LOGGER.info(f"Device properties: {device_config.get(CONF_PROPERTIES, [])}")
        coordinator = TuyaDeviceCoordinator(
            hass,
            config,
            device_id,
            device_config.get(CONF_PROPERTIES, []),
            device_config.get(CONF_SCAN_INTERVAL, 60)
        )
        try:
            await coordinator.async_config_entry_first_refresh()
            coordinators[device_id] = coordinator
            _LOGGER.info(f"Coordinator setup successful for device: {device_id}")
        except Exception as err:
            _LOGGER.error(f"Failed to setup coordinator for device {device_id}: {err}", exc_info=True)
    
    # Store coordinators in hass.data for use in sensor platform
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinators": coordinators
    }

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

def generate_sign(client_secret, token, t, method='HMAC-SHA256'):
    """Generate Tuya API signature."""
    message = f"{token}{t}"
    sign = hmac.new(
        client_secret.encode('utf-8'), 
        message.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest().upper()
    return sign

class TuyaDeviceCoordinator(DataUpdateCoordinator):
    """Coordinator for Tuya devices."""

    def __init__(
        self, 
        hass, 
        config,
        device_id, 
        properties, 
        scan_interval
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Tuya Device {device_id}",
            update_interval=timedelta(seconds=scan_interval)
        )
        self.hass = hass
        self.config = config
        self.device_id = device_id
        self.properties = properties

    async def _async_update_data(self):
        """Fetch data from Tuya API."""
        try:
            async with async_timeout.timeout(10):
                # Construct the Tuya API endpoint for device properties
                region_map = {
                    "us": "https://openapi.tuyaus.com",
                    "eu": "https://openapi.tuyaeu.com",
                    "cn": "https://openapi.tuyacn.com",
                    "in": "https://openapi.tuyain.com"
                }
                base_url = region_map.get(self.config.get(CONF_REGION, "us"), 
                                          "https://openapi.tuyaus.com")
                
                # Prepare timestamp and signature
                t = str(int(time.time() * 1000))
                client_id = self.config[CONF_CLIENT_ID]
                client_secret = self.config[CONF_CLIENT_SECRET]
                access_token = self.config[CONF_ACCESS_TOKEN]
                
                # Construct the URL for fetching device properties
                url = f"{base_url}/v2.0/cloud/thing/{self.device_id}/shadow/properties"
                
                # Prepare query parameters (property codes)
                params = {
                    "codes": ",".join(self.properties)
                }
                
                # Prepare headers for authentication
                sign = generate_sign(client_secret, access_token, t)
                headers = {
                    "client_id": client_id,
                    "t": t,
                    "sign_method": "HMAC-SHA256",
                    "sign": sign,
                    "access_token": access_token,
                    "Content-Type": "application/json",
                    "mode": "cors"
                }
                
                _LOGGER.info(f"Fetching data from URL: {url}")
                _LOGGER.info(f"Requested properties: {self.properties}")
                _LOGGER.info(f"Headers: {headers}")
                _LOGGER.info(f"Params: {params}")
                
                # Use the session from Home Assistant
                session = async_get_clientsession(self.hass)
                
                # Make the API request
                async with session.get(url, headers=headers, params=params) as response:
                    _LOGGER.info(f"API Response Status: {response.status}")
                    
                    if response.status != 200:
                        response_text = await response.text()
                        _LOGGER.error(f"API Error Response: {response_text}")
                        raise UpdateFailed(f"API returned status code {response.status}")
                    
                    # Parse the response
                    data = await response.json()
                    _LOGGER.info(f"Full API Response: {data}")
                    
                    # Process the new response structure
                    if not data.get("success", False):
                        raise UpdateFailed("API request was not successful")
                    
                    # Extract and process properties
                    raw_properties = data.get("result", {}).get("properties", [])
                    properties = []
                    for prop in raw_properties:
                        if prop.get("code") in self.properties:
                            properties.append({
                                "code": prop.get("code"),
                                "value": prop.get("value")
                            })
                    
                    _LOGGER.info(f"Filtered Properties: {properties}")
                    return {"properties": properties}
        
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Tuya API connection error: {err}", exc_info=True)
            raise UpdateFailed(f"Error communicating with Tuya API: {err}") from err
        except Exception as err:
            _LOGGER.error(f"Unexpected error fetching Tuya device data: {err}", exc_info=True)
            raise UpdateFailed(f"Unexpected error: {err}")
