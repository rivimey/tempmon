from reading import Reading
from output import BaseOutput
import usb_cdc

class USBSerial(BaseOutput):

    output = None

    def __init__(self, opts):
        super().__init__(opts)
        self.whereto(self.opts["serialto_console"])

    def whereto(self, toconsole: bool):
        if toconsole and usb_cdc.console is not None and usb_cdc.console.connected:
            self.output = usb_cdc.console
        elif not toconsole and usb_cdc.data is not None and usb_cdc.data.connected:
            self.output = usb_cdc.data
        else:
            self.output = None


    def write(self, value: Reading):
        self.whereto(self.opts["serialto_console"])
        if self.output is not None:
            print(self.json(value), file=self.output, flush=True)

    @property
    def exists(self) -> bool:
        return not (usb_cdc.console is None and usb_cdc.data is None)

    def json(self, value: Reading):
        return f"{{\"time\": {value.secs_f}, \"temp\": {value.temp}, \"humidity\": {value.humidity} }}"
