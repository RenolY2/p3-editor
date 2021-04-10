from collections import OrderedDict
from copy import deepcopy
from .libgen import GeneratorReader, GeneratorWriter
from .vectors import Vector3

WP_BLANK = """
0.0 0.0 0.0 # Waypoint position (ignore this)
50.0 # Waypoint radius
"" # Waypoint ID
0 # Waypoint type
"""


class TooManyLinks(Exception):
    pass


class LinkAlreadyExists(Exception):
    pass


class ImproperLinking(Exception):
    pass


def read_link(reader: GeneratorReader, version):
    token = reader.read_token()

    vals = token.split(" ")
    try:
        if version == 4:
            return int(vals[0]), float(vals[1]), int(vals[2]), 0
        else:
            return int(vals[0]), float(vals[1]), int(vals[2]), int(vals[3])
    except Exception:
        print("Tried reading path link at line", reader.current_line-1, "but data was malformed")
        raise


def write_link(writer: GeneratorWriter, index, distance, val1, val2, version):
    if version == 4:
        res = "{0} {1:.8f} {2}".format(index, distance, val1)
    else:
        res = "{0} {1:.8f} {2} {3}".format(index, distance, val1, val2)

    if "e" in res or "inf" in res:
        raise RuntimeError("invalid float: {0}".format(res))

    writer.write_token(res)


class Waypoint(object):
    def __init__(self, index, id, position, radius, wp_list=None):
        self.index = index
        self.position = position
        self.radius = radius
        self.id = id
        self.waypoint_type = 0

        self.incoming_links = OrderedDict()
        self.outgoing_links = OrderedDict()

        self._wp_list: list = wp_list

    def get_index(self):
        if self._wp_list is None:
            return None
        else:
            if self in self._wp_list:
                return self._wp_list.index(self)
            else:
                return None

    def name(self):
        wpname = "Waypoint"
        if self.id != "":
            wpname += " "+self.id
        index = self.get_index()
        if index is not None:
            wpname += " ({0})".format(index)

        return wpname

    def short_name(self):
        wpname = "WP"
        index = self.get_index()
        if index is not None:
            wpname += " {0}".format(index)

        return wpname

    def remove_link(self, waypoint):
        if waypoint in self.incoming_links:
            del self.incoming_links[waypoint]
        if waypoint in self.outgoing_links:
            del self.outgoing_links[waypoint]

    def add_incoming(self, waypoint, unkfloat, unkint, unkint2):
        if len(self.incoming_links) >= 8:
            raise TooManyLinks("Too many incoming links, cannot add more")
        if waypoint in self.incoming_links:
            raise LinkAlreadyExists("Link already exists")

        self.incoming_links[waypoint] = [unkfloat, unkint, unkint2]

    def add_outgoing(self, waypoint, unkfloat, unkint, unkint2):
        if len(self.outgoing_links) >= 8:
            raise TooManyLinks("Too many outgoing links, cannot add more")
        if waypoint in self.outgoing_links:
            raise LinkAlreadyExists("Link already exists")
        self.outgoing_links[waypoint] = [unkfloat, unkint, unkint2]

    def add_path_to(self, waypoint, unkfloat, unkint, unkint2):
        if waypoint in self.outgoing_links and self in waypoint.incoming_links:
            return

        if waypoint in self.outgoing_links and not self in waypoint.incoming_links:
            raise RuntimeError("This is a very odd situation between {0} and {1}".format(
                self.name(), waypoint.name()
            ))

        if waypoint not in self.outgoing_links and self in waypoint.incoming_links:
            raise RuntimeError("This is a very odd situation between {0} and {1}".format(
                self.name(), waypoint.name()
            ))

        if len(self.outgoing_links) >= 8 or len(waypoint.incoming_links) >= 8:
            raise TooManyLinks("Destination or Start Waypoint has 8 links already. (MAX)")

        unkfloat = round((waypoint.position - self.position).norm(), 8)

        self.outgoing_links[waypoint] = [unkfloat, unkint, unkint2]
        waypoint.incoming_links[self] = [unkfloat, unkint, unkint2]

    def remove_path_to(self, waypoint):
        if waypoint not in self.outgoing_links and self not in waypoint.incoming_links:
            return

        if waypoint in self.outgoing_links and not self in waypoint.incoming_links:
            raise RuntimeError("This is a very odd situation between {0} and {1}".format(
                self.name(), waypoint.name()
            ))

        if waypoint not in self.outgoing_links and self in waypoint.incoming_links:
            raise RuntimeError("This is a very odd situation between {0} and {1}".format(
                self.name(), waypoint.name()
            ))
        del self.outgoing_links[waypoint]
        del waypoint.incoming_links[self]

    @classmethod
    def from_compact_path_data(cls, reader):

        position = Vector3(*reader.read_vector3f())
        radius = reader.read_float()
        id = reader.read_string()
        waypoint_type = reader.read_integer()

        waypoint = cls(None, id, position, radius)
        return waypoint

    """def get_incoming_info(self, index):
        for val in self.incoming_links:
            if val[0] == index:
                return val
        return None

    def get_outgoing_info(self, index):
        for val in self.outgoing_links:
            if val[0] == index:
                return val
        return None"""


