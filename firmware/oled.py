from time import sleep
import adafruit_ssd1306
from circularbuffer import CircularBuffer
from output import BaseOutput
from reading import Reading

try:
    from typing import List, Tuple, Union
    from typing_extensions import Literal
    from circuitpython_typing import ReadableBuffer
except ImportError:
    pass


class SSD1306(BaseOutput):
    OLED_FG = 1
    OLED_BG = 0
    OLED_W = 128
    OLED_H = 32

    opts = {}
    oled = None
    bus = None
    buffer = None

    # Graph drawing:
    t_range = 0
    t_scale = 0
    s_range = 0
    s_scale = 0
    min_s = 0
    min_t = 0
    max_s = 0
    max_t = 0
    gx = 0
    gy = 0
    gw = 0
    gh = 0

    def __init__(self, bus, buffer, opts: dict):
        super().__init__(opts)
        self.oled = None
        self.bus = bus
        self.opts = opts
        self.buffer = buffer
        self.is_reverse = False

        for c in range(1, 2):
            try:
                self.oled = adafruit_ssd1306.SSD1306_I2C(width=self.OLED_W, height=self.OLED_H,
                                                         i2c=self.bus)
                self.oled.rotate(True)
                self.oled.fill(0)

                # This flashing is to signal the OLED is alive & healthy.
                self.oled.fill(1)
                sleep(0.1)
                self.oled.fill(0)
                self.oled.auto_show = False
                self.reversevideo = opts["oled_reversevideo"]
                break

            except Exception as ex:
                print(f"Exception: On connect to oled: {ex}")
                self.show_i2cdevs()
                sleep(0.01)


    @property
    def exists(self):
        return self.oled is not None


    @property
    def reversevideo(self) -> bool:
        return self.is_reverse


    @reversevideo.setter
    def reversevideo(self, rev: bool):
        self.oled.invert(rev)
        self.is_reverse = rev


    def timestr(self, secs: int) -> str:
        ss = secs % 60
        mm = (secs // 60) % 60
        hh = int(secs // 3600)
        if hh > 0:
            return f"{hh:02}h{mm:02}m"
        if mm > 0:
            return f"{mm:02}m{ss:02}s"
        return f"{ss:02}s"


    def show_i2cdevs(self):
        self.bus.try_lock()
        print("I2C addresses found:", [hex(device_address) for device_address in self.bus.scan()])
        self.bus.unlock()


    def get_bounds(self, buffer: CircularBuffer):
        # Calculate the Bounds of the data
        min_s, max_s = 100_000_000, 0
        min_t, max_t = 100, 0
        for v in buffer:
            min_t = min(min_t, v.temp)
            min_s = min(min_s, v.secs)
            max_t = max(max_t, v.temp)
            max_s = max(max_s, v.secs)
        self.min_s = min_s
        self.min_t = min_t
        self.max_s = max_s
        self.max_t = max_t


    def drawchart(self, buffer: CircularBuffer, color: int, point: tuple, size: tuple):
        if self.exists and not buffer.is_empty():
            (w, h) = size
            (sx, sy) = point

            # Allow for the Y axis.
            self.gx, self.gy = sx + 14, sy
            self.gw, self.gh = w - 14, h - 1

            self.get_bounds(buffer)

            # Allow 'slack' around Y limits (& also prevent div0 error!)
            self.min_t -= 0.25
            self.max_t += 0.25

            # Calculate range & scale:
            self.t_range = self.max_t - self.min_t
            self.t_scale = self.gh / self.t_range
            self.s_range = max(self.max_s - self.min_s, 32)
            self.s_scale = self.gw / self.s_range

            # Integer Y's near the min & max Y axis.
            min_y = int(round(self.min_t, 0))
            _, py1 = self.rescale(self.min_s, min_y)
            max_y = int(round(self.max_t, 0))
            _, py2 = self.rescale(self.min_s, max_y)

            # vline for Y axis:
            self.oled.line(self.gx, self.gy, self.gx, self.gy + self.gh, color)

            # tick for Y axis:
            self.oled.line(self.gx - 2, py1, self.gx + 2, py1, color)
            self.oled.line(self.gx - 2, py2, self.gx + 2, py2, color)

            self.oled.text(f"{max_y}", sx, sy, color=color)
            self.oled.text(f"{min_y}", sx, sy + h - 7, color=color)
            self.oled.text(f"T{self.timestr(self.s_range)}", sx + 84, sy + 25, color=color)

            # Now plot the graph
            lastpx, lastpy = None, None
            for v in buffer:
                px, py = self.rescale(v.secs, v.temp)

                if lastpx is None:
                    self.oled.pixel(px, py, color)
                else:
                    self.oled.line(lastpx, lastpy, px, py, color)
                lastpx, lastpy = px, py


    def rescale(self, vx, vy):
        px = ((vx - self.min_s) * self.s_scale)
        px = self.gx + int(round(px))

        py = ((vy - self.min_t) * self.t_scale)
        py = self.gy + self.gh - int(round(py))
        return px, py


    def drawtext(self, text, color=1, point=(0, 0), scale=1):
        self.oled.text(text, point[0], point[1], color=color, size=scale)


    def drawscreen(self, buffer, t: float, h: float, status, sec: int, opts: dict):
        self.oled.fill(self.OLED_BG)

        if opts["chartmode"]:
            self.drawchart(buffer=buffer, color=self.OLED_FG, point=(0, 0), size=(128, 18))
            self.drawtext(f"{t:4.1f}C", color=self.OLED_FG, point=(0, 25))
            self.drawtext(f"{h:4.1f}%", color=self.OLED_FG, point=(42, 25))
        else:
            self.drawtext(f"{t:4.1f}", color=self.OLED_FG, point=(0, 2), scale=2)
            self.drawtext(f"C", color=self.OLED_FG, point=(54, 10))
            self.drawtext(f"{h:4.1f}", color=self.OLED_FG, point=(70, 2), scale=2)
            self.drawtext(f"%", color=self.OLED_FG, point=(122, 10))
            self.drawtext(f"{sec:6} s", color=self.OLED_FG, point=(80, 25))

            # Flag whether the USB drive is available to the host.
            # [WIP, not working yet]
            if opts["usbdrive_visible"]:
                self.drawtext(text=f"USB", color=self.OLED_FG, point=(0, 25))

            if status is not None:
                self.drawtext(text=f"S:{status:04x}", color=self.OLED_FG, point=(33, 25))

        try:
            self.oled.show()
        except Exception as ex:
            pass
            # print(f"Exception thrown writing oled: {ex}")


    def write(self, value: Reading):
        if self.exists:
            self.drawscreen(self.buffer, value.temp, value.humidity, value.status, value.secs, self.opts)

