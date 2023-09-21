from time import sleep
from sensor import BaseSensor
import adafruit_am2320_ext


class AM23(BaseSensor):
    am2320 = None


    def __init__(self, bus, opts):
        super().__init__(bus, opts)
        self.am2320 = None
        for c in range(1, 2):
            try:
                am2320 = adafruit_am2320_ext.AM2320Cached(self.bus)
                print(f"Loaded AM2320 model: {am2320.model}, id: {am2320.device_id}")
                print(f"Caching driver in use, expiry: {am2320.expiry}")
                break
            except Exception as ex:
                print(f"Exception: On connect to sensor: {ex}")
                self.show_i2cdevs()
                sleep(0.5)


    @property
    def relhumidity(self) -> float:
        return self.am2320.relative_humidity


    @property
    def celcius(self) -> float:
        return self.am2320.temperature


    @property
    def exists(self) -> bool:
        return self.am2320 is not None
