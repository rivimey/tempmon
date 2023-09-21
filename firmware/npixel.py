from reading import Reading
from output import BaseOutput
from time import sleep
import neopixel

class NeoPixel(BaseOutput):
    npixel = None

    def __init__(self, pin, opts):
        super().__init__(opts)
        self.npixel = neopixel.NeoPixel(pin=pin, n=1, brightness=0.5)
        self.npixel[0] = (0, 0, 0)
        print(f"Loaded Neopixel")


    def write(self, value: Reading):
        if self.exists:
            T, H = int(value.secs), int(value.temp)
            self.npixel[0] = (T >> 2, H >> 3, (T + H) >> 3)


    @property
    def exists(self) -> bool:
        return True
