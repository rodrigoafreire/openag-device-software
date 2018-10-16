# Import standard python modules
import time, json

# Import python types
from typing import Optional, List, Dict, Any, Tuple

# Import device utilities
from device.utilities.modes import Modes

# Import peripheral event mixin
from device.peripherals.classes.peripheral.events import PeripheralEvents

# Import peripheral utilities
from device.peripherals.utilities import light

# Import driver exceptions
from device.peripherals.classes.peripheral.exceptions import DriverError

# Initialze vars
TURN_ON_EVENT = "Turn On"
TURN_OFF_EVENT = "Turn Off"
SET_CHANNEL_EVENT = "Set Channel"
FADE_EVENT = "Fade"
SUNRISE_EVENT = "Sunrise"
ORBIT_EVENT = "Orbit"


class LEDDAC5578Events(PeripheralEvents):  # type: ignore
    """Peripheral event handler."""

    # Initialize var types
    mode: str
    request: Optional[Dict[str, Any]]

    def create_peripheral_specific_event(
        self, request: Dict[str, Any]
    ) -> Tuple[str, int]:
        """Processes peripheral specific event."""
        if request["type"] == TURN_ON_EVENT:
            return self.turn_on()
        elif request["type"] == TURN_OFF_EVENT:
            return self.turn_off()
        elif request["type"] == SET_CHANNEL_EVENT:
            return self.set_channel(request)
        elif request["type"] == FADE_EVENT:
            return self.fade()
        elif request["type"] == SUNRISE_EVENT:
            return self.sunrise()
        elif request["type"] == ORBIT_EVENT:
            return self.orbit()
        else:
            return "Unknown event request type", 400

    def check_peripheral_specific_events(self, request: Dict[str, Any]) -> None:
        """Checks peripheral specific events."""
        if request["type"] == TURN_ON_EVENT:
            self._turn_on()
        elif request["type"] == TURN_OFF_EVENT:
            self._turn_off()
        elif request["type"] == SET_CHANNEL_EVENT:
            self._set_channel(request)
        elif request["type"] == FADE_EVENT:
            self._fade()
        elif request["type"] == SUNRISE_EVENT:
            self._sunrise()
        elif request["type"] == ORBIT_EVENT:
            self._orbit()
        else:
            message = "Invalid event request type in queue: {}".format(request["type"])
            self.logger.error(message)

    def turn_on(self) -> Tuple[str, int]:
        """Pre-processes turn on event request."""
        self.logger.debug("Pre-processing turn on event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            return "Must be in manual mode", 400

        # Add event request to event queue
        request = {"type": TURN_ON_EVENT}
        self.queue.put(request)

        # Successfully turned on
        return "Turning on", 200

    def _turn_on(self) -> None:
        """Processes turn on event request."""
        self.logger.debug("Processing turn on event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical("Tried to turn on from {} mode".format(self.mode))

        # Turn on driver and update reported variables
        try:
            self.manager.channel_setpoints = self.manager.driver.turn_on()
            self.manager.update_reported_variables()
        except DriverError as e:
            self.mode = Modes.ERROR
            message = "Unable to turn on: {}".format(e)
            self.logger.debug(message)
        except:
            self.mode = Modes.ERROR
            message = "Unable to turn on, unhandled exception"
            self.logger.exception(message)

    def turn_off(self) -> Tuple[str, int]:
        """Pre-processes turn off event request."""
        self.logger.debug("Pre-processing turn off event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            return "Must be in manual mode", 400

        # Add event request to event queue
        request = {"type": TURN_OFF_EVENT}
        self.queue.put(request)

        # Successfully turned off
        return "Turning off", 200

    def _turn_off(self) -> None:
        """Processes turn off event request."""
        self.logger.debug("Processing turn off event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical("Tried to turn off from {} mode".format(self.mode))

        # Turn off driver and update reported variables
        try:
            self.manager.channel_setpoints = self.manager.driver.turn_off()
            self.manager.update_reported_variables()
        except DriverError as e:
            self.mode = Modes.ERROR
            message = "Unable to turn off: {}".format(e)
            self.logger.debug(message)
        except:
            self.mode = Modes.ERROR
            message = "Unable to turn off, unhandled exception"
            self.logger.exception(message)

    def set_channel(self, request: Dict[str, Any]) -> Tuple[str, int]:
        """Pre-processes set channel event request."""
        self.logger.debug("Pre-processing set channel event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            message = "Must be in manual mode"
            self.logger.debug(message)
            return message, 400

        # Get request parameters
        try:
            response = request["value"].split(",")
            channel = str(response[0])
            percent = float(response[1])
        except KeyError as e:
            message = "Unable to set channel, invalid request parameter: {}".format(e)
            self.logger.debug(message)
            return message, 400
        except ValueError as e:
            message = "Unable to set channel, {}".format(e)
            self.logger.debug(message)
            return message, 400
        except:
            message = "Unable to set channel, unhandled exception"
            self.logger.exception(message)
            return message, 500

        # Verify channel name
        if channel not in self.manager.channel_names:
            message = "Invalid channel name: {}".format(channel)
            self.logger.debug(message)
            return message, 400

        # Verify percent
        if percent < 0 or percent > 100:
            message = "Unable to set channel, invalid intensity: {:.0F}%".format(
                percent
            )
            self.logger.debug(message)
            return message, 400

        # Add event request to event queue
        request = {"type": SET_CHANNEL_EVENT, "channel": channel, "percent": percent}
        self.queue.put(request)

        # Return response
        return "Setting {} to {:.0F}%".format(channel, percent), 200

    def _set_channel(self, request: Dict[str, Any]) -> None:
        """Processes set channel event request."""
        self.logger.debug("Processing set channel event")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical("Tried to set channel from {} mode".format(self.mode))

        # Get channel and percent
        channel = request.get("channel")
        percent = float(request.get("percent"))  # type: ignore

        # Set channel and update reported variables
        try:
            self.manager.driver.set_output(channel, percent)
            self.manager.channel_setpoints[channel] = percent
            self.manager.update_reported_variables()
        except DriverError as e:
            self.mode = Modes.ERROR
            message = "Unable to set channel: {}".format(e)
            self.logger.debug(message)
        except:
            self.mode = Modes.ERROR
            message = "Unable to set channel, unhandled exception"
            self.logger.exception(message)

    def fade(self) -> Tuple[str, int]:
        """Pre-processes fade event request."""
        self.logger.debug("Pre-processing fade event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            return "Must be in manual mode", 400

        # Add event request to event queue
        request = {"type": FADE_EVENT}
        self.queue.put(request)

        # Return not implemented yet
        return "Fading", 200

    def _fade(self, channel_name: Optional[str] = None) -> None:
        """Processes fade event request."""
        self.logger.debug("Fading")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical("Tried to fade from {} mode".format(self.mode))

        # Turn off channels
        try:
            self.manager.driver.turn_off()
        except Exception as e:
            self.logger.exception("Unable to fade driver")
            return

        # Set channel or channels
        if channel_name != None:
            channel_names = [channel_name]
        else:
            channel_outputs = self.manager.driver.build_channel_outputs(0)
            channel_names = channel_outputs.keys()

        # Loop forever
        while True:

            # Loop through all channels
            for channel_name in channel_names:

                # Fade up at exp(1.6)
                steps = [
                    0,
                    1,
                    3,
                    5,
                    9,
                    13,
                    17,
                    22,
                    27,
                    33,
                    39,
                    46,
                    53,
                    60,
                    68,
                    76,
                    84,
                    93,
                    100,
                ]
                for step in steps:

                    # Set driver output
                    self.logger.info("Channel {}: {}%".format(channel_name, step))
                    try:
                        self.manager.driver.set_output(channel_name, step)
                    except Exception as e:
                        self.logger.exception("Unable to fade driver")
                        return

                    # Check for events
                    if not self.queue.empty():
                        return

                # Update every 1ms
                time.sleep(0.001)

                # Fade down at exp(1.6)
                steps = [
                    100,
                    93,
                    84,
                    76,
                    68,
                    60,
                    53,
                    46,
                    39,
                    33,
                    27,
                    22,
                    17,
                    13,
                    9,
                    5,
                    3,
                    1,
                    0,
                ]
                for step in steps:

                    # Set driver output
                    self.logger.info("Channel {}: {}%".format(channel_name, step))
                    try:
                        self.manager.driver.set_output(channel_name, step)
                    except Exception as e:
                        self.logger.exception("Unable to fade driver")
                        return

                    # Check for events
                    if not self.queue.empty():
                        return

                # Update every 1ms
                time.sleep(0.001)

    def sunrise(self) -> Tuple[str, int]:
        """Pre-processes sunrise event request."""
        self.logger.debug("Pre-processing sunrise event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            return "Must be in manual mode", 400

        # Get channel names from config
        channel_outputs = self.manager.driver.build_channel_outputs(0)
        channel_names = channel_outputs.keys()

        # Check required channels exist in config
        required_channel_names = ["R", "FR", "WW", "CW", "G", "B"]
        for channel_name in required_channel_names:
            if channel_name not in channel_names:
                message = "Config must have channel named: {}".format(channel_name)
                return message, 500

        # Add event request to event queue
        request = {"type": SUNRISE_EVENT}
        self.queue.put(request)

        # Return not implemented yet
        return "Starting sunrise demo", 200

    def _sunrise(self) -> None:
        """Processes sunrise event request."""
        self.logger.debug("Starting sunrise demo")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical(
                "Tried to start sunrise demo from {} mode".format(self.mode)
            )

        # Turn off channels
        try:
            self.manager.driver.turn_off()
        except Exception as e:
            self.logger.exception("Unable to run sunrise demo driver")
            return

        # Initialize sunrise properties
        delay_fast = 0.001
        pause = 0.5
        steps_delta_slow = 1
        steps_delta_fast = 10
        steps_min = 0
        steps_max = 100
        channel_lists = [["FR"], ["R"], ["WW"], ["CW"]]

        # Loop forever
        while True:

            # Simulate sunrise
            for channel_list in channel_lists:

                # Set step delta
                if len(channel_list) == 1:
                    step_delta = steps_delta_slow
                else:
                    step_delta = steps_delta_dast

                # Run through all channels in list
                for channel in channel_list:

                    # Run through all steps
                    step = steps_min
                    while step <= steps_max:

                        # Set output on driver
                        message = "Setting channel {} to {}%".format(channel, step)
                        self.logger.debug(message)
                        try:
                            self.manager.driver.set_output(channel, step)
                        except Exception as e:
                            message = "Unable to set output, unhandled exception: {}".format(
                                type(e)
                            )
                            self.logger.exception(message)

                        # Increment step
                        step += step_delta

                        # Check for events
                        if not self.queue.empty():
                            return

                        # Wait delay time
                        time.sleep(delay_fast)

                    # Set step max
                    try:
                        self.manager.driver.set_output(channel, steps_max)
                    except Exception as e:
                        message = "Unable to set output, unhandled exception: {}".format(
                            type(e)
                        )
                        self.logger.exception(message)

            # Simulate noon
            time.sleep(pause)

            # Check for events
            if not self.queue.empty():
                return

            # Simulate sunset
            for channel_list in reversed(channel_lists):

                # Set step delta
                if len(channel_list) == 1:
                    step_delta = steps_delta_slow
                else:
                    step_delta = steps_delta_dast

                # Run through all channels in list
                for channel in channel_list:

                    # Run through all steps
                    step = steps_max
                    while step >= steps_min:

                        # Set output on driver
                        message = "Setting channel {} to {}%".format(channel, step)
                        self.logger.debug(message)
                        try:
                            self.manager.driver.set_output(channel, step)
                        except Exception as e:
                            message = "Unable to set output, unhandled exception: {}".format(
                                type(e)
                            )
                            self.logger.exception(message)

                        # Decrement step
                        step -= step_delta

                        # Check for events
                        if not self.queue.empty():
                            return

                        # Wait delay time
                        time.sleep(delay_fast)

                    # Set step min
                    try:
                        self.manager.driver.set_output(channel, steps_min)
                    except Exception as e:
                        message = "Unable to set output, unhandled exception: {}".format(
                            type(e)
                        )
                        self.logger.exception(message)

            # Simulate mignight
            time.sleep(pause)

            # Check for events
            if not self.queue.empty():
                return

    def orbit(self) -> Tuple[str, int]:
        """Pre-processes orbit event request."""
        self.logger.debug("Pre-processing orbit event request")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            return "Must be in manual mode", 400

        # Get channel names from config
        channel_outputs = self.manager.driver.build_channel_outputs(0)
        channel_names = channel_outputs.keys()

        # Check required channels exist in config
        required_channel_names = ["R", "FR", "WW", "CW", "G", "B"]
        for channel_name in required_channel_names:
            if channel_name not in channel_names:
                message = "Config must have channel named: {}".format(channel_name)
                return message, 500

        # Add event request to event queue
        request = {"type": ORBIT_EVENT}
        self.queue.put(request)

        # Return not implemented yet
        return "Starting orbit demo", 200

    def _orbit(self) -> None:
        """Processes sunrise event request."""
        self.logger.debug("Starting orbit demo")

        # Require mode to be in manual
        if self.mode != Modes.MANUAL:
            self.logger.critical(
                "Tried to start orbit demo from {} mode".format(self.mode)
            )

        # Turn off channels
        try:
            self.manager.driver.turn_off()
        except Exception as e:
            self.logger.exception("Unable to run orbit demo")
            return

        # Set channel or channels
        channel_outputs = self.manager.driver.build_channel_outputs(0)
        channel_names = channel_outputs.keys()

        # Loop forever
        while True:

            # Check for events
            if not self.queue.empty():
                return

            # Loop through each panel
            for panel in self.manager.driver.panels:

                # Turn on red channel
                par_setpoint = 100
                channel_name = "R"
                try:
                    self.logger.debug("Setting panel {} red".format(panel.name))
                    channel_number = self.manager.driver.get_channel_number(
                        channel_name
                    )
                    dac_setpoint = self.manager.driver.translate_setpoint(par_setpoint)
                    panel.driver.write_output(channel_number, dac_setpoint)
                except:
                    self.logger.exception("Unable to run orbit demo")
                    return

                # Check for events
                if not self.queue.empty():
                    return

                # Update every 0.5
                time.sleep(0.5)
