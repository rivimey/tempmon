
def wr_param(outf: io.TextIOBase, vname: str, value: float, vtype: str = "gauge", keys: dict = {}):
    """
    Write out a node_exporter parameter type line and value line to 'outf'.

    Global 'prefix' is used as the first part of the parameter name.
    The second (unique) part of the name is 'vname', and the parameter's value
    is 'value'. vtype is the parameter type (Prometheus typenames), and
    keys are associated context for this parameter, such as a channel number.
    """
    global prefix

    vname = prefix + vname
    value = f"{value:8.3f}"

    kv = [f"{k}=\"{v}\"" for k, v in keys.items()]
    k_str = ",".join(kv)

    print(f"# TYPE {vname} {vtype}", file=outf)
    print(vname + "{" + k_str +"} " + str(value), file=outf)


def write_outfile(fout: io.TextIOBase, is_open: bool, line: str, tod: float) -> dict:
    """
    Write the complete parameter file to the stream, using data values found
    in 'line', which is a self-contained JSON coded object.
    If the serial input is not open, create an output with a 'prefix_up 0'
    value to indicate the service is down.
    """
    global in_port, __version__

    wr_param(fout, "info", 1, keys={"name": "tempmon", "version": __version__, "tty": in_port} )
    wr_param(fout, "up", 1 if is_open and len(line) > 0 else 0)

    # only lines starting '{' are json, ignore others.
    if is_open and len(line) > 0 and line[0] == '{':

        if args.stdout:
            print(f"{tod}: parsing '{line}' as JSON", file=sys.stderr)

        try:
            data = json.loads(line)
        except Exception as ex:
            print(f"{tod}: Exception {ex} while parsing '{line}' as JSON", file=sys.stderr)
            return {}

        # If there are serial line errors the names may get corrupted.
        if "temp" in data and "humidity" in data and "time" in data:
            wr_param(fout, "temp", data["temp"], keys={"unit": "C"})         # centigrade
            wr_param(fout, "humidity", data["humidity"], keys={"unit": "%"}) # RH %
            wr_param(fout, "uptime", data["time"], keys={"unit": "s"})       # time secs
        else:
            print(f"{tod}: Dictionary invalid while parsing '{line}' as JSON", file=sys.stderr)
            return {}

        fout.flush()
        return data

    fout.flush()
    return {}


def write_promfile(out_file: str, is_open: bool, line: str, tod: float):
    """
    Write the promfile to the output file and if required to stdout.
    """
    global args

    if args.stdout:
        write_outfile(sys.stdout, is_open, line, tod)

    with open(out_file, "w", buffering=1) as fout:
        data = write_outfile(fout, is_open, line, tod)

    return data

