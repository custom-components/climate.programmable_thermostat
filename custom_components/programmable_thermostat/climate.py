"""Adds support for generic thermostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE, CURRENT_HVAC_COOL, CURRENT_HVAC_HEAT, CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF,HVAC_MODE_HEAT_COOL,
    PRESET_AWAY, SUPPORT_PRESET_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_NAME, EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES, PRECISION_TENTHS, PRECISION_WHOLE, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_ON, STATE_OFF, STATE_UNKNOWN)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

__version__ = '2.2.2'

DEPENDENCIES = ['switch', 'sensor']

DEFAULT_TOLERANCE = 0.5
DEFAULT_NAME = 'Programmable Thermostat'
DEFAULT_MAX_TEMP = 40
DEFAULT_MIN_TEMP = 5

CONF_HEATER = 'heater'
CONF_COOLER = 'cooler'
CONF_SENSOR = 'actual_temp_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET = 'target_temp_sensor'
CONF_TOLERANCE = 'tolerance'
CONF_INITIAL_HVAC_MODE = 'initial_hvac_mode'
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HEATER): cv.entity_id,
    vol.Optional(CONF_COOLER): cv.entity_id,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Required(CONF_TARGET): cv.entity_id,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
    vol.Optional(CONF_INITIAL_HVAC_MODE):
        vol.In([HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL]),
})

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    cooler_entity_id = config.get(CONF_COOLER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_entity_id = config.get(CONF_TARGET)
    tolerance = config.get(CONF_TOLERANCE)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    unit = hass.config.units.temperature_unit

    async_add_entities([ProgrammableThermostat(
        hass, name, heater_entity_id, cooler_entity_id, sensor_entity_id, min_temp,
        max_temp, target_entity_id, tolerance, initial_hvac_mode, unit)])


class ProgrammableThermostat(ClimateDevice, RestoreEntity):
    """ProgrammableThermostat."""

    def __init__(self, hass, name, heater_entity_id, cooler_entity_id,
                 sensor_entity_id, min_temp, max_temp, target_entity_id,
                 tolerance, initial_hvac_mode, unit):
        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.cooler_entity_id = cooler_entity_id
        self.sensor_entity_id = sensor_entity_id
        self._tolerance = tolerance
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._initial_hvac_mode = initial_hvac_mode
        self.target_entity_id = target_entity_id
        self._unit = unit

        self._target_temp = float(hass.states.get(target_entity_id).state)
        self._restore_temp = self._target_temp
        self._cur_temp = self._target_temp
        self._active = False
        self._temp_lock = asyncio.Lock()
        self._hvac_action = CURRENT_HVAC_OFF
        self._hvac_action_variable = "off"

        if self.heater_entity_id is not None and self.cooler_entity_id is not None:
            self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF]
        elif self.heater_entity_id is not None and self.cooler_entity_id is None:
            self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF]
        elif self.cooler_entity_id is not None and self.heater_entity_id is None:
            self._hvac_list = [HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF]
        else:
            self._hvac_list = [HVAC_MODE_OFF]
            _LOGGER.error("ERROR, you have to define at least one between heater and cooler")
        if initial_hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
        elif initial_hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
        elif initial_hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
        else:
            self._hvac_mode = HVAC_MODE_OFF
        self._support_flags = SUPPORT_FLAGS
        self._restore_target_temp_state = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self.sensor_entity_id, self._async_sensor_changed)
        if self._hvac_mode == HVAC_MODE_HEAT:
            async_track_state_change(
                self.hass, self.heater_entity_id, self._async_switch_changed)
        elif self._hvac_mode == HVAC_MODE_COOL:
            async_track_state_change(
                self.hass, self.cooler_entity_id, self._async_switch_changed)
        async_track_state_change(
            self.hass, self.target_entity_id, self._async_target_changed)

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state != STATE_UNKNOWN:
                self._async_update_temp(sensor_state)
            target_state = self.hass.states.get(self.target_entity_id)
            if target_state and target_state.state != STATE_UNKNOWN and self._hvac_mode != HVAC_MODE_HEAT_COOL:
                self._async_update_program_temp(target_state)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        _LOGGER.info("old state: %s", old_state)
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    if self.hass.states.get(target_entity_id).state is None:
                        self._target_temp = float(self.hass.states.get(target_entity_id).state)
                    else:
                        self._target_temp = float((self._min_temp + self._max_temp)/2)
                    _LOGGER.warning("Undefined target temperature,"
                                    "falling back to %s", self._target_temp)
                else:
                    self._target_temp = float(
                        old_state.attributes[ATTR_TEMPERATURE])
            if (self._initial_hvac_mode is None and
                    old_state.state is not None):
                self._hvac_mode = \
                    old_state.state
                self._enabled = self._hvac_mode != HVAC_MODE_OFF

        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                self._target_temp = float((self._min_temp + self._max_temp)/2)
            _LOGGER.warning("No previously saved temperature, setting to %s",
                            self._target_temp)

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    async def control_system_mode(self, mode=None):
        if mode == "off":
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_heater_turn_off()
                if opmod is HVAC_MODE_COOL:
                    await self._async_cooler_turn_off()
            self._hvac_action_variable = "off"
        elif mode == "heat":
            await self._async_control_heating()
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_COOL:
                    await self._async_cooler_turn_off()
                    return
        elif mode == "cool":
            await self._async_control_cooling()
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_heater_turn_off()
                    return
        elif mode is None:
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_control_heating()
                if opmod is HVAC_MODE_COOL:
                    await self._async_control_cooling()
        return

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            self._async_restore_program_temp()
            await self.control_system_mode(mode="heat")
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
            self._async_restore_program_temp()
            await self.control_system_mode(mode="cool")
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            await self.control_system_mode(mode="off")
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
            await self.control_system_mode()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()
        #await self._async_set_hvac_action()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        if self._hvac_mode == HVAC_MODE_HEAT_COOL:
            await self.control_system_mode()
        elif self._hvac_mode == HVAC_MODE_HEAT:
            await self.control_system_mode(mode="heat")
        elif self._hvac_mode == HVAC_MODE_COOL:
            await self.control_system_mode(mode="cool")
        elif self._hvac_mode == HVAC_MODE_OFF:
            await self.control_system_mode(mode="off")
        await self.async_update_ha_state()
        #await self._async_set_hvac_action()

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return
        self._async_update_temp(new_state)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_target_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes in the program."""
        if new_state is None:
            return
        self._restore_temp = float(new_state.state)
        if self._hvac_mode != HVAC_MODE_HEAT_COOL:
            self._async_restore_program_temp()
            await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)
        await self.async_update_ha_state()
        await self._async_set_hvac_action()

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)
        await self.async_update_ha_state()
        await self._async_set_hvac_action()

    async def _async_cooler_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.cooler_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)
        await self.async_update_ha_state()
        await self._async_set_hvac_action()

    async def _async_cooler_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.cooler_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)
        await self.async_update_ha_state()
        await self._async_set_hvac_action()

    async def _async_set_hvac_action(self):
            """Return the current running hvac operation if supported.

            Need to be one of CURRENT_HVAC_*.
            """
            if self._hvac_action_variable == "cool":
                self._hvac_action = CURRENT_HVAC_COOL
            elif self._hvac_action_variable == "heat":
                self._hvac_action = CURRENT_HVAC_HEAT
            else:
                self._hvac_action = CURRENT_HVAC_OFF
            _LOGGER.info("new action %s", self._hvac_action)
            return

    async def _async_control_heating(self):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.info("Obtained current and target temperature. "
                             "Generic thermostat active. %s, %s",
                             self._cur_temp, self._target_temp)

            if not self._active or self._hvac_mode == HVAC_MODE_OFF or self._hvac_mode == HVAC_MODE_COOL:
                return

            self._check_mode_type = "heat"
            if self._is_device_active:
                if (self._target_temp - self._cur_temp) <= 0:
                    _LOGGER.info("Turning off heater %s", self.heater_entity_id)
                    self._hvac_action_variable = "off"
                    await self._async_heater_turn_off()
            else:
                if (self._target_temp - self._cur_temp) >= self._tolerance:
                    _LOGGER.info("Turning on heater %s", self.heater_entity_id)
                    self._hvac_action_variable = "heat"
                    await self._async_heater_turn_on()

    async def _async_control_cooling(self):
        """Activate and de-activate cooling."""
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.info("Obtained current and target temperature. "
                             "Programmable thermostat active. %s, %s",
                             self._cur_temp, self._target_temp)

            if not self._active or self._hvac_mode == HVAC_MODE_OFF or self._hvac_mode == HVAC_MODE_HEAT:
                return

            self._check_mode_type = "cool"
            if self._is_device_active:
                if (self._cur_temp - self._target_temp) <= 0:
                    _LOGGER.info("Turning off cooler %s", self.cooler_entity_id)
                    self._hvac_action_variable = "off"
                    await self._async_cooler_turn_off()
            else:
                if (self._cur_temp - self._target_temp) >= self._tolerance:
                    _LOGGER.info("Turning on cooler %s", self.cooler_entity_id)
                    self._hvac_action_variable = "cool"
                    await self._async_cooler_turn_on()

    @callback
    def _async_switch_changed(self, entity_id, old_state, new_state):
        """Handle heater switch state changes."""
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @callback
    def _async_restore_program_temp(self):
        """Update thermostat with latest state from sensor to have back automatic value."""
        try:
            self._target_temp = self._restore_temp
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @callback
    def _async_update_program_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._target_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        if self._hvac_mode == HVAC_MODE_HEAT:
            return self.hass.states.is_state(self.heater_entity_id, STATE_ON)
        elif self._hvac_mode == HVAC_MODE_COOL:
            return self.hass.states.is_state(self.cooler_entity_id, STATE_ON)
        elif self._hvac_mode == HVAC_MODE_HEAT_COOL:
            if self._check_mode_type == "cool":
                return self.hass.states.is_state(self.cooler_entity_id, STATE_ON)
            elif self._check_mode_type == "heat":
                return self.hass.states.is_state(self.heater_entity_id, STATE_ON)
            else:
                return False
        else:
            return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return self._hvac_action
