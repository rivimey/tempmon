import time
import json
import board
import digitalio
import busio
import neopixel
import adafruit_ssd1306
import adafruit_am2320
import supervisor

SECS = 5   # secs
SECS_TO_NANOSECS = 1_000_000_000
SECS_TO_MILLISECS = 1_000_000

# create the I2C shared bus
OLED_FG = 1
OLED_BG = 0
OLED_W = 128
OLED_H = 32

button_a = digitalio.DigitalInOut(board.D2)
button_a.direction = digitalio.Direction.INPUT
button_a.pull = digitalio.Pull.UP
button_b = digitalio.DigitalInOut(board.D3)
button_b.direction = digitalio.Direction.INPUT
button_b.pull = digitalio.Pull.UP

def temp_calib(meas: float) -> float:
    return meas - 1


def humid_calib(meas: float) -> float:
    return meas - 1


def drawtext(text, color=1, point=(0, 0), scale=1):
    global oled
    if oled is not None:
        oled.text(text, point[0], point[1], color=color, size=scale)


# The AM2320 chip can't run faster than 100KHz
i2c = busio.I2C(board.SCL, board.SDA, frequency=100_000)
while True:
    try:
        am = adafruit_am2320.AM2320(i2c)
        break
    except:
        time.sleep(0.01)

# Try to find the OLED
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
        break
    except:
        time.sleep(0.01)


# Try to find the OLED
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
start = now
step = SECS * SECS_TO_NANOSECS
while True:
    # (now - start) is 'uptime', calculate it in 'ms' and 's'.
    ms = int((now - start)/SECS_TO_MILLISECS)
    sec = int(ms/1000)

    # Read a value from each sensor.
    try:
        t = round(temp_calib(am.temperature), 4)
        h = round(humid_calib(am.relative_humidity), 4)
    except:
        t,h = 0,0

    # Reflect the values in the colour of the neopixel.
    if npixel is not None:
        T, H = int(t), int(h)
        npixel[0] = (T>>2, H>>3, (T+H)>>3)

    # Create a dict with our readings and punt it down the
    # serial line.
    v = { "time": sec, "temp": t, "humidity": h, }
    print(json.dumps(v))

    # If we have an OLED, write the readings there as well.
    if oled is not None:
        oled.fill(OLED_BG)
        drawtext(f"{t:4.1f}", color=OLED_FG, point=(0, 2), scale=2)
        drawtext(f"C", color=OLED_FG, point=(54, 10))
        drawtext(f"{h:4.1f}", color=OLED_FG, point=(70, 2), scale=2)
        drawtext(f"%", color=OLED_FG, point=(122, 10))
        drawtext(f"{sec:6} s", color=OLED_FG, point=(80, 25))

        # Flag whether the USB drive is available to the host.
        # [WIP, not working yet]
        if not (button_a.value and button_a.value):
            drawtext(text=f"USB", color=OLED_FG, point=(0, 25))

        oled.show()

    # Update the time we should next make a measurement, and wait
    # for that time. This avoids overall timing drift. The length of
    # sleep partly determines the accuracy of our next measurement
    # time, otherwise we could 'sleep' in longer chunks.
    now = now + step
    while time.monotonic_ns() < now:
        time.sleep(0.0001)  # 100us or thereabouts.

