"""Tuya Monitor for Home Assistant

A simple integration to monitor property values from Tuya devices using the Tuya Cloud API.
"""
import logging
from datetime import timedelta
import json
import time
import hashlib
import hmac
import base64
import uuid

import aiohttp
import async_timeout

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
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRATION,
)

from .token_manager import refresh_tuya_token, get_new_token, generate_sign, generate_nonce

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tuya Monitor from a config entry."""
    # Store a reference to the entry to access options later
    hass.data.setdefault(DOMAIN, {})
    
    # Get Tuya API credentials from config entry
    config = dict(entry.data)
    
    # Create a dictionary to store coordinators for each device
    coordinators = {}
    
    # Setup coordinators for each configured device
    devices = entry.options.get(CONF_DEVICES, {})
    if not devices:
        _LOGGER.warning("No Tuya devices configured")
    
    for device_id, device_config in devices.items():
        _LOGGER.info(f"Setting up coordinator for device: {device_id}")
        
        # Ensure properties is a list
        properties = device_config.get(CONF_PROPERTIES, [])
        if isinstance(properties, str):
            properties = [p.strip() for p in properties.split(",")]
            
        _LOGGER.info(f"Device properties: {properties}")
        
        coordinator = TuyaDeviceCoordinator(
            hass,
            config,
            device_id,
            properties,
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

def get_device_sign(client_id, access_token, secret, t):
    """Generate Tuya API signature for device requests."""
    message = client_id + access_token + t
    sign = hmac.new(
        secret.encode('utf-8'),
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
                # Check if token needs refresh
                current_time = int(time.time())
                token_expiration = self.config.get(CONF_TOKEN_EXPIRATION, 0)
                
                # If token expires in the next 5 minutes, refresh it
                if current_time + 300 > token_expiration:
                    _LOGGER.info("Access token expiring soon, refreshing...")
                    session = async_get_clientsession(self.hass)
                    
                    # Try to refresh using refresh token first
                    new_token_info = None
                    if CONF_REFRESH_TOKEN in self.config:
                        new_token_info = await refresh_tuya_token(
                            session,
                            self.config[CONF_CLIENT_ID],
                            self.config[CONF_CLIENT_SECRET],
                            self.config[CONF_REFRESH_TOKEN],
                            self.config[CONF_REGION]
                        )
                    
                    # If refresh failed or no refresh token, get a new token
                    if not new_token_info:
                        new_token_info = await get_new_token(
                            session,
                            self.config[CONF_CLIENT_ID],
                            self.config[CONF_CLIENT_SECRET],
                            self.config[CONF_REGION]
                        )
                    
                    if new_token_info:
                        # Update config with new token
                        self.config[CONF_ACCESS_TOKEN] = new_token_info["access_token"]
                        self.config[CONF_REFRESH_TOKEN] = new_token_info["refresh_token"]
                        self.config[CONF_TOKEN_EXPIRATION] = new_token_info["expiration_time"]
                        
                        # Update config entry too
                        entry = None
                        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
                            if config_entry.data.get(CONF_CLIENT_ID) == self.config[CONF_CLIENT_ID]:
                                entry = config_entry
                                break
                        
                        if entry:
                            self.hass.config_entries.async_update_entry(
                                entry,
                                data={
                                    **entry.data,
                                    CONF_ACCESS_TOKEN: new_token_info["access_token"],
                                    CONF_REFRESH_TOKEN: new_token_info["refresh_token"],
                                    CONF_TOKEN_EXPIRATION: new_token_info["expiration_time"]
                                }
                            )
                    else:
                        _LOGGER.error("Failed to refresh access token")
                
                # Construct the Tuya API endpoint for device properties
                region_map = {
                    "us": "https://openapi.tuyaus.com",
                    "eu": "https://openapi.tuyaeu.com",
                    "cn": "https://openapi.tuyacn.com",
                    "in": "https://openapi.tuyain.com"
                }
                base_url = region_map.get(self.config.get(CONF_REGION, "us"), 
                                          "https://openapi.tuyaus.com")
                
                # Prepare timestamp, client info and access token
                timestamp = str(int(time.time() * 1000))
                client_id = self.config[CONF_CLIENT_ID]
                client_secret = self.config[CONF_CLIENT_SECRET]
                access_token = self.config[CONF_ACCESS_TOKEN]
                
                # Generate signature for device access
                signature = get_device_sign(
                    client_id,
                    access_token,
                    client_secret,
                    timestamp
                )
                
                # Construct the URL for fetching device properties
                url = f"{base_url}/v1.0/devices/{self.device_id}/status"
                
                # Prepare headers for authentication
                headers = {
                    "client_id": client_id,
                    "access_token": access_token,
                    "t": timestamp,
                    "sign": signature,
                    "sign_method": "HMAC-SHA256",
                    "Content-Type": "application/json"
                }
                
                _LOGGER.debug(f"Fetching data from URL: {url}")
                _LOGGER.debug(f"Headers: {headers}")
                
                # Use the session from Home Assistant
                session = async_get_clientsession(self.hass)
                
                # Make the API request
                async with session.get(url, headers=headers) as response:
                    response_text = await response.text()
                    _LOGGER.debug(f"API Response: {response_text}")
                    
                    if response.status != 200:
                        _LOGGER.error(f"API Error Response: {response_text}")
                        raise UpdateFailed(f"API returned status code {response.status}")
                    
                    # Parse the response
                    try:
                        data = await response.json()
                    except Exception as e:
                        _LOGGER.error(f"Failed to parse JSON response: {e}")
                        _LOGGER.error(f"Response text: {response_text}")
                        raise UpdateFailed(f"Failed to parse API response: {e}")
                    
                    _LOGGER.debug(f"Full API Response: {data}")
                    
                    # Check success status
                    if not data.get("success", False):
                        error_msg = data.get("msg", "Unknown error")
                        _LOGGER.error(f"API error: {error_msg}")
                        raise UpdateFailed(f"API request was not successful: {error_msg}")
                    
                    # Process the response data according to the Tuya API structure
                    result = data.get("result", [])
                    if not result:
                        _LOGGER.warning("No device status data returned from API")
                        return {"properties": []}
                    
                    # Format the device properties in a standard way
                    properties = []
                    
                    # Filter properties if needed
                    filter_properties = len(self.properties) > 0
                    
                    for status_item in result:
                        code = status_item.get("code")
                        value = status_item.get("value")
                        
                        if not filter_properties or code in self.properties:
                            properties.append({
                                "code": code,
                                "value": value
                            })
                    
                    _LOGGER.debug(f"Filtered Properties: {properties}")
                    return {"properties": properties}
        
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Tuya API connection error: {err}", exc_info=True)
            raise UpdateFailed(f"Error communicating with Tuya API: {err}") from err
        except Exception as err:
            _LOGGER.error(f"Unexpected error fetching Tuya device data: {err}", exc_info=True)
            raise UpdateFailed(f"Unexpected error: {err}")
