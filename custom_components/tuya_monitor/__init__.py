"""Tuya Monitor for Home Assistant

A simple integration to monitor property values from Tuya devices using the Tuya Cloud API.
"""
import logging
from datetime import timedelta

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
    for device_id, device_config in entry.options.get(CONF_DEVICES, {}).items():
        coordinator = TuyaDeviceCoordinator(
            hass,
            config,
            device_id,
            device_config.get(CONF_PROPERTIES, []),
            device_config.get(CONF_SCAN_INTERVAL, 60)
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[device_id] = coordinator
    
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
                # Note: This is a placeholder and needs to be replaced with actual Tuya API endpoint
                region_map = {
                    "us": "https://openapi.tuyaus.com",
                    "eu": "https://openapi.tuyaeu.com",
                    "cn": "https://openapi.tuyacn.com",
                    "in": "https://openapi.tuyain.com"
                }
                base_url = region_map.get(self.config.get(CONF_REGION, "us"), 
                                          "https://openapi.tuyaus.com")
                
                # Construct the URL for fetching device properties
                url = f"{base_url}/v1.0/devices/{self.device_id}/properties"
                
                # Prepare headers for authentication
                headers = {
                    "Authorization": f"Bearer {self.config[CONF_ACCESS_TOKEN]}",
                    "Content-Type": "application/json"
                }
                
                # Use the session from Home Assistant
                session = async_get_clientsession(self.hass)
                
                # Make the API request
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"API returned status code {response.status}")
                    
                    # Parse the response
                    data = await response.json()
                    
                    # Filter and process only the requested properties
                    properties = []
                    for prop in data.get("result", []):
                        if prop.get("code") in self.properties:
                            properties.append({
                                "code": prop.get("code"),
                                "value": prop.get("value")
                            })
                    
                    return {"properties": properties}
        
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Tuya API connection error: {err}")
            raise UpdateFailed(f"Error communicating with Tuya API: {err}") from err
        except Exception as err:
            _LOGGER.error(f"Unexpected error fetching Tuya device data: {err}")
            raise UpdateFailed(f"Unexpected error: {err}") from err"""Tuya Monitor for Home Assistant

A simple integration to monitor property values from Tuya devices using the Tuya Cloud API.
"""
import logging
from datetime import timedelta

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
    for device_id, device_config in entry.options.get(CONF_DEVICES, {}).items():
        coordinator = TuyaDeviceCoordinator(
            hass,
            config,
            device_id,
            device_config.get(CONF_PROPERTIES, []),
            device_config.get(CONF_SCAN_INTERVAL, 60)
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[device_id] = coordinator
    
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
                # Note: This is a placeholder and needs to be replaced with actual Tuya API endpoint
                region_map = {
                    "us": "https://openapi.tuyaus.com",
                    "eu": "https://openapi.tuyaeu.com",
                    "cn": "https://openapi.tuyacn.com",
                    "in": "https://openapi.tuyain.com"
                }
                base_url = region_map.get(self.config.get(CONF_REGION, "us"), 
                                          "https://openapi.tuyaus.com")
                
                # Construct the URL for fetching device properties
                url = f"{base_url}/v1.0/devices/{self.device_id}/properties"
                
                # Prepare headers for authentication
                headers = {
                    "Authorization": f"Bearer {self.config[CONF_ACCESS_TOKEN]}",
                    "Content-Type": "application/json"
                }
                
                # Use the session from Home Assistant
                session = async_get_clientsession(self.hass)
                
                # Make the API request
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"API returned status code {response.status}")
                    
                    # Parse the response
                    data = await response.json()
                    
                    # Filter and process only the requested properties
                    properties = []
                    for prop in data.get("result", []):
                        if prop.get("code") in self.properties:
                            properties.append({
                                "code": prop.get("code"),
                                "value": prop.get("value")
                            })
                    
                    return {"properties": properties}
        
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Tuya API connection error: {err}")
            raise UpdateFailed(f"Error communicating with Tuya API: {err}") from err
        except Exception as err:
            _LOGGER.error(f"Unexpected error fetching Tuya device data: {err}")
            raise UpdateFailed(f"Unexpected error: {err}") from err
