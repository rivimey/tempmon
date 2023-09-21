

class BaseSensor:
    bus = None
    opts = {}

    def __init__(self, thebus, opts):
        self.bus = thebus
        self.opts = opts

    @property
    def relhumidity(self) -> float:
        return 0

    @property
    def celcius(self) -> float:
        return 0

    @property
    def status(self) -> int:
        return 0

    @property
    def exists(self) -> bool:
        return False

    def show_i2cdevs(self):
        self.bus.try_lock()
        print("I2C addresses found:", [hex(device_address) for device_address in self.bus.scan()])
        self.bus.unlock()
