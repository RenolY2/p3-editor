from collections import OrderedDict
from copy import deepcopy
from .vectors import Vector3


class GeneratorWriter(object):
    def __init__(self, file):
        self.f = file
        self.current_line = 1

        self.indent = 0

    def write_token(self, token, comment = None):
        self.f.write(self.indent*"\t")
        self.f.write(token)

        if comment is not None:
            if not comment.startswith("//") and not comment.startswith("#"):
                raise RuntimeError("Comment started with invalid character: {0}".format(comment))
            self.f.write(" ")
            self.f.write(comment)

        self.f.write("\n")

    def write_comment(self, comment):
        if not comment.startswith("//") and not comment.startswith("#"):
            raise RuntimeError("Comment started with invalid character: {0}".format(comment))
        self.f.write(self.indent*"\t")
        self.f.write(" ")
        self.f.write(comment)

        self.f.write("\n")

    def open_bracket(self):
        self.write_token("{")
        self.indent += 1

    def close_bracket(self):
        self.indent -= 1
        self.write_token("}")

    def write_vector3f(self, x, y, z):
        res = "{0:.8f} {1:.8f} {2:.8f}".format(x, y, z)
        if "e" in res or "inf" in res:
            raise RuntimeError("invalid float: {0}".format(res))
        self.write_token(res)

    def write_string(self, string):
        self.write_token("\""+string+"\"")

    def write_float(self, val):
        res = "{0:.8f}".format(val)
        if "e" in res or "inf" in res:
            raise RuntimeError("invalid float: {0}".format(res))
        self.write_token(res)

    def write_integer(self, val):
        assert isinstance(val, int)
        self.write_token(str(val))

    def write_string_tripple(self, string1, string2, string3):
        res = "{0} {1} {2}".format(string1, string2, string3)
        self.write_token(res)

    def write_float_int(self, f, i):
        res = "{0} {1}".format(f, i)
        self.write_token(res)


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
        print(val)
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

    def read_float_int(self):
        val = self.read_token()
        f, i = val.split(" ")
        return float(f), int(i)


class GeneratorParameters(object):
    pass


class GeneratorObject(object):
    def __init__(self, name, version, generatorid=["", "", ""]):
        self.name = name
        self.version = version
        self.generatorid = generatorid

        self.spline = []
        self.spline_float = None
        self.spline_params = []

        self.position = Vector3(0, 0, 0)
        self.rotation = Vector3(0, 0, 0)
        self.scale = 1.0

        self.unknown_params = OrderedDict()

    def from_other(self, obj):
        self.name = obj.name
        self.version = obj.version
        self.generatorid = obj.generatorid

        self.spline = obj.spline
        self.spline_params = obj.spline_params

        self.position = obj.position
        self.rotation = obj.rotation
        self.scale = obj.scale

        self.unknown_params = obj.unknown_params

    def copy(self):
        return deepcopy(self)

    @classmethod
    def from_generator_file(cls, reader: GeneratorReader):
        name = reader.read_string()
        version = reader.read_string()
        generatorid = reader.read_string_tripple()
        gen = cls(name, version, generatorid)
        gen.read_parameters(reader)
        gen._read_spline(reader)

        return gen

    def write(self, writer: GeneratorWriter):
        writer.write_string(self.name)
        writer.write_string(self.version)
        writer.write_string_tripple(*self.generatorid)
        self.write_parameters(writer)
        if len(self.spline) == 0:
            writer.write_string("no-spline")
        else:
            writer.write_string("spline")
            writer.write_integer(len(self.spline))
            for x, y, z in self.spline:
                writer.write_vector3f(x, y, z)


            writer.write_float_int(self.spline_float, len(self.spline_params))
            for param in self.spline_params:
                idname, mtype = param

                writer.write_token(idname)
                writer.open_bracket()
                writer.open_bracket()
                writer.write_string("mType")
                writer.write_integer(mtype)
                writer.close_bracket()
                writer.close_bracket()


    def write_parameters(self, writer:GeneratorWriter):
        writer.open_bracket()

        writer.open_bracket()
        writer.write_string("mPos")
        writer.write_vector3f(self.position.x, self.position.y, self.position.z)
        writer.close_bracket()


        writer.open_bracket()
        writer.write_string("mBaseScale")
        writer.write_float(self.scale)
        writer.close_bracket()


        writer.open_bracket()
        writer.write_string("mPosture")
        writer.write_vector3f(self.rotation.x, self.rotation.y, self.rotation.z)
        writer.close_bracket()

        for param, values in self.unknown_params.items():
            writer.open_bracket()
            writer.write_string(param)

            if param == "mEmitRadius":
                writer.write_float(values)
            else:
                for val in values:
                    writer.write_token(val)
            writer.close_bracket()

        writer.close_bracket()

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
            elif param_name == "mEmitRadius":
                self.unknown_params[param_name] = reader.read_float()
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

            self.spline_float, paramcount = reader.read_float_int()
            self.spline_params = []

            for i in range(paramcount):
                param = []
                idname = reader.read_token()
                assert reader.read_token() == "{"
                assert reader.read_token() == "{"
                assert reader.read_string()== "mType"
                mtype = reader.read_integer()
                assert reader.read_token() == "}"
                assert reader.read_token() == "}"
                self.spline_params.append((idname, mtype))


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

    def write(self, writer: GeneratorWriter):
        writer.open_bracket()
        for genobj in self.generators:
            genobj.write(writer)
        writer.close_bracket()


if __name__ == "__main__":
    with open("p29.txt", "r", encoding="shift-jis", errors="replace") as f:
        genfile = GeneratorFile.from_file(f)
