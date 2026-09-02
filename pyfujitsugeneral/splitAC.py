"""Library interface for Fujitsu General AC."""

import logging
from typing import Any

from pyfujitsugeneral.client import FGLairApiClient
from pyfujitsugeneral.const import (
    CAPABILITY_NOT_AVAILABLE,
    DEVICE_CAPABILITIES,
    Capability,
)
from pyfujitsugeneral.exceptions import (
    FGLairMethodException,
    FGLairMethodOrDirectionOutOfRangeException,
    FGLairOperationModeNoneException,
    FGLairTemperatureOutOfRangeException,
    FGLairVanePositionNotSupportedException,
)

_LOGGER = logging.getLogger(__name__)


def get_prop_from_json(property_name: str, properties: Any) -> dict[str, Any]:
    """Extract property from JSON response with improved error handling.

    Returns:
        dict with 'value' and 'key' keys if property found, empty dict if not found

    """
    if not properties or not isinstance(properties, (list, tuple)):
        _LOGGER.debug(
            "Properties list is empty or invalid for property: %s", property_name
        )
        return {}

    for property_item in properties:
        if not isinstance(property_item, dict):
            _LOGGER.debug("Property item is not a dict for property: %s", property_name)
            continue

        if "property" not in property_item:
            _LOGGER.debug("Property item missing 'property' key for: %s", property_name)
            continue

        if property_item["property"]["name"] == property_name:
            if property_name == "refresh":
                return {
                    "value": property_item["property"]["value"],
                    "key": property_item["property"]["key"],
                    "data_updated_at": property_item["property"]["data_updated_at"],
                }
            return {
                "value": property_item["property"]["value"],
                "key": property_item["property"]["key"],
            }

    _LOGGER.debug("Property '%s' not found in device properties", property_name)
    return {}


