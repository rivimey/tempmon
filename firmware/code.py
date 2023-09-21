from time import sleep, monotonic_ns
from math import floor, ceil
import board
import digitalio
import busio
## import async_button

from sensor import BaseSensor
from reading import Reading
from oled import SSD1306
from npixel import NeoPixel
from am23 import AM23
from sht3x import SHT3x
from usbserial import USBSerial
from circularbuffer import CircularBuffer

BUFFER_MAX = 64  # samples

# Hardware present:
ENABLE_OLED = True
ENABLE_AM2320 = False
ENABLE_SHT3x = True
ENABLE_NEOPIXEL = True
ENABLE_SERIAL = True

INITIAL_CHARTMODE = True

READING_INTERVAL_MILLISECS = 5_000

MILLISECS_TO_NANOSECS = 1_000_000
MICROSECS_TO_NANOSECS = 1_000

MICROSECS_TO_SECS = 1_000_000
MICROSECS_TO_MILLISECS = 1_000
NANOSECS_TO_MILLISECS = 1_000_000
NANOSECS_TO_MICROSECS = 1_000

NAP_TIME_MICROSECS = 20     # 20us or thereabouts.
NAP_TIME_SECS = float(NAP_TIME_MICROSECS) / float(MICROSECS_TO_SECS)
BUTTON_PRESS_MILLISECS = 50  # approximate!

opts = {
    "oled_reversevideo": True,
    "usbdrive_visible": False,
    "serialto_console": False,  # else to COM2
    "chartmode": INITIAL_CHARTMODE,
}

# Global state:
i2c = None

# Buffer to store last N readings in.
buffer = CircularBuffer(BUFFER_MAX)

# Initialise the Buttions
button_a = digitalio.DigitalInOut(board.D3)
button_a.direction = digitalio.Direction.INPUT
button_a.pull = digitalio.Pull.DOWN
button_b = digitalio.DigitalInOut(board.D2)
button_b.direction = digitalio.Direction.INPUT
button_b.pull = digitalio.Pull.DOWN

# The AM2320 chip tops at 100KHz. The SHT30 can do 1MHz.
i2c = busio.I2C(board.SCL, board.SDA, frequency=400_000)

# BaseSensor is a dummy input.
sensor = BaseSensor(i2c, opts)
if ENABLE_AM2320:
    sensor = AM23(i2c, opts)
elif ENABLE_SHT3x:
    sensor = SHT3x(i2c, opts)

outputs = []
if ENABLE_SERIAL:
    serial = USBSerial(opts)
    outputs.append(serial)

if ENABLE_NEOPIXEL:
    neopixel = NeoPixel(board.NEOPIXEL, opts)
    outputs.append(neopixel)

if ENABLE_OLED:
    oled = SSD1306(i2c, buffer, opts)
    outputs.append(oled)

# We want to avoid drift so 'now' is captured and then
# compared to clock-now, rather than a simple sleep(n).
now = monotonic_ns()

start = now
step = READING_INTERVAL_MILLISECS * MILLISECS_TO_NANOSECS

while True:
    us = int((now - start) / NANOSECS_TO_MICROSECS)

    status = -1
    t, h = 0, 0
    try:
        if sensor.exists:
            t = round(sensor.celcius, 3)
            h = round(sensor.relhumidity, 3)
            status = sensor.status
    except Exception as ex:
        print(f"Exception thrown reading sensor: {ex}")

    reading = Reading(us, t, h, status)
    buffer.overwrite(reading)

    for chan in outputs:
        chan.write(reading)

    # Update the time we should next make a measurement, and wait
    # for that time. This avoids overall timing drift due to overheads
    # in calculations, but not if the clock itself is fast or slow.
    # The length of sleep partly determines the accuracy of our next
    # measurement time, otherwise we could 'sleep' in longer chunks.
    now = now + step
    c1a = 0
    c1b = 0
    while monotonic_ns() < now:
        if button_a.value:
            c1a += 1
        if button_b.value:
            c1b += 1
        sleep(NAP_TIME_SECS)

    # c1 is time pressed in nap-times, but is also approximate!
    if (c1a * NAP_TIME_MICROSECS) > (BUTTON_PRESS_MILLISECS * MICROSECS_TO_MILLISECS):
        print("pressed")
        opts["chartmode"] = not opts["chartmode"]

    # c1 is time pressed in nap-times, but is also approximate!
    if (c1b * NAP_TIME_MICROSECS) > (BUTTON_PRESS_MILLISECS * MICROSECS_TO_MILLISECS):
        print("pressed")
        opts["serialto_console"] = not opts["serialto_console"]
