import serial
import queue
import time
import traceback
import sys

SerialThreadPoison = False

def constrain(v, mn, mx):
    if v >= mn and v <= mx:
        return v
    elif v < mn:
        return mn
    else: #if v > mx:
        return mx

class ReadLine:
    """
    Class to read bytes into a buffer and return buffer prefixes
    that end in a newline. Requires Serial.in_waiting.
    """

    def __init__(self, stream):
        self.buf = bytearray()
        self.stream = stream

    def valid(self):
        return self.stream is not None 

    def readline(self):
        i = self.buf.find(b"\n")
        if i >= 0:
            line = self.buf[:i+1]
            self.buf = self.buf[i+1:]
            #print(f"rl: newline {line}")
            return line
        while True:
            i = constrain(self.stream.in_waiting, 1, 2048)
            data = self.stream.read(i)
            i = data.find(b"\n")
            if i >= 0:
                line = self.buf + data[:i+1]
                self.buf[0:] = data[i+1:]
                #print(f"rl: read-newline {line}")
                return line
            else:
                #print(f"rl: extend with {data}")
                self.buf.extend(data)


class LineItem:
    """
    Data class to be transmitted in a Queue instance to
    a reader. Stores a status integer and a string.
    """
    OK = 1

    ENOPORT = 2  # unable to open port
    ETIMEOUT = 3

    def __init__(self, stat: int = OK, line: str = ""):
        self.ln = line
        self.st = stat

    @property
    def status(self):
        return self.st

    @property
    def line(self):
        return self.ln


def SerialReadlineThread(out_queue, port, baud, nbits, parity, stopb):
    """
    Long-lived thread that tries (repeatedly if needed) to open a serial
    port and read lines of text to insert into a Queue.
    If the serial port can't be opened, status messages are still added
    to the queue so the reaader can monitor.
    """

    def close_port(tty_in):
        if tty_in is not None:
            tty_in.close()

    def open_port():
        tty_in = serial.Serial()
        if tty_in is not None:
            tty_in.port = port
            tty_in.baudrate = baud
            tty_in.parity = parity
            tty_in.bytesize = nbits
            tty_in.stopbits = stopb
            tty_in.open()

        return tty_in

    print("SerialReadlineThread started")
    tty_in = None
    readln = None
    while not SerialThreadPoison:
        try:
            if tty_in is None:
                tty_in = open_port()
                print(f"create tty_in {tty_in}", file=sys.stderr)

            if tty_in is not None and readln is None:
                #print(f"create readln", file=sys.stderr)
                readln = ReadLine(tty_in)

            if tty_in is None:
                #print(f"queue nak {readln}", file=sys.stderr)
                item = LineItem(LineItem.ENOPORT)
                out_queue.put(item)
                time.sleep(1) # 1s
            else:
                #print(f"readline()", file=sys.stderr)
                line = readln.readline()
                text = line.decode('latin1')
                item = LineItem(LineItem.OK, text)
                #print(f"queue line Pre: {text}", file=sys.stderr)
                out_queue.put(item)

        except Exception as ex:
            print(f"Error: {ex}")
            #traceback.print_tb(ex.__traceback__, limit=3, file=sys.stderr)
            readln = None
            close_port(tty_in)
            tty_in = None
            time.sleep(1) # 1s

    print("SerialReadlineThread poisoned")

