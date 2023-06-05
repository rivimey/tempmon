# SPDX-FileCopyrightText: 2018 Limor Fried for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_am2320`
====================================================

This is a CircuitPython driver for the AM2320 temperature and humidity sensor.

* Author(s): Limor Fried

Implementation Notes
--------------------

**Hardware:**

* Adafruit `AM2320 Temperature & Humidity Sensor
  <https://www.adafruit.com/product/3721>`_ (Product ID: 3721)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

"""

# imports
import struct
import time

from adafruit_bus_device.i2c_device import I2CDevice
from micropython import const

try:
    # Used only for typing
    import typing  # pylint: disable=unused-import
    from busio import I2C
except ImportError:
    pass

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_am2320.git"


AM2320_DEFAULT_ADDR = const(0x5C) # Docs mention 0xB8: that val includes r/w bit

AM2320_CMD_READREG = const(0x03)
AM2320_CMD_WRITEREG = const(0x10) # Very little point in writes...

AM2320_DEVSETUP_T = const(0.1)    # Time to wait to try again if initial
                                  # i2c connect fails.
AM2320_DEVWAKE_T = const(0.003)   # After wakeup request, max time before
                                  # sending a cmd is 3ms (min 800us)
AM2320_DEVREAD_T = const(0.0015)  # After read reg request, time to wait 1.5ms

AM2320_DEVHIBER_T = const(2000)   # Millisecs after which we assume dev
                                  # has hibernated.
AM2320_CACHE_EXP_T = const(1992)  # Default millisecs after which T, H cache
                                  # has expired. Change with am.expiry = val.
                                  # Device sleeps for ~2s after measurements.

AM2320_REG_HUM_H = const(0x0)     # 2 bytes
AM2320_REG_TEMP_H = const(0x2)    # 2 bytes
# Regs 4,5,6,7 are unused
AM2320_REG_MODEL_H = const(0x8)   # 2 bytes
AM2320_REG_VERSION = const(0xA)   # One byte
AM2320_REG_DEVID_H = const(0xB)   # 4 bytes
AM2320_REG_STATUS = const(0xF)    # One byte, all bits 'reserved'

# Regs 0x10 to 0x13 are 'user' regs 'a' and '2', r/w
# Status register 0xF can be written to but only on its own.
# Regs 0x14 to 0x1F are unused

# Return error code:
#   0x80: not support function code
#   0x81: Read an illegal address
#   0x82: write data beyond the scope
#   0x83: CRC checksum error
#   0x84: Write disabled

def _crc16(data: bytearray) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


class AM2320Cached:
    """A driver for the AM2320 temperature and humidity sensor.

    This driver includes a one place register cache to speed up transfer
    of temperature and humidity data when reading both at once. It also
    includes properties to read device id and model info.

    :param ~busio.I2C i2c_bus: The I2C bus the AM2320 is connected to.
                               This is the only required parameter.
    :param int address: (optional) The I2C address of the device. Defaults to :const:`0x5C`

    **Quickstart: Importing and using the AM2320Cached**

        Here is an example of using the :class:`AM2320Cached` class.
        First you will need to import the libraries to use the sensor

        .. code-block:: python

            import board
            import adafruit_am2320_ext

        Once this is done you can define your `board.I2C` object and define your sensor object

        .. code-block:: python

            i2c = board.I2C()   # uses board.SCL and board.SDA
            am = adafruit_am2320_ext.AM2320Cached(i2c)

        Now you have access to the temperature using :attr:`temperature` attribute and
        the relative humidity using the :attr:`relative_humidity` attribute

        .. code-block:: python

            temperature = am.temperature
            relative_humidity = am.relative_humidity

    """


    def __init__(self, i2c_bus: I2C, address: int = AM2320_DEFAULT_ADDR):

        self._regbuffer = None
        self._lastread_time = self._lastwrite_time = time.monotonic_ms()
        self._expires = AM2320_CACHE_EXP_T # millisecs

        for _ in range(3):
            # retry since we have to wake up the devices
            try:
                self._i2c = I2CDevice(i2c_bus, address)
                return
            except ValueError:
                pass
            time.sleep(AM2320_DEVSETUP_T)
        raise ValueError("AM2320 not found")

    @expiry.setter
    def expiry(self, val):
        """
        Set the expiry time in milliseconds since the last T+H read.

        Device minimum interval btw reads is 2s, so set expiry just
        below that time.
        """
        if val > 1950:
            self._expires = val
        else:
            raise RuntimeError("expiry too short")

    @property
    def expiry(self):
        """
        The expiry time in milliseconds since the last read.
        """
        return self._expires

    def reset_cache(self):
        """
        Delete the cache, so forcing a re-read of the device.
        """
        self._regbuffer = None

    def _read(self, register: int) -> bytearray:
        """
        Read temp and humidity registers with a 1ms (default) duration cache.

        Reading the device hardware takes several milliseconds, so if we
        last read it very recently ago we're going to get a result faster
        by using the last value read. This is mostly of value when reading
        both temp & humidity in the same cycle.

        The downside of this is that we always read all 4 bytes, so taking
        slightly longer c.f. a one value 2 byte read.  At 100KHz, 2 bytes
        extra is approx 180us extra. However, if you always do two distinct
        2 byte reads, overheads mean at least 50 times the wait, and maybe
        200x if the device has gone back to sleep (3s after last comms).
        """
        if register != AM2320_REG_TEMP_H and register != AM2320_REG_HUM_H:
            # This fn can only read temp & humidity & only as BE int16.
            raise RuntimeError("am2320 read reg error")

        now = time.monotonic_ms()
        if self._regbuffer is None or (now - self.lastread_time) > self._expires:
            # HUM is 0, TEMP is 2, so read HUM..HUM+4 reads both.
            self._regbuffer = self._read_register(AM2320_REG_HUM_H, 4)
            self._lastread_time = time.monotonic_ms()

            # Device auto-sleeps after reading temp/hum. so will need
            # wake procedure to restart it.
            self._lastwrite_time = now - AM2320_DEVHIBER_T

        return self._regbuffer[register:register+2]


    def _read_register(self, register: int, length: int) -> bytearray:
        """
        Read registers from the AM2320 from the start reg for length bytes.
        Returns a bytearray of the values.
        """
	    if length > 10 or register > 0x10:
            raise RuntimeError("am2320 read reg error")

        with self._i2c as i2c:
            now = time.monotonic_ms()
            # Will dev have gone back to sleep yet?
            if (now - self._lastwrite_time) > AM2320_DEVHIBER_T:     # 1s
                # wake up sensor
                awoken = False
                while not awoken:
                    try:
                        i2c.write(bytes([0x00]))
                        time.sleep(AM2320_DEVWAKE_T)  # wait ~10 ms to wake
                        awoken = True
                    except OSError:
                        pass

            # Send command to read register
            cmd = [AM2320_CMD_READREG, register & 0x1F, length]
            # print("readreg cmd: %s" % [hex(i) for i in cmd])
            i2c.write(bytes(cmd))
            time.sleep(AM2320_DEVREAD_T)  # wait for reply
            result = bytearray(length + 4)  # 2 bytes pre, 2 bytes crc
            i2c.readinto(result)

            self._lastwrite_time = time.monotonic_ms()

            # print("> r%d => %s" % (register, [hex(i) for i in result]))
            # Check preamble indicates correct readings
            if result[0] != 0x3 or result[1] != length:
                #print("I2C read failure")
                raise RuntimeError("am2320 readreg failure")
            # Check CRC on all but last 2 bytes
            crc1 = struct.unpack("<H", bytes(result[-2:]))[0]
            crc2 = _crc16(result[0:-2])
            if crc1 != crc2:
                raise RuntimeError("am2320 CRC 0x%04X != 0x%04X" % (crc1, crc2))
            # Return bytes from 2 from start up to 2 from end.
            return result[2:-2]

    @property
    def temperature(self) -> float:
        """The measured temperature in Celsius."""
        regval = self._read(AM2320_REG_TEMP_H)
        # Unpack big-endian (hi then lo) bytes as _unsigned_ 16bit int
        temp_i = struct.unpack(">H", regval)[0]
        # print("temp: %d x256 + %d => %d => " % (regval[0], regval[1], temp_i))
        if temp_i >= 32768:
            # One's complement negation (bit 15 is sign, remaining bits value).
            # 32768 is '-0', 32769 is -1, 32770 is -2, 32778 is -10, etc
            temp_i = 32768 - temp_i
        temp_f = temp_i / 10.0
        # print("temp: %f" % (temp_f))
        return temp_f

    @property
    def relative_humidity(self) -> float:
        """The measured relative humidity in percent."""
        regval = self._read(AM2320_REG_HUM_H)
        # Unpack big-endian (hi then lo) bytes as _unsigned_ 16bit int
        # Value should be in range 0..1_000) rep. 0% to 100.0%, but sensor
        # isn't specified up to 100% RH. So for the Hi byte only bottom
        # 2 bits are used.
        hum_i = struct.unpack(">H", regval)[0]
        hum_f = hum_i / 10.0
        # print("temp: %f" % (hum_f))
        return hum_f

    @property
    def model(self) -> tuple:
        """Read the device model and version numbers."""
        regval = self._read_register(AM2320_REG_MODEL_H, 3)
        # Unpack big-endian (hi then lo) bytes as _unsigned_ 16bit int
        # and an 8-bit int.
        model, vers = struct.unpack(">HB", regval)
        # print("model: %x, version: %d" % (model, vers))
        return (model, vers)

    @property
    def device_id(self) -> int:
        """Read the device id."""
        regval = self._read_register(AM2320_REG_DEVID_H, 4)
        # Unpack big-endian (hi then lo) bytes as _unsigned_ 32bit int
        id = struct.unpack(">L", regval)[0]
        # print("dev id: %x" % (id))
        return id

