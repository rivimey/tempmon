# Simple Temperature & Humidity Monitor

Node-exporter textfile collector for Temp & Humidity readings produced
from the companion firmware.

Requires the [Prometheus Node
Exporter](https://github.com/prometheus/node_exporter) to pass metrics
to the monitoring system.

## Installation and Usage

The `node_exporter` listens on HTTP port 9100 by default. See the `--help`
output for more options.  One of its options is for a textfile-collector
directory, which if present it will scan for input and when found,
pass on.

By writing a file into this directory in 'Prometheus-metrics' format,
you can thus include it in the node\_exporter output.

A simple converter is required to read data from the device's serial
port and write it in the correct format to the text collector directory.

## Text-Collector Location

Because the files in this directory are rewritten very frequently and
they are also ephemeral, it is best to put it in a filesystem using the
`tmpfs` filesystem, such as /var/run/node\_exporter/textcollector.

## Hardware

The hardware device consists of a Raspberry Pico (RP2040) chip on a board
such as the Seeed XIAO RP2040 or the Adafruit Trinkey QT2040, although
the exact form doesn't matter. The board layout included here was for the
XIAO.

The MCU board is connected to an AM2320 temperature & humidity monitor
using the Pico's I2C bus. Two 3K pullup resistors are required on the
I2C lines.

The device also supports an SSD1306-based 128x32 OLED (of which there
are many sources), and if present it will show the current readings.

The whole unit is connected to the host PC using the USB serial port,
which appears on a Linux host at least as /dev/ttyACM?.

## Firmware

The device firmware is written in CircuitPython (v8), using the SSD1306
and am2320 adafruit libraries (Thanks Adafruit!)

Although there is a fair bit of error-checking code it is fairly simple
in form: setup the peripherals, then forever loop reading a value, writing
it to the serial port and OLED (if present).

The data is written to the serial port using JSON. It is important to
the host collector that it is all on one line.

The Seeed XIAO RP2040 includes a Neopixel which the firmware writes a
colour to that reflects (very imperfectly) the measurements.

## Software

The Host collector code is ironically more complex, becuase it has to
report `samples` whether or not info is coming on the serial port, or
even if there is no port! This is so it can report the 'up' value, 
showing whether the data source is present or not.

Most of the reader uses a Stream object to represent either PySerial
or a normal File source.

Data from the serial port is read in as it comes into a buffer, and
once a whole line is available in the buffer that is extracted and
parsed as Json. The JSON dictionary is then written to a new text file
using wr\_param(), and the whole process restarts.

## Accuracy

The AM2320 is not marketed as an especially accurate device and has
not shown itself to be so... expect values within about 2 deg C 
and something like 5% RH. I did investigate calibration of my 
particular device and on that basis the firmware adjusts the returned
measurements before passing them on. YMMV.

I have found the relative (minute-on-minute) measurements to reflect
reality with more precision, though: a sequence of readings in a
cooling or warming environment show that cooling or warming properly.

## Known issues:

* Currently the File source is broken because readline\_partial()
wants to use .in\_waiting, which is not present for Files.

* The firmware expects the Neopixel to exist, which it will for
the XIAO but for other boards it may not.


