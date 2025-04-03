"""Sensor platform for Tuya Monitor integration."""
import logging
from typing import Optional, Dict, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DEVICES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up Tuya Monitor sensors based on config entry."""
    _LOGGER.info("Setting up Tuya Monitor sensors")
    
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        coordinators = entry_data["coordinators"]
        
        _LOGGER.info(f"Found {len(coordinators)} coordinators")
        
        sensors = []
        for device_id, coordinator in coordinators.items():
            _LOGGER.info(f"Processing device: {device_id}")
            
            # Get the device data and properties from the entry options
            device_data = entry.options[CONF_DEVICES][device_id]
            
            # Handle properties that might be a string or list
            properties = device_data.get("properties", [])
            if isinstance(properties, str):
                properties = [p.strip() for p in properties.split(",") if p.strip()]
            
            _LOGGER.info(f"Device properties: {properties}")
            
            # If empty properties list, create sensors for all properties found in the data
            if not properties and coordinator.data and "properties" in coordinator.data:
                for prop in coordinator.data["properties"]:
                    if "code" in prop:
                        properties.append(prop["code"])
                _LOGGER.info(f"Auto-detected properties: {properties}")
            
            # Create a sensor for each property
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
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{property_code}"
        
        _LOGGER.debug(f"Initializing sensor: {self._attr_name}")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data:
                _LOGGER.warning(f"No data available for {self._attr_name}")
                return None
                
            if "properties" not in self.coordinator.data:
                _LOGGER.warning(f"No properties in coordinator data for {self._attr_name}")
                return None
                
            for prop in self.coordinator.data["properties"]:
                if prop.get("code") == self.property_code:
                    value = prop.get("value")
                    _LOGGER.debug(f"Found value for {self.property_code}: {value}")
                    return value
            
            _LOGGER.debug(f"Property {self.property_code} not found in data")
            return None
        except Exception as err:
            _LOGGER.error(f"Error getting native value for {self._attr_name}: {err}", exc_info=True)
            return None

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": f"Tuya Device {self.device_id}",
            "manufacturer": "Tuya",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # First check if the coordinator is available
        if not self.coordinator.last_update_success:
            return False
            
        # Then check if we have data for this specific property
        if not self.coordinator.data or "properties" not in self.coordinator.data:
            return False
            
        # Check if this property exists in the data
        return any(prop.get("code") == self.property_code for prop in self.coordinator.data["properties"])