class SplitAC:
    def __init__(
        self,
        dsn: str,
        client: FGLairApiClient,
        tokenpath: str,
        temperature_offset: float,
    ) -> None:
        self._dsn = dsn
        self._client = client  # Setting the API object
        self._tokenpath = tokenpath
        self._temperature_offset = temperature_offset
        self.set_properties(None)
        self._device_name: dict[str, str] = {}
        self._device_capability: dict[str, str] = {}
        self._af_vertical_swing: dict[str, bool] = {}
        self._af_vertical_direction: dict[str, int] = {}
        self._af_vertical_num_dir: dict[str, int] = {}
        self._af_horizontal_swing: dict[str, bool] = {}
        self._af_horizontal_direction: dict[str, int] = {}
        self._af_horizontal_num_dir: dict[str, int] = {}
        self._economy_mode: dict[str, bool] = {}
        self._fan_speed: dict[str, int] = {}
        self._powerful_mode: dict[str, bool] = {}
        self._min_heat: dict[str, bool] = {}
        self._outdoor_low_noise: dict[str, bool] = {}
        self._refresh: dict[str, int] = {}
        self._operation_mode: dict[str, int] = {}
        self._adjust_temperature: dict[str, int] = {}
        self._display_temperature: dict[str, int] = {}
        self._outdoor_temperature: dict[str, int] = {}

        # self.properties: For now this variable is not used but lots of device properties which are not implemented
        # this variable can be used to expose those properties and implement them.
        # self.async_update_properties()

    # Method for getting new (refreshing) properties values
    async def async_update_properties(self) -> Any:
        self.set_properties(await self._client.async_get_device_properties(self._dsn))
        self.set_device_name(self.get_properties())
        self.set_device_capability(self.get_properties())
        await self.async_set_af_vertical_swing(self.get_properties())
        await self.async_set_af_vertical_direction(self.get_properties())
        self.set_af_vertical_num_dir(self.get_properties())
        await self.async_set_af_horizontal_swing(self.get_properties())
        await self.async_set_af_horizontal_direction(self.get_properties())
        self.set_af_horizontal_num_dir(self.get_properties())
        await self.async_set_economy_mode(self.get_properties())
        await self.async_set_fan_speed(self.get_properties())
        await self.async_set_powerful_mode(self.get_properties())
        await self.async_set_min_heat(self.get_properties())
        await self.async_set_outdoor_low_noise(self.get_properties())
        await self.async_set_refresh(self.get_properties())
        await self.async_set_operation_mode(self.get_properties())
        await self.async_set_adjust_temperature(self.get_properties())
        await self.async_set_display_temperature(self.get_properties())
        await self.async_set_outdoor_temperature(self.get_properties())
        return self.get_properties()

    # To Turn on the device get the last operation mode using property history method
    # Find the last not 'OFF'/'0' O.M.
    # Turn on by setting O.M. to the last O.M
    async def async_turnOn(self) -> None:
        # Turning on the AC based on the last known operation mode
        datapoints = await self._async_get_device_property_history(
            self.get_operation_mode()["key"]
        )
        last_operation_mode = self._operation_mode_translate("auto")
        for datapoint in reversed(datapoints):
            if datapoint["datapoint"]["value"] != 0:
                last_operation_mode = int(datapoint["datapoint"]["value"])
                break
        await self.async_set_operation_mode(last_operation_mode)
        await self.async_update_properties()

    async def async_turnOff(self) -> None:
        # Turning off the AC
        await self.async_set_operation_mode(0)
        await self.async_update_properties()

    async def async_economy_mode_on(self) -> None:
        # Turning on economy mode
        await self.async_set_economy_mode(1)

    async def async_economy_mode_off(self) -> None:
        # Turning off economy mode
        await self.async_set_economy_mode(0)

    async def async_powerful_mode_on(self) -> None:
        # Turning on powerful mode
        await self.async_set_powerful_mode(1)

    async def async_powerful_mode_off(self) -> None:
        # Turning off powerful mode
        await self.async_set_powerful_mode(0)

    async def async_min_heat_mode_on(self) -> None:
        # Turning on min_heat mode
        await self.async_set_min_heat(1)

    async def async_min_heat_mode_off(self) -> None:
        # Turning off min_heat mode
        await self.async_set_min_heat(0)

    # Fan speed setting
    # Quiet Low Medium High Auto
    async def async_changeFanSpeed(self, speed: str) -> None:
        # Changing the fan speed
        if speed.upper() == "QUIET":
            await self.async_fan_speed_quiet()
        elif speed.upper() == "LOW":
            await self.async_fan_speed_low()
        elif speed.upper() == "MEDIUM":
            await self.async_fan_speed_medium()
        elif speed.upper() == "HIGH":
            await self.async_fan_speed_high()
        elif speed.upper() == "AUTO":
            await self.async_fan_speed_auto()

    async def async_fan_speed_quiet(self) -> None:
        # Setting the fan speed to Quiet
        await self.async_set_fan_speed(0)

    async def async_fan_speed_low(self) -> None:
        # Setting the fan speed to Low
        await self.async_set_fan_speed(1)

    async def async_fan_speed_medium(self) -> None:
        # Setting the fan speed to Medium
        await self.async_set_fan_speed(2)

    async def async_fan_speed_high(self) -> None:
        # Setting the fan speed to High
        await self.async_set_fan_speed(3)

    async def async_fan_speed_auto(self) -> None:
        # Setting the fan speed to Auto
        await self.async_set_fan_speed(4)

    def get_fan_speed_desc(self) -> str:
        """Get the description of the fan speed.

        The supported fan speeds vary from device to device. The available modes are
        read from the Device capability attributes.

        """
        FAN_SPEED_DICT = {0: "Quiet", 1: "Low", 2: "Medium", 3: "High", 4: "Auto"}

        fan_speed = self.get_fan_speed()["value"]
        if fan_speed == 5:
            """For very few AC the resulting value is 5 BUT this value "5" is a not documented value,
            I assume it as the Low value according:
            https://github.com/deiger/AirCon/blob/master/devicetypes/deiger/hisense-air-conditioner.src/hisense-air-conditioner.groovy#L198
            """
            return FAN_SPEED_DICT[1]

        if fan_speed == 7:
            """For very few AC the resulting value is 7 BUT this value "7" is a not documented value,
            I assume it as the High value according:
            https://github.com/deiger/AirCon/blob/master/devicetypes/deiger/hisense-air-conditioner.src/hisense-air-conditioner.groovy#L204
            """
            return FAN_SPEED_DICT[3]

        if fan_speed == 9:
            """For very few AC the resulting value is 9 BUT this value "9" is a not documented value,
            I assume it as the Auto value according:
            https://github.com/deiger/AirCon/blob/master/devicetypes/deiger/hisense-air-conditioner.src/hisense-air-conditioner.groovy#L210
            """
            return FAN_SPEED_DICT[4]

        return FAN_SPEED_DICT[fan_speed]

    def get_swing_modes_supported(self) -> str:
        # Getting supported swing modes
        SWING_DICT = {0: "None", 1: "Vertical", 2: "Horizontal", 3: "Both"}
        key = 0

        vertical_direction = self.get_af_vertical_direction()
        if vertical_direction and vertical_direction.get("value") is not None:
            key = key | 1

        horizontal_direction = self.get_af_horizontal_direction()
        if horizontal_direction and horizontal_direction.get("value") is not None:
            key = key | 2

        return SWING_DICT[key]

    # Vertical
    async def async_vertical_swing_on(self) -> None:
        # Turning on vertical swing
        await self.async_set_af_vertical_swing(1)

    async def async_vertical_swing_off(self) -> None:
        # Turning off vertical swing
        await self.async_set_af_vertical_swing(0)

    def vane_vertical_positions(self) -> list[int]:
        """Get the vertical vane positions as a list of integers."""
        # Safely getting the number of vertical vane positions
        vertical_num_dir = self.get_af_vertical_num_dir()

        # Check if the property is not available (None or empty dict)
        if not vertical_num_dir:
            _LOGGER.debug(
                "Vertical vane positions not available - device may not support"
                " vertical swing"
            )
            return []

        num_positions = vertical_num_dir.get("value")

        if not isinstance(num_positions, int) or num_positions < 0:
            _LOGGER.debug(
                "Invalid or missing 'value' in get_af_vertical_num_dir response: %s -"
                " device may not support vertical swing",
                vertical_num_dir,
            )
            return []

        return list(range(1, num_positions + 1))

    def vane_vertical(self) -> int:
        try:
            # Getting the current vertical vane position
            vertical_direction = self.get_af_vertical_direction()
        except Exception:
            return -1  # Return a default error value

        if isinstance(vertical_direction, dict) and "value" in vertical_direction:
            return vertical_direction["value"]
        # Invalid data format or 'value' key not found
        return -1  # Return a default error

    async def async_set_vane_vertical_position(self, pos: int) -> None:
        # Setting the vertical vane position
        if 1 <= pos <= self.get_af_vertical_num_dir()["value"]:
            await self.async_set_af_vertical_swing(0)
            await self.async_set_af_vertical_direction(pos)
        else:
            raise FGLairVanePositionNotSupportedException

    # Horizontal
    async def async_horizontal_swing_on(self) -> None:
        # Turning on horizontal swing
        await self.async_set_af_horizontal_swing(1)

    async def async_horizontal_swing_off(self) -> None:
        # Turning off horizontal swing
        await self.async_set_af_horizontal_swing(0)

    def capabilities(self) -> dict[str, bool]:
        active_capabilities: dict[str, bool] = {}

        device_state = self.get_device_capability().get("value")

        if not isinstance(device_state, int) or device_state <= 0:
            _LOGGER.error(
                "Invalid or missing 'value' in _device_capability response: %s",
                self._device_capability,
            )
            return active_capabilities

        for capability in Capability:
            # Check if the capability is active in the device state
            if device_state & capability:
                active_capabilities[capability.name] = True
            else:
                active_capabilities[capability.name] = False

        return active_capabilities

    def has_capability(self, capability: Capability) -> bool:
        all_capabilities: dict[str, bool] = self.capabilities()

        return all_capabilities.get(capability.name, False)

    def vane_horizontal_positions(self) -> list[int]:
        """Get the horizontal vane positions as a list of integers."""
        # Safely getting the number of horizontal vane positions
        result = self.get_af_horizontal_num_dir()

        # Check if the property is not available (None or empty dict)
        if not result:
            _LOGGER.debug(
                "Horizontal vane positions not available - device may not support"
                " horizontal swing"
            )
            return []

        value = result.get("value")

        if not isinstance(value, int) or value < 0:
            _LOGGER.debug(
                "Invalid or missing 'value' in get_af_horizontal_num_dir response: %s -"
                " device may not support horizontal swing",
                result,
            )
            return []

        return list(range(1, value + 1))

    def vane_horizontal(self) -> int:
        # Getting the current horizontal vane position
        horizontal_direction = self.get_af_horizontal_direction()
        if horizontal_direction and "value" in horizontal_direction:
            return horizontal_direction["value"]
        return -1  # Return a default error value

    async def async_set_vane_horizontal_position(self, pos: int) -> None:
        # Setting the horizontal vane position
        if 1 <= pos <= self.get_af_horizontal_num_dir()["value"]:
            await self.async_set_af_horizontal_swing(0)
            await self.async_set_af_horizontal_direction(pos)
        else:
            raise FGLairVanePositionNotSupportedException

    # Temperature setting
    async def async_change_temperature(self, new_temperature: int | float) -> None:
        # Set temperature for degree C
        if not isinstance(new_temperature, int) and not isinstance(
            new_temperature, float
        ):
            raise FGLairMethodException

        # Fixing temps if not given as multiplies of 10 less than 160
        if new_temperature < 160:
            new_temperature = int(new_temperature * 10)

        if 160 <= new_temperature <= 320:
            await self.async_set_adjust_temperature(new_temperature)
        else:
            raise FGLairTemperatureOutOfRangeException

    # Operation Mode setting
    async def async_change_operation_mode(
        self, operation_mode: str | int | None
    ) -> None:
        if operation_mode is not None:
            if not isinstance(operation_mode, int):
                operation_mode = self._operation_mode_translate(operation_mode)
            await self.async_set_operation_mode(operation_mode)
        else:
            raise FGLairOperationModeNoneException

    # Class properties:

    def get_dsn(self) -> str:
        return self._dsn

    def get_refresh(self) -> dict[str, int]:
        return self._refresh

    async def async_set_refresh(self, properties: Any) -> None:
        # Sending an asynchronous refresh display_temperature request
        if isinstance(properties, (list, tuple)):
            self._refresh = get_prop_from_json("refresh", properties)
        elif isinstance(properties, int):
            # no update properties process will be invoked after that
            refresh_data = self.get_refresh()
            if refresh_data and "key" in refresh_data:
                await self._client.async_set_device_property(
                    refresh_data["key"], properties
                )
            else:
                _LOGGER.warning("Cannot set refresh property - key not available")
        else:
            raise FGLairMethodException

    def get_operation_mode(self) -> dict[str, int]:
        return self._operation_mode

    def get_operation_mode_desc(self) -> Any:
        operation_mode = self.get_operation_mode()
        if operation_mode and "value" in operation_mode:
            return self._operation_mode_translate(operation_mode["value"])
        return "unknown"

    async def async_set_operation_mode(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._operation_mode = get_prop_from_json("operation_mode", properties)
        elif isinstance(properties, int):
            operation_mode_data = self.get_operation_mode()
            if operation_mode_data and "key" in operation_mode_data:
                await self._client.async_set_device_property(
                    operation_mode_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set operation mode - key not available")
        else:
            raise FGLairMethodException

    # property to get display temperature in degree C
    async def async_get_display_temperature_degree(self) -> float | None:
        if (
            isinstance(self._display_temperature, dict)
            and "value" in self._display_temperature
        ):
            display_temperature_value = self._display_temperature["value"]
            if display_temperature_value == CAPABILITY_NOT_AVAILABLE:
                datapoints = await self._async_get_device_property_history(
                    self._display_temperature["key"]
                )
                # Get the latest setting other than invalid value
                for datapoint in reversed(datapoints):
                    if datapoint["datapoint"]["value"] != CAPABILITY_NOT_AVAILABLE:
                        display_temperature_value = int(datapoint["datapoint"]["value"])
                        break
            data = round((display_temperature_value - 5000) / 100, 1)
            return data - self._temperature_offset
        return None

    # property returns display temperature dict in 10 times of degree C
    def get_display_temperature(self) -> dict[str, int]:
        return self._display_temperature

    async def async_set_display_temperature(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._display_temperature = get_prop_from_json(
                "display_temperature", properties
            )
        elif isinstance(properties, float | int):
            display_temp_data = self.get_display_temperature()
            if display_temp_data and "key" in display_temp_data:
                await self._client.async_set_device_property(
                    display_temp_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set display temperature - key not available")
        else:
            raise FGLairMethodException

    # property to get outdoor temperature in degree C
    def get_outdoor_temperature_degree(self) -> float | None:
        data = None
        if self._outdoor_temperature is not None:
            data = round((self._outdoor_temperature["value"] - 5000) / 100, 1)
        return data

    # property returns outdoor temperature dict in 10 times of degree C
    def get_outdoor_temperature(self) -> dict[str, int]:
        return self._outdoor_temperature

    async def async_set_outdoor_temperature(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._outdoor_temperature = get_prop_from_json(
                "outdoor_temperature", properties
            )
        elif isinstance(properties, float | int):
            outdoor_temp_data = self.get_outdoor_temperature()
            if outdoor_temp_data and "key" in outdoor_temp_data:
                await self._client.async_set_device_property(
                    outdoor_temp_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set outdoor temperature - key not available")
        else:
            raise FGLairMethodException

    # property to get temperature in degree C
    async def async_get_adjust_temperature_degree(self) -> float | None:
        if self._adjust_temperature is None:
            return None

        adjust_temperature_value: int = self._adjust_temperature["value"]

        if adjust_temperature_value == CAPABILITY_NOT_AVAILABLE:
            datapoints = await self._async_get_device_property_history(
                self._adjust_temperature["key"]
            )

            # Get the latest setting other than invalid value
            for datapoint in reversed(datapoints):
                value = int(datapoint["datapoint"]["value"])
                if value != CAPABILITY_NOT_AVAILABLE:
                    adjust_temperature_value = value
                    break
            else:
                return None

        return round(adjust_temperature_value / 10, 1)

    # property returns temperature dict in 10 times of degree C
    def get_adjust_temperature(self) -> dict[str, int]:
        return self._adjust_temperature

    async def async_set_adjust_temperature(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._adjust_temperature = get_prop_from_json(
                "adjust_temperature", properties
            )
        elif isinstance(properties, float | int):
            adjust_temp_data = self.get_adjust_temperature()
            if adjust_temp_data and "key" in adjust_temp_data:
                await self._client.async_set_device_property(
                    adjust_temp_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set adjust temperature - key not available")
        else:
            raise FGLairMethodException

    def get_outdoor_low_noise(self) -> dict[str, bool]:
        return self._outdoor_low_noise

    async def async_set_outdoor_low_noise(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._outdoor_low_noise = get_prop_from_json(
                "outdoor_low_noise", properties
            )
        elif isinstance(properties, int):
            outdoor_low_noise_data = self.get_outdoor_low_noise()
            if outdoor_low_noise_data and "key" in outdoor_low_noise_data:
                await self._client.async_set_device_property(
                    outdoor_low_noise_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set outdoor low noise - key not available")
        else:
            raise FGLairMethodException

    def get_powerful_mode(self) -> dict[str, bool]:
        return self._powerful_mode

    async def async_set_powerful_mode(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._powerful_mode = get_prop_from_json("powerful_mode", properties)
        elif isinstance(properties, int):
            powerful_mode_data = self.get_powerful_mode()
            if powerful_mode_data and "key" in powerful_mode_data:
                await self._client.async_set_device_property(
                    powerful_mode_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set powerful mode - key not available")
        else:
            raise FGLairMethodException

    def get_properties(self) -> Any:
        return self._properties

    def set_properties(self, properties: Any) -> None:
        self._properties = properties

    def get_fan_speed(self) -> dict[str, int]:
        return self._fan_speed

    async def async_set_fan_speed(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._fan_speed = get_prop_from_json("fan_speed", properties)
        elif isinstance(properties, int):
            fan_speed_data = self.get_fan_speed()
            if fan_speed_data and "key" in fan_speed_data:
                await self._client.async_set_device_property(
                    fan_speed_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set fan speed - key not available")
        else:
            raise FGLairMethodException

    def get_min_heat(self) -> dict[str, bool]:
        return self._min_heat

    async def async_set_min_heat(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._min_heat = get_prop_from_json("min_heat", properties)
        elif isinstance(properties, int):
            min_heat_data = self.get_min_heat()
            if min_heat_data and "key" in min_heat_data:
                await self._client.async_set_device_property(
                    min_heat_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set min heat - key not available")
        else:
            raise FGLairMethodException

    def get_economy_mode(self) -> dict[str, bool]:
        return self._economy_mode

    async def async_set_economy_mode(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._economy_mode = get_prop_from_json("economy_mode", properties)
        elif isinstance(properties, int):
            economy_mode_data = self.get_economy_mode()
            if economy_mode_data and "key" in economy_mode_data:
                await self._client.async_set_device_property(
                    economy_mode_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set economy mode - key not available")
        else:
            raise FGLairMethodException

    def get_af_horizontal_num_dir(self) -> dict[str, int]:
        return self._af_horizontal_num_dir

    def set_af_horizontal_num_dir(self, properties: Any) -> None:
        self._af_horizontal_num_dir = get_prop_from_json(
            "af_horizontal_num_dir", properties
        )

    def get_af_horizontal_direction(self) -> dict[str, int]:
        return self._af_horizontal_direction

    async def async_set_af_horizontal_direction(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._af_horizontal_direction = get_prop_from_json(
                "af_horizontal_direction", properties
            )
        elif isinstance(properties, int):
            horizontal_direction_data = self.get_af_horizontal_direction()
            if horizontal_direction_data and "key" in horizontal_direction_data:
                await self._client.async_set_device_property(
                    horizontal_direction_data["key"], properties
                )
                await (
                    self.async_horizontal_swing_off()
                )  # If direction set then swing will be turned OFF
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set horizontal direction - key not available")
        else:
            raise FGLairMethodOrDirectionOutOfRangeException

    def get_af_horizontal_swing(self) -> dict[str, bool]:
        return self._af_horizontal_swing

    async def async_set_af_horizontal_swing(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._af_horizontal_swing = get_prop_from_json(
                "af_horizontal_swing", properties
            )
        elif isinstance(properties, int):
            horizontal_swing_data = self.get_af_horizontal_swing()
            if horizontal_swing_data and "key" in horizontal_swing_data:
                await self._client.async_set_device_property(
                    horizontal_swing_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set horizontal swing - key not available")
        else:
            raise FGLairMethodException

    def get_af_vertical_num_dir(self) -> dict[str, int]:
        return self._af_vertical_num_dir

    def set_af_vertical_num_dir(self, properties: Any) -> None:
        self._af_vertical_num_dir = get_prop_from_json(
            "af_vertical_num_dir", properties
        )

    def get_af_vertical_direction(self) -> dict[str, int]:
        return self._af_vertical_direction

    async def async_set_af_vertical_direction(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._af_vertical_direction = get_prop_from_json(
                "af_vertical_direction", properties
            )
        elif isinstance(properties, int):
            vertical_direction_data = self.get_af_vertical_direction()
            if vertical_direction_data and "key" in vertical_direction_data:
                await self._client.async_set_device_property(
                    vertical_direction_data["key"], properties
                )
                await (
                    self.async_vertical_swing_off()
                )  ##If direction set then swing will be turned OFF
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set vertical direction - key not available")
        else:
            raise FGLairMethodOrDirectionOutOfRangeException

    def get_af_vertical_swing(self) -> dict[str, bool]:
        return self._af_vertical_swing

    async def async_set_af_vertical_swing(self, properties: Any) -> None:
        if isinstance(properties, (list, tuple)):
            self._af_vertical_swing = get_prop_from_json(
                "af_vertical_swing", properties
            )
        elif isinstance(properties, int):
            vertical_swing_data = self.get_af_vertical_swing()
            if vertical_swing_data and "key" in vertical_swing_data:
                await self._client.async_set_device_property(
                    vertical_swing_data["key"], properties
                )
                await self.async_update_properties()
            else:
                _LOGGER.warning("Cannot set vertical swing - key not available")
        else:
            raise FGLairMethodException

    def get_device_name(self) -> dict[str, str]:
        return self._device_name

    def set_device_name(self, properties: Any) -> None:
        self._device_name = get_prop_from_json("device_name", properties)

    def get_op_status(self) -> dict[str, int]:
        return get_prop_from_json("op_status", self.get_properties())

    def get_op_status_desc(self) -> str | None:
        data = None
        op_status = self.get_op_status()
        if op_status and op_status.get("value") is not None:
            DICT_OP_MODE = {0: "Normal", 16777216: "Defrost"}
            status = op_status["value"]
            data = DICT_OP_MODE.get(status, f"Unknown {status}")
            return data
        return data

    def set_device_capability(self, properties: Any) -> None:
        self._device_capability = get_prop_from_json(DEVICE_CAPABILITIES, properties)

    def get_device_capability(self) -> dict[str, str]:
        return self._device_capability

    # Get a property history
    async def _async_get_device_property_history(self, property_code: int) -> Any:
        property_history = await self._client.async_get_device_property(property_code)
        return property_history

    # Translate the operation mode to descriptive values and reverse
    def _operation_mode_translate(self, operation_mode: str | int) -> Any:
        DICT_OPERATION_MODE = {
            "off": 0,
            "unknown": 1,
            "auto": 2,
            "cool": 3,
            "dry": 4,
            "fan_only": 5,
            "heat": 6,
            0: "off",
            1: "unknown",
            2: "auto",
            3: "cool",
            4: "dry",
            5: "fan_only",
            6: "heat",
        }
        return DICT_OPERATION_MODE[operation_mode]

    # Helper methods for Home Assistant integration
    def get_swing_vertical_value(self) -> bool | None:
        """Get vertical swing value directly for HA integration."""
        data = self.get_af_vertical_swing()
        return data.get("value") if data else None

    def get_swing_horizontal_value(self) -> bool | None:
        """Get horizontal swing value directly for HA integration."""
        data = self.get_af_horizontal_swing()
        return data.get("value") if data else None

    def get_swing_vertical_num_dir_value(self) -> int | None:
        """Get vertical swing number of directions value directly for HA integration."""
        data = self.get_af_vertical_num_dir()
        return data.get("value") if data else None

    def get_swing_horizontal_num_dir_value(self) -> int | None:
        """Get horizontal swing number of directions value directly for HA integration."""
        data = self.get_af_horizontal_num_dir()
        return data.get("value") if data else None

    # Helper methods for preset modes (Home Assistant integration)
    def get_economy_mode_value(self) -> bool | None:
        """Get economy mode value directly for HA integration."""
        data = self.get_economy_mode()
        return data.get("value") if data else None

    def get_powerful_mode_value(self) -> bool | None:
        """Get powerful mode value directly for HA integration."""
        data = self.get_powerful_mode()
        return data.get("value") if data else None

    def get_min_heat_value(self) -> bool | None:
        """Get min heat mode value directly for HA integration."""
        data = self.get_min_heat()
        return data.get("value") if data else None
