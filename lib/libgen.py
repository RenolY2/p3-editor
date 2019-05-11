from collections import OrderedDict

from .vectors import Vector3


class GeneratorReader(object):
    def __init__ (self, file):
        self.f = file
        self.current_line = 1

    def read_token(self):
        line = self.f.readline()
        self.current_line += 1
        if not line:
            return ""
        line = line.strip()
        comment = line.find("#")

        if comment != -1:
            line = line[:comment]

        comment2 = line.find("//")
        if comment2 != -1:
            line = line[:comment2]

        if line.strip() == "":
            line = self.read_token()  # Try reading the next token

        return line.strip()

    def peek_token(self):
        curr = self.f.tell()
        next_token = self.read_token()

        self.f.seek(curr)
        return next_token

    def read_section_rest_raw(self):
        curr = f.tell()
        self.skip_current_section()
        end = f.tell()
        f.seek(curr)

        rest = f.read(end-curr)

        f.seek(curr)
        return rest

    def skip_next_section(self):
        token = self.read_token()
        if token == "{":
            level = 1

            while level != 0:
                token = self.read_token()

                if token == "{":
                    level += 1
                elif token == "}":
                    level -= 1
                elif token == "":
                    raise RuntimeError("Reached end of file while skipping {{ }} block. File is likely malformed")
        else:
            raise RuntimeError("Expected '{{' for start of section, instead got {0}".format(token))

    def skip_current_section(self):
        level = 0
        while level != -1:
            token = self.read_token()
            if token == "{":
                level += 1
            elif token == "}":
                level -= 1
            elif token == "":
                raise RuntimeError("Reached end of file while skipping to end of current { } block. File is likely malformed.")

    def read_vector3f(self):
        val = self.read_token()
        floats = val.split(" ")
        if len(floats) != 3:
            raise RuntimeError("Tried to read Vector3f but got {0}".format(floats))

        return float(floats[0]), float(floats[1]), float(floats[2])

    def read_integer(self):
        val = self.read_token()
        if val == "":
            raise RuntimeError("Reached end of file while reading integer!")
        return int(val)

    def read_float(self):
        val = self.read_token()
        if val == "":
            raise RuntimeError("Reached end of file while reading float!")
        return float(val)

    def read_string(self):
        val = self.read_token()
        assert val[0] == "\"" and val[-1] == "\""
        return val[1:-1]

    def read_string_tripple(self):
        val = self.read_token()
        tripple = []

        start = None

        #for i in range(3):
        for i, char in enumerate(val):
            if char == "\"" and start is None:
                start = i
            elif char == "\"" and start is not None:
                tripple.append(val[start:i+1])
                start = None

        if start is not None:
            raise RuntimeError("Malformed string tripple {0}".format(val))

        return tripple


class GeneratorParameters(object):
    pass


class GeneratorObject(object):
    def __init__(self, name, version, generatorid=["", "", ""]):
        self.name = name
        self.version = version
        self.generatorid = generatorid

        self.spline = []
        self.spline_params = None

        self.position = Vector3(0, 0, 0)
        self.rotation = Vector3(0, 0, 0)
        self.scale = 1.0

        self.unknown_params = OrderedDict()

    @classmethod
    def from_generator_file(cls, reader: GeneratorReader):
        name = reader.read_string()
        version = reader.read_string()
        generatorid = reader.read_string_tripple()
        gen = cls(name, version, generatorid)
        gen.read_parameters(reader)
        gen._read_spline(reader)

        return gen

    def read_parameters(self, reader: GeneratorReader):
        if reader.read_token() != "{":
            raise RuntimeError("")

        next = reader.read_token()
        if next == "":
            raise RuntimeError("Tried to read parameters but encountered EOF")

        assert next in ("{", "}")

        while next != "}":
            param_name = reader.read_string()
            if param_name == "mPos":
                self.position = Vector3(*reader.read_vector3f())
                reader.read_token()
            elif param_name == "mPosture":
                self.rotation = Vector3(*reader.read_vector3f())
                reader.read_token()
            elif param_name == "mBaseScale":
                self.scale = reader.read_float()
                reader.read_token()
            else:
                unkdata = []
                level = 0
                while level != -1:
                    subnext = reader.read_token()
                    if subnext == "":
                        raise RuntimeError("Encountered EOF while reading parameter")
                    elif subnext == "{":
                        level += 1
                    elif subnext == "}":
                        level -= 1

                    if level != -1:
                        unkdata.append(subnext)

                self.unknown_params[param_name] = unkdata

            next = reader.read_token()
            assert next in ("{", "}", "")

    def _read_spline(self, reader: GeneratorReader):
        splinetext = reader.read_string()

        if splinetext == "no_spline":
            pass
        elif splinetext == "spline":
            spline_count = reader.read_integer()
            for i in range(spline_count):
                self.spline.append(reader.read_vector3f())

            self.spline_params = reader.read_token()

    def render(self):
        a


class GeneratorFile(object):
    def __init__(self):
        self.generators = []

    @classmethod
    def from_file(cls, f):
        genfile = cls()
        reader = GeneratorReader(f)

        start = reader.read_token()
        if start != "{":
            raise RuntimeError("Expected file to start with '{'")

        next = reader.peek_token()
        if next == "":
            raise RuntimeError("Malformed file, expected generator object or '}'")

        while next != "}":
            generator = GeneratorObject.from_generator_file(reader)

            genfile.generators.append(generator)
            next = reader.peek_token()

            if next == "":
                raise RuntimeError("Malformed file, expected generator object or '}'")

        return genfile

if __name__ == "__main__":
    with open("p29.txt", "r", encoding="shift-jis", errors="replace") as f:
        genfile = GeneratorFile.from_file(f)
