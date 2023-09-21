

class Reading:
    def __init__(self, se=0, tm=0, hu=0, st=0):
        self._time = se
        self._temp = tm
        self._hum = hu
        self._stat = st

    @property
    def secs(self) -> int:
        return int(self._time/1_000_000)

    @property
    def status(self) -> int:
        return self._stat

    @property
    def secs_f(self) -> float:
        return round(self._time/1_000_000, 6)

    @property
    def humidity(self):
        return self._hum

    @property
    def temp(self):
        return self._temp
