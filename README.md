# PROGRAMMABLE THERMOSTAT
This component is a revision of the official Home Assistant component 'Generic Thermostat' in order to have possibility to have target temperature variable according to a sensor state value.

## HOW TO INSTALL
Just copy paste the content of the `climate.programmable_thermostat/custom_components` folder in your `config/custom_components` directory.

As example you will get the '.py' file in the following path: `/config/custom_components/programmable_thermostat/climate.py`.

Note: This component is uploaded on the custom-components repository. To track its updated you should add the following to your `custom_updater` till I'll figure out how to automatically manage it with `customjson` on HassIO.

```yaml
custom_updater:
  card_urls:
    - https://raw.githubusercontent.com/MapoDan/home-assistant/master/custom_components/custom_components.json
```

## EXAMPLE OF SETUP
Here below the example of setup of sensor and parameters to configure.

```yaml
climate:
  - platfrom: programmable_thermostat
    name: Termostato
    heat_switch: switch.riscaldamento
    actual_temp_sensor: sensor.temperatura_reale
    min_temp: 5
    max_temp: 30
    target_temp_sensor: sensor.temperatura_desiderata
    cold_tolerance: 0.3
    hot_tolerance: 0.3
    initial_operation_mode: heat
    
```

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `programmable_thermostat` | *Required* |
name| Programmable Thermostat | Optional |
heat_switch |  | *Required* | Switch that will activate/deactivate the heating system.
actual_temp_sensor |  | *Required* | Sensor of actual room temperature.
min_temp | 5 | Optional | Minimum temperature manually selectable.
max_temp | 40 | Optional | Maximum temperature manually selectable.
target_temp_sensor |  | *Required* | Sensor that rapresent the desired temperature for the room. Suggestion: use my [`file_restore`][1] compontent or somthing similar.
cold_tolerance | 0.5 | Optional | Tolerance for cooling mode. NOT ACTIVE AT THE MOMENT.
hot_tolerance | 0.5 | Optional | Tolerance for heating mode.
initial_operation_mode | heat, manual, off | Optional | If not set, components will restore old state after restart.

## SPECIFICITIES
### TARGET TEMPERATURE SENSOR
`target_temp_sensor` is the Home Assistant `entity_id` of a sensor which state change accrodingly a specified temperature profile. This temperature profile should described the desired temperature for the room each day/hour.
`target_temp_sensor` must have a temperature value (number with or without decimal) as state.

Suggestion: use my [`file_restore`][1] custom components.

### ADDITIONAL INFO
Programmed temperature will change accordingly to the one set by the `target_temp_sensor`, this will not happen if the mode is set to `manual`.
In `heat` and `cool` (not supported at the moment) modes you can still change manually the temperature for the room, but in this case the target temperature will be set, again, to the one of `target_temp_sensor` at its first change.

`heat` and `cool` (not supported at the moment) modes rapresent the automatic mode. In those modes climate entity state will be `auto`.

After a restart of Home Assistant, room temperature e planned room temperature will match till `actual_temp_sensor` will return a temperature value.
This is done to avoid possible issues with Homekit support with temperature sensor that need some time to sync with Home Assistant.

**`cool` mode is not supported at the moment. It will be in a future release.**

## NOTE
This component has been developed for the bigger project of building a smart thermostat using Home Assistant and way cheeper then the commercial ones.
You can find more info on that [here][3]

***
Due to how `custom_components` are loaded, it could be possible to have a `ModuleNotFoundError` error on first boot after adding this; to resolve it, restart Home-Assistant.

***
![logo][2]


[1]: https://github.com/MapoDan/home-assistant/tree/master/custom_components/sensor.file_restore
[2]: https://github.com/MapoDan/home-assistant/blob/master/mapodanlogo.png
[3]: https://github.com/MapoDan/home-assistant
