from OpenGL.GL import *
from .vectors import Vector3
from struct import unpack
from OpenGL.GL import *


def read_vertex(v_data):
    split = v_data.split("/")
    if len(split) == 3:
        vnormal = int(split[2])
    else:
        vnormal = None
    v = int(split[0])
    return v, vnormal


class Mesh(object):
    def __init__(self, name):
        self.name = name
        self.primtype = "Triangles"
        self.vertices = []
        self.texcoords = []
        self.triangles = []

        self._displist = None

        self.texture = None

    def generate_displist(self):
        if self._displist is not None:
            glDeleteLists(self._displist, 1)

        displist = glGenLists(1)
        glNewList(displist, GL_COMPILE)
        glBegin(GL_TRIANGLES)
        for v1, v2, v3 in self.triangles:
            v1i, v1coord = v1
            v2i, v2coord = v2
            v3i, v3coord = v3
            glVertex3f(*self.vertices[v1i])
            glVertex3f(*self.vertices[v2i])
            glVertex3f(*self.vertices[v3i])
        glEnd()
        glEndList()
        self._displist = displist

    def render(self):
        if self._displist is None:
            self.generate_displist()
        glCallList(self._displist)

    def render_colorid(self, id):
        glColor3ub((id >> 16) & 0xFF, (id >> 8) & 0xFF, (id >> 0) & 0xFF)
        self.render()


class Model(object):
    def __init__(self):
        self.mesh_list = []
        self.named_meshes = {}

    def render(self):
        for mesh in self.mesh_list:
            mesh.render()

    def render_coloredid(self, id):
        glColor3ub((id >> 16) & 0xFF, (id >> 8) & 0xFF, (id >> 0) & 0xFF)
        self.render()

    def add_mesh(self, mesh: Mesh):
        if mesh.name not in self.named_meshes:
            self.named_meshes[mesh.name] = mesh
            self.mesh_list.append(mesh)
        elif mesh.name != "":
            raise RuntimeError("Duplicate mesh name: {0}".format(mesh.name))
        else:
            self.mesh_list.append(mesh)

    @classmethod
    def from_obj(cls, f, scale=1.0, rotate=False):
        model = cls()
        vertices = []
        texcoords = []

        curr_mesh = None

        for line in f:
            line = line.strip()
            args = line.split(" ")

            if len(args) == 0 or line.startswith("#"):
                continue
            cmd = args[0]

            if cmd == "o":
                objectname = args[1]
                if curr_mesh is not None:
                    model.add_mesh(curr_mesh)
                curr_mesh = Mesh(objectname)
                curr_mesh.vertices = vertices

            elif cmd == "v":
                if "" in args:
                    args.remove("")
                x, y, z = map(float, args[1:4])
                if not rotate:
                    vertices.append((x*scale, y*scale, z*scale))
                else:
                    vertices.append((x * scale, z * scale, -y * scale, ))
            elif cmd == "f":
                if curr_mesh is None:
                    curr_mesh = Mesh("")
                    curr_mesh.vertices = vertices

                # if it uses more than 3 vertices to describe a face then we panic!
                # no triangulation yet.
                if len(args) == 5:
                    #raise RuntimeError("Model needs to be triangulated! Only faces with 3 vertices are supported.")
                    print(args)
                    v1, v2, v3, v4 = map(read_vertex, args[1:5])
                    curr_mesh.triangles.append(((v1[0] - 1, None), (v2[0] - 1, None), (v3[0] - 1, None)))
                    curr_mesh.triangles.append(((v3[0] - 1, None), (v4[0] - 1, None), (v1[0] - 1, None)))

                elif len(args) == 4:
                    v1, v2, v3 = map(read_vertex, args[1:4])
                    curr_mesh.triangles.append(((v1[0]-1, None), (v2[0]-1, None), (v3[0]-1, None)))
        model.add_mesh(curr_mesh)
        return model
        #elif cmd == "vn":
        #    nx, ny, nz = map(float, args[1:4])
        #    normals.append((nx, ny, nz))




ALPHA = 0.8


class Waterbox(Model):
    def __init__(self, corner_bottomleft, corner_topright):
        self.corner_bottomleft = corner_bottomleft
        self.corner_topright = corner_topright

    def render(self):
        x1,y1,z1 = self.corner_bottomleft
        x2,y2,z2 = self.corner_topright
        glColor4f(0.1, 0.1875, 0.8125, ALPHA)
        glBegin(GL_TRIANGLE_FAN) # Bottom, z1
        glVertex3f(x2, y1, z1)
        glVertex3f(x2, y2, z1)
        glVertex3f(x1, y2, z1)
        glVertex3f(x1, y1, z1)
        glEnd()
        glBegin(GL_TRIANGLE_FAN) # Front, x1
        glVertex3f(x1, y1, z1)
        glVertex3f(x1, y1, z2)
        glVertex3f(x1, y2, z2)
        glVertex3f(x1, y2, z1)
        glEnd()

        glBegin(GL_TRIANGLE_FAN) # Side, y1
        glVertex3f(x1, y1, z1)
        glVertex3f(x1, y1, z2)
        glVertex3f(x2, y1, z2)
        glVertex3f(x2, y1, z1)
        glEnd()
        glBegin(GL_TRIANGLE_FAN) # Back, x2
        glVertex3f(x2, y1, z1)
        glVertex3f(x2, y1, z2)
        glVertex3f(x2, y2, z2)
        glVertex3f(x2, y2, z1)
        glEnd()
        glBegin(GL_TRIANGLE_FAN) # Side, y2
        glVertex3f(x1, y2, z1)
        glVertex3f(x1, y2, z2)
        glVertex3f(x2, y2, z2)
        glVertex3f(x2, y2, z1)
        glEnd()
        glBegin(GL_TRIANGLE_FAN) # Top, z2
        glVertex3f(x1, y1, z2)
        glVertex3f(x1, y2, z2)
        glVertex3f(x2, y2, z2)
        glVertex3f(x2, y1, z2)
        glEnd()


