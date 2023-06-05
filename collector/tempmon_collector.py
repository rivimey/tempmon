#!/bin/env python3

import sys
import os
import serial
import argparse
import json
import time
import threading
import queue

from promfile import PromFile
from serialreadline import SerialReadlineThread, LineItem

__version__ = "1.0"

#in_port = "/dev/serial/by-id/hwoudhv"
in_port = "/dev/ttyACM0"
in_baud = 9600
in_nbits = serial.EIGHTBITS
in_parity = serial.PARITY_NONE
in_stopb = serial.STOPBITS_ONE
maxPromfileAge = 7  # secs

out_filename="/var/run/node_exporter/textfile-collector/tempmon.prom"

prefix = "airtemp_"


def track_timestamp(data: dict, tod: float, starttime: float, start_tod: float):
    if 'time' in data:
        # Reset our state if needed.
        if starttime < 0 or starttime > data['time']:   # first time round or rebooted
            starttime, start_tod = data['time'], tod

        # Calculate what time the sensor would tell if it had full
        # unix epoch time available...
        calc_tod = (data['time'] - starttime) + start_tod
        diff = calc_tod - tod
        if diff < -1.0 or diff > 0.5:
            print(f"{get_tod()}: Time drifting: {diff}", file=sys.stderr)
        if diff < -1.5 or diff > 1.0:
            starttime = get_tod()
            print(f"{get_tod()}: Time reset: was {diff}", file=sys.stderr)
    return starttime, start_tod


def try_get_input(serial_queue, tty_open, line):
    # Try to read a line of text
    #print(f"Check queue:", file=sys.stderr)
    try:
        item = serial_queue.get(block=True, timeout=1)
        if item.status == LineItem.OK:
            #print(f"Got line {item.line}", file=sys.stderr)
            line = item.line.rstrip()
            tty_open = True

        else:  # if item.status == LineItem.ENOPORT:
            tty_open = False

    except queue.Empty:
        pass

    return tty_open, line


def get_tod():
    """
    Return the current timestamp to 3 d.p
    """
    return round(time.time(), 3)


def main():
    global args

    argp = argparse.ArgumentParser(
            description=
            """Serial-to-promfile converter for TempMon gadget. See the
            Prometheus 'node_exporter' for details of textfile-collector
            promfiles. Locate the output file on a tmpfs (memory) file
            system.""",
            epilog="(c) 2023 Ruth Ivimey-Cook")
    argp.add_argument("-i", "--serial", action='store', metavar="PORT", default=in_port, help="Serial port to read")
    argp.add_argument("-T", "--tty", action='store_true', default=False, help="Treat input PORT as an OS serial port (default to read as a file)")
    argp.add_argument("-b", "--baud", action='store', metavar="BAUD", type=int, default=in_baud, help="Serial port baud rate (only if -T)")
    argp.add_argument("-o", "--promfile", action='store', default=out_filename, help="Full path to promfile to write to")
    argp.add_argument("-O", "--stdout", action='store_true', default=False, help="Write results to stdout as well as promfile")
    args = argp.parse_args()

    print(f"Tempmon {__version__} (c) 2023 Ruth Ivimey-Cook")
    print(f"Read from {args.serial}, write to {args.promfile}")
    print(f"Serial {'is' if args.tty else 'is not'} treated as a tty")

    # Objective: write a promfile even if no serial port.

    serial_queue = queue.SimpleQueue()
    serialIn = threading.Thread(
            target=SerialReadlineThread,
            args=(serial_queue, args.serial, args.baud, in_nbits, in_parity, in_stopb),
            daemon=True)
    serialIn.start()

    # value of data[time] and time.time() when last reset
    starttime, start_tod = -1, get_tod()
    promFile = PromFile(prefix, args.promfile, args)

    print(f"{get_tod()}: enter main loop", file=sys.stderr)
    tty_open = False
    while True:
        line = ""
        tod = get_tod()

        try:
            promFile.delete_expired_promfiles(maxAge=maxPromfileAge)

            tty_open, line = try_get_input(serial_queue, tty_open, line)

            # If we haven't accumulated a complete line yet, that's all.
            if len(line) == 0:
                continue

            data = promFile.write_promfile(tty_open, line, tod)
            starttime, start_tod = track_timestamp(data, tod, starttime, start_tod)

        except KeyboardInterrupt as ex:
            raise ex

        except Exception as ex:
            print(f"{get_tod()}: Exception: {ex}", file=sys.stderr)
            time.sleep(0.25)

        sys.stderr.flush()
        time.sleep(0.25)


if __name__ == '__main__':
    try:
        main()
        exit(0)

    except KeyboardInterrupt:
        print("Quit.", file=sys.stderr)
        exit(1)

