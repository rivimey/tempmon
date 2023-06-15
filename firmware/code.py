import time
from math import floor, ceil
import board
import digitalio
import busio
import neopixel
import adafruit_ssd1306
# import adafruit_am2320_ext
# import adafruit_sht4x
import adafruit_sht31d
from circularbuffer import CircularBuffer

BUFFER_MAX = 500

SECS = 5   # secs
SECS_TO_NANOSECS = 1_000_000_000
SECS_TO_MILLISECS = 1_000_000

# create the I2C shared bus
OLED_FG = 1
OLED_BG = 0
OLED_W = 128
OLED_H = 32

class Reading:
    def __init__(self, se=0, tm=0, hu=0):
        self._time = se
        self._temp = tm
        self._hum = hu

    @property
    def secs(self) -> int:
        return int(self._time/1000)

    @property
    def secs_f(self) -> float:
        return round(self._time/1000, 4)

    @property
    def humidity(self):
        return self._hum

    @property
    def temp(self):
        return self._temp

    @property
    def json(self):
        return f"{{\"time\": {self.secs_f}, \"temp\": {self._temp}, \"humidity\": {self._hum} }}"

def timestr(secs: int):
    ss = secs % 60
    mm = (secs // 60) % 60
    hh = int(secs // 3600)
    if hh > 0:
        return f"{hh:02}h{mm:02}m"
    if mm > 0:
        return f"{mm:02}m{ss:02}s"
    return f"{ss:02}s"

def drawchart(color: int, point: tuple, size: tuple):
    global oled, buffer
    if oled is not None and not buffer.is_empty():
        (w,h) = size
        (sx,sy) = point
        gx, gy = sx + 14, sy    # Allow for axis.
        gw, gh = w - 14, h - 1
        min_s, max_s = 1000000, 0
        min_t, max_t = 100, 0
        min_h, max_h = 100, 0
        for v in buffer:
            min_t = min(min_t, v.temp)
            min_h = min(min_h, v.humidity)
            min_s = min(min_s, v.secs)
            max_t = max(max_t, v.temp)
            max_h = max(max_h, v.humidity)
            max_s = max(max_s, v.secs)
        min_t = min_t-0.5
        max_t = max_t+0.5
        t_range = max_t - min_t
        t_scale = gh / t_range
        s_range = max(max_s - min_s, 32)
        s_scale = gw / s_range

        oled.text(f"{int(round(max_t,0))}", sx, sy, color=color)
        oled.text(f"{int(round(min_t,0))}", sx, sy+h-7, color=color)
        oled.text(f"T{timestr(s_range)}", 84, 25, color=color)

        lastpx, lastpy = None, None
        for v in buffer:
            px = ((v.secs - min_s) * s_scale)
            px = gx + int(round(px))
            py = ((v.temp - min_t) * t_scale)
            py = gy + gh - int(round(py))
            if lastpx is None:
                oled.pixel(px, py, color)
            else:
                oled.line(lastpx, lastpy, px, py, color)
            lastpx, lastpy = px, py


def drawtext(text, color=1, point=(0, 0), scale=1):
    global oled
    if oled is not None:
        oled.text(text, point[0], point[1], color=color, size=scale)


# Buffer to store last N readings in.
buffer = CircularBuffer(BUFFER_MAX)

# Initialise the Buttions: button B is currently the only one with
# a switch installed!
button_a = digitalio.DigitalInOut(board.D2)
button_a.direction = digitalio.Direction.INPUT
button_a.pull = digitalio.Pull.DOWN
button_b = digitalio.DigitalInOut(board.D3)
button_b.direction = digitalio.Direction.INPUT
button_b.pull = digitalio.Pull.DOWN

# The AM2320 chip tops at 100KHz. The SHT30 can do 1MHz.
i2c = busio.I2C(board.SCL, board.SDA, frequency=400_000)

while True:
    try:
        # am = adafruit_am2320_ext.AM2320Cached(i2c)
        # print(f"Loaded AM2320 model: {am.model}, id: {am.device_id}")
        # print(f"Caching driver in use, expiry: {am.expiry}")
        sht = adafruit_sht31d.SHT31D(i2c, 0x45)
        print(f"Found SHT3x with serial number {sht.serial_number:x}")
        sht.repeatability = adafruit_sht31d.REP_HIGH
        break
    except Exception as ex:
        print(f"Exception: On connect to sensor: {ex}")
        i2c.try_lock()
        print("I2C addresses found:", [hex(device_address) for device_address in i2c.scan()])
        i2c.unlock()
        time.sleep(0.5)

# Try to find the OLED
oled = None
for c in range(1,3):
    try:
        oled = adafruit_ssd1306.SSD1306_I2C(OLED_W, OLED_H, i2c)
        # We write several things per update, so disable autoshow.
        oled.auto_show = False
        # This flashing is to signal the OLED is alive & healthy.
        oled.fill(1)
        oled.show()
        time.sleep(0.002)
        oled.fill(0)
        oled.show()
    except:
        time.sleep(0.01)


# Try to find the Neopixel (on uC)
npixel = None
for c in range(1,3):
    try:
        npixel = neopixel.NeoPixel(pin=board.NEOPIXEL, n=1, brightness=0.5)
        npixel[0] = (0,0,0)
        break
    except:
        time.sleep(0.01)

# We want to avoid drift so 'now' is captured and then
# compared to clock-now, rather than a simple sleep(n).
now = time.monotonic_ns()
usbdrive_visible = False
chartmode = True
start = now
step = SECS * SECS_TO_NANOSECS
while True:
    # (now - start) is 'uptime', calculate it in 'ms' and 's'.
    ms = int((now - start)/SECS_TO_MILLISECS)
    sec = int(ms/1000)
    press_c = 0
    t,h = 0,0

    # Read a value from temp sensor.
    try:
        # t, h = sht.measurements
        t = round(sht.temperature, 3)
    except Exception as ex:
        print(f"Exception thrown reading sensor: {ex}")

    # Read a value from humidity sensor.
    try:
        h = round(sht.relative_humidity, 3)
    except Exception as ex:
        print(f"Exception thrown reading sensor: {ex}")

    # Read a value from temp sensor.
    status = None
    try:
        # t, h = sht.measurements
        status = sht.status
    except Exception as ex:
        print(f"Exception thrown reading sensor: {ex}")

    # Reflect the values in the colour of the neopixel.
    if npixel is not None:
        T, H = int(t), int(h)
        npixel[0] = (T>>2, H>>3, (T+H)>>3)

    reading = Reading(ms, t, h)
    buffer.overwrite(reading)

    # Send to host
    print(reading.json)

    # If we have an OLED, write the readings there as well.
    if oled is not None:
        oled.fill(OLED_BG)

        if chartmode:
            drawchart(color=OLED_FG, point=(0,0), size=(128,18))
            drawtext(f"{t:4.1f}C", color=OLED_FG, point=(0, 25))
            drawtext(f"{h:4.1f}%", color=OLED_FG, point=(42, 25))
        else:
            drawtext(f"{t:4.1f}", color=OLED_FG, point=(0, 2), scale=2)
            drawtext(f"C", color=OLED_FG, point=(54, 10))
            drawtext(f"{h:4.1f}", color=OLED_FG, point=(70, 2), scale=2)
            drawtext(f"%", color=OLED_FG, point=(122, 10))
            drawtext(f"{sec:6} s", color=OLED_FG, point=(80, 25))

            # Flag whether the USB drive is available to the host.
            # [WIP, not working yet]
            if usbdrive_visible:
                drawtext(text=f"USB", color=OLED_FG, point=(0, 25))
            if status is not None:
                drawtext(text=f"S:{status:04x}", color=OLED_FG, point=(33, 25))

        oled.show()

    # Update the time we should next make a measurement, and wait
    # for that time. This avoids overall timing drift due to overheads
    # in calculations, but not if the clock itself is fast or slow.
    # The length of sleep partly determines the accuracy of our next
    # measurement time, otherwise we could 'sleep' in longer chunks.
    now = now + step
    while time.monotonic_ns() < now:
        if button_b.value:
            press_c += 1
        time.sleep(0.0001)  # 100us or thereabouts.

    # print(f"button: count={c} (A: {button_a.value} B: {button_b.value})")
    if press_c > 100:
        chartmode = not chartmode
        sht.clearstatus()

