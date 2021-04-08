from collections import OrderedDict

from .libgen import GeneratorReader
from .vectors import Vector3
WP_BLANK = """
0 # index
0 0 0 # pos
50 # radius
"" # id
# ## links
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
# ## incomings
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
-1 0.00000000 0 0 # link [-1]
1 # type
"""

def read_link(reader: GeneratorReader):
    token = reader.read_token()

    vals = token.split(" ")
    try:
        return int(vals[0]), float(vals[1]), int(vals[2]), int(vals[3])
    except:
        print("Tried reading path link at line", reader.current_line-1, "but data was malformed")
        raise


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
            raise RuntimeError("Too many incoming links, cannot add more")
        if waypoint in self.incoming_links:
            raise RuntimeError("Link already exists")

        self.incoming_links[waypoint] = [unkfloat, unkint, unkint2]

    def add_outgoing(self, waypoint, unkfloat, unkint, unkint2):
        if len(self.outgoing_links) >= 8:
            raise RuntimeError("Too many outgoing links, cannot add more")
        if waypoint in self.outgoing_links:
            raise RuntimeError("Link already exists")
        self.outgoing_links[waypoint] = [unkfloat, unkint, unkint2]

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
        self.waypoints = []

        self.unique_paths = []
        
        #self.wide_paths = []

        #self.path_info = {}

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
        if version != 5:
            raise RuntimeError("Unsupported Path Version: {0}".format(version))

        pointcount = reader.read_integer()
        waypoints = [Waypoint(i, "", Vector3(0.0, 0.0, 0.0), 100, paths.waypoints) for i in range(pointcount)]

        for i in range(pointcount):
            assert i == reader.read_integer()  # index

            waypoint = waypoints[i]
            waypoint.position = Vector3(*reader.read_vector3f())
            waypoint.radius = reader.read_float()
            waypoint.id = reader.read_string()
            #Waypoint(i, id, Vector3(*position), radius)

            for i in range(8):
                link = read_link(reader)
                wp, data = link[0], link[1:]

                if wp != -1:
                    waypoint.add_outgoing(waypoints[wp], *data)

            for i in range(8):
                link = read_link(reader)
                wp, data = link[0], link[1:]

                if wp != -1:
                    waypoint.add_incoming(waypoints[wp], *data)
            waypoint.waypoint_type = reader.read_integer()
            paths.waypoints.append(waypoint)

        paths.regenerate_unique_paths()
        #paths._regenerate_pathwidths()

        return paths
