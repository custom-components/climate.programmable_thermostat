"""Adds support for generic thermostat units."""
import asyncio
import logging
import json
from datetime import timedelta
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval
)
from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    VERSION,
    DOMAIN,
    PLATFORM
)
from .config_schema import(
    CLIMATE_SCHEMA,
    CONF_HEATER,
    CONF_COOLER,
    CONF_SENSOR,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TARGET,
    CONF_TOLERANCE,
    CONF_INITIAL_HVAC_MODE,
    CONF_RELATED_CLIMATE,
    CONF_HVAC_OPTIONS,
    CONF_AUTO_MODE,
    CONF_MIN_CYCLE_DURATION,
    SUPPORT_FLAGS
)
from .helpers import dict_to_timedelta

_LOGGER = logging.getLogger(__name__)

__version__ = VERSION

DEPENDENCIES = ['switch', 'sensor']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLIMATE_SCHEMA)

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Add ProgrammableThermostat entities from configuration.yaml."""
    _LOGGER.info("Setup entity coming from configuration.yaml named: %s", config.get(CONF_NAME))
    await async_setup_reload_service(hass, DOMAIN, PLATFORM)
    async_add_entities([ProgrammableThermostat(hass, config)])

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add ProgrammableThermostat entities from configuration flow."""
    result = {}
    if config_entry.options != {}:
        result = config_entry.options
    else:
        result = config_entry.data
    _LOGGER.info("setup entity-config_entry_data=%s",result)
    await async_setup_reload_service(hass, DOMAIN, PLATFORM)
    async_add_devices([ProgrammableThermostat(hass, result)])


