
from reading import Reading

class BaseOutput:
    opts = {}

    def __init__(self, opts):
        self.opts = opts

    def write(self, value: Reading):
        pass

    @property
    def exists(self) -> bool:
        return False
