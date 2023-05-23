import adafruit_displayio_ssd1306
import time
import json
import board
import digitalio
import busio
import neopixel
import adafruit_ssd1306
import adafruit_am2320
import supervisor

supervisor.runtime.autoreload = False

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
    return meas - 2


def humid_calib(meas: float) -> float:
    return meas - 2


def drawtext(text, color=1, point=(0, 0), scale=1):
    if oled is not None:
        oled.text(text, point[0], point[1], color=color, size=scale)


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
        oled.auto_show = False
        oled.fill(1)
        oled.show()
        time.sleep(0.002)
        oled.fill(0)
        oled.show()
        break
    except:
        time.sleep(0.01)


npixel = neopixel.NeoPixel(pin=board.NEOPIXEL, n=1, brightness=0.5)
npixel[0] = (0,0,0)
now = time.monotonic_ns()
start = now
step = SECS * SECS_TO_NANOSECS
while True:
    try:
        t = round(temp_calib(am.temperature), 4)
        h = round(humid_calib(am.relative_humidity), 4)
    except:
        t,h = 0,0
        pass

    T, H = int(t), int(h)
    npixel[0] = (T>>2, H>>3, (T+H)>>3)

    ms = int((now - start)/SECS_TO_MILLISECS)
    sec = int(ms/1000)
    #print(f"  {sec:3} Temperature: {t:8.2f}  Humidity: {h:8.2f}")

    v = { "time": sec, "temp": t, "humidity": h, }
    print(json.dumps(v))

    if oled is not None:
        oled.fill(OLED_BG)
        drawtext(text=f"{t:4.1f}", color=OLED_FG, point=(0, 2), scale=2)
        drawtext(text=f"C", color=OLED_FG, point=(54, 10))
        drawtext(text=f"{h:4.1f}", color=OLED_FG, point=(70, 2), scale=2)
        drawtext(text=f"%", color=OLED_FG, point=(122, 10))
        drawtext(text=f"{sec:6} s", color=OLED_FG, point=(80, 25))
        if not (button_a.value and button_a.value):
            drawtext(text=f"USB", color=OLED_FG, point=(0, 25))
        oled.show()

    now = now + step
    while time.monotonic_ns() < now:
        time.sleep(0.0001)

