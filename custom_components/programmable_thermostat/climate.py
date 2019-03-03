"""
This add support for a custom built smart thermostat.
This will requeire thermometer, program file and switch (for valve)

"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.core import DOMAIN as HA_DOMAIN
from homeassistant.components.climate import (
    STATE_HEAT, STATE_COOL, STATE_IDLE, STATE_MANUAL, STATE_AUTO, ClimateDevice,
    ATTR_OPERATION_MODE, ATTR_AWAY_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE, SUPPORT_TARGET_TEMPERATURE, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_TEMPERATURE, CONF_NAME, ATTR_ENTITY_ID,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_UNKNOWN, PRECISION_HALVES,
    PRECISION_TENTHS, PRECISION_WHOLE)
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

__version__ = '1.0.0'

DEPENDENCIES = ['switch', 'sensor']

DEFAULT_TOLERANCE = 0.5
DEFAULT_NAME = 'Programmable Thermostat'
DEFAULT_MAX_TEMP = 40
DEFAULT_MIN_TEMP = 5

CONF_HEAT_SWITCH = 'heat_switch'
CONF_ACT_SENSOR = 'actual_temp_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET_SENSOR = 'target_temp_sensor'
CONF_COLD_TOLERANCE = 'cold_tolerance'
CONF_HOT_TOLERANCE = 'hot_tolerance'
CONF_INITIAL_OPERATION_MODE = 'initial_operation_mode'
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_OPERATION_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HEAT_SWITCH): cv.entity_id,
    vol.Required(CONF_ACT_SENSOR): cv.entity_id,
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(
        float),
    vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(
        float),
    vol.Required(CONF_TARGET_SENSOR): cv.entity_id,
    vol.Optional(CONF_INITIAL_OPERATION_MODE):
        vol.In([STATE_HEAT, STATE_MANUAL, STATE_OFF]),
})

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    heat_switch_entity_id = config.get(CONF_HEAT_SWITCH)
    act_sensor_entity_id = config.get(CONF_ACT_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_sensor_entity_id = config.get(CONF_TARGET_SENSOR)
    cold_tolerance = config.get(CONF_COLD_TOLERANCE)
    hot_tolerance = config.get(CONF_HOT_TOLERANCE)
    initial_operation_mode = config.get(CONF_INITIAL_OPERATION_MODE)

    async_add_entities([ProgrammableThermostat(
        hass, name, heat_switch_entity_id, act_sensor_entity_id, min_temp, max_temp,
        target_sensor_entity_id, cold_tolerance,hot_tolerance, initial_operation_mode)])

class ProgrammableThermostat(ClimateDevice, RestoreEntity):
    """Programmable Thermostat."""

    def __init__(self, hass, name, heat_switch_entity_id, act_sensor_entity_id,
                 min_temp, max_temp, target_sensor_entity_id, cold_tolerance,
                 hot_tolerance, initial_operation_mode):
        """Initialize thermostat."""
        self.hass = hass
        self._name = name
        self.heat_switch_entity_id = heat_switch_entity_id
        self.act_sensor_entity_id = act_sensor_entity_id
        self._min_temp = min_temp
        self._max_temp = max_temp
        self.target_sensor_entity_id = target_sensor_entity_id
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._initial_operation_mode = initial_operation_mode

        self._target_temp = float(hass.states.get(target_sensor_entity_id).state)
        self._restore_temp = float(hass.states.get(target_sensor_entity_id).state)
        self._active = False
        self._cur_temp = float(hass.states.get(target_sensor_entity_id).state)
        self._temp_lock = asyncio.Lock()
        self._unit = hass.config.units.temperature_unit
        self._operation_list = [STATE_HEAT, STATE_MANUAL, STATE_OFF]
        if initial_operation_mode == STATE_OFF:
            self._current_operation = STATE_OFF
            self._enabled = False
        elif initial_operation_mode == STATE_MANUAL:
            self._current_operation = STATE_MANUAL
            self._enabled = True
        else:
            self._current_operation = STATE_HEAT
            self._enabled = True
        self._support_flags = SUPPORT_FLAGS
        self._restore_target_temp_state = None

        async_track_state_change(
            hass, act_sensor_entity_id, self._async_act_sensor_changed)
        async_track_state_change(
            hass, heat_switch_entity_id, self._async_heat_switch_changed)
        async_track_state_change(
            hass, target_sensor_entity_id, self._async_target_sensor_changed)

        act_sensor_state = hass.states.get(act_sensor_entity_id)
        if act_sensor_state and act_sensor_state.state != STATE_UNKNOWN:
            self._async_update_temp(act_sensor_state)
        target_sensor_state = hass.states.get(target_sensor_entity_id)
        if target_sensor_state and target_sensor_state.state != STATE_UNKNOWN and self._current_operation != STATE_MANUAL:
            self._async_update_program_temp(target_sensor_state)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        # Check if we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If wwe have previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    if hass.states.get(target_sensor_entity_id).state is None:
                        self._target_temp = float(hass.states.get(target_sensor_entity_id).state)
                    else:
                        self._target_temp = float((self._min_temp + self._max_temp)/2)
                    _LOGGER.warning("Undefined target temperature,"
                                    "falling back to %s", self._target_temp)
                else:
                    self._target_temp = float(
                        old_state.attributes[ATTR_TEMPERATURE])
                if (self._initial_operation_mode is None and
                        old_state.attributes[ATTR_OPERATION_MODE] is not None):
                    self._current_operation = \
                        old_state.attributes[ATTR_OPERATION_MODE]
                    self._enabled = self._current_operation != STATE_OFF
        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                self._target_temp = float((self._min_temp + self._max_temp)/2)
            _LOGGER.warning("No previously saved temperature, setting to %s",
                            self._target_temp)

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode == STATE_HEAT:
            self._current_operation = STATE_HEAT
            self._enabled = True
            await self._async_restore_program_temp()
            await self._async_control_heating()
        elif operation_mode == STATE_OFF:
            self._current_operation = STATE_OFF
            self._enabled = False
            if self._is_device_active:
                await self._async_heater_turn_off()
        elif operation_mode == STATE_MANUAL:
            self._current_operation = STATE_MANUAL
            self._enabled = True
            await self._async_control_heating()
        else:
            _LOGGER.error("Unrecognized operation mode: %s", operation_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    async def async_turn_on(self):
        """Turn thermostat on."""
        await self.async_set_operation_mode(STATE_HEAT)

    async def async_turn_off(self):
        """Turn thermostat off."""
        await self.async_set_operation_mode(STATE_OFF)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        await self._async_control_heating()
        await self.async_update_ha_state()

    async def _async_act_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes in the room temperature."""
        if new_state is None:
            return

        self._async_update_temp(new_state)
        await self._async_control_heating()
        await self.async_update_ha_state()

    async def _async_target_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes in the program."""
        if new_state is None:
            return
        self._restore_temp = float(new_state.state)
        if self._current_operation != STATE_MANUAL:
            self._async_update_program_temp(new_state)
        await self._async_control_heating()
        await self.async_update_ha_state()

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heat_switch_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heat_switch_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def _async_restore_program_temp(self):
        """Update thermostat with latest state from sensor to have back automatic value."""
        try:
            self._target_temp = self._restore_temp
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @callback
    def _async_heat_switch_changed(self, entity_id, old_state, new_state):
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
    def _async_update_program_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._target_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_control_heating(self):
        """Activate and de-activate heating."""
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.info("Obtained current and target temperature. "
                             "Generic thermostat active. %s, %s",
                             self._cur_temp, self._target_temp)

            if not self._active or not self._enabled:
                return

            if self._is_device_active:
                if (self._target_temp - self._cur_temp) <= 0:
                    _LOGGER.info("Turning off heater %s",
                                 self.heat_switch_entity_id)
                    await self._async_heater_turn_off()
            else:
                if (self._target_temp - self._cur_temp) >= self._hot_tolerance:
                    _LOGGER.info("Turning on heater %s", self.heat_switch_entity_id)
                    await self._async_heater_turn_on()

    @property
    def state(self):
        """Return the current state."""
        if self._is_device_active and self._current_operation != STATE_MANUAL:
            return STATE_ON
        if self._enabled and self._current_operation != STATE_MANUAL:
            return STATE_AUTO
        if self._enabled and self._current_operation == STATE_MANUAL:
            return STATE_MANUAL
        return STATE_OFF

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
    def current_operation(self):
        """Return current operation."""
        return self._current_operation

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

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
        return self.hass.states.is_state(self.heat_switch_entity_id, STATE_ON)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags
