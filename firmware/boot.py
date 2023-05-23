import usb_midi
usb_midi.disable()

import usb_hid
usb_hid.disable()

import supervisor
supervisor.runtime.autoreload = False

# Disable devices only if button is not pressed.
import board
import digitalio
button_a = digitalio.DigitalInOut(board.D2)
button_b = digitalio.DigitalInOut(board.D3)

# button_a.direction = digitalio.Direction.INPUT
# button_b.direction = digitalio.Direction.INPUT
# button_a.pull = digitalio.Pull.DOWN
# button_b.pull = digitalio.Pull.DOWN

# if button_a.value and button_b.value:
#     import storage
#     storage.disable_usb_drive()
