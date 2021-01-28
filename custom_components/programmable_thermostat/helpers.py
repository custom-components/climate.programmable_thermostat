import logging
import re
from .const import REGEX_STRING
from datetime import timedelta, datetime

_LOGGER = logging.getLogger(__name__)

def are_entities_valid(self, entities_list) -> bool:
    """ To validate the existence of the entities list """
    entities = string_to_list(entities_list)
    for entity in entities:
        try:
            self.hass.states.get(entity).state
        except:
            return False
    return True

def string_to_list(string):
    """ To convert a string of entities diveded by commas into a list. """
    if string is None or string == "":
        return []
    return list(map(lambda x: x.strip(), string.split(",")))

def string_to_timedelta(string):
    """ to convert a string with format hh:mm:ss or mm:ss into a timedelta data. """
    string = re.match(REGEX_STRING, string)
    if string is None or string == "":
        return []
    string = string.groupdict()
    return string

def dict_to_string(time_delta: dict = {}) -> str:
    """ to convert a dict like {'hours': hh, 'minutes': mm, 'seconds': ss} into a string hh:mm:ss.
        dict is expected sorted as hours-minutes-seconds """
    result = ''
    for key in time_delta.keys():
        if time_delta[key] == None:
            result = result + '00:'
        else:
            result = result + str(time_delta[key]) + ':'
    return result[0:len(result)-1:]

def dict_to_timedelta(string):
    """ to convert dict (mappingproxy) like {'hours': hh, 'minutes': mm, 'seconds': ss} into a timedelta's class element. """
    time_params = {}
    for name in string.keys():
        if string[name]:
            time_params[name] = int(string[name])
    return timedelta(**time_params)

def null_data_cleaner(original_data: dict, data: dict) -> dict:
    """ this is to remove all null parameters from data that are added during option flow """
    for key in data.keys():
        if data[key] == "null":
            original_data[key] = ""
        else:
            original_data[key]=data[key]
    return original_data
