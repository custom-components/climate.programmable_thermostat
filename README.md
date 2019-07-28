# PROGRAMMABLE THERMOSTAT
This component is a revision of the official Home Assistant component 'Generic Thermostat' in order to have possibility to have target temperature variable according to a sensor state value.

## HOW TO INSTALL
Just copy paste the content of the `climate.programmable_thermostat/custom_components` folder in your `config/custom_components` directory.

As example you will get the '.py' file in the following path: `/config/custom_components/programmable_thermostat/climate.py`.

Note: you can install through HACS.

## EXAMPLE OF SETUP
Here below the example of setup of sensor and parameters to configure.

```yaml
climate:
  - platform: programmable_thermostat
    name: room
    heater: switch.riscaldamento
    cooler: switch.condizionamento
    actual_temp_sensor: sensor.target_temperature
    min_temp: 10
    max_temp: 30
    target_temp_sensor: sensor.program_temperature
    tolerance: 0.3
    
```

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `programmable_thermostat` | *Required* |
name| Programmable Thermostat | Optional |
heater |  | *Conditional* | Switch that will activate/deactivate the heating system. At least one between `heater` and `cooler` has to be defined.
cooler |  | *Conditional* | Switch that will activate/deactivate the cooling system. At least one between `heater` and `cooler` has to be defined.
actual_temp_sensor |  | *Required* | Sensor of actual room temperature.
min_temp | 5 | Optional | Minimum temperature manually selectable.
max_temp | 40 | Optional | Maximum temperature manually selectable.
target_temp_sensor |  | *Required* | Sensor that rapresent the desired temperature for the room. Suggestion: use my [`file_restore`][1] compontent or somthing similar.
tolerance | 0.5 | Optional | Tolerance for turn on and off the switches mode.
initial_hvac_mode | `heat`, `cool`, `off` | Optional | If not set, components will restore old state after restart. I suggest to not use it.

## SPECIFICITIES
### TARGET TEMPERATURE SENSOR
`target_temp_sensor` is the Home Assistant `entity_id` of a sensor which state change accrodingly a specified temperature profile. This temperature profile should described the desired temperature for the room each day/hour.
`target_temp_sensor` must have a temperature value (number with or without decimal) as state.

Suggestion: use my [`file_restore`][1] custom components.

### ADDITIONAL INFO
Programmed temperature will change accordingly to the one set by the `target_temp_sensor`, this will not happen if the mode is set to `heat_cool`. (it is the old `manual` mode that has been removed from the climate component)
In `heat` and `cool` modes you can still change manually the temperature for the room, but in this case the target temperature will be set, again, to the one of `target_temp_sensor` at its first change.

`heat` and `cool` modes rapresent the automatic mode.

After a restart of Home Assistant, room temperature e planned room temperature will match till `actual_temp_sensor` will return a temperature value.
This is done to avoid possible issues with Homekit support with temperature sensor that need some time to sync with Home Assistant.

## NOTE
This component has been developed for the bigger project of building a smart thermostat using Home Assistant and way cheeper then the commercial ones.
You can find more info on that [here][3]

***
Everything is available through HACS.

***
![logo][2]


[1]: https://github.com/MapoDan/home-assistant/tree/master/custom_components/sensor.file_restore
[2]: https://github.com/MapoDan/home-assistant/blob/master/mapodanlogo.png
[3]: https://github.com/MapoDan/home-assistant
