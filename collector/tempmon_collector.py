#!/bin/env python3

import sys
import os
import io
import serial
import argparse
import json
import time

__version__ = "1.0"

#in_port = "/dev/serial/by-id/hwoudhv"
in_port = "/dev/ttyACM0"
in_baud = 9600
in_nbits = serial.EIGHTBITS
in_parity = serial.PARITY_NONE
in_stopb = serial.STOPBITS_ONE

out_filename="/var/run/node_exporter/textfile-collector/tempmon.prom"

prefix = "airtemp_"

partial_line = ""
def readline_partial(ser):
    global partial_line

    # Check if incoming bytes are waiting to be read from the serial input
    # buffer.
    retline = None
    if ser.in_waiting > 0:
        d = ser.readline()
        d = d.decode('latin1')
        if len(d) > 0:
            partial_line += d
            parts = d.split("\n", maxsplit=1)
            if len(parts) > 1:
                retline = parts[0]
                parts.pop(0)

            if len(parts) > 0:
                partial_line = parts[0]
            else:
                partial_line = ""

    return retline
            

def get_tod():
    return round(time.time(), 3)

def open_tty(tty_open, msg_suppress):
    global args

    tty_in = None
    #print(f"{get_tod()}: Open tty", file=sys.stderr)
    try:
        tty_open = False
        if args.tty:
            print(f"{get_tod()}: Open tty=serial", file=sys.stderr)
            # tty_in = serial.Serial(args.serial, baudrate=args.baud, bytesize=in_nbits, parity=in_parity, stopbits=in_stopb, timeout=10)

            if tty_in is None:
                tty_in = serial.Serial(timeout=0.1)
                print("C", tty_in)

            if tty_in is not None:
                tty_in.port = args.serial
                tty_in.baudrate = args.baud
                tty_in.parity = in_parity
                tty_in.stopbits = in_stopb
                tty_in.open()

            if tty_in is not None and tty_in.is_open:
                tty_open = True
                print(f"{get_tod()}: Opened Serial", file=sys.stderr)
            else:
                print(f"{get_tod()}: Open Serial failed {tty_in}", file=sys.stderr)
        else:
            print(f"{get_tod()}: Open tty=file", file=sys.stderr)
            tty_in = open(args.serial, "r")
            tty_open = True
        msg_suppress = False

    except OSError as ex:
        tty_open = False
        print(f"{get_tod()}: Open exception", file=sys.stderr)
        if not msg_suppress:
            tod = get_tod()
            print(f"{tod}: Open FileError: {ex}", file=sys.stderr)
            # Only half as often as we try opening it:
            msg_suppress = not msg_suppress
    except Exception as ex:
        tty_open = False
        print(f"{get_tod()}: Open Exception: {ex}", file=sys.stderr)

    return tty_in, tty_open, msg_suppress


def wr_param(outf: io.TextIOBase, vname: str, value: float, vtype: str = "gauge", keys: dict = {}):
    global args
    global prefix

    vname = prefix + vname
    value = f"{value:8.3f}"

    kv = [f"{k}=\"{v}\"" for k, v in keys.items()]
    k_str = ",".join(kv)

    print(f"# TYPE {vname} {vtype}", file=outf)
    print(vname + "{" + k_str +"} " + str(value), file=outf)


def write_outfile(fout: io.TextIOBase, is_open: bool, line: str, tod: float) -> dict:
    wr_param(fout, "info", 1, keys={"name": "tempmon", "version": __version__, "tty": in_port} )
    wr_param(fout, "up", 1 if is_open and len(line) > 0 else 0)

    # only lines starting '{' are json, ignore others.
    if is_open and len(line) > 0 and line[0] == '{':

        d = json.loads(line)
        wr_param(fout, "temp", d["temp"], keys={"unit": "C"})         # centigrade
        wr_param(fout, "humidity", d["humidity"], keys={"unit": "%"}) # RH %
        wr_param(fout, "uptime", d["time"]/100, keys={"unit": "s"})   # from msec to sec
        return d

    return {}


def write_promfile(out_file: str, is_open: bool, line: str, tod: float):
    global args

    write_outfile(sys.stdout, is_open, line, tod)

    with open(out_file, "w", buffering=1) as fout:
        d = write_outfile(fout, is_open, line, tod)

    return d


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
    suppress = False

    # value of d[time] and time.time() when last reset
    starttime, start_tod = -1, get_tod()

    tty_open = False
    while True:
        tod = get_tod()
        line = ""

        # Other end can close too...
        #present = os.path.exists(args.serial)
        #if not present and tty_open:
        #    try:
        #        tty_in.close()
        #    except:
        #        pass
        #    tty_open = False

        # Try to open our input
        if not tty_open:
            (tty_in, tty_open, suppress) = open_tty(tty_open, suppress)

        try:
            # Try to read a line of text
            if tty_open:
                p = readline_partial(tty_in)
                if p is not None:
                    line = p.rstrip()
                    tod = get_tod()
        except Exception as ex:
            print(f"{tod}: Readline Exception: {ex}", file=sys.stderr)


        if len(line) == 0:
            time.sleep(0.1)
            continue

        #print(f"{tod}: Read line=\"{line}\"", file=sys.stderr)

        try:
            # Try to write the text as a promfile
            d = write_promfile(args.promfile, tty_open, line, tod)

            if 'time' in d:
                # Reset our state if needed.
                if starttime < 0 or starttime > d['time']:   # first time round or rebooted
                    starttime, start_tod = d['time'], tod
                    starttime, start_tod = d['time'], tod

                calc_tod = (d['time'] - starttime) + start_tod
                diff = calc_tod - tod
                if diff < -0.1 or diff > 0.1:
                    print(f"{tod}: Time drifting: {diff}", file=sys.stderr)
            #print(f"{tod}: Written", file=sys.stderr)
            
        #except Exception as ex:
        except KeyboardInterrupt as ex:
            print(f"{tod}: Write Exception: {ex}", file=sys.stderr)
            time.sleep(0.25)

        time.sleep(0.25 if tty_open else 5)


if __name__ == '__main__':
    try:
        main()
        exit(0)

    except KeyboardInterrupt:
        print("Quit.", file=sys.stderr)
        exit(1)