class ProgrammableThermostat(ClimateEntity, RestoreEntity):
    """ProgrammableThermostat."""

    def __init__(self, hass, config):

        """Initialize the thermostat."""
        self.hass = hass
        self._name = config.get(CONF_NAME)
        self.heaters_entity_ids = self._getEntityList(config.get(CONF_HEATER))
        self.coolers_entity_ids = self._getEntityList(config.get(CONF_COOLER))
        self.sensor_entity_id = config.get(CONF_SENSOR)
        self._tolerance = config.get(CONF_TOLERANCE)
        self._min_temp = config.get(CONF_MIN_TEMP)
        self._max_temp = config.get(CONF_MAX_TEMP)
        self._initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
        self.target_entity_id = config.get(CONF_TARGET)
        self._unit = hass.config.units.temperature_unit
        self._related_climate = self._getEntityList(config.get(CONF_RELATED_CLIMATE))
        self._hvac_options = config.get(CONF_HVAC_OPTIONS)
        self._auto_mode = config.get(CONF_AUTO_MODE)
        self._hvac_list = []
        self.min_cycle_duration = config.get(CONF_MIN_CYCLE_DURATION)
        if type(self.min_cycle_duration) == type({}):
            self.min_cycle_duration = dict_to_timedelta(self.min_cycle_duration)
        self._target_temp = self._getFloat(self._getStateSafe(self.target_entity_id), None)
        self._restore_temp = self._target_temp
        self._cur_temp = self._getFloat(self._getStateSafe(self.sensor_entity_id), self._target_temp)
        self._active = False
        self._temp_lock = asyncio.Lock()
        self._hvac_action = CURRENT_HVAC_OFF

        """Setting up of HVAC list according to the option parameter"""
        options = "{0:b}".format(self._hvac_options).zfill(3)[::-1]
        if options[0] == "1":
            self._hvac_list.append(HVAC_MODE_OFF)
        if self.heaters_entity_ids is not None and options[1] == "1":
            self._hvac_list.append(HVAC_MODE_HEAT)
        if self.coolers_entity_ids is not None and options[1] == "1":
            self._hvac_list.append(HVAC_MODE_COOL)
        if (self.heaters_entity_ids != None or self.coolers_entity_ids != None) and  options[2] == "1":
            self._hvac_list.append(HVAC_MODE_HEAT_COOL)
        if self.heaters_entity_ids == None and self.coolers_entity_ids == None:
            _LOGGER.error("ERROR on climate.%s, you have to define at least one between heater and cooler", self._name)
        if not self._hvac_list:
            self._hvac_list.append(HVAC_MODE_OFF)
            _LOGGER.error("ERROR on climate.%s, you have choosen a wrong value of hvac_options, please check documentation", self._name)

        if self._initial_hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
        elif self._initial_hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
        elif self._initial_hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
        else:
            self._hvac_mode = HVAC_MODE_OFF
        self._support_flags = SUPPORT_FLAGS

        """ Check if heaters and coolers are the same """
        if self.heaters_entity_ids == self.coolers_entity_ids:
            self._are_entities_same = True
        else:
            self._are_entities_same = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.sensor_entity_id, self._async_sensor_changed))
        if self._hvac_mode == HVAC_MODE_HEAT:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self.heaters_entity_ids, self._async_switch_changed))
        elif self._hvac_mode == HVAC_MODE_COOL:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self.coolers_entity_ids, self._async_switch_changed))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.target_entity_id, self._async_target_changed))
        if self._related_climate is not None:
            for _related_entity in self._related_climate:
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, _related_entity, self._async_switch_changed))

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
        _LOGGER.info("climate.%s old state: %s", self._name, old_state)
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    target_entity_state = self._getStateSafe(self.target_entity_id)
                    if target_entity_state is not None:
                        self._target_temp = float(target_entity_state)
                    else:
                        self._target_temp = float((self._min_temp + self._max_temp)/2)
                    _LOGGER.warning("climate.%s - Undefined target temperature,"
                                    "falling back to %s", self._name , self._target_temp)
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
            _LOGGER.warning("climate.%s - No previously saved temperature, setting to %s", self._name,
                            self._target_temp)

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    async def control_system_mode(self):
        """this is used to decide what to do, so this function turn off switches and run the function
           that control the temperature."""
        if self._hvac_mode == HVAC_MODE_OFF:
            _LOGGER.debug("set to off")
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT:
                    await self._async_turn_off(mode="heat", forced=True)
                if opmod is HVAC_MODE_COOL:
                    await self._async_turn_off(mode="cool", forced=True)
            self._hvac_action = CURRENT_HVAC_OFF
        elif self._hvac_mode == HVAC_MODE_HEAT:
            _LOGGER.debug("set to heat")
            await self._async_control_thermo(mode="heat")
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_COOL and not self._are_entities_same:
                    await self._async_turn_off(mode="cool", forced=True)
                    return
        elif self._hvac_mode == HVAC_MODE_COOL:
            _LOGGER.debug("set to cool")
            await self._async_control_thermo(mode="cool")
            for opmod in self._hvac_list:
                if opmod is HVAC_MODE_HEAT and not self._are_entities_same:
                    await self._async_turn_off(mode="heat", forced=True)
                    return
        else:
            _LOGGER.debug("set to auto")
            for opmod in self._hvac_list:
            # Check of self._auto_mode has been added to avoid cooling a room that has just been heated and vice versa
            # LET'S PRESERVE ENERGY!
            # If you don't want to check that you have just to set auto_mode=all
                if opmod is HVAC_MODE_HEAT and self._auto_mode != 'cooling':
                    _LOGGER.debug("climate.%s - Entered here in heating mode", self._name)
                    await self._async_control_thermo(mode="heat")
                if opmod is HVAC_MODE_COOL and self._auto_mode != 'heating':
                    _LOGGER.debug("climate.%s - Entered here in cooling mode", self._name)
                    await self._async_control_thermo(mode="cool")
        return

    async def _async_turn_on(self, mode=None):
        """Turn heater toggleable device on."""
        if mode == "heat":
            data = {ATTR_ENTITY_ID: self.heaters_entity_ids}
        elif mode == "cool":
            data = {ATTR_ENTITY_ID: self.coolers_entity_ids}
        else:
            _LOGGER.error("climate.%s - No type has been passed to turn_on function", self._name)

        if not self._is_device_active_function(forced=False) and self.is_active_long_enough(mode=mode):
            self._set_hvac_action_on(mode=mode)
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)
            await self.async_update_ha_state()

    async def _async_turn_off(self, mode=None, forced=False):
        """Turn heater toggleable device off."""
        if self._related_climate is not None:
            for _climate in self._related_climate:
                related_climate_hvac_action = self.hass.states.get(_climate).attributes['hvac_action']
                if related_climate_hvac_action == CURRENT_HVAC_HEAT or related_climate_hvac_action == CURRENT_HVAC_COOL:
                    _LOGGER.info("climate.%s - Master climate object action is %s, so no action taken.", self._name, related_climate_hvac_action)
                    return
        if mode == "heat":
            data = {ATTR_ENTITY_ID: self.heaters_entity_ids}
        elif mode == "cool":
            data = {ATTR_ENTITY_ID: self.coolers_entity_ids}
        else:
            _LOGGER.error("climate.%s - No type has been passed to turn_off function", self._name)
        self._check_mode_type = mode
        if self._is_device_active_function(forced=forced) and self.is_active_long_enough(mode=mode):
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
            _LOGGER.error("climate.%s - Unrecognized hvac mode: %s", self._name, hvac_mode)
            return
        await self.control_system_mode()
        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._async_update_temp(new_state.state)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_target_changed(self, event):
        """Handle temperature changes in the program."""
        new_state = event.data.get("new_state")
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
            _LOGGER.info("climate.%s - Abort _async_control_thermo as _cur_temp is None", self._name)
            return
        if self._target_temp is None:
            _LOGGER.info("climate.%s - Abort _async_control_thermo as _target_temp is None", self._name)
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
            _LOGGER.error("climate.%s - No type has been passed to control_thermo function", self._name)
        self._check_mode_type = mode
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.debug("climate.%s - Obtained current and target temperature. "
                             "Generic thermostat active. %s, %s", self._name,
                             self._cur_temp, self._target_temp)

            if not self._active or self._hvac_mode == HVAC_MODE_OFF or self._hvac_mode == hvac_mode:
                return

            if delta <= 0:
                if not self._areAllInState(entities, STATE_OFF):
                    _LOGGER.debug("Turning off %s", entities)
                    await self._async_turn_off(mode=mode)
                self._set_hvac_action_off(mode=mode)
            elif delta >= self._tolerance:
                self._set_hvac_action_on(mode=mode)
                if not self._areAllInState(entities, STATE_ON):
                    _LOGGER.debug("Turning on %s", entities)
                    await self._async_turn_on(mode=mode)

    def _set_hvac_action_off(self, mode=None):
        """This is used to set CURRENT_HVAC_OFF on the climate integration.
           This has been split form turn_off function since this will allow to make dedicated calls.
           For the other CURRENT_HVAC_*, this is not needed becasue they work perfectly at the turn_on."""
        # This if condition is necessary to correctly manage the action for the different modes.
        _LOGGER.debug("climate.%s - mode=%s \r\ntarget=%s \r\n current=%s", self._name, mode, self._target_temp, self._cur_temp)
        if mode == "heat":
            delta = self._target_temp - self._cur_temp
            entities = self.coolers_entity_ids
            mode_2 = "cool"
        elif mode == "cool":
            delta = self._cur_temp - self._target_temp
            entities = self.heaters_entity_ids
            mode_2 = "heat"
        else:
            _LOGGER.error("climate.%s - No type has been passed to control_thermo function", self._name)
            mode_2 = None
        _LOGGER.debug("climate.%s - delta=%s", self._name, delta)
        if (((mode == "cool" and not self._hvac_mode == HVAC_MODE_HEAT) or \
           (mode == "heat" and not self._hvac_mode == HVAC_MODE_COOL)) and \
           not self._hvac_mode == HVAC_MODE_HEAT_COOL):
            self._hvac_action = CURRENT_HVAC_OFF
            _LOGGER.debug("climate.%s - new action %s", self._name, self._hvac_action)
        elif self._hvac_mode == HVAC_MODE_HEAT_COOL and delta <= 0:
            self._hvac_action = CURRENT_HVAC_OFF
            _LOGGER.debug("climate.%s - new action %s", self._name, self._hvac_action)
            if abs(delta) >= self._tolerance and entities != None:
                self._set_hvac_action_on(mode=mode_2)
        else:
            if self._are_entities_same and not self._is_device_active_function(forced=False):
                self._hvac_action = CURRENT_HVAC_OFF
            else:
                _LOGGER.error("climate.%s - Error during set of HVAC_ACTION", self._name)

    def _set_hvac_action_on(self, mode=None):
        """This is used to set CURRENT_HVAC_* according to the mode that is running."""
        if mode == "heat":
            self._hvac_action = CURRENT_HVAC_HEAT
        elif mode == "cool":
            self._hvac_action = CURRENT_HVAC_COOL
        else:
            _LOGGER.error("climate.%s - No type has been passed to turn_on function", self._name)
        _LOGGER.debug("climate.%s - new action %s", self._name, self._hvac_action)

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
        if valStr!=STATE_UNKNOWN and valStr!=STATE_UNAVAILABLE and valStr is not None:
            return float(valStr)
        return defaultVal

    def _areAllInState(self, entity_ids, state):
        for entity_id in entity_ids:
            if not self.hass.states.is_state(entity_id, state):
                return False
        return True

    def _is_device_active_function(self, forced):
        """If the toggleable device is currently active."""
        _LOGGER.debug("climate.%s - \r\nheaters: %s \r\ncoolers: %s \r\n_check_mode_type: %s \r\n_hvac_mode: %s \r\nforced: %s", self._name, self.heaters_entity_ids, self.coolers_entity_ids, self._check_mode_type, self._hvac_mode, forced)
        if not forced:
            _LOGGER.debug("climate.%s - 410- enter in classic mode: %s", self._name, forced)
            if self._hvac_mode == HVAC_MODE_HEAT_COOL:
                if self._check_mode_type == "cool":
                    return self._areAllInState(self.coolers_entity_ids, STATE_ON)
                elif self._check_mode_type == "heat":
                    return self._areAllInState(self.heaters_entity_ids, STATE_ON)
                else:
                    return False
            elif self._hvac_mode == HVAC_MODE_HEAT:
                _LOGGER.debug("climate.%s - 419 - heaters: %s", self._name, self.heaters_entity_ids)
                return self._areAllInState(self.heaters_entity_ids, STATE_ON)
            elif self._hvac_mode == HVAC_MODE_COOL:
                _LOGGER.debug("climate.%s - 422 - coolers: %s", self._name, self.coolers_entity_ids)
                return self._areAllInState(self.coolers_entity_ids, STATE_ON)
            else:
                return False
                """if self._check_mode_type == "cool":
                    return self._areAllInState(self.coolers_entity_ids, STATE_ON)
                elif self._check_mode_type == "heat":
                    return self._areAllInState(self.heaters_entity_ids, STATE_ON)
                else:
                    return False"""
        else:
            _LOGGER.debug("climate.%s - 433- enter in forced mode: %s", self._name, forced)
            if self._check_mode_type == "heat":
                _LOGGER.debug("climate.%s - 435 - heaters: %s", self._name, self.heaters_entity_ids)
                return self._areAllInState(self.heaters_entity_ids, STATE_ON)
            elif self._check_mode_type == "cool":
                _LOGGER.debug("climate.%s - 438 - coolers: %s", self._name, self.coolers_entity_ids)
                return self._areAllInState(self.coolers_entity_ids, STATE_ON)
            else:
                return False

    def is_active_long_enough(self, mode=None):
        """ This function is to check if the heater/cooler has been active long enough """
        if not self.min_cycle_duration:
            return True
        if self._is_device_active:
            current_state = STATE_ON
        else:
            current_state = STATE_OFF
        if mode == "heat":
            for entity in self.heaters_entity_ids:
                return condition.state(self.hass, entity, current_state, self.min_cycle_duration)
        elif mode == "cool":
            for entity in self.coolers_entity_ids:
                return condition.state(self.hass, entity, current_state, self.min_cycle_duration)
        else:
            _LOGGER.error("Wrong mode have been passed to function is_active_long_enough")
        return True

    @callback
    def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to update current temperature from sensor: %s", self._name, ex)

    @callback
    def _async_restore_program_temp(self):
        """Update thermostat with latest state from sensor to have back automatic value."""
        try:
            if self._restore_temp is not None:
                self._target_temp = self._restore_temp
            else:
                self._target_temp = self._getFloat(self._getStateSafe(self.target_entity_id), None)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to restore program temperature from sensor: %s", self._name, ex)

    @callback
    def _async_update_program_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._target_temp = float(state)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to update target temperature from sensor: %s", self._name, ex)

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
        return self._is_device_active_function(forced=False)

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
