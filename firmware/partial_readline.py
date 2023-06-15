
partial_line = ""
def readline_partial(ser):
    """
    Read characters from stream 'ser' into a buffer, and when that buffer
    contains a newline, return the text up to that newline for processing.
    Stream 'ser' can be either a PySerial stream (args.tty=True) or an
    os.file stream.
    """
    global partial_line

    # Check if incoming bytes are waiting to be read from the serial input
    # buffer.
    retline = None
    octets = None

    if args.tty:
        if ser.in_waiting > 0:
            octets = ser.readline()
        #else:
        #    print(".", end="", file=sys.stderr)
    else:
        try:
            octets = os.read(ser, 64)
        except BlockingIOError as ex:
            pass
        #    print(".", end="", file=sys.stderr)

    if type(octets) == bytes:
        octets = octets.decode('latin1')
        #print(f"{get_tod()}: readline decoded", file=sys.stderr)

    if type(octets) == str:
        #print("=", end="", file=sys.stderr)
        if len(octets) > 0:
            #print(">", file=sys.stderr)
            #print(f"{get_tod()}: readline got: '{octets}' adding to '{partial_line}'", file=sys.stderr)
            partial_line += octets
            parts = octets.split("\n", maxsplit=1)
            if len(parts) > 1:
                #print(f"{get_tod()}: readline got a line", file=sys.stderr)
                retline = parts[0]
                parts.pop(0)
            if len(parts) > 0:
                partial_line = parts[0]
                #print(f"{get_tod()}: readline partial line remaining, len:{len(partial_line)}", file=sys.stderr)
            else:
                partial_line = ""
    
    sys.stderr.flush()
    return retline
            
