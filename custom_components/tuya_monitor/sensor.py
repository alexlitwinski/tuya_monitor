"""Sensor platform for Tuya Monitor integration."""
import logging
from typing import Optional, Dict, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN, CONF_DEVICES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Tuya Monitor sensors based on config entry."""
    _LOGGER.info("Setting up Tuya Monitor sensors")
    
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        coordinators = entry_data["coordinators"]
        
        _LOGGER.info(f"Found {len(coordinators)} coordinators")
        
        sensors = []
        for device_id, coordinator in coordinators.items():
            _LOGGER.info(f"Processing device: {device_id}")
            
            device_data = entry.options[CONF_DEVICES][device_id]
            properties = device_data.get("properties", [])
            
            _LOGGER.info(f"Device properties: {properties}")
            
            for property_code in properties:
                sensor = TuyaPropertySensor(
                    coordinator,
                    device_id,
                    property_code,
                )
                sensors.append(sensor)
                _LOGGER.info(f"Created sensor for {device_id} - {property_code}")
        
        async_add_entities(sensors)
        _LOGGER.info(f"Added {len(sensors)} Tuya Monitor sensors")
    
    except Exception as err:
        _LOGGER.error(f"Error setting up Tuya Monitor sensors: {err}", exc_info=True)

class TuyaPropertySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tuya device property sensor."""

    def __init__(self, coordinator, device_id, property_code):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.property_code = property_code
        self._attr_name = f"Tuya {device_id} {property_code}"
        self._attr_unique_id = f"{device_id}_{property_code}"
        
        _LOGGER.info(f"Initializing sensor: {self._attr_name}")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        _LOGGER.info(f"Fetching value for {self._attr_name}")
        _LOGGER.info(f"Coordinator data: {self.coordinator.data}")
        
        try:
            if self.coordinator.data and "properties" in self.coordinator.data:
                for prop in self.coordinator.data["properties"]:
                    _LOGGER.info(f"Checking property: {prop}")
                    if prop.get("code") == self.property_code:
                        value = prop.get("value")
                        _LOGGER.info(f"Found value for {self.property_code}: {value}")
                        return value
            
            _LOGGER.warning(f"No value found for {self.property_code}")
            return None
        except Exception as err:
            _LOGGER.error(f"Error getting native value: {err}", exc_info=True)
            return None

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": f"Tuya Device {self.device_id}",
            "manufacturer": "Tuya",
        }
