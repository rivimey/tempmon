from time import sleep

from sensor import BaseSensor
# import adafruit_sht4x
import adafruit_sht31d


class SHT3x(BaseSensor):
    sht30 = None

    def __init__(self, bus, opts):
        super().__init__(bus, opts)
        sht30_addr = 0x45
        for _ in range(1, 4):
            try:
                self.sht30 = adafruit_sht31d.SHT31D(self.bus, sht30_addr)
                print(
                    f"Found SHT3x at {hex(sht30_addr)} with serial number {self.sht30.serial_number:x}")
                self.sht30.repeatability = adafruit_sht31d.REP_HIGH
                break
            except Exception as ex:
                print(f"Exception: On connect to sensor: {ex}")
                self.show_i2cdevs()
                sht30_addr = 0x44 if sht30_addr == 0x45 else 0x45
                sleep(0.5)


    @property
    def exists(self) -> bool:
        return self.sht30 is not None


    @property
    def status(self) -> int:
        return self.sht30.status


    @property
    def relhumidity(self) -> float:
        return self.sht30.relative_humidity


    @property
    def celcius(self) -> float:
        return self.sht30.temperature
