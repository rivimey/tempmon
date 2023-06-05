import io
import sys
import os
import json
import time

__version__ = "1.0"

class PromFile:

    def __init__(self, prefix: str, promfile: str, args: dict={}):
        self.args = args
        self.prefix = prefix
        self.promfile = promfile
        self.lastwrite = 0

        self.in_port = ""
        if "serial" in args:
            self.in_port = args.serial

        self.echo_stdout = False
        if "stdout" in args:
            self.echo_stdout = args.stdout

    def wr_param(self, outf: io.TextIOBase, vname: str, value: float, vtype: str = "gauge", keys: dict = {}):
        """
        Write out a node_exporter parameter type line and value line to 'outf'.

        'prefix' is used as the first part of the parameter name.
        The second (unique) part of the name is 'vname', and the parameter's value
        is 'value'. vtype is the parameter type (Prometheus typenames), and
        keys are associated context for this parameter, such as a channel number.
        """
        vname = self.prefix + vname
        value = f"{value:8.3f}"

        kv = [f"{k}=\"{v}\"" for k, v in keys.items()]
        k_str = ",".join(kv)

        print(f"# TYPE {vname} {vtype}", file=outf)
        print(vname + "{" + k_str +"} " + str(value), file=outf)


    def write_outfile(self, fout: io.TextIOBase, is_open: bool, line: str, tod: float) -> dict:
        """
        Write the complete parameter file to the stream, using data values found
        in 'line', which is a self-contained JSON coded object.
        If the serial input is not open, create an output with a '|prefix_|up 0'
        value to indicate the service is down.
        """
        global __version__

        self.wr_param(fout, "info", 1, keys={"name": "tempmon", "version": __version__, "tty": self.in_port} )
        self.wr_param(fout, "up", 1 if is_open and len(line) > 0 else 0)

        # only lines starting '{' are json, ignore others.
        if is_open and len(line) > 0 and line[0] == '{':

            if self.echo_stdout:
                print(f"{tod}: parsing '{line}' as JSON", file=sys.stderr)

            try:
                data = json.loads(line)
            except Exception as ex:
                print(f"{tod}: Exception {ex} while parsing '{line}' as JSON", file=sys.stderr)
                return {}

            # If there are serial line errors the names may get corrupted.
            if "temp" in data and "humidity" in data and "time" in data:
                self.wr_param(fout, "temp", data["temp"], keys={"unit": "C"})         # centigrade
                self.wr_param(fout, "humidity", data["humidity"], keys={"unit": "%"}) # RH %
                self.wr_param(fout, "uptime", data["time"], keys={"unit": "s"})       # time secs
            else:
                print(f"{tod}: Dictionary invalid while parsing '{line}' as JSON", file=sys.stderr)
                return {}

            fout.flush()
            self.lastwrite = time.time()
            return data

        fout.flush()
        return {}


    def write_promfile(self, is_open: bool, line: str, tod: float):
        """
        Write the promfile to the output file and if required to stdout.
        """

        if self.echo_stdout:
            self.write_outfile(sys.stdout, is_open, line, tod)

        with open(self.promfile, "w", buffering=1) as fout:
            data = self.write_outfile(fout, is_open, line, tod)

        return data

    def delete_expired_promfiles(self, maxAge: int = 10):
        """
        Don't leave promfiles lying around too long or they give a false view
        of the system state.
        """
        now = time.time()
        if ((now - self.lastwrite) > maxAge and
            os.path.exists(self.promfile) and
            (now - os.path.getmtime(self.promfile)) > maxAge):
            try:
                print(f"{get_tod()}: Delete file {self.promfile}, too old ({now - self.lastwrite}s)", file=sys.stderr)
                os.remove(self.promfile)
            except:
                pass

