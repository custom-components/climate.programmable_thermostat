# PROGRAMMABLE THERMOSTAT
This component is a revision of the official Home Assistant component 'Generic Thermostat' to have the possibility to have the target temperature vary according to a sensor state value.

## HOW TO INSTALL
Use HACS to install the custom component and configure it through the user interface (settings/integration) to have easy and smooth usage.

If you are for the manual method:
Just copy paste the content of the `climate.programmable_thermostat/custom_components` folder in your `config/custom_components` directory.

For example, you will get the '.py' file in the following path: `/config/custom_components/programmable_thermostat/climate.py`.

## EXAMPLE OF SETUP
Config flow is available, so just configure all the entities you want through the user interface.

Here below the example of manual setup of sensor and parameters to configure.
```yaml
climate:
  - platform: programmable_thermostat
    name: room
    heater: 
      - switch.riscaldamento_1
      - switch.riscaldamento_2
    cooler: switch.condizionamento
    actual_temp_sensor: sensor.target_temperature
    min_temp: 10
    max_temp: 30
    target_temp_sensor: sensor.program_temperature
    tolerance: 0.3
    related_climate: climate.room_2
    hvac_options: 7
    auto_mode: all
    min_cycle_duration:
      seconds: 20
```

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `programmable_thermostat` | *Required* |
name| Programmable Thermostat | Optional |
heater |  | *Conditional* | Switch that will activate/deactivate the heating system. This can be a single entity or a list of entities. At least one between `heater` and `cooler` has to be defined.
cooler |  | *Conditional* | Switch that will activate/deactivate the cooling system.  This can be a single entity or a list of entities. At least one between `heater` and `cooler` has to be defined.
actual_temp_sensor |  | *Required* | Sensor of actual room temperature.
min_temp | 5 | Optional | Minimum temperature manually selectable.
max_temp | 40 | Optional | Maximum temperature manually selectable.
target_temp_sensor |  | *Required* | Sensor that represent the desired temperature for the room. Suggestion: use my [`file_restore`][1] component or something similar.
tolerance | 0.5 | Optional | Tolerance for turn on and off the switches mode.
initial_hvac_mode | `heat_cool`, `heat`, `cool`, `off` | Optional | If not set, components will restore old state after restart. I suggest not to use it.
related_climate |  | Optional | To be used if the climate object is a slave of another one. below 'Related climate' chapter a description.
hvac_options | 7 | Optional | This defines which combination of manual-auto-off options you want to activate. Refer to the chapter below for the value.
auto_mode | `all`, `heating`, `cooling` | Optional | This allows limiting the heating/cooling function with HVAC mode HEAT_COOL.
min_cycle_duration |  | Optional | TIMEDELTA type. This will allow protecting devices that request a minimum type of work/rest before changing status. On this, you have to define hours, minutes and/or seconds as son elements.

## SPECIFICITIES
### TARGET TEMPERATURE SENSOR
`target_temp_sensor` is the Home Assistant `entity_id` of a sensor which' state change accordingly a specified temperature profile. This temperature profile should describe the desired temperature for the room each day/hour.
`target_temp_sensor` must have a temperature value (a number with or without decimal) as a state.

Suggestion: use my [`file_restore`][1] custom components.

### ADDITIONAL INFO
The programmed temperature will change accordingly to the one set by the `target_temp_sensor` when in `heat_cool` mode. You can still change it temporarily with the slider. Target temperature will be set, again, to the one of `target_temp_sensor` at its first change.
`heat` and `cool` modes are the manual mode; in this mode, the planning will not be followed.

After a restart of Home Assistant, room temperature and planned room temperature will match till `actual_temp_sensor` will return a temperature value.
This is done to avoid possible issues with Homekit support with a temperature sensor that needs some time to sync with Home Assistant.

### RELATED CLIMATE
This field is used if the climate-to-climate objects are related to each other, for example, if they use the same heater.
Set this field with the `entity_id` with a different climate object and this will prevent the heater/cooler to be turned off by the slavery climate if the master one is active.

For example, I have two climate objects, one for the room and one for the boiler.
The boiler's climate is used to prevent freezing and, if the temperature is lower than the programmed one, the room heater is turned on.
This means that, if the room's heater is on and the boiler's heater is off, the boiler will turn off the heater despite the room climate demands heat.
With this `master_climate` field this unwanted turn-off will not happen.

Note: my suggestion is to set it to both climates that are related to each other.

### HVAC OPTIONS
This parameter allows you to define which mode you want to activate for that climate object. This is a number with a meaning of every single bit. Here below the table.

bit3 - AUTOMATIC | bit2 - MANUAL | bit1 - OFF | RESULT | Meaning
--- | --- | --- | --- | ---
0 | 0 | 0 | 0 | Noting active - USELESS
0 | 0 | 1 | 1 | OFF only
0 | 1 | 0 | 2 | MANUAL only, you will have only `heat` and/or `cool` modes
0 | 1 | 1 | 3 | MANUAL and OFF
1 | 0 | 0 | 4 | AUTOMATIC only, you will have only `heat_cool` modes
1 | 0 | 1 | 5 | AUTOMATIC and OFF
1 | 1 | 0 | 6 | AUTOMATIC and MANUAL
1 | 1 | 1 | 7 | DEAFAULT - Full mode, you will have active all the options.

### HEATERS AND COOLER SPECIFICS
From version 7.6 you will be able to set `heaters` and `coolers` to the same list and you'll get the correct way of work in manual mode.
This means that `heat` and `cool` mode will work correctly with the same list, but `heat_cool` mode will not (otherwise you will not be able to switch the real device between the 2 modes).
My suggestion is to set `hvac_options: 3` to remove the auto mode.

## NOTE
This component has been developed for the bigger project of building a smart thermostat using Home Assistant and way cheaper than the commercial ones.
You can find more info on that [here][3]

***
Everything is available through HACS.

##### CREDITS
Icons made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon"> www.flaticon.com</a>

***
![logo][2]


[1]: https://github.com/custom-components/sensor.file_restore
[2]: https://github.com/MapoDan/home-assistant/blob/master/mapodanlogo.png
[3]: https://github.com/MapoDan/home-assistant
