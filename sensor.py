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
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinators = entry_data["coordinators"]
    
    sensors = []
    for device_id, coordinator in coordinators.items():
        device_data = entry.options[CONF_DEVICES][device_id]
        properties = device_data.get("properties", [])
        
        for property_code in properties:
            sensors.append(
                TuyaPropertySensor(
                    coordinator,
                    device_id,
                    property_code,
                )
            )
    
    async_add_entities(sensors)

class TuyaPropertySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tuya device property sensor."""

    def __init__(self, coordinator, device_id, property_code):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.property_code = property_code
        self._attr_name = f"Tuya {device_id} {property_code}"
        self._attr_unique_id = f"{device_id}_{property_code}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "properties" in self.coordinator.data:
            for prop in self.coordinator.data["properties"]:
                if prop.get("code") == self.property_code:
                    return prop.get("value")
        return None

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": f"Tuya Device {self.device_id}",
            "manufacturer": "Tuya",
        }
