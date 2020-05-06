import voluptuous as vol
import logging
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import CONF_NAME, CONF_ENTITIES
from .const import (
    DOMAIN,
    DEFAULT_TOLERANCE,
    DEFAULT_NAME,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_HVAC_OPTIONS,
    DEFAULT_AUTO_MODE,
    MAX_HVAC_OPTIONS,
    AUTO_MODE_OPTIONS,
    INITIAL_HVAC_MODE_OPTIONS)

_LOGGER = logging.getLogger(__name__)

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

CLIMATE_SCHEMA = {
    vol.Optional(CONF_HEATER): cv.entity_ids,
    vol.Optional(CONF_COOLER): cv.entity_ids,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Required(CONF_TARGET): cv.entity_id,
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
    vol.Optional(CONF_RELATED_CLIMATE): cv.entity_id,
    vol.Optional(CONF_HVAC_OPTIONS, default=DEFAULT_HVAC_OPTIONS): vol.In(range(MAX_HVAC_OPTIONS)),
    vol.Optional(CONF_AUTO_MODE, default=DEFAULT_AUTO_MODE): vol.In(AUTO_MODE_OPTIONS),
    vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(INITIAL_HVAC_MODE_OPTIONS)
}

def get_config_flow_schema(config: dict = {}, config_flow_step: int = 0) -> dict:
    if not config:
        config = {
            CONF_NAME: DEFAULT_NAME,
            CONF_HEATER: "input_boolean.f1",
            CONF_COOLER: "",
            CONF_SENSOR: "sensor.mi_t_4c65a8d894a8",
            CONF_TARGET: "sensor.cameretta",
            CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
            CONF_TOLERANCE: DEFAULT_TOLERANCE,
            CONF_RELATED_CLIMATE: "",
            CONF_HVAC_OPTIONS: DEFAULT_HVAC_OPTIONS,
            CONF_AUTO_MODE: DEFAULT_AUTO_MODE,
            CONF_INITIAL_HVAC_MODE: ""
        }
    if config_flow_step==1:
        return {
            vol.Optional(CONF_NAME, default=config.get(CONF_NAME)): str,
            vol.Optional(CONF_HEATER, default=config.get(CONF_HEATER)): str,
            vol.Optional(CONF_COOLER, default=config.get(CONF_COOLER)): str,
            vol.Required(CONF_SENSOR, default=config.get(CONF_SENSOR)): str,
            vol.Required(CONF_TARGET, default=config.get(CONF_TARGET)): str
        }
    elif config_flow_step==2:
        return {
            vol.Optional(CONF_MAX_TEMP, default=config.get(CONF_MAX_TEMP)): int,
            vol.Optional(CONF_MIN_TEMP, default=config.get(CONF_MIN_TEMP)): int,
            vol.Optional(CONF_TOLERANCE, default=config.get(CONF_TOLERANCE)): float
        }
    elif config_flow_step==3:
        return {
            vol.Optional(CONF_RELATED_CLIMATE, default=config.get(CONF_RELATED_CLIMATE)): str,
            vol.Optional(CONF_HVAC_OPTIONS, default=config.get(CONF_HVAC_OPTIONS)):  vol.In(range(MAX_HVAC_OPTIONS)),
            vol.Optional(CONF_AUTO_MODE, default=config.get(CONF_AUTO_MODE)): vol.In(AUTO_MODE_OPTIONS),
            vol.Optional(CONF_INITIAL_HVAC_MODE, default=config.get(CONF_INITIAL_HVAC_MODE)): vol.In(INITIAL_HVAC_MODE_OPTIONS)
        }

    return {}
