# https://pynative.com/make-python-class-json-serializable/

import json
from json import JSONEncoder

class TelemetryData:
    """
    A class representing telemetry data with various sensor readings.

    """
    
    def __init__(self, timestamp, float_values_tuple: tuple):
        """
        Constructor:
        
        Attributes:
            TIMESTAMP (float): Unix timestamp of when the data was collected.
            BATT_AMP (float): Battery current in amperes.
            BATT_VOLT (float): Battery voltage in volts.
            BOARD_AMP (float): Board current in amperes.
            HYDRO (float): Hydrogen sensor data in %.
            TEMP (float): Temperature sensor data in °C.
            PRESSURE (float): Pressure sensor data in XXX.
            LONGITUDE (float): GPS longitude coordinate.
            LATITUDE (float): GPS latitude coordinate.
        """
        self.TIMESTAMP = timestamp
        self.BATT_AMP = round(float_values_tuple[0], 6)
        self.BATT_VOLT = round(float_values_tuple[1],6)
        self.BOARD_AMP = round(float_values_tuple[2], 6)
        self.HYDRO = round(float_values_tuple[3], 6)
        self.TEMP = round(float_values_tuple[4], 6)
        self.PRESSURE = round(float_values_tuple[5], 6)
        self.LONGITUDE = round(float_values_tuple[6], 6)
        self.LATITUDE = round(float_values_tuple[7], 6)

class TelemetryDataEncoder(JSONEncoder):
    """
    A class for serializing TelemetryData objects.
    """
    def default(self, o):
        """
        Overrides the JSONEncoder method to serialize TelemetryData objects.

        Returns:
            A dictionary of the object's attribute-value pairs.
        """
        return o.__dict__