class Paths(object):
    def __init__(self):
        self.version = 5
        self.waypoints = []

        self.unique_paths = []
        
        #self.wide_paths = []

        #self.path_info = {}

    def remove_waypoint(self, wp):
        self.waypoints.remove(wp)
        for other_wp in self.waypoints:
            other_wp.remove_link(wp)

    def readd_waypoint(self, wp):
        #wp = deepcopy(wp)
        self.waypoints.append(wp)

        for other_wp, data in wp.incoming_links.items():
            try:
                other_wp.add_outgoing(wp, *data)
            except LinkAlreadyExists:
                pass
            except TooManyLinks:
                del wp.incoming_links[other_wp]

        for other_wp, data in wp.outgoing_links.items():
            try:
                other_wp.add_incoming(wp, *data)
            except LinkAlreadyExists:
                pass
            except TooManyLinks:
                del wp.outgoing_links[other_wp]

    def regenerate_unique_paths(self):
        checked = {}
        paths = []
        for waypoint in self.waypoints:
            for link in waypoint.outgoing_links:
                # print(link)
                s = waypoint  # waypoint.index
                t = link  # link.index

                if (s,t) not in checked and (t,s) not in checked:
                    paths.append((s, t))
                    checked[s, t] = True

            """for link in waypoint.incoming_links:
                t = waypoint.index
                s = link[0]

                if (s,t) not in checked or (t,s) not in checked:
                    paths.append((s, t))
                    checked[s, t] = True"""

        self.unique_paths = paths

    def _regenerate_pathwidths(self):
        return

        self.wide_paths = []
        up = Vector3(0, 1, 0)

        for s, t in self.unique_paths:
            p1 = self.waypoints[s]
            p2 = self.waypoints[t]

            dir = p2.position - p1.position

            left = dir.cross(up)
            left.normalize()

            info = p1.get_outgoing_info(p2.index)
            print("hi", info)
            if info is not None:
                info2 = p2.get_incoming_info(p1.index)

                assert info2 is not None

                width1 = info[1]/2
                width2 = info2[1]/2

                c1 = p1.position - left*width1
                c2 = p1.position + left*width1
                c3 = p2.position + left*width2
                c4 = p2.position - left*width2

                self.wide_paths.append((c1, c2, c3, c4))


    @classmethod
    def from_file(cls, f):
        paths = cls()
        reader = GeneratorReader(f)
        version = reader.read_integer()
        if version != 5 and version != 4:
            raise RuntimeError("Unsupported Path Version: {0}".format(version))
        paths.version = version

        pointcount = reader.read_integer()
        waypoints = [Waypoint(i, "", Vector3(0.0, 0.0, 0.0), 100, paths.waypoints) for i in range(pointcount)]

        for i in range(pointcount):
            assert i == reader.read_integer()  # index

            waypoint = waypoints[i]
            waypoint.position = Vector3(*reader.read_vector3f())
            waypoint.radius = reader.read_float()
            waypoint.id = reader.read_string()
            #Waypoint(i, id, Vector3(*position), radius)

            for j in range(8):
                link = read_link(reader, version)
                wp, data = link[0], link[1:]

                if wp != -1:
                    waypoint.add_outgoing(waypoints[wp], *data)

            for j in range(8):
                link = read_link(reader, version)
                wp, data = link[0], link[1:]

                if wp != -1:
                    waypoint.add_incoming(waypoints[wp], *data)
            waypoint.waypoint_type = reader.read_integer()
            paths.waypoints.append(waypoint)

        for waypoint in paths.waypoints:
            for wp in waypoint.outgoing_links:
                #print(waypoint.name(), wp.name())
                #print(waypoint.outgoing_links[wp][1], wp.incoming_links[waypoint][1])
                if waypoint not in wp.incoming_links:
                    raise ImproperLinking("{0} not found in Incoming Links of {1}".format(waypoint.name(), wp.name()))

                assert waypoint.outgoing_links[wp][1] == wp.incoming_links[waypoint][1]
                # assert waypoint.outgoing_links[wp][2] == wp.incoming_links[waypoint][2]


        paths.regenerate_unique_paths()
        #paths._regenerate_pathwidths()

        return paths

    def write(self, f):
        writer = GeneratorWriter(f)

        writer.write_integer(5)
        writer.write_integer(len(self.waypoints))

        for i, waypoint in enumerate(self.waypoints):
            writer.write_comment("# ------------------")
            writer.write_integer(i)
            writer.write_vector3f(waypoint.position.x, waypoint.position.y, waypoint.position.z)
            writer.write_float(waypoint.radius)
            writer.write_string(waypoint.id)

            writer.write_comment("# Outgoing Links")
            for outgoing, data in waypoint.outgoing_links.items():
                write_link(writer, self.waypoints.index(outgoing), *data, self.version)

            for i in range(8 - len(waypoint.outgoing_links)):
                write_link(writer, -1, 0.0, 0, 0, self.version)

            writer.write_comment("# Incoming Links")
            for incoming, data in waypoint.incoming_links.items():
                write_link(writer, self.waypoints.index(incoming), *data, self.version)

            for i in range(8 - len(waypoint.incoming_links)):
                write_link(writer, -1, 0.0, 0, 0, self.version)

            writer.write_integer(waypoint.waypoint_type)