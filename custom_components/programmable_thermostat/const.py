"""Programmable thermostat's constant """
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL)

#Generic
VERSION = '6.1'
DOMAIN = 'programmable_thermostat'
PLATFORM = 'climate'
ISSUE_URL = 'https://github.com/custom-components/climate.programmable_thermostat/issues'


#Defaults
DEFAULT_TOLERANCE = 0.5
DEFAULT_NAME = 'Programmable Thermostat'
DEFAULT_MAX_TEMP = 40
DEFAULT_MIN_TEMP = 5
DEFAULT_HVAC_OPTIONS = 7
DEFAULT_AUTO_MODE = 'all'

#Others
MAX_HVAC_OPTIONS = 8
AUTO_MODE_OPTIONS = ['all', 'heating', 'cooling']
INITIAL_HVAC_MODE_OPTIONS = ['', HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL]