class GenericObject(Model):
    def __init__(self):
        with open("resources/generic_object.obj", "r") as f:
            model = Model.from_obj(f, scale=10, rotate=True)
        self.mesh_list = model.mesh_list
        self.named_meshes = model.mesh_list

    def render(self, selected=False):
        glEnable(GL_CULL_FACE)
        if selected:
            glColor4f(1.0, 0.0, 0.0, 1.0)
        else:
            glColor4f(0.0, 0.0, 0.0, 1.0)
        glCullFace(GL_FRONT)
        glPushMatrix()

        if selected:
            glScalef(1.5, 1.5, 1.5)
        else:
            glScalef(1.2, 1.2, 1.2)

        self.mesh_list[1].render()
        glPopMatrix()
        glCullFace(GL_BACK)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        self.mesh_list[1].render()
        glColor4ub(0x09, 0x93, 0x00, 0xFF)
        self.mesh_list[0].render()
        glDisable(GL_CULL_FACE)

    def render_coloredid(self, id):
        glColor3ub((id >> 16) & 0xFF, (id >> 8) & 0xFF, (id >> 0) & 0xFF)
        glPushMatrix()
        glScalef(1.2, 1.2, 1.2)
        self.mesh_list[1].render()
        glPopMatrix()

class TexturedPlane(object):
    def __init__(self, planewidth, planeheight, qimage):
        ID = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, ID)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_BASE_LEVEL, 0)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0)

        imgdata = bytes(qimage.bits().asarray(qimage.width()*qimage.height()*4))
        glTexImage2D(GL_TEXTURE_2D, 0, 4, qimage.width(), qimage.height(), 0, GL_BGRA, GL_UNSIGNED_BYTE, imgdata)

        self.ID = ID
        self.planewidth = planewidth
        self.planeheight = planeheight

        self.offset_x = 0
        self.offset_z = 0
        self.color = (0.0, 0.0, 0.0)

    def set_offset(self, x, z):
        self.offset_x = x
        self.offset_z = z

    def set_color(self, color):
        self.color = color

    def apply_color(self):
        glColor4f(self.color[0], self.color[1], self.color[2], 1.0)

    def render(self):
        w, h = self.planewidth, self.planeheight
        offsetx, offsetz = self.offset_x, self.offset_z
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.ID)
        glBegin(GL_TRIANGLE_FAN)
        glTexCoord2f(0.0, 0.0)
        glVertex3f(-0.5*w+offsetx, -0.5*h+offsetz, 0)
        glTexCoord2f(0.0, 1.0)
        glVertex3f(-0.5*w+offsetx, 0.5*h+offsetz, 0)
        glTexCoord2f(1.0, 1.0)
        glVertex3f(0.5*w+offsetx, 0.5*h+offsetz, 0)
        glTexCoord2f(1.0, 0.0)
        glVertex3f(0.5*w+offsetx, -0.5*h+offsetz, 0)
        glEnd()

    def render_coloredid(self, id):
        w, h = self.planewidth, self.planeheight
        offsetx, offsetz = self.offset_x, self.offset_z
        glDisable(GL_TEXTURE_2D)
        glColor3ub((id >> 16) & 0xFF, (id >> 8) & 0xFF, (id >> 0) & 0xFF)
        glBegin(GL_TRIANGLE_FAN)
        #glTexCoord2f(0.0, 0.0)
        glVertex3f(-0.5*w+offsetx, -0.5*h+offsetz, 0)
        #glTexCoord2f(0.0, 1.0)
        glVertex3f(-0.5*w+offsetx, 0.5*h+offsetz, 0)
        #glTexCoord2f(1.0, 1.0)
        glVertex3f(0.5*w+offsetx, 0.5*h+offsetz, 0)
        #glTexCoord2f(1.0, 0.0)
        glVertex3f(0.5*w+offsetx, -0.5*h+offsetz, 0)
        glEnd()


class Grid(Mesh):
    def __init__(self, width, length):
        super().__init__("Grid")
        self.width = width
        self.length = length

    def generate_displist(self):
        if self._displist is not None:
            glDeleteLists(self._displist, 1)

        offset = +0.5
        width = self.width
        length = self.length

        self._displist = glGenLists(1)
        glNewList(self._displist, GL_COMPILE)
        glColor3f(0.0, 0.0, 0.0)
        glLineWidth(4.0)
        glBegin(GL_LINES)
        glVertex3f(-width, 0, offset)
        glVertex3f(width, 0, offset)

        glVertex3f(0, -length, offset)
        glVertex3f(0, length, offset)
        glEnd()
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for ix in range(-width, width+500, 500):
            glVertex3f(ix, -length, offset)
            glVertex3f(ix, length, offset)

        for iy in range(-length, length+500, 500):
            glVertex3f(-width, iy, offset)
            glVertex3f(width, iy, offset)

        glEnd()
        glEndList()
