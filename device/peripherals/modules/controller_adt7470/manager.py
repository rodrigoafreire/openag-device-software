# Import standard python modules
import time, json

# Import python types
from typing import Optional, Tuple, Dict, Any

# Import peripheral parent class
from device.peripherals.classes.peripheral import manager, modes

# Import manager elements
from device.peripherals.common.adt7470 import driver
from device.peripherals.modules.actuator_pca9633 import exceptions, events


class ControllerADT7470Manager(manager.PeripheralManager):
    """Manages a temperature sensor hub and fan controller driver."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes manager."""

        # Initialize parent class
        super().__init__(*args, **kwargs)

        # Initialize sensors and actuators
        self.sensors = self.parameters.get("sensors", [])
        self.actuators = self.parameters.get("actuators", [])

        # Initialize setpoints
        for actuator in self.actuators:
            control_sensor_id = actuator.get("control_sensor_id")
            if type(control_sensor_id) is int:
                minimum_temperature = actuator.get("minimum_temperature")
                for sensor in self.sensors:
                    sensor_id = sensor.get("sensor_id")
                    if sensor_id == control_sensor_id:
                        variable_name = sensor.get("variable_name")
                        value = "Less Than {}".format(minimum_temperature)
                        self.state.set_peripheral_desired_sensor_value(
                            self.name, variable_name, value
                        )
                        self.state.set_environment_desired_sensor_value(
                            variable_name, value
                        )

        # Set default sampling interval
        self.default_sampling_interval = 3  # seconds
        self.prev_update = 0  # timestamp

    def set_sensor(self, name: str, value: Any) -> None:
        """Sets a sensor value in state."""
        self.state.set_peripheral_reported_sensor_value(self.name, name, value)
        self.state.set_environment_reported_sensor_value(self.name, name, value)

    def set_actuator(self, name: str, value: Any) -> None:
        """Sets an actuator output value in state."""
        self.state.set_peripheral_reported_actuator_value(self.name, name, value)
        self.state.set_environment_reported_actuator_value(name, value)
        # self.state.set_environment_desired_actuator_value(name, value)

    def initialize_peripheral(self) -> None:
        """Initializes manager."""
        self.logger.info("Initializing")

        # Clear reported values
        self.clear_reported_values()

        # Initialize health
        self.health = 100.0

        # TODO: Add simulated bytes
        if self.simulate:
          return

        # Initialize driver
        try:
            self.driver = driver.ADT7470Driver(
                name=self.name,
                i2c_lock=self.i2c_lock,
                bus=self.bus,
                mux=self.mux,
                channel=self.channel,
                address=self.address,
                simulate=self.simulate,
                mux_simulator=self.mux_simulator,
            )
        except exceptions.DriverError as e:
            self.logger.exception("Unable to initialize: {}".format(e))
            self.health = 0.0
            self.mode = modes.ERROR

    def setup_peripheral(self) -> None:
        """Sets up peripheral."""
        self.logger.debug("Setting up peripheral")

        # TODO: Add simulated bytes
        if self.simulate:
          return

        try:
            # Set drive mode
            if len(self.actuators) > 0:
                actuator = self.actuators[0]
                drive_frequency_mode = actuator.get("drive_frequency_mode")
                if drive_frequency_mode == "low":
                    self.driver.enable_low_frequency_fan_drive()
                else:
                    self.driver.enable_high_frequency_fan_drive()

            # Turn on tach enabled fans
            for actuator in self.actuators:
                fan_id = actuator.get("fan_id")
                tachometer_enabled = actuator.get("tachometer_enabled")
                if tachometer_enabled:
                    self.driver.enable_manual_fan_control(fan_id)
                    self.driver.write_current_duty_cycle(fan_id, 100)

            # Enable monitoring
            self.driver.enable_monitoring()

            # Wait 5 seconds for fans to turn on
            time.sleep(5)

            # Verify fans with tachs work
            for actuator in self.actuators:
                fan_id = actuator.get("fan_id")
                tachometer_enabled = actuator.get("tachometer_enabled")
                if tachometer_enabled:
                    fan_speed = self.driver.read_fan_speed(fan_id)
                    self.logger.debug("Fan {}: Speed: {} RPM".format(fan_id, fan_speed))
                    if fan_speed == 0:
                        self.logger.error("Unable to verify fan {} is functional".format(fan_id))
                        self.health = 60.0

            # Set fan modes and limits
            for actuator in self.actuators:

                # Get actuator parameters
                control_sensor_id = actuator.get("control_sensor_id")
                fan_id = actuator.get("fan_id")

                # Setup manual fans
                if control_sensor_id is None:
                    self.driver.enable_manual_fan_control(fan_id)

                # Setup automatic fans
                else:
                    control_sensor_id = actuator.get("control_sensor_id")
                    minimum_temperature = actuator.get("minimum_temperature")
                    minimum_duty_cycle = actuator.get("minimum_duty_cycle")
                    maximum_duty_cycle = actuator.get("maximum_duty_cycle")
                    self.driver.write_thermal_zone_config(fan_id, control_sensor_id)
                    self.driver.write_thermal_zone_minimum_temperature(
                        fan_id, minimum_temperature
                    )
                    self.driver.write_minimum_duty_cycle(fan_id, minimum_duty_cycle)
                    self.driver.write_maximum_duty_cycle(fan_id, maximum_duty_cycle)
                    self.driver.enable_automatic_fan_control(fan_id)

        except exceptions.DriverError as e:
            self.logger.exception("Unable to setup")
            self.mode = modes.ERROR
            self.health = 0.0
            return

    def update_peripheral(self) -> None:
        """Updates peripheral by getting temperatures and fan speeds."""
        
        # TODO: Add simulated bytes
        if self.simulate:
          return
        
        try:
            # Update sensors
            for sensor in self.sensors:
                sensor_id = sensor.get("sensor_id")
                variable_name = sensor.get("variable_name")
                temperature = self.driver.read_temperature(sensor_id, reset_monitor=False)
                self.set_sensor(variable_name, temperature)

            # Update actuators
            health = 100.0
            for actuator in self.actuators:
                fan_id = actuator.get("fan_id")
                duty_cycle_name = actuator.get("duty_cycle_name")
                fan_speed_name = actuator.get("fan_speed_name")
                tachometer_enabled = actuator.get("tachometer_enabled")
                duty_cycle = self.driver.read_current_duty_cycle(fan_id)
                fan_speed = self.driver.read_fan_speed(fan_id)
                self.set_actuator(duty_cycle_name, duty_cycle)
                self.set_actuator(fan_speed_name, fan_speed)
                if tachometer_enabled and duty_cycle > 0 and fan_speed == 0:
                  self.logger.error("Unable to verify fan {} is functional. Duty Cycle: {}, Fan Speed: {}".format(fan_id, duty_cycle, fan_speed))
                  health = 60.0
            self.health = health
        except exceptions.DriverError as e:
            self.logger.exception("Unable to update peripheral: {}".format(e))
            self.mode = modes.ERROR
            self.health = 0.0

    def reset_peripheral(self) -> None:
        """Resets sensor."""
        self.logger.info("Resetting")
        self.clear_reported_values()

    def shutdown_peripheral(self) -> None:
        """Shutsdown peripheral."""
        self.logger.info("Shutting down")
        try:
            self.driver.shutdown()
        except exceptions.DriverError as e:
            message = "Unable to turn off driver before shutting down: {}".format(
                type(e)
            )
            self.logger.warning(message)
        self.clear_reported_values()

    def clear_reported_values(self) -> None:
        """Clears reported values."""
        for sensor in self.sensors:
            variable_name = sensor.get("variable_name")
            self.set_sensor(variable_name, None)
        for actuator in self.actuators:
            duty_cycle_name = actuator.get("duty_cycle_name")
            fan_speed_name = actuator.get("fan_speed_name")
            self.set_actuator(duty_cycle_name, None)
            self.set_actuator(fan_speed_name, None)

