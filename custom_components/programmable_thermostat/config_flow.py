""" Configuration flow for the programmable_thermostat integration to allow user
    to define all programmable_thermostat entities from Lovelace UI."""
import logging
from homeassistant.core import callback
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
import uuid

from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_START
)
from .const import DOMAIN
from .config_schema import (
    get_config_flow_schema,
    CONF_HEATER,
    CONF_COOLER,
    CONF_SENSOR,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TARGET,
    CONF_TOLERANCE,
    CONF_RELATED_CLIMATE
)


_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class ProgrammableThermostatConfigFlow(config_entries.ConfigFlow):
    """Programmable Thermostat config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._data = {}
        self._data["unique_id"] = str(uuid.uuid4())

    """ INITIATE CONFIG FLOW """
    async def async_step_user(self, user_input={}):
        """User initiated config flow."""
        self._errors = {}
        if user_input is not None:
            if self.are_first_step_data_valid(user_input):
                self._data.update(user_input)
                self._data[CONF_HEATER] = self.string_to_list(self._data[CONF_HEATER])
                self._data[CONF_COOLER] = self.string_to_list(self._data[CONF_COOLER])
                _LOGGER.info("First input data are valid. Proceed with second step. %s", self._data)
                return await self.async_step_second()
            _LOGGER.warning("Wrong date have been input in the first form")
            return await self._show_config_form_first(user_input)
        return await self._show_config_form_first(user_input)

    """ SHOW FIRST FORM """
    async def _show_config_form_first(self, user_input):
        """ Show form for config flow """
        _LOGGER.info("Show first form")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(get_config_flow_schema(user_input, 1)),
            errors=self._errors
        )

    """ SECOND CONFIG FLOW STEP """
    async def async_step_second(self, user_input={}):
        """User proceed on the second step config flow."""
        self._errors = {}
        if user_input is not None and user_input != {}:
            if self.are_second_step_data_valid(user_input):
                self._data.update(user_input)
                _LOGGER.info("Second input data are valid. Proceed with final step.")
                return await self.async_step_final()
            _LOGGER.warning("Wrong date have been input in the second form")
            return await self._show_config_form_second(user_input)
        return await self._show_config_form_second(user_input)

    """ SHOW SECOND FORM """
    async def _show_config_form_second(self, user_input):
        """ Show form for config flow """
        _LOGGER.info("Show second form")
        return self.async_show_form(
            step_id="second",
            data_schema=vol.Schema(get_config_flow_schema(user_input, 2)),
            errors=self._errors
        )

    """ LAST CONFIG FLOW STEP """
    async def async_step_final(self, user_input={}):
        """User initiated config flow."""
        if user_input is not None and user_input != {}:
            if self.are_third_step_data_valid(user_input):
                self._data.update(user_input)
                final_data = {}
                for key in self._data.keys():
                    if self._data[key] != "" and self._data[key] != []:
                        final_data.update({key: self._data[key]})
                _LOGGER.info("Data are valid. Proceed with entity creation. - %s", final_data)
                return self.async_create_entry(title=final_data["name"], data=final_data)
            _LOGGER.warning("Wrong date have been input in the first form")
            return await self._show_config_form_final(user_input)
        return await self._show_config_form_final(user_input)

    """ SHOW LAST FORM """
    async def _show_config_form_final(self, user_input):
        """ Show form for config flow """
        _LOGGER.info("Show final form")
        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema(get_config_flow_schema(user_input, 3)),
            errors=self._errors
        )

    """ DATA VALIDATION FUCTIONS """
    def are_first_step_data_valid(self, user_input) -> bool:
        if user_input[CONF_HEATER] == "" and user_input[CONF_COOLER] == "":
            self._errors["base"]="heater and cooler"
            return False
        else:
            if user_input[CONF_HEATER] != "":
                if not self.are_entities_valid(user_input, CONF_HEATER):
                    self._errors["base"]="heater wrong"
                    return False
            if user_input[CONF_COOLER] != "":
                if not self.are_entities_valid(user_input, CONF_COOLER):
                    self._errors["base"]="cooler wrong"
                    return False
        if not self.are_entities_valid(user_input, CONF_SENSOR):
            self._errors["base"]="sensor wrong"
            return False
        if not self.are_entities_valid(user_input, CONF_TARGET):
            self._errors["base"]="target wrong"
            return False
        return True

    def are_second_step_data_valid(self, user_input) -> bool:
        if not user_input[CONF_MIN_TEMP]<user_input[CONF_MAX_TEMP]:
            self._errors["base"]="min_temp"
            return False
        if (not user_input[CONF_TOLERANCE] > 0) or (not user_input[CONF_TOLERANCE] < abs(user_input[CONF_MIN_TEMP])):
            self._errors["base"]="tolerance"
            return False
        return True

    def are_third_step_data_valid(self, user_input) -> bool:
        if user_input[CONF_RELATED_CLIMATE] != "":
            if not self.are_entities_valid(user_input, CONF_RELATED_CLIMATE) or not user_input[CONF_RELATED_CLIMATE][:8:] == "climate." :
                self._errors["base"]="related climate"
                return False
        return True

    def are_entities_valid(self, user_input, check_value) -> bool:
        """ To validate the existence of the entities list """
        entities = self.string_to_list(user_input[check_value])
        for entity in entities:
            try:
                self.hass.states.get(entity).state
            except:
                return False
        return True

    def string_to_list(self, string):
        """ To convert a string of entities diveded by commas into a list """
        if string is None or string == "":
            return []
        return list(map(lambda x: x.strip(), string.split(",")))

    """ SHOW CONFIGURATION.YAML ENTITIES """
    async def async_step_import(self, user_input):
        """Import a config entry.
        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="configuration.yaml", data={})
"""
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        if config_entry.options.get("unique_id", None) is not None:
            return OptionsFlowHandler(config_entry)
        else:
            return EmptyOptions(config_entry)"""
