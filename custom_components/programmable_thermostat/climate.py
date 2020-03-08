"""Adds support for generic thermostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_interval)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

__version__ = '5.1'

DEPENDENCIES = ['switch', 'sensor']

DEFAULT_TOLERANCE = 0.5
DEFAULT_NAME = 'Programmable Thermostat'
DEFAULT_MAX_TEMP = 40
DEFAULT_MIN_TEMP = 5
DEFAULT_HVAC_OPTIONS = 7
DEFAULT_AUTO_MODE = 'all'

CONF_HEATER = 'heater'
CONF_COOLER = 'cooler'
CONF_SENSOR = 'actual_temp_sensor'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TARGET = 'target_temp_sensor'
CONF_TOLERANCE = 'tolerance'
CONF_INITIAL_HVAC_MODE = 'initial_hvac_mode'
CONF_RELATED_CLIMATE = 'related_climate'
CONF_HVAC_OPTIONS = 'hvac_options'
CONF_AUTO_MODE = 'auto_mode'
SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HEATER): cv.entity_ids,
    vol.Optional(CONF_COOLER): cv.entity_ids,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Required(CONF_TARGET): cv.entity_id,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
    vol.Optional(CONF_RELATED_CLIMATE): cv.entity_id,
    vol.Optional(CONF_HVAC_OPTIONS, default=DEFAULT_HVAC_OPTIONS): vol.In(range(8)),
    vol.Optional(CONF_AUTO_MODE, default=DEFAULT_AUTO_MODE): vol.In(['all', 'heating', 'cooling']),
    vol.Optional(CONF_INITIAL_HVAC_MODE):
        vol.In([HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL]),
})

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    heaters_entity_ids = config.get(CONF_HEATER)
    coolers_entity_ids = config.get(CONF_COOLER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_entity_id = config.get(CONF_TARGET)
    tolerance = config.get(CONF_TOLERANCE)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    related_climate = config.get(CONF_RELATED_CLIMATE)
    hvac_options = config.get(CONF_HVAC_OPTIONS)
    auto_mode = config.get(CONF_AUTO_MODE)
    unit = hass.config.units.temperature_unit

    async_add_entities([ProgrammableThermostat(
        hass,
        name,
        heaters_entity_ids,
        coolers_entity_ids,
        sensor_entity_id,
        min_temp,
        max_temp,
        target_entity_id,
        tolerance,
        initial_hvac_mode,
        unit,
        related_climate,
        hvac_options,
        auto_mode)])


class ProgrammableThermostat(ClimateDevice, RestoreEntity):
    """ProgrammableThermostat."""

    def __init__(
        self,
        hass,
        name,
        heaters_entity_ids,
        coolers_entity_ids,
        sensor_entity_id,
        min_temp, max_temp,
        target_entity_id,
        tolerance,
        initial_hvac_mode,
        unit,
        related_climate,
        hvac_options,
        auto_mode):

        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self.heaters_entity_ids = self._getEntityList(heaters_entity_ids)
        self.coolers_entity_ids = self._getEntityList(coolers_entity_ids)
        self.sensor_entity_id = sensor_entity_id
        self._tolerance = tolerance
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._initial_hvac_mode = initial_hvac_mode
        self.target_entity_id = target_entity_id
        self._unit = unit
        self._related_climate = related_climate
        self._hvac_options = hvac_options
        self._auto_mode = auto_mode
        self._hvac_list = []

        self._target_temp = self._getFloat(self._getStateSafe(target_entity_id), None)
        self._restore_temp = self._target_temp
        self._cur_temp = self._getFloat(self._getStateSafe(sensor_entity_id), self._target_temp)
        self._active = False
        self._temp_lock = asyncio.Lock()
        self._hvac_action = CURRENT_HVAC_OFF

        """Setting up of HVAC list according to the option parameter"""
        options = "{0:b}".format(self._hvac_options).zfill(3)[::-1]
        if options[0] is "1":
            self._hvac_list.append(HVAC_MODE_OFF)
        if self.heaters_entity_ids is not None and options[1] is "1":
            self._hvac_list.append(HVAC_MODE_HEAT)
        if self.coolers_entity_ids is not None and options[1] is "1":
            self._hvac_list.append(HVAC_MODE_COOL)
        if (self.heaters_entity_ids is not None or self.coolers_entity_ids is not None) and  options[2] is "1":
            self._hvac_list.append(HVAC_MODE_HEAT_COOL)
        if self.heaters_entity_ids is None and self.coolers_entity_ids is None:
            _LOGGER.error("ERROR, you have to define at least one between heater and cooler")
        if not self._hvac_list:
            self._hvac_list.append(HVAC_MODE_OFF)
            _LOGGER.error("ERROR, you have choosen a wrong value of hvac_options, please check documentation")

        if initial_hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
        elif initial_hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
        elif initial_hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
        else:
            self._hvac_mode = HVAC_MODE_OFF
        self._support_flags = SUPPORT_FLAGS

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self.sensor_entity_id, self._async_sensor_changed)
        if self._hvac_mode == HVAC_MODE_HEAT:
            async_track_state_change(
                self.hass, self.heaters_entity_ids, self._async_switch_changed)
        elif self._hvac_mode == HVAC_MODE_COOL:
            async_track_state_change(
                self.hass, self.coolers_entity_ids, self._async_switch_changed)
        async_track_state_change(
            self.hass, self.target_entity_id, self._async_target_changed)
        if self._related_climate is not None:
            async_track_state_change(
                self.hass, self._related_climate, self._async_switch_changed)

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self._getStateSafe(self.sensor_entity_id)
            if sensor_state and sensor_state != STATE_UNKNOWN:
                self._async_update_temp(sensor_state)
            target_state = self._getStateSafe(self.target_entity_id)
            if target_state and \
               target_state != STATE_UNKNOWN and \
               self._hvac_mode != HVAC_MODE_HEAT_COOL:
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
                    target_entity_state = self._getStateSafe(target_entity_id)
                    if target_entity_state is not None:
                        self._target_temp = float(target_entity_state)
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

    async def control_system_mode(self):
        """this is used to decide what to do, so this function turn off switches and run the function
           that control the temperature."""
        if self._hvac_mode == HVAC_MODE_OFF:
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_turn_off(mode="heat")
                if opmod is HVAC_MODE_COOL:
                    await self._async_turn_off(mode="cool")
        elif self._hvac_mode == HVAC_MODE_HEAT:
            await self._async_control_thermo(mode="heat")
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_COOL:
                    await self._async_turn_off(mode="cool")
                    return
        elif self._hvac_mode == HVAC_MODE_COOL:
            await self._async_control_thermo(mode="cool")
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_turn_off(mode="heat")
                    return
        else:
            for opmod in self._hvac_list:
            # Check of self._auto_mode has been added to avoid cooling a room that has just been heated and vice versa
            # LET'S PRESERVE ENERGY!
            # If you don't want to check that you have just to set auto_mode=all
                if opmod is HVAC_MODE_HEAT and self._auto_mode != 'cooling':
                    _LOGGER.info("Entered here in heating mode")
                    await self._async_control_thermo(mode="heat")
                if opmod is HVAC_MODE_COOL and self._auto_mode != 'heating':
                    _LOGGER.info("Entered here in cooling mode")
                    await self._async_control_thermo(mode="cool")
        return

    async def _async_turn_on(self, mode=None):
        """Turn heater toggleable device on."""
        if mode == "heat":
            data = {ATTR_ENTITY_ID: self.heaters_entity_ids}
        elif mode == "cool":
            data = {ATTR_ENTITY_ID: self.coolers_entity_ids}
        else:
            _LOGGER.error("No type has been passed to turn_on function")
        self._set_hvac_action_on(mode=mode)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)
        await self.async_update_ha_state()

    async def _async_turn_off(self, mode=None):
        """Turn heater toggleable device off."""
        if self._related_climate is not None:
            related_climate_hvac_action = self.hass.states.get(self._related_climate).attributes['hvac_action']
            if related_climate_hvac_action == CURRENT_HVAC_HEAT or related_climate_hvac_action == CURRENT_HVAC_COOL:
                _LOGGER.info("Master climate object action is %s, so no action taken.", related_climate_hvac_action)
                return
        if mode == "heat":
            data = {ATTR_ENTITY_ID: self.heaters_entity_ids}
        elif mode == "cool":
            data = {ATTR_ENTITY_ID: self.coolers_entity_ids}
        else:
            _LOGGER.error("No type has been passed to turn_off function")
        self._set_hvac_action_off(mode=mode)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)
        await self.async_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
            self._async_restore_program_temp()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        await self.control_system_mode()
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return
        self._async_update_temp(new_state.state)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_target_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes in the program."""
        if new_state is None:
            return
        self._restore_temp = float(new_state.state)
        if self._hvac_mode == HVAC_MODE_HEAT_COOL:
            self._async_restore_program_temp()
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_control_thermo(self, mode=None):
        """Check if we need to turn heating on or off."""
        if self._cur_temp is None:
            _LOGGER.warn("Abort _async_control_thermo as _cur_temp is None")
            return
        if self._target_temp is None:
            _LOGGER.warn("Abort _async_control_thermo as _target_temp is None")
            return

        if mode == "heat":
            hvac_mode = HVAC_MODE_COOL
            delta = self._target_temp - self._cur_temp
            entities = self.heaters_entity_ids
        elif mode == "cool":
            hvac_mode = HVAC_MODE_HEAT
            delta = self._cur_temp - self._target_temp
            entities = self.coolers_entity_ids
        else:
            _LOGGER.error("No type has been passed to control_thermo function")
        self._check_mode_type = mode
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.info("Obtained current and target temperature. "
                             "Generic thermostat active. %s, %s",
                             self._cur_temp, self._target_temp)

            if not self._active or self._hvac_mode == HVAC_MODE_OFF or self._hvac_mode == hvac_mode:
                return

            if delta <= 0:
                if not self._areAllInState(entities, STATE_OFF):
                    _LOGGER.info("Turning off %s", entities)
                    await self._async_turn_off(mode=mode)
                self._set_hvac_action_off(mode=mode)
            elif delta >= self._tolerance:
                self._set_hvac_action_on(mode=mode)
                if not self._areAllInState(entities, STATE_ON):
                    _LOGGER.info("Turning on %s", entities)
                    await self._async_turn_on(mode=mode)

    def _set_hvac_action_off(self, mode=None):
        """This is used to set CURRENT_HVAC_OFF on the climate integration.
           This has been split form turn_off function since this will allow to make dedicated calls.
           For the other CURRENT_HVAC_*, this is not needed becasue they work perfectly at the turn_on."""
        # This if condition is necessary to correctly manage the action for the different modes.
        if (((mode == "cool" and not self._hvac_mode == HVAC_MODE_HEAT) or \
           (mode == "heat" and not self._hvac_mode == HVAC_MODE_COOL)) and \
           not self._hvac_mode == HVAC_MODE_HEAT_COOL):
            self._hvac_action = CURRENT_HVAC_OFF
            _LOGGER.info("new action %s", self._hvac_action)

    def _set_hvac_action_on(self, mode=None):
        """This is used to set CURRENT_HVAC_* according to the mode that is running."""
        if mode == "heat":
            self._hvac_action = CURRENT_HVAC_HEAT
        elif mode == "cool":
            self._hvac_action = CURRENT_HVAC_COOL
        else:
            _LOGGER.error("No type has been passed to turn_on function")
        _LOGGER.info("new action %s", self._hvac_action)

    def _getEntityList(self, entity_ids):
        if entity_ids is not None:
            if not isinstance(entity_ids, list):
                return [ entity_ids ]
            elif len(entity_ids)<=0:
                return None
        return entity_ids

    def _getStateSafe(self, entity_id):
        full_state = self.hass.states.get(entity_id)
        if full_state is not None:
            return full_state.state
        return None

    def _getFloat(self, valStr, defaultVal):
        if valStr!=STATE_UNKNOWN and valStr is not None:
            return float(valStr)
        return defaultVal

    def _areAllInState(self, entity_ids, state):
        for entity_id in entity_ids:
            if not self.hass.states.is_state(entity_id, state):
                return False
        return True

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
            self._cur_temp = float(state)
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
            self._target_temp = float(state)
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
            return self._areAllInState(self.heaters_entity_ids, STATE_ON)
        elif self._hvac_mode == HVAC_MODE_COOL:
            return self._areAllInState(self.coolers_entity_ids, STATE_ON)
        elif self._hvac_mode == HVAC_MODE_HEAT_COOL:
            if self._check_mode_type == "cool":
                return self._areAllInState(self.coolers_entity_ids, STATE_ON)
            elif self._check_mode_type == "heat":
                return self._areAllInState(self.heaters_entity_ids, STATE_ON)
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